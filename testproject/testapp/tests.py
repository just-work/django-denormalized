from django.db.models import F, Sum, Min, QuerySet, Aggregate, Q, Count, Max
from django.test import TestCase

from testproject.testapp import models


class DenormalizedTrackerTestCaseBase(TestCase):
    """ Base class for tests."""
    field_name: str
    value_for_empty_set = 0
    aggregate: Aggregate

    def setUp(self):
        self.group = models.Group.objects.create()
        self.team = models.Team.objects.create()
        self.member = models.Member.objects.create(
            group=self.group, team=self.team)

    def assertDenormalized(self, group: models.Group = None):
        """ """
        group = group or self.group
        group.refresh_from_db()

        expected = self.get_denormalized_value(group.member_set.all())
        value = getattr(group, self.field_name)
        self.assertEqual(value, expected)

    def get_denormalized_value(self, queryset: QuerySet):
        aggregate = queryset.aggregate(aggregate=self.aggregate)
        value = aggregate['aggregate']
        if value is None:
            return self.value_for_empty_set
        return value


class TrackerTestCase(DenormalizedTrackerTestCaseBase):
    """ Common tests for denormalized tracker."""

    def test_collector_delete(self):
        """ Cascade delete works correctly."""
        models.Member.objects.create(active=False, group=self.group)

        self.group.delete()

        self.assertEqual(models.Group.objects.count(), 0)

    def assertPointsSum(self, obj):
        obj.refresh_from_db()
        value = obj.member_set.filter(active=True).aggregate(
            Sum('points'))['points__sum']
        self.assertEqual(obj.points_sum, value)

    def test_track_multiple_foreign_keys(self):
        """ Multiple foreign keys tracked correctly."""
        team = models.Team.objects.create()
        self.member.team = team
        self.member.save()

        self.assertPointsSum(team)
        self.assertPointsSum(self.group)

        self.member.points += 1
        self.member.save()

        self.assertPointsSum(team)
        self.assertPointsSum(self.group)


class CountTestCase(DenormalizedTrackerTestCaseBase):
    field_name = 'members_count'
    aggregate = Count('id', filter=Q(active=True))

    def test_initial_value(self):
        """ After setUp group has single member."""
        self.assertDenormalized()

    def test_increment_on_new(self):
        """ Creating new member increments counter."""
        models.Member.objects.create(group=self.group)

        self.assertDenormalized()

    def test_skip_increment_on_new(self):
        """ Creating new non-suitable member leaves counter same."""
        member = models.Member()
        member.group = self.group
        member.active = False

        member.save()

        self.assertDenormalized()

    def test_decrement_on_delete(self):
        """ Deleting member decrements counter."""
        self.member.delete()

        self.assertDenormalized()

    def test_skip_decrement_on_delete(self):
        """ Deleting member decrements counter."""
        member = models.Member.objects.create(group=self.group, active=False)

        member.delete()

        self.assertDenormalized()

    def test_increment_on_change(self):
        """ Changing foreign key increments counter."""
        group = models.Group.objects.create()
        self.member.group = group

        self.member.save()

        self.assertDenormalized()

    def test_decrement_on_change(self):
        """ Changing foreign key decrements counter for old value."""
        group = models.Group.objects.create()
        self.member.group = group

        self.member.save()

        self.assertDenormalized()

    def test_increment_on_set_group(self):
        """ If object without group is moved to group, increment."""
        member = models.Member.objects.create(group=None, active=True)
        member.group = self.group

        member.save()

        self.assertDenormalized()

    def test_increment_and_change_group(self):
        """
        If object changes group and becomes active, only new group increments.
        """
        group = models.Group.objects.create()
        self.member.active = False
        self.member.save()

        self.member.active = True
        self.member.group = group
        self.member.save()

        self.assertDenormalized()
        self.assertDenormalized(group)

    def test_decrement_and_change_group(self):
        """
        If object changes group and becomes inactive, only old group increments.
        """
        group = models.Group.objects.create()

        self.member.active = False
        self.member.group = group
        self.member.save()

        self.assertDenormalized()
        self.assertDenormalized(group)

    def test_denormalize(self):
        """ Count can be refreshed from db."""
        setattr(self.group, self.field_name, 1000000)
        self.group.save()

        self.group.member_set.denormalize()

        self.assertDenormalized()

    def test_denormalize_with_conditions(self):
        """ Count can be refreshed from db."""
        models.Member.objects.create(group=self.group, active=False)
        setattr(self.group, self.field_name, 1000000)
        self.group.save()

        self.group.member_set.denormalize()

        self.assertDenormalized()

    def test_decrement_on_became_not_suitable(self):
        """ If object is not suitable anymore, decrement."""
        self.member.active = False

        self.member.save()

        self.assertDenormalized()

    def test_increment_on_become_suitable(self):
        """ If object became suitable, increment."""
        member = models.Member.objects.create(active=False, group=self.group)

        self.assertDenormalized()

        member.active = True
        member.save()

        self.assertDenormalized()

    def test_no_dirty_increments(self):
        """
        Increment respects operations performed in db by another processes.
        """
        group = models.Group.objects.get(pk=self.group.pk)
        models.Member.objects.create(group=group)

        models.Member.objects.create(group=self.group)

        self.assertDenormalized()

    def test_previous_state_reset_on_save(self):
        """ Save resets saved previous state for tracked object."""
        member = models.Member.objects.create(group=self.group, active=False)

        member.active = True
        member.save()

        self.assertDenormalized()

        member.active = False
        member.save()

        self.assertDenormalized()

    def test_handle_nullable_foreign_key(self):
        """ Nullable foreign key is skipped for trackers."""
        models.Member.objects.create(group=None)

        self.assertDenormalized()

    def test_foreign_key_become_null(self):
        """ If foreign key became null, decrement."""
        self.member.group = None
        self.member.save()

        self.assertDenormalized()

    def test_foreign_key_become_not_null(self):
        """ If foreign key became not null, increment."""
        member = models.Member.objects.create(group=None)

        member.group = self.group
        member.save()

        self.assertDenormalized()

    def test_save_not_affects_counters(self):
        """
        Saving fields not related to denormalized values not affects counts.
        """
        self.member.save()

        self.assertDenormalized()


class SumTestCase(CountTestCase):
    field_name = 'points_sum'
    aggregate = Sum('points', filter=Q(active=True))

    def test_save_incremental(self):
        """
        Using F-objects for tracked models
        """
        points = self.group.points_sum
        self.member.points = F('points') + 1

        self.member.save()

        self.group.refresh_from_db()
        self.assertEqual(self.group.points_sum, points + 1)


class MinTestCase(SumTestCase):
    field_name = 'points_min'
    aggregate = Min('points', filter=Q(active=True))
    value_for_empty_set = None

    def test_track_value_changed_on_increase(self):
        """
        Separate case for increasing tracked value.
        """
        self.member.points = 10
        self.member.save()

        self.assertDenormalized()

    def test_track_min_value_changed_on_decrease(self):
        """
        Separate case for decreasing tracked value.
        """
        self.member.points = -10
        self.member.save()

        self.assertDenormalized()


class MaxTestCase(MinTestCase):
    field_name = 'points_max'
    aggregate = Max('points', filter=Q(active=True))
