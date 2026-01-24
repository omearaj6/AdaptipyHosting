import os
import random
from django.db import transaction
from django.utils import timezone

from .models import UserLearningProfile, TopicProficiency, ALL_TOPICS

DECAY_PER_DAY = float(os.getenv("DECAY_PER_DAY", "0.1"))


def clamp(x: float, lo: float = 0.0, hi: float = 5.0) -> float:
    return max(lo, min(hi, x))


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


@transaction.atomic
def apply_decay_if_needed(user) -> int:
    ensure_proficiency_rows(user)

    profile = (
        UserLearningProfile.objects
        .select_for_update()
        .get(user=user)
    )

    now = timezone.now()

    if not profile.last_decay_applied_at:
        profile.last_decay_applied_at = now
        profile.save(update_fields=["last_decay_applied_at"])
        return 0

    days = (now.date() - profile.last_decay_applied_at.date()).days
    if days <= 0:
        return 0

    decay_amount = DECAY_PER_DAY * days

    rows = list(TopicProficiency.objects.filter(user=user).only("id", "proficiency"))
    for r in rows:
        r.proficiency = clamp(float(r.proficiency) - decay_amount)
        r.updated_at = now

    TopicProficiency.objects.bulk_update(rows, ["proficiency", "updated_at"])

    profile.last_decay_applied_at = now
    profile.save(update_fields=["last_decay_applied_at"])

    return days


def get_proficiencies(user) -> dict:
    ensure_proficiency_rows(user)
    qs = TopicProficiency.objects.filter(user=user).only("topic", "proficiency")
    return {r.topic: float(r.proficiency) for r in qs}


@transaction.atomic
def update_proficiency(user, topic: str, delta: float) -> float:
    ensure_proficiency_rows(user)
    now = timezone.now()

    row = (
        TopicProficiency.objects
        .select_for_update()
        .get(user=user, topic=topic)
    )

    row.proficiency = clamp(float(row.proficiency) + float(delta))
    row.last_practiced_at = now
    row.save(update_fields=["proficiency", "last_practiced_at", "updated_at"])

    UserLearningProfile.objects.filter(user=user).update(last_topic=topic)

    return float(row.proficiency)


def choose_next_topic(user, profs: dict) -> str:
    ensure_proficiency_rows(user)

    profile = UserLearningProfile.objects.get(user=user)
    last_topic = profile.last_topic or ""

    lvl1 = ["print_basics", "variables", "primitive_data_types", "simple_operators"]
    lvl2 = ["while_loops", "for_loops", "conditionals", "lists", "strings_advanced", "basic_edge_cases"]
    lvl3 = ["dictionaries", "functions", "all_loops_advanced"]

    def p(t: str) -> float:
        return float(profs.get(t, 0.0))

    if all(p(t) <= 0.0 for t in lvl1):
        return "print_basics"

    pool = list(lvl1)

    if all(p(t) >= 3.0 for t in lvl1):
        pool += lvl2

        if all(p(t) >= 3.0 for t in lvl2):
            pool += lvl3

    now = timezone.now()

    candidates = [t for t in pool if t != last_topic] or pool

    # Weight: low proficiency higher + small recency bonus
    rows = {
        r.topic: r
        for r in TopicProficiency.objects.filter(user=user, topic__in=candidates).only(
            "topic", "last_practiced_at"
        )
    }

    weights = []
    for t in candidates:
        prof = p(t)

        base = (5.0 - prof) + 0.25

        last = rows.get(t).last_practiced_at if rows.get(t) else None
        days = (now - last).days if last else 365
        recency_bonus = 1.0 + min(days, 14) / 28.0  # max +0.5

        weights.append(max(0.01, base * recency_bonus))

    return random.choices(candidates, weights=weights, k=1)[0]

