from django.db import models
from django.db.models import Sum

from denormalized.models import DenormalizedForeignKey
from denormalized.tracker import DenormalizedTracker


class Group(models.Model):
    members_count = models.PositiveIntegerField(default=0)
    points_sum = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'testapp'


class Member(models.Model):
    group = DenormalizedForeignKey(
        Group, models.CASCADE,
        trackers=[DenormalizedTracker("members_count",
                                      callback=lambda obj: obj.active),
                  DenormalizedTracker("points_sum", aggregate=Sum("points"))])
    active = models.BooleanField(default=True)
    points = models.IntegerField(default=0)

    class Meta:
        app_label = 'testapp'
