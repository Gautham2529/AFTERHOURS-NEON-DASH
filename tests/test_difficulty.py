from engine.difficulty import DifficultyCurve


def test_calm_curve_stays_slower_and_keeps_more_reaction_time():
    for elapsed in (0, 30, 120, 600):
        assert DifficultyCurve.speed(elapsed, True) < DifficultyCurve.speed(elapsed, False)
        assert DifficultyCurve.spawn_interval(elapsed, True) >= DifficultyCurve.CALM_SPAWN_FLOOR
        assert DifficultyCurve.spawn_interval(elapsed, True) > DifficultyCurve.spawn_interval(elapsed, False)


def test_speed_curves_cap_and_overdrive_is_temporary_input():
    assert DifficultyCurve.speed(10_000, True) == DifficultyCurve.CALM_SPEED_CAP
    assert DifficultyCurve.speed(10_000, False) == DifficultyCurve.STANDARD_SPEED_CAP
    assert DifficultyCurve.speed(10, True, overdrive=True) > DifficultyCurve.speed(10, True)
    assert DifficultyCurve.speed(-10, True) == DifficultyCurve.speed(0, True)
