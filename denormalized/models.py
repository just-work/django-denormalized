""" Django ORM fields and descriptors."""
import functools
from collections import defaultdict
from typing import Iterable, Dict

from django.db import models
from django.db.models.fields import related_descriptors
from django.db.models.signals import post_save, post_delete, post_init, class_prepared
from django.utils.functional import cached_property

from denormalized.tracker import PREVIOUS_VERSION_FIELD, DenormalizedTracker
from denormalized.types import IncrementalUpdates


class DenormalizedReverseManyToOneDescriptor(
        related_descriptors.ReverseManyToOneDescriptor):

    @cached_property
    def related_manager_cls(self):
        base = super().related_manager_cls
        manager = type(f"Denormalized{base.__name__}", (base,),
                       {"denormalize": self._build_denormalize_method()})
        return manager

    def _build_denormalize_method(self):
        def denormalize(related_manager):
            foreign_object = related_manager.instance
            changed = set()
            for tracker in self.field.trackers:
                value = related_manager.filter(tracker.query).aggregate(
                    a=tracker.aggregate)['a']
                setattr(foreign_object, tracker.field, value)
                changed.add(tracker.field)
            foreign_object.save(update_fields=changed)
        return denormalize


class DenormalizedForeignKey(models.ForeignKey):
    related_accessor_class = DenormalizedReverseManyToOneDescriptor

    def __init__(self, to, on_delete, related_name=None,
                 related_query_name=None, limit_choices_to=None,
                 parent_link=False, to_field=None, db_constraint=True,
                 trackers: Iterable[DenormalizedTracker] = (), **kwargs):
        self.trackers = trackers
        self.__in_init = False
        super().__init__(to, on_delete, related_name=related_name,
                         related_query_name=related_query_name,
                         limit_choices_to=limit_choices_to,
                         parent_link=parent_link, to_field=to_field,
                         db_constraint=db_constraint, **kwargs)

    @staticmethod
    def store_initial_state(instance):
        """ Save initial version of tracked instance in it's __dict__."""
        model = type(instance)
        prev = model()
        old = instance.__dict__.copy()
        del old['_state']
        prev.__dict__.update(old)
        setattr(instance, PREVIOUS_VERSION_FIELD, prev)

    @staticmethod
    def update_object(obj, **updates):
        """ Update denormalized fields incrementally with F-objects.

        After update receives actual object version from db.
        """
        obj.__dict__.update(updates)
        obj.save(update_fields=set(updates))
        obj.refresh_from_db()

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        super().contribute_to_class(cls, name, private_only, **kwargs)
        suffix = f':{cls.__name__}:{name}'
        post_init.connect(
            self._track_previous_version, sender=cls,
            dispatch_uid=f'denormalized_track_previous:{suffix}')
        post_save.connect(
            self._track_changes, sender=cls,
            dispatch_uid=f'denormalized_update_value_on_save:{suffix}')
        post_delete.connect(
            self._track_changes, sender=cls,
            dispatch_uid=f'denormalized_update_value_on_delete:{suffix}')
        class_prepared.connect(
            self._wrap_save, sender=cls,
            dispatch_uid=f'denormalized_wrap_save:{suffix}')
        for tracker in self.trackers:
            tracker.foreign_key = self.name

    # noinspection PyUnusedLocal
    def _wrap_save(self, sender, **kwargs):
        """ Wraps model save with state post-invalidation."""

        if hasattr(sender.save, 'denormalized_wrapper'):
            return
        save = sender.save

        @functools.wraps(save)
        def wrapped(instance, *args, **kw):
            """ Reset cached initial state after save call completed."""
            save(instance, *args, **kw)
            self.store_initial_state(instance)

        wrapped.denormalized_wrapper = True

        sender.save = wrapped

    # noinspection PyUnusedLocal
    def _track_previous_version(self, sender=None, instance=None, **kwargs):
        if self.__in_init:
            return
        self.__in_init = True
        try:
            self.store_initial_state(instance)
        finally:
            self.__in_init = False

    # noinspection PyUnusedLocal
    def _track_changes(self, sender=None, instance=None, signal=None,
                       created=None, **kwargs):
        deleted = signal is post_delete

        changed: Dict[models.Model, IncrementalUpdates] = defaultdict(dict)

        for tracker in self.trackers:
            # collecting changes from all trackers to denormalized objects
            changes = tracker.track_changes(instance, created, deleted)
            for foreign_object, updates in filter(None, changes):
                changed[foreign_object].update(updates)

        for foreign_object, updates in changed.items():
            # applying changes to denormalized objects
            self.update_object(foreign_object, **updates)
