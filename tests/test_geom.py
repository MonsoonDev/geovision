import math
from pathlib import Path

import pytest

from geovision.geom import (
    GeometryError,
    circumcircle,
    circle_circle,
    compile_expr,
    line_intersection,
    orthocenter,
    sample_curve,
    vec,
)

ROOT = Path(__file__).parents[1]


def test_circumcircle_of_right_triangle():
    center, radius, normal = circumcircle(vec(0, 0), vec(4, 0), vec(0, 3))
    assert center == pytest.approx((2, 1.5, 0))
    assert radius == pytest.approx(2.5)
    assert normal == pytest.approx((0, 0, 1))


def test_circumcircle_rejects_collinear_points():
    with pytest.raises(GeometryError, match="collinear"):
        circumcircle(vec(0, 0), vec(1, 0), vec(2, 0))


def test_orthocenter_of_right_triangle():
    center = orthocenter(vec(0, 0), vec(4, 0), vec(0, 3))
    assert center == pytest.approx((0, 0, 0))


def test_line_intersection():
    hit = line_intersection(vec(0, 0), vec(2, 0), vec(1, -1), vec(0, 3))
    assert hit == pytest.approx((1, 0, 0))


def test_parallel_lines_do_not_meet():
    assert line_intersection(vec(0, 0), vec(1, 0), vec(0, 1), vec(1, 0)) is None


def test_circle_circle_intersections():
    hits = circle_circle(vec(0, 0), 1, vec(0, 0, 1), vec(1, 0), 1, vec(0, 0, 1))
    assert len(hits) == 2
    assert hits[0] == pytest.approx((0.5, math.sqrt(3) / 2, 0))
    assert hits[1] == pytest.approx((0.5, -math.sqrt(3) / 2, 0))


def test_plot_samples_a_parabola_and_splits_a_gap():
    assert compile_expr("x^2")(2) == pytest.approx(4)
    paths = sample_curve("x^2", -2, 2, 21)
    assert len(paths) == 1
    nearest = min(paths[0], key=lambda point: abs(point[0] - 2))
    assert nearest[1] == pytest.approx(4)
    assert len(sample_curve("1/x", -2, 2, 81)) >= 2


def test_plot_rejects_python():
    with pytest.raises(GeometryError):
        compile_expr("__import__('os')")
    with pytest.raises(GeometryError):
        compile_expr("sin.__class__")


def test_clip_keeps_the_visible_part_of_a_segment():
    from geovision.geom import clip_segment

    clipped = clip_segment(vec(-2, 0), vec(2, 0), (-1, -1, 1, 1))
    assert clipped[0] == pytest.approx((-1, 0, 0))
    assert clipped[1] == pytest.approx((1, 0, 0))
