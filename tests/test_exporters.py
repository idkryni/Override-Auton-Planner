import csv
import io
import json

from override_planner.export import FORMATS, ExportOptions
from override_planner.export import ez, generic, jar, lemlib
from override_planner.model.actions import Action
from override_planner.model.path import Route
from override_planner.model.profile import RobotConfig

ROBOT = RobotConfig()


def sample_route() -> Route:
    r = Route(name="test")
    r.add(23.11, 70.20)                       # start, heading 0
    r.waypoints[0].heading = 90
    i = r.add(46.66, 70.20)
    r.waypoints[i].actions.append(Action.make("intake_on"))
    i = r.add(46.66, 93.75)
    r.waypoints[i].reverse = True
    i = r.add(70.20, 117.30)
    r.set_curve(i, True)
    r.waypoints[i].speed = 50
    r.waypoints[i].actions.append(Action.make("score_goal"))
    return r


def test_lemlib():
    code = lemlib.export(sample_route(), ROBOT)
    assert "chassis.setPose(-47.09, 0, 90);" in code
    assert "chassis.moveToPoint(-23.55, 0," in code
    assert ".forwards = false" in code
    assert "chassis.moveToPose(0, 47.09," in code and ".maxSpeed = 64" in code
    assert "intakeOn();" in code and "scoreGoal();" in code and "pros::delay(600);" in code
    assert code.count("{") == code.count("}")


def test_jar():
    code = jar.export(sample_route(), ROBOT, ExportOptions(origin="bottom_left"))
    assert "chassis.set_coordinates(23.11, 70.2, 90);" in code
    assert "chassis.drive_to_point(46.66, 70.2);" in code
    assert "chassis.turn_to_point(46.66, 93.75, 180);" in code
    assert "chassis.drive_distance(-23.55);" in code
    assert "chassis.drive_to_pose(70.2, 117.3," in code
    assert "wait(600, msec);" in code


def test_ez():
    code = ez.export(sample_route(), ROBOT)
    assert "chassis.odom_xyt_set(-47.09_in, 0_in, 90_deg);" in code
    assert "chassis.pid_odom_set({{-23.55_in, 0_in}, fwd, DRIVE_SPEED}, true);" in code
    assert ", rev, TURN_SPEED);" in code
    assert "DRIVE_SPEED * 50 / 100" in code


def test_generic():
    r = sample_route()
    doc = json.loads(generic.export_json(r, ROBOT))
    assert len(doc["waypoints"]) == 4 and doc["estimated_time"] > 0
    assert doc["steps"][0]["kind"] == "set_pose"
    rows = list(csv.reader(io.StringIO(generic.export_csv(r, ROBOT))))
    assert rows[0][0] == "index" and len(rows) == 5


def test_all_formats_run_on_empty_and_single():
    for fn, _ in FORMATS.values():
        fn(Route(), ROBOT)
        r = Route()
        r.add(10, 10)
        fn(r, ROBOT)
