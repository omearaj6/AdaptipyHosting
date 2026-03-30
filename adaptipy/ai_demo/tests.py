from datetime import timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from .models import TopicProficiency, UserLearningProfile, UserNotebook
from .proficiencies import (
    apply_decay_if_needed,
    ensure_proficiency_rows,
    update_proficiency,
)


class BasicTestCase(TestCase):
    def test_basic_math(self):
        self.assertEqual(1 + 1, 2)

    def test_home_page_status(self):
        response = self.client.get("/")
        self.assertIn(response.status_code, [200, 302])


class ProficiencyTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="testuser",
            password="testpass123",
        )
        ensure_proficiency_rows(self.user)

    def test_update_proficiency_increases_value(self):
        new_value = update_proficiency(self.user, "print_basics", 1.0)
        self.assertEqual(new_value, 1.0)

        row = TopicProficiency.objects.get(user=self.user, topic="print_basics")
        self.assertEqual(float(row.proficiency), 1.0)
        self.assertIsNotNone(row.last_practiced_at)

    def test_update_proficiency_decreases_but_not_below_zero(self):
        new_value = update_proficiency(self.user, "print_basics", -0.25)
        self.assertEqual(new_value, 0.0)

        row = TopicProficiency.objects.get(user=self.user, topic="print_basics")
        self.assertEqual(float(row.proficiency), 0.0)

    def test_update_proficiency_caps_at_five(self):
        update_proficiency(self.user, "print_basics", 10.0)

        row = TopicProficiency.objects.get(user=self.user, topic="print_basics")
        self.assertEqual(float(row.proficiency), 5.0)

    def test_apply_decay_if_needed_reduces_proficiency_after_days(self):
        update_proficiency(self.user, "print_basics", 3.0)

        profile = UserLearningProfile.objects.get(user=self.user)
        profile.last_decay_applied_at = timezone.now() - timedelta(days=3)
        profile.save(update_fields=["last_decay_applied_at"])

        days = apply_decay_if_needed(self.user)

        self.assertEqual(days, 3)

        row = TopicProficiency.objects.get(user=self.user, topic="print_basics")
        self.assertAlmostEqual(float(row.proficiency), 2.7, places=2)

    def test_apply_decay_if_needed_does_not_go_below_zero(self):
        update_proficiency(self.user, "print_basics", 0.2)

        profile = UserLearningProfile.objects.get(user=self.user)
        profile.last_decay_applied_at = timezone.now() - timedelta(days=5)
        profile.save(update_fields=["last_decay_applied_at"])

        apply_decay_if_needed(self.user)

        row = TopicProficiency.objects.get(user=self.user, topic="print_basics")
        self.assertEqual(float(row.proficiency), 0.0)

    def test_apply_decay_if_needed_returns_zero_if_same_day(self):
        days = apply_decay_if_needed(self.user)
        self.assertEqual(days, 0)


class ViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="viewuser",
            password="testpass123",
        )
        self.client = Client()

    def test_coding_demo_page_responds(self):
        response = self.client.get(reverse("coding_demo"))
        self.assertIn(response.status_code, [200, 302])

    def test_coding_demo_loads_for_logged_in_user(self):
        logged_in = self.client.login(username="viewuser", password="testpass123")
        self.assertTrue(logged_in)

        response = self.client.get(reverse("coding_demo"))
        self.assertEqual(response.status_code, 200)

    def test_save_notebook_requires_login(self):
        response = self.client.post(reverse("save_notebook"), {"content": "Test note"})
        self.assertEqual(response.status_code, 302)

    def test_save_notebook_creates_notebook(self):
        logged_in = self.client.login(username="viewuser", password="testpass123")
        self.assertTrue(logged_in)

        response = self.client.post(
            reverse("save_notebook"),
            {"content": "My first note"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {"success": True, "message": "Notebook saved"},
        )

        notebook = UserNotebook.objects.get(user=self.user)
        self.assertEqual(notebook.content, "My first note")

    def test_save_notebook_updates_existing_notebook(self):
        UserNotebook.objects.create(user=self.user, content="Old content")

        logged_in = self.client.login(username="viewuser", password="testpass123")
        self.assertTrue(logged_in)

        response = self.client.post(
            reverse("save_notebook"),
            {"content": "Updated content"},
        )
        self.assertEqual(response.status_code, 200)

        notebook = UserNotebook.objects.get(user=self.user)
        self.assertEqual(notebook.content, "Updated content")