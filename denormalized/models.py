from typing import Iterable

from django.db import models
from django.db.models.fields import related_descriptors
from django.db.models.signals import pre_save, post_save, post_delete

from denormalized.tracker import PREVIOUS_VERSION_FIELD, DenormalizedTracker


class DenormalizedForeignKey(models.ForeignKey):
    related_accessor_class = related_descriptors.ReverseManyToOneDescriptor

    def __init__(self, to, on_delete, related_name=None,
                 related_query_name=None, limit_choices_to=None,
                 parent_link=False, to_field=None, db_constraint=True,
                 trackers: Iterable[DenormalizedTracker]=(), **kwargs):
        self.trackers = trackers
        super().__init__(to, on_delete, related_name=related_name,
                         related_query_name=related_query_name,
                         limit_choices_to=limit_choices_to,
                         parent_link=parent_link, to_field=to_field,
                         db_constraint=db_constraint, **kwargs)

    def contribute_to_class(self, cls, name, private_only=False, **kwargs):
        super().contribute_to_class(cls, name, private_only, **kwargs)
        pre_save.connect(self._track_previous_version, sender=cls,
                         dispatch_uid='denormalized_track_previous')
        post_save.connect(self._track_changes, sender=cls,
                          dispatch_uid='denormalized_update_value_on_save')
        post_delete.connect(self._track_changes, sender=cls,
                            dispatch_uid='denormalized_update_value_on_delete')

    # noinspection PyUnusedLocal
    @staticmethod
    def _track_previous_version(sender=None, instance=None, **kwargs):
        setattr(instance, PREVIOUS_VERSION_FIELD,
                instance.__dict__.copy())

    # noinspection PyUnusedLocal
    def _track_changes(self, sender=None, instance=None, signal=None,
                       created=None, **kwargs):
        deleted = signal is post_delete
        for tracker in self.trackers:
            tracker.track_changes(instance, created, deleted)



