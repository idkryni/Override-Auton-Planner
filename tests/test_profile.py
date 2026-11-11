import math

from override_planner.model.actions import Action
from override_planner.model.path import Route
from override_planner.model.profile import RobotConfig, build_timeline, trapezoid_pos, trapezoid_time

ROBOT = RobotConfig(max_velocity=60, max_acceleration=120, max_angular_velocity=360, max_angular_acceleration=900)


def test_trapezoid():
    # full speed reached: d=60 -> 60/60 + 60/120 = 1.5 s
    assert math.isclose(trapezoid_time(60, 60, 120), 1.5)
    # triangular: d=10 -> 2*sqrt(10/120)
    assert math.isclose(trapezoid_time(10, 60, 120), 2 * math.sqrt(10 / 120))
    t = trapezoid_time(60, 60, 120)
    assert math.isclose(trapezoid_pos(t, 60, 60, 120), 60)
    assert math.isclose(trapezoid_pos(t / 2, 60, 60, 120), 30)


def test_timeline_straight_turn_action():
    r = Route()
    r.add(20, 20)            # start heading 0
    r.add(20, 80)            # straight ahead, 60 in
    i = r.add(80, 80)        # needs a 90 deg turn
    r.waypoints[i].actions.append(Action("score_goal", 0.5))
    tl = build_timeline(r, ROBOT)
    kinds = [p.kind for p in tl.phases]
    assert kinds == ["drive", "turn", "drive", "action"]
    assert math.isclose(tl.phases[0].duration, 1.5)
    x, y, h, _ = tl.pose_at(tl.total)
    assert (round(x, 3), round(y, 3), round(h, 3)) == (80, 80, 90)
    assert math.isclose(tl.total, tl.arrival[2] + 0.5)


def test_reverse_and_mirror():
    r = Route()
    r.add(20, 20)
    i = r.add(20, 0.0 + 5)
    r.waypoints[i].reverse = True   # back up while facing 0
    tl = build_timeline(r, ROBOT)
    assert [p.kind for p in tl.phases] == ["drive"]
    assert r.heading_at(1) == 0
    r.mirror()
    assert math.isclose(r.waypoints[0].x, 140.41 - 20)


def test_curve_heading_matches_pose():
    r = Route()
    r.add(20, 20)
    r.add(60, 60)
    r.set_curve(1, True)
    r.set_heading(1, 90)
    assert math.isclose(r.curve_end_heading(1), 90, abs_tol=1e-6)
    tl = build_timeline(r, ROBOT)
    assert tl.phases[-1].curve
    _, _, h, _ = tl.pose_at(tl.total)
    assert math.isclose(h, 90, abs_tol=1.0)
