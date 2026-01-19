from django.db import models
from django.conf import settings
from django.utils import timezone


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



TOPICS_LEVEL_1 = ["print_basics", "variables", "primitive_data_types", "simple_operators"]
TOPICS_LEVEL_2 = ["while_loops", "for_loops", "conditionals", "lists", "strings_advanced", "basic_edge_cases"]
TOPICS_LEVEL_3 = ["dictionaries", "functions", "all_loops_advanced"]

ALL_TOPICS = TOPICS_LEVEL_1 + TOPICS_LEVEL_2 + TOPICS_LEVEL_3
TOPIC_CHOICES = [(t, t) for t in ALL_TOPICS]


class UserLearningProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="learning_profile",
    )
    last_decay_applied_at = models.DateTimeField(default=timezone.now)
    last_topic = models.CharField(max_length=64, blank=True, default="")

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