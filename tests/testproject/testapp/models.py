from django.db import models
from django.db.models import Sum, Min, Count, Q, Max

from denormalized import DenormalizedForeignKey
from denormalized import DenormalizedTracker


class Group(models.Model):
    members_count = models.PositiveIntegerField(default=0)
    points_sum = models.PositiveIntegerField(default=0)
    points_min = models.PositiveIntegerField(null=True)
    points_max = models.PositiveIntegerField(null=True)

    class Meta:
        app_label = 'testapp'


class Team(models.Model):
    points_sum = models.PositiveIntegerField(default=0)
    members_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'testapp'


class Member(models.Model):
    group = DenormalizedForeignKey(
        Group, models.CASCADE, null=True,
        trackers=[
            DenormalizedTracker(
                "members_count",
                callback=lambda obj: obj.active,
                query=Q(active=True),
                aggregate=Count("pk")),
            DenormalizedTracker(
                "points_sum",
                callback=lambda obj: obj.active,
                aggregate=Sum("points")),
            DenormalizedTracker(
                "points_min",
                callback=lambda obj: obj.active,
                query=Q(active=True),
                aggregate=Min("points")),
            DenormalizedTracker(
                "points_max",
                callback=lambda obj: obj.active,
                query=Q(active=True),
                aggregate=Max("points"))
        ])
    team = DenormalizedForeignKey(
        Team, models.CASCADE, null=True,
        trackers=[
            DenormalizedTracker(
                "points_sum",
                aggregate=Sum("points")),
            DenormalizedTracker("members_count"),
        ])
    active = models.BooleanField(default=True)
    points = models.IntegerField(default=0)

    class Meta:
        app_label = 'testapp'

    def save(self, force_insert=False, force_update=False, using=None,
             update_fields=None):
        """
        Override base save to test whether overridden save is also wrapped
        in DenormalizedForeignKey._wrap_save.
        """
        super().save(force_insert, force_update, using, update_fields)
