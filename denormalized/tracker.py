""" Tracking changes for denormalized fields."""
from typing import Optional, Iterable, Tuple

from django.db import models
from django.db.models import Count, Q, F
from django.db.models.expressions import CombinedExpression, Expression, \
    OuterRef, Subquery
from django.db.models.functions import Coalesce, Least, Greatest

from denormalized.types import IncrementalUpdates

PREVIOUS_VERSION_FIELD = '_denormalized_previous_version'


# what's going on with group member
ENTERING, CHANGING, LEAVING = 1, 0, -1


class DenormalizedTracker:
    """
    Tracks changes for some field and updates denormalized aggregate for that
    field in foreign object.
    """
    def __init__(self, field, aggregate=Count('*'), callback=lambda obj: True,
                 related_name=None):
        self.field = field
        self.aggregate = aggregate
        self.callback = callback
        self.foreign_key = related_name

    def __repr__(self):
        return f'{self.field} = {self.aggregate}'

    def get_foreign_object(self, instance: models.Model
                           ) -> Optional[models.Model]:
        """ Safely returns foreign object from instance."""
        try:
            return getattr(instance, self.foreign_key)
        except models.ObjectDoesNotExist:
            # this may raise DNE while cascade deleting with Collector
            return None

    def track_changes(self, instance=None, created=None, deleted=None
                      ) -> Iterable[Tuple[models.Model, IncrementalUpdates]]:
        foreign_object = self.get_foreign_object(instance)
        is_suitable = self.callback(instance)
        if created:
            if not is_suitable:
                return ()
            # new suitable object is added to denormalized object set
            delta = self._get_delta(instance, mode=ENTERING)
            return self._update_value(foreign_object, delta),
        elif deleted:
            if not is_suitable:
                return ()
            # a suitable object is deleted from denormalized object set
            delta = self._get_delta(instance, mode=LEAVING)
            return self._update_value(foreign_object, delta),

        old_instance = getattr(instance, PREVIOUS_VERSION_FIELD)
        old_suitable = self.callback(old_instance)
        old_foreign_object = self.get_foreign_object(old_instance)

        changed = []
        sign = is_suitable - old_suitable
        if foreign_object == old_foreign_object and sign != 0:
            # object is entering or leaving denormalized object set
            mode = ENTERING if is_suitable else LEAVING
            delta = self._get_delta(instance, mode=mode)
            changed.append(self._update_value(foreign_object, delta))
        elif foreign_object != old_foreign_object:
            if old_suitable:
                # object is removed from old_foreign_object denormalized object set
                old_delta = self._get_delta(old_instance, mode=LEAVING)
                changed.append(self._update_value(old_foreign_object, old_delta))
            if is_suitable:
                # at the same time object is added to foreign_object denormalized
                # object set
                delta = self._get_delta(instance, mode=ENTERING)
                changed.append(self._update_value(foreign_object, delta))
        else:
            # object preserves suitability and foreign object reference, only
            # tracked value itself may change
            # (foreign_object == old_foreign_object and sign == 0)
            delta = self._get_delta(instance, mode=CHANGING,
                                    previous=old_instance)
            changed.append(self._update_value(foreign_object, delta))

        return filter(None, changed)

    def _update_value(self,
                      foreign_object: models.Model,
                      delta: Optional[Expression],
                      ) -> Optional[Tuple[models.Model, IncrementalUpdates]]:
        if not foreign_object or delta is None:
            return None
        return foreign_object, {self.field: delta}

    def _get_delta(self,
                   instance: models.Model,
                   mode: int,
                   previous: Optional[models.Model] = None,
                   ) -> Optional[Expression]:
        """
        Get update expression for foreign object.

        :param instance: new version of tracked object
        :param mode: one of
            -1 - instance is removed from denormalized object set
            0  - tracked value for instance is changed
            +1 - new instance is added to denormalized object set
        :param previous: initial version of tracked object
        :return: expression to update foreign object with.
        """
        callback_name = f'_get_{self.aggregate.name.lower()}_delta'
        try:
            callback = getattr(self, callback_name)
            return callback(instance, mode, previous)
        except AttributeError:  # pragma: no cover
            raise NotImplementedError()

    # noinspection PyUnusedLocal
    def _get_count_delta(self, instance, mode, previous):
        """ Get incremental update for Count aggregate."""
        if mode == CHANGING:
            # updates not needed
            return None
        return F(self.field) + mode

    def _get_sum_delta(self, instance, mode, previous):
        """ Get incremental update for Sum aggregate."""
        new_value = self._get_value_from_instance(instance)
        if mode == CHANGING:
            old_value = self._get_value_from_instance(previous)
            if new_value - old_value == 0:
                # updates not needed
                return None
            return F(self.field) + new_value - old_value
        # mode is ENTERING or LEAVING, only new_value matters.
        return F(self.field) + new_value * mode

    def _get_min_delta(self, instance, mode, previous):
        """ Get incremental update for Min aggregate."""
        new_value = self._get_value_from_instance(instance)
        if mode == LEAVING:
            # new denormalized value is somewhere in DB, computing full
            # aggregate
            return self._get_full_aggregate(instance)
        if mode == ENTERING:
            return Coalesce(Least(F(self.field), new_value), new_value)
        if mode == CHANGING:
            old_value = self._get_value_from_instance(previous)
            if old_value > new_value:
                # value decreases, so denormalized value also may decrease
                return Coalesce(Least(F(self.field), new_value), new_value)
        # (mode == CHANGING and value increases)
        # in this situation we can't make anything except full recompute
        return self._get_full_aggregate(instance)

    def _get_max_delta(self, instance, mode, previous):
        """ Get incremental update for Max aggregate."""
        new_value = self._get_value_from_instance(instance)
        if mode == LEAVING:
            # new denormalized value is somewhere in DB, computing full
            # aggregate
            return self._get_full_aggregate(instance)
        if mode == ENTERING:
            return Coalesce(Greatest(F(self.field), new_value), new_value)
        if mode == CHANGING:
            old_value = self._get_value_from_instance(previous)
            if old_value < new_value:
                # value increases, so denormalized value also may increase
                return Coalesce(Least(F(self.field), new_value), new_value)
        # (mode == CHANGING and value decreases)
        # in this situation we can't make anything except full recompute
        return self._get_full_aggregate(instance)

    def _get_value_from_instance(self, instance):
        """ Get tracked value from instance."""
        arg = self.aggregate.source_expressions[0]
        value = getattr(instance, arg.name)
        if isinstance(value, CombinedExpression):
            instance.refresh_from_db(fields=(arg.name,))
            value = getattr(instance, arg.name)
        return value

    def _get_full_aggregate(self, instance: models.Model) -> Optional[Subquery]:
        """ Get aggregate subquery for full recompute of min/max aggregates."""
        foreign_object = self.get_foreign_object(instance)
        if foreign_object is None:
            return None
        object_queryset = type(instance).objects.filter(
            Q((self.foreign_key, OuterRef('pk')))).values(self.foreign_key)
        return Subquery(object_queryset.annotate(self.aggregate).values(
            self.aggregate.default_alias), output_field=models.IntegerField)
