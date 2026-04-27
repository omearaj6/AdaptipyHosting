from datetime import timedelta
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone
from unittest.mock import patch
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


   def test_ensure_proficiency_rows_creates_rows(self):
       self.assertTrue(TopicProficiency.objects.filter(user=self.user).exists())


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




   def test_cannot_resubmit_same_problem_for_extra_proficiency(self):
       self.client.login(username="viewuser", password="testpass123")


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "print('Hello') outputs Hello",
       }
       session["current_problem_awarded"] = False
       session.save()


       with patch("ai_demo.views.check_user_code") as mock_runner, \
           patch("ai_demo.views.codestral_analyse") as mock_ai:


           mock_runner.return_value = ("Hello", "", 0)
           mock_ai.return_value = {
               "correct": True,
               "delta": 1.0,
               "feedback": "Correct",
           }


           self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Hello')",
                   "submit_code": "1",
               },
           )


           self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Hello')",
                   "submit_code": "1",
               },
           )


       prof = TopicProficiency.objects.get(
           user=self.user,
           topic="print_basics",
       )


       self.assertEqual(float(prof.proficiency), 1.0)




   def test_incorrect_submission_reduces_proficiency(self):
       self.client.login(username="viewuser", password="testpass123")


       TopicProficiency.objects.create(
           user=self.user,
           topic="print_basics",
           proficiency=2.0,
       )


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "print('Hello') outputs Hello",
       }
       session["current_problem_awarded"] = False
       session.save()


       with patch("ai_demo.views.check_user_code") as mock_runner, \
           patch("ai_demo.views.codestral_analyse") as mock_ai:


           mock_runner.return_value = ("Wrong", "", 0)
           mock_ai.return_value = {
               "correct": False,
               "delta": -0.5,
               "feedback": "Incorrect output",
           }


           response = self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Wrong')",
                   "submit_code": "1",
               },
           )


       self.assertEqual(response.status_code, 200)


       prof = TopicProficiency.objects.get(
           user=self.user,
           topic="print_basics",
       )


       self.assertEqual(float(prof.proficiency), 1.5)




   def test_correct_submission_increases_proficiency(self):
       self.client.login(username="viewuser", password="testpass123")


       TopicProficiency.objects.create(
           user=self.user,
           topic="print_basics",
           proficiency=2.0,
       )


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "print('Hello') outputs Hello",
       }
       session["current_problem_awarded"] = False
       session.save()


       with patch("ai_demo.views.check_user_code") as mock_runner, \
           patch("ai_demo.views.codestral_analyse") as mock_ai:


           mock_runner.return_value = ("Hello", "", 0)
           mock_ai.return_value = {
               "correct": True,
               "delta": 1.0,
               "feedback": "Correct",
           }


           response = self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Hello')",
                   "submit_code": "1",
               },
           )


       self.assertEqual(response.status_code, 200)


       prof = TopicProficiency.objects.get(
           user=self.user,
           topic="print_basics",
       )


       self.assertEqual(float(prof.proficiency), 3.0)




   def test_correct_submission_does_not_exceed_max_proficiency(self):
       self.client.login(username="viewuser", password="testpass123")


       TopicProficiency.objects.create(
           user=self.user,
           topic="print_basics",
           proficiency=4.8,
       )


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "print('Hello') outputs Hello",
       }
       session["current_problem_awarded"] = False
       session.save()


       with patch("ai_demo.views.check_user_code") as mock_runner, \
           patch("ai_demo.views.codestral_analyse") as mock_ai:


           mock_runner.return_value = ("Hello", "", 0)
           mock_ai.return_value = {
               "correct": True,
               "delta": 1.0,
               "feedback": "Correct",
           }


           response = self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Hello')",
                   "submit_code": "1",
               },
           )


       self.assertEqual(response.status_code, 200)


       prof = TopicProficiency.objects.get(
           user=self.user,
           topic="print_basics",
       )


       self.assertEqual(float(prof.proficiency), 5.0)




   def test_run_code_does_not_change_proficiency(self):
       self.client.login(username="viewuser", password="testpass123")


       TopicProficiency.objects.create(
           user=self.user,
           topic="print_basics",
           proficiency=2.0,
       )


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "print('Hello') outputs Hello",
       }
       session["current_problem_awarded"] = False
       session.save()


       with patch("ai_demo.views.check_user_code") as mock_runner:
           mock_runner.return_value = ("Hello", "", 0)


           response = self.client.post(
               reverse("coding_demo"),
               {
                   "code": "print('Hello')",
                   "run_code": "1",
               },
           )


       self.assertEqual(response.status_code, 200)


       prof = TopicProficiency.objects.get(
           user=self.user,
           topic="print_basics",
       )


       self.assertEqual(float(prof.proficiency), 2.0)


   def test_new_problem_resets_current_problem_session(self):
       self.client.login(username="viewuser", password="testpass123")


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Old problem",
           "expected_output": "Old output",
           "lesson": "Old lesson",
           "explanation": "Old explanation",
       }
       session["current_problem_awarded"] = True
       session["show_explanation"] = True
       session.save()


       with patch("ai_demo.views.generate_problem_with_solution") as mock_generate:
           mock_generate.return_value = {
               "problem": "New problem",
               "expected_output": "New output",
               "lesson": "New lesson",
               "explanation": "New explanation",
           }


           response = self.client.post(
               reverse("coding_demo"),
               {
                   "new_problem": "1",
               },
           )


       self.assertEqual(response.status_code, 200)


       session = self.client.session
       self.assertEqual(session["current_problem_json"]["problem"], "New problem")
       self.assertFalse(session["current_problem_awarded"])
       self.assertNotIn("show_explanation", session)


   def test_i_dont_understand_shows_explanation(self):
       self.client.login(username="viewuser", password="testpass123")


       session = self.client.session
       session["active_topic"] = "print_basics"
       session["current_problem_json"] = {
           "problem": "Print Hello",
           "expected_output": "Hello",
           "lesson": "Use print",
           "explanation": "Use print('Hello') to output Hello.",
       }
       session["current_problem_awarded"] = False
       session.save()


       response = self.client.post(
           reverse("coding_demo"),
           {
               "i_dont_understand": "1",
           },
       )


       self.assertEqual(response.status_code, 200)
       self.assertTrue(self.client.session.get("show_explanation"))


   def test_coding_demo_requires_login(self):
       response = self.client.get(reverse("coding_demo"))
       self.assertEqual(response.status_code, 302)

