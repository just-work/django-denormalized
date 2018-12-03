from django.db.models import Count, Q, Sum


PREVIOUS_VERSION_FIELD = '_denormalized_previous_version'


class DenormalizedTracker:
    def __init__(self, field, aggregate=Count, query=Q(),
                 callback=lambda obj: True, related_name=None):
        self.field = field
        self.aggregate = aggregate
        self.query = query
        self.callback = callback
        self.foreign_key = related_name

    def track_changes(self, instance=None, created=None, deleted=None) -> bool:
        foreign_object = getattr(instance, self.foreign_key)
        is_suitable = self.callback(instance)
        if created and is_suitable:
            return self._update_value(foreign_object, instance, sign=1)
        elif deleted and is_suitable:
            return self._update_value(foreign_object, instance, sign=-1)
        changed = False
        # handling instance update
        if is_suitable:
            changed += self._update_value(foreign_object, instance, sign=1)
        # rolling back previous version
        old_instance = getattr(instance, PREVIOUS_VERSION_FIELD)
        is_suitable = self.callback(old_instance)
        if is_suitable:
            changed += self._update_value(foreign_object, old_instance, sign=-1)
        return bool(changed)

    def _update_value(self, foreign_object, instance, sign=1) -> bool:
        delta = self._get_delta(instance) * sign
        if delta == 0:
            return False
        prev = getattr(foreign_object, self.field)
        setattr(foreign_object, self.field, prev + delta)
        return True

    def _get_delta(self, instance):
        if self.aggregate is Count:
            return 1
        elif self.aggregate is Sum:
            arg = self.aggregate.source_expressions[0]
            return getattr(instance, arg)
        raise NotImplementedError()


