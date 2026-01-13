from django.db import models

# Create your models here.
from django.conf import settings
from django.db import models
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
