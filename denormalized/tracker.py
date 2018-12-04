from typing import Optional, Iterable

from django.db import models
from django.db.models import Count, Q, Sum, F

PREVIOUS_VERSION_FIELD = '_denormalized_previous_version'


class DenormalizedTracker:
    def __init__(self, field, aggregate=Count('*'), query=Q(),
                 callback=lambda obj: True, related_name=None):
        self.field = field
        self.aggregate = aggregate
        self.query = query
        self.callback = callback
        self.foreign_key = related_name

    def track_changes(self, instance=None, created=None, deleted=None
                      ) -> Iterable[models.Model]:
        changed = []
        try:
            foreign_object = getattr(instance, self.foreign_key)
        except models.ObjectDoesNotExist:
            # this may raise DNE while cascade deleting with Collector
            foreign_object = None
        is_suitable = self.callback(instance)
        delta = self._get_delta(instance)
        if created and is_suitable:
            return self._update_value(foreign_object, delta, sign=1),
        elif deleted and is_suitable:
            return self._update_value(foreign_object, delta, sign=-1),
        old_instance = getattr(instance, PREVIOUS_VERSION_FIELD)
        old_delta = self._get_delta(old_instance)
        old_suitable = self.callback(old_instance)
        try:
            old_foreign_object = getattr(old_instance, self.foreign_key)
        except models.ObjectDoesNotExist:
            old_foreign_object = None

        sign = is_suitable - old_suitable
        if foreign_object == old_foreign_object and sign != 0:
            changed.append(self._update_value(foreign_object, delta, sign=sign))
        elif foreign_object != old_foreign_object:
            changed.append(self._update_value(
                old_foreign_object, old_delta, sign=-1))
            changed.append(self._update_value(foreign_object, delta, sign=1))
        else:
            # foreign_object == old_foreign_object and sign == 0
            changed.append(self._update_value(
                foreign_object, delta - old_delta, sign=1))

        return filter(None, changed)

    def _update_value(self, foreign_object, delta, sign=1
                      ) -> Optional[models.Model]:
        if delta == 0 or not foreign_object:
            return None
        setattr(foreign_object, self.field, F(self.field) + delta * sign)
        return foreign_object

    def _get_delta(self, instance):
        if isinstance(self.aggregate, Count):
            return 1
        elif isinstance(self.aggregate, Sum):
            arg = self.aggregate.source_expressions[0]
            return getattr(instance, arg.name)
        raise NotImplementedError()  # pragma: no cover
