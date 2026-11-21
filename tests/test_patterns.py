import random

from engine.patterns import PatternGenerator


def test_generated_patterns_keep_lanes_valid_and_leave_hazards_avoidable():
    generator = PatternGenerator(random.Random(1999))
    recent_lanes = []
    hazard_count = 0
    for _ in range(500):
        pattern = generator.generate(battery_level=5)
        assert pattern
        assert all(0 <= entity["lane"] <= 2 and entity["y"] >= 0 for entity in pattern)
        hazards = [entity for entity in pattern if entity["kind"] in generator.HAZARDS]
        assert len(hazards) <= 1
        if hazards:
            hazard_count += 1
            # A single-lane blocker always leaves two collision-free lanes.
            assert len({0, 1, 2} - {hazards[0]["lane"]}) == 2
        recent_lanes.append(pattern[0]["lane"])
        if len(recent_lanes) >= 3:
            assert not recent_lanes[-1] == recent_lanes[-2] == recent_lanes[-3]
    assert hazard_count > 100


def test_route_validator_models_reaction_window_and_sequential_lane_choice():
    assert PatternGenerator.has_reachable_route(
        [{"kind": "barrier", "lane": 1, "y": 145},
         {"kind": "gate", "lane": 0, "y": 250}], 360, player_lane=1)
    assert not PatternGenerator.has_reachable_route(
        [{"kind": "barrier", "lane": 1, "y": 400}], 200, player_lane=1)


def test_route_validator_rejects_all_lanes_blocked_at_once():
    row = [{"kind": kind, "lane": lane, "y": 300}
           for kind, lane in (("barrier", 0), ("gate", 1), ("fence", 2))]
    assert not PatternGenerator.has_reachable_route(row, 360, player_lane=1)
