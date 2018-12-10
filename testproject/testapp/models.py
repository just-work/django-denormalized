from django.db import models
from django.db.models import Sum, Q

from denormalized.models import DenormalizedForeignKey
from denormalized.tracker import DenormalizedTracker


class Group(models.Model):
    members_count = models.PositiveIntegerField(default=0)
    points_sum = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'testapp'


class Team(models.Model):
    points_sum = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'testapp'


class Member(models.Model):
    group = DenormalizedForeignKey(
        Group, models.CASCADE, null=True,
        trackers=[DenormalizedTracker("members_count",
                                      callback=lambda obj: obj.active,
                                      query=Q(active=True)),
                  DenormalizedTracker("points_sum", aggregate=Sum("points"))])
    team = DenormalizedForeignKey(
        Team, models.CASCADE, null=True,
        trackers=[DenormalizedTracker("points_sum", aggregate=Sum("points"))]
    )
    active = models.BooleanField(default=True)
    points = models.IntegerField(default=0)

    class Meta:
        app_label = 'testapp'
