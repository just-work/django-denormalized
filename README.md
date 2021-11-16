# django-denormalized
Utils for maintaining denormalized aggregates for Django models.

[![Build Status](https://github.com/just-work/django-denormalized/actions/workflows/build.yml/badge.svg)](https://github.com/just-work/django-denormalized/actions/workflows/build.yml)
[![codecov](https://github.com/just-work/django-denormalized/actions/workflows/codecov.yml/badge.svg)](https://github.com/just-work/django-denormalized/actions/workflows/codecov.yml)
[![PyPI version](https://badge.fury.io/py/django-denormalized.svg)](https://badge.fury.io/py/django-denormalized)

# Example

```python
from django.db import models
from denormalized import DenormalizedTracker, DenormalizedForeignKey


class Group(models.Model):
    members_count = models.PositiveIntegerField(default=0)
    points_sum = models.PositiveIntegerField(default=0)


class Member(models.Model):
    group = DenormalizedForeignKey(
        Group, models.CASCADE,
        trackers=[
            DenormalizedTracker(
                # name of field to store denormalized count of active members
                "members_count",                    
                # callback to determine whether object should be counted or not
                callback=lambda obj: obj.active,
                # QuerySet filter to count only suitable objects
                query=models.Q(active=True)),
            DenormalizedTracker(
                # multiple denormalized fields tracked for single foreign key
                "points_sum",
                # Sum/Min/Max is also supported
                aggregate=models.Sum("points"))
        ])
    active = models.BooleanField(default=True)
    points = models.IntegerField(default=0)

```
