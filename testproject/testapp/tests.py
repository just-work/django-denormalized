from django.test import TestCase

from testproject.testapp import models


class CountTestCase(TestCase):
    def setUp(self):
        self.group = models.Group.objects.create()
        self.member = models.Member.objects.create(group=self.group)

    def test_initial_value(self):
        """ After setUp group has single member."""
        self.group.refresh_from_db()
        self.assertEqual(self.group.members_count, 1)

    def test_increment_on_new(self):
        """ Creating new member increments counter."""
        models.Member.objects.create(group=self.group)

        self.group.refresh_from_db()
        self.assertEqual(self.group.members_count, 2)

    def test_decrement_on_delete(self):
        """ Deleting member decrements counter."""
        self.member.delete()

        self.group.refresh_from_db()
        self.assertEqual(self.group.members_count, 0)

    def test_increment_on_change(self):
        """ Changing foreign key increments counter."""
        group = models.Group.objects.create()
        self.member.group = group

        self.member.save()

        group.refresh_from_db()
        self.assertEqual(group.members_count, 1)

    def test_decrement_on_change(self):
        """ Changing foreign key decrements counter for old value."""
        group = models.Group.objects.create()
        self.member.group = group

        self.member.save()

        self.group.refresh_from_db()
        self.assertEqual(self.group.members_count, 0)

    def test_refresh(self):
        """ Count cat be refreshed from db."""
        self.group.members_count = None

        self.group.member_set._build_denormalize_method()

        self.assertEqual(self.group.members_count, 1)
