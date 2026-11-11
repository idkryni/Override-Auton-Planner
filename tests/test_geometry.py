import math

from override_planner.model.geometry import (angle_diff, bezier, heading_to, norm_heading, point_at_length,
                                             cumulative_lengths, rotated_rect, sample_bezier)


def test_heading_convention():
    assert heading_to((0, 0), (0, 10)) == 0
    assert heading_to((0, 0), (10, 0)) == 90
    assert heading_to((0, 0), (0, -10)) == 180
    assert heading_to((0, 0), (-10, 0)) == 270


def test_angle_diff_and_norm():
    assert angle_diff(10, 350) == 20
    assert angle_diff(350, 10) == -20
    assert norm_heading(-90) == 270
    assert norm_heading(720) == 0


def test_bezier_endpoints_and_length():
    p = [(0, 0), (0, 10), (10, 10), (10, 0)]
    assert bezier(*p, 0) == (0, 0)
    assert bezier(*p, 1) == (10, 0)
    straight = sample_bezier((0, 0), (0, 10), (0, 20), (0, 30))
    cum = cumulative_lengths(straight)
    assert math.isclose(cum[-1], 30, rel_tol=1e-6)
    (x, y), h = point_at_length(straight, cum, 15)
    assert math.isclose(y, 15, abs_tol=1e-6) and h == 0


def test_rotated_rect():
    pts = rotated_rect(0, 0, 90, 10, 20)
    xs = sorted(p[0] for p in pts)
    assert math.isclose(xs[-1], 10) and math.isclose(xs[0], -10)
