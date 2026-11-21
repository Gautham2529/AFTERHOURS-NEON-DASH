"""Small, data-driven run missions and lifetime achievements."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Goal:
    key: str
    title: str
    detail: str
    metric: str
    target: int
    reward: int


MISSIONS = (
    Goal("distance_1000", "NIGHT SHIFT", "Travel 1,000 metres in one run", "distance", 1000, 10),
    Goal("tokens_20", "TOKEN TRAIL", "Collect 20 tokens in one run", "coins", 20, 10),
    Goal("dash_5", "CLEAR THE LINE", "Dash through 5 hazards in one run", "dash_clears", 5, 15),
    Goal("lane_8", "CHANGE THE BEAT", "Change lanes 8 times in one run", "lane_changes", 8, 12),
    Goal("jumps_3", "CLEAR THE BARRICADE", "Successfully jump 3 barriers", "jump_successes", 3, 12),
    Goal("slides_3", "LOW PROFILE", "Successfully slide under 3 gates", "slide_successes", 3, 12),
    Goal("powerups_3", "CHARGED UP", "Collect 3 power-ups in one run", "powerup_count", 3, 12),
    Goal("near_miss_4", "CLOSE CALL", "Pass 4 hazards in a nearby lane", "near_misses", 4, 12),
    Goal("survive_60", "STAY IN THE FLOW", "Survive for 60 seconds", "elapsed", 60, 15),
)

CAREER_MISSIONS = (
    Goal("career_distance_5000", "ALL NIGHTER", "Travel 5,000 metres across runs", "distance", 5000, 40),
    Goal("career_tokens_75", "TOKEN BANK", "Collect 75 tokens across runs", "coins", 75, 35),
    Goal("career_dash_20", "LIVE CIRCUIT", "Clear 20 hazards with dash across runs", "dash_clears", 20, 45),
    Goal("career_clean_25", "CLEAN RHYTHM", "Land 25 clean jumps or slides across runs", "clean_moves", 25, 40),
    Goal("career_powerups_15", "FULLY CHARGED", "Collect 15 power-ups across runs", "powerup_count", 15, 40),
    Goal("career_evasions_30", "ALWAYS A WAY", "Make 30 successful hazard evasions across runs", "successful_avoids", 30, 50),
)

DEFAULT_MISSIONS = MISSIONS[:3]


def select_missions(analytics: object, claimed: set[str], history: tuple[str, ...] = (),
                    count: int = 3) -> tuple[Goal, ...]:
    """Select achievable goals; after a small history, gently target weak skills."""
    runs = getattr(analytics, "runs", [])
    if len(runs) < 3:
        preferred = list(DEFAULT_MISSIONS) + list(MISSIONS[3:])
    else:
        recent = runs[-5:]
        jumps = sum(max(0, int(run.get("jumps", 0))) for run in recent)
        jump_success = sum(max(0, int(run.get("jump_successes", 0))) for run in recent)
        slides = sum(max(0, int(run.get("slides", 0))) for run in recent)
        slide_success = sum(max(0, int(run.get("slide_successes", 0))) for run in recent)
        powerups = sum(sum(run.get("powerups", {}).values())
                       for run in recent if isinstance(run.get("powerups"), dict))
        lane_changes = sum(max(0, int(run.get("lane_changes", 0))) for run in recent)
        collision_kinds = {}
        for run in recent:
            kinds = run.get("collisions", {})
            if isinstance(kinds, dict):
                for kind, total in kinds.items():
                    collision_kinds[kind] = collision_kinds.get(kind, 0) + max(0, int(total))
        candidates = []
        if (jumps and jump_success / jumps < .70) or collision_kinds.get("barrier", 0) >= 2:
            candidates.append(MISSIONS[4])
        if (slides and slide_success / slides < .70) or collision_kinds.get("gate", 0) >= 2:
            candidates.append(MISSIONS[5])
        if powerups / max(1, len(recent)) < 1:
            candidates.append(MISSIONS[6])
        if lane_changes / max(1, len(recent)) < 4:
            candidates.append(MISSIONS[3])
        candidates.extend((MISSIONS[0], MISSIONS[1], MISSIONS[2], MISSIONS[3], MISSIONS[7], MISSIONS[8]))
        recent_keys = set(history[-3:])
        preferred = [goal for goal in candidates if goal.key not in recent_keys]
        if len(preferred) < count:
            preferred.extend(goal for goal in candidates if goal not in preferred)
    selected = []
    for goal in preferred:
        if goal.key not in claimed and goal not in selected:
            selected.append(goal)
        if len(selected) == count:
            break
    # Once the finite catalog has been claimed, allow replayable goals as fallback.
    if len(selected) < count:
        selected.extend(goal for goal in preferred if goal not in selected)
    return tuple(selected[:count])


def select_career_missions(analytics: object, claimed: set[str], history: tuple[str, ...] = (),
                           count: int = 2) -> tuple[Goal, ...]:
    """Select unclaimed cumulative contracts, gently favoring underused actions."""
    count = max(0, int(count))
    if count == 0:
        return ()
    runs = getattr(analytics, "runs", [])
    targeted = []
    if runs:
        recent = runs[-5:]
        jumps = sum(max(0, int(run.get("jumps", 0))) for run in recent)
        jump_success = sum(max(0, int(run.get("jump_successes", 0))) for run in recent)
        slides = sum(max(0, int(run.get("slides", 0))) for run in recent)
        slide_success = sum(max(0, int(run.get("slide_successes", 0))) for run in recent)
        if (jumps and jump_success / jumps < .70) or (slides and slide_success / slides < .70):
            targeted.append(CAREER_MISSIONS[3])
        powerups = sum(sum(run.get("powerups", {}).values())
                       for run in recent if isinstance(run.get("powerups"), dict))
        if powerups / max(1, len(recent)) < 1:
            targeted.append(CAREER_MISSIONS[4])
        if sum(max(0, int(run.get("dash_activations", 0))) for run in recent) == 0:
            targeted.append(CAREER_MISSIONS[2])
    ordered = targeted + list(CAREER_MISSIONS)
    recent_keys = set(history[-3:])
    selected = []
    for avoid_recent in (True, False):
        for goal in ordered:
            if (goal.key in claimed or goal in selected
                    or (avoid_recent and goal.key in recent_keys)):
                continue
            selected.append(goal)
            if len(selected) >= count:
                return tuple(selected)
    return tuple(selected)

ACHIEVEMENTS = (
    Goal("first_run", "FIRST NIGHT", "Finish your first run", "total_runs", 1, 10),
    Goal("tokens_100", "POCKET CHANGE", "Collect 100 tokens in total", "lifetime_coins", 100, 25),
    Goal("distance_10000", "LONG WAY HOME", "Travel 10,000 metres in total", "lifetime_distance", 10_000, 50),
    Goal("dash_25", "LIVE WIRE", "Dash through 25 hazards in total", "lifetime_dash_clears", 25, 30),
)

DAILY_CHALLENGES = (
    Goal("daily_distance", "DAILY DISTANCE", "Cover 1,500 metres in one run", "distance", 1500, 25),
    Goal("daily_tokens", "DAILY TOKEN RUN", "Collect 30 tokens in one run", "coins", 30, 25),
    Goal("daily_dash", "DAILY LIVE WIRE", "Dash through 8 hazards in one run", "dash_clears", 8, 30),
)

WEEKLY_CHALLENGES = (
    Goal("weekly_distance", "WEEKLY MILEAGE", "Travel 4,000 metres across this week", "distance", 4000, 60),
    Goal("weekly_tokens", "WEEKLY TOKEN BANK", "Collect 100 tokens across this week", "coins", 100, 60),
    Goal("weekly_dash", "WEEKLY LIVE WIRE", "Dash through 20 hazards this week", "dash_clears", 20, 70),
)


def daily_challenge_for(day: date) -> Goal:
    """Choose the same offline daily objective for every launch on a given date."""
    return DAILY_CHALLENGES[day.toordinal() % len(DAILY_CHALLENGES)]


def weekly_challenge_for(day: date) -> Goal:
    """Choose a stable offline objective for the current ISO week."""
    return WEEKLY_CHALLENGES[day.isocalendar().week % len(WEEKLY_CHALLENGES)]


def newly_completed(goals: tuple[Goal, ...], values: dict[str, int], already_claimed: set[str]) -> list[Goal]:
    """Return eligible goals once, in stable display order."""
    return [goal for goal in goals
            if goal.key not in already_claimed and values.get(goal.metric, 0) >= goal.target]
