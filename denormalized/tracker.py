""" Tracking changes for denormalized fields."""

from typing import Optional, Iterable, Tuple, Union

from django.db import models
from django.db.models import Count, Q, Sum, Min, F
from django.db.models.expressions import CombinedExpression

from denormalized.types import IncrementalUpdates


PREVIOUS_VERSION_FIELD = '_denormalized_previous_version'


# what's going on with group member
ENTERING, CHANGING, LEAVING = 1, 0, -1


class DenormalizedTracker:
    def __init__(self, field, aggregate=Count('*'), query=Q(),
                 callback=lambda obj: True, related_name=None):
        self.field = field
        self.aggregate = aggregate
        self.query = query
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
                      delta: Optional[CombinedExpression],
                      ) -> Optional[Tuple[models.Model, IncrementalUpdates]]:
        if not foreign_object or delta is None:
            return None
        return foreign_object, {self.field: delta}

    def _get_delta(self,
                   instance: models.Model,
                   mode: int,
                   previous: Optional[models.Model] = None,
                   ) -> Optional[CombinedExpression]:
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
        if isinstance(self.aggregate, Count):
            if mode == CHANGING:
                # updates not needed
                return None
            return F(self.field) + mode
        elif isinstance(self.aggregate, Sum):
            new_value = self.get_value_from_instance(instance)
            if mode == CHANGING:
                old_value = self.get_value_from_instance(previous)
                if new_value - old_value == 0:
                    # updates not needed
                    return None
                return F(self.field) + new_value - old_value
            # mode is ENTERING or LEAVING, only new_value matters.
            return F(self.field) + new_value * mode
        elif isinstance(self.aggregate, Min):
            pass

        raise NotImplementedError()  # pragma: no cover

    def get_value_from_instance(self, instance):
        arg = self.aggregate.source_expressions[0]
        value = getattr(instance, arg.name)
        if isinstance(value, CombinedExpression):
            instance.refresh_from_db(fields=(arg.name,))
            value = getattr(instance, arg.name)
        return value

    def _get_full_aggregate(self, instance):
        # Computes full aggregate excluding passed instance
        raise NotImplementedError()
