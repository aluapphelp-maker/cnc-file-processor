"""Tests for geometry primitives."""

from core.geometry import Line, Point, Polyline


def test_point_dist_and_tol():
    a = Point(0, 0)
    b = Point(3, 4)
    assert a.dist(b) == 5.0
    assert a.almost_equal(Point(0.005, 0), tol=0.01)
    assert not a.almost_equal(Point(0.02, 0), tol=0.01)


def test_line_bidirectional():
    line = Line(Point(0, 0), Point(10, 0))
    assert line.length == 10.0
    assert line.almost_equal(Line(Point(10, 0), Point(0, 0)))
    assert not line.almost_equal(Line(Point(10, 0), Point(0, 0)), bidirectional=False)


def test_polyline_closed_segments():
    poly = Polyline(
        points=[Point(0, 0), Point(10, 0), Point(10, 5), Point(0, 5)],
        closed=True,
    )
    assert len(poly.segments) == 4
    assert poly.bbox == (0, 0, 10, 5)
    assert poly.total_length() == 30.0
