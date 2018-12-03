from typing import Tuple, Optional, Iterable

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
        foreign_object = getattr(instance, self.foreign_key)
        is_suitable = self.callback(instance)
        if created and is_suitable:
            return self._update_value(foreign_object, instance, sign=1),
        elif deleted and is_suitable:
            return self._update_value(foreign_object, instance, sign=-1),
        changed = []
        # handling instance update
        if is_suitable:
            changed.append(self._update_value(foreign_object, instance, sign=1))
        # rolling back previous version
        old_instance = getattr(instance, PREVIOUS_VERSION_FIELD)
        is_suitable = self.callback(old_instance)
        if is_suitable:
            old_foreign_object = getattr(old_instance, self.foreign_key)
            changed.append(self._update_value(old_foreign_object, old_instance,
                                              sign=-1))
        return changed

    def _update_value(self, foreign_object, instance, sign=1
                      ) -> Optional[models.Model]:
        delta = self._get_delta(instance) * sign
        if delta == 0:
            return None
        setattr(foreign_object, self.field, F(self.field) + delta)
        return foreign_object

    def _get_delta(self, instance):
        if isinstance(self.aggregate, Count):
            return 1
        elif isinstance(self.aggregate, Sum):
            arg = self.aggregate.source_expressions[0]
            return getattr(instance, arg.name)
        raise NotImplementedError()
