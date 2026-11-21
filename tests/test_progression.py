from datetime import date, timedelta

from engine.progression import (DAILY_CHALLENGES, WEEKLY_CHALLENGES,
                                daily_challenge_for, newly_completed,
                                weekly_challenge_for)


def test_offline_daily_objective_is_stable_for_the_day_and_rotates():
    start = date(2026, 11, 21)
    assert daily_challenge_for(start) == daily_challenge_for(start)
    assert {daily_challenge_for(start + timedelta(days=offset)).key
            for offset in range(len(DAILY_CHALLENGES))} == {goal.key for goal in DAILY_CHALLENGES}


def test_goal_reward_is_only_returned_before_it_is_claimed():
    goal = DAILY_CHALLENGES[0]
    assert newly_completed((goal,), {goal.metric: goal.target}, set()) == [goal]
    assert newly_completed((goal,), {goal.metric: goal.target}, {goal.key}) == []


def test_offline_weekly_objective_is_stable_for_iso_week():
    assert weekly_challenge_for(date(2026, 11, 16)) == weekly_challenge_for(date(2026, 11, 22))
    assert weekly_challenge_for(date(2026, 11, 16)).key in {goal.key for goal in WEEKLY_CHALLENGES}
