from django.db import models


class Group(models.Model):
    members_count = models.PositiveIntegerField(default=0)

    class Meta:
        app_label = 'testapp'


class Member(models.Model):
    group = models.ForeignKey(Group, models.CASCADE)
    active = models.BooleanField(default=False)

    class Meta:
        app_label = 'testapp'
