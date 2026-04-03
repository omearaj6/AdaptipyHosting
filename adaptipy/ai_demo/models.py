from django.db import models
from django.conf import settings
from django.utils import timezone


# for SM2, could be removed
class TopicProgress(models.Model):
    """
    One SM-2 record per (user, topic).
    """

    TOPIC_CHOICES = [
        ("loops", "loops"),
        ("strings", "strings"),
        ("arrays", "arrays"),
        ("recursion", "recursion"),
        ("conditionals", "conditionals"),
        ("variables", "variables"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sm2_progress",
    )

    topic = models.CharField(max_length=64, choices=TOPIC_CHOICES)

    ef = models.FloatField(default=2.5)
    interval = models.FloatField(default=0.0)
    reps = models.IntegerField(default=0)
    lapses = models.IntegerField(default=0)
    due = models.DateTimeField(default=timezone.now)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], name="uniq_user_topic_sm2")
        ]
        indexes = [
            models.Index(fields=["user", "due"]),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.topic}"



TOPICS_LEVEL_1 = ["print_basics", "variables", "operators", "strings"]
TOPICS_LEVEL_2 = ["lists", "conditionals", "for_loops", "while_loops"]

ALL_TOPICS = TOPICS_LEVEL_1 + TOPICS_LEVEL_2
TOPIC_CHOICES = [(t, t) for t in ALL_TOPICS]


class UserLearningProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_profile",
    )
    last_decay_applied_at = models.DateTimeField(default=timezone.now)
    last_topic = models.CharField(max_length=64, blank=True, default="")
    editor_theme = models.CharField(max_length=10, default='vs-dark', choices=[('vs-dark', 'Dark'), ('vs', 'Light')])

    def __str__(self):
        return f"LearningProfile(user_id={self.user_id})"


class TopicProficiency(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="topic_proficiencies",
    )
    topic = models.CharField(max_length=64, choices=TOPIC_CHOICES)
    proficiency = models.FloatField(default=0.0)
    last_practiced_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "topic"], name="uniq_user_topic_proficiency")
        ]
        indexes = [
            models.Index(fields=["user", "topic"], name="idx_user_topic_prof"),
            models.Index(fields=["user", "proficiency"], name="idx_user_prof_value"),
        ]

    def __str__(self):
        return f"{self.user_id}:{self.topic}={self.proficiency}"


class UserNotebook(models.Model):
    """Simple one-notebook-per-user model."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notebook",
        primary_key=True
    )
    content = models.TextField(blank=True, default="")
    updated_at = models.DateTimeField(auto_now=True)  # Just to know when it was last saved

    def __str__(self):
        return f"Notebook for {self.user.username}"