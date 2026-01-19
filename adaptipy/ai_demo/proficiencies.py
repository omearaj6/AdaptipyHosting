from django.utils import timezone
from .models import UserLearningProfile, TopicProficiency, ALL_TOPICS

def ensure_proficiency_rows(user):
    now = timezone.now()

    UserLearningProfile.objects.get_or_create(
        user=user,
        defaults={"last_decay_applied_at": now, "last_topic": ""},
    )

    existing = set(
        TopicProficiency.objects.filter(user=user).values_list("topic", flat=True)
    )
    missing = [t for t in ALL_TOPICS if t not in existing]
    if missing:
        TopicProficiency.objects.bulk_create(
            [TopicProficiency(user=user, topic=t, proficiency=0.0) for t in missing],
            ignore_conflicts=True,
        )
