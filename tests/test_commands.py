import math
from pathlib import Path

import pytest

from geovision.cli import main, make_server
from geovision.commands import CommandError, apply_lines, format_ls
from geovision.export_svg import scene_to_svg
from geovision.scene import CONSTRUCTED_COLOR, GIVEN_COLOR, Scene

ROOT = Path(__file__).parents[1]


def run(path: Path, *lines: str) -> Scene:
    assert main(["--scene", str(path), "do", *lines]) == 0
    return Scene.load(path)


def test_circumcircle_command_and_colors(tmp_path):
    scene = run(
        tmp_path / "s.json",
        "point A 0 0 label=A",
        "point B 4 0 label=B",
        "point C 0 3 label=C",
        "circumcircle c A B C",
    )
    assert scene.objects["A"]["style"]["color"] == GIVEN_COLOR
    assert scene.objects["c"]["style"]["color"] == CONSTRUCTED_COLOR
    assert scene.objects["c"]["center"] == pytest.approx([2, 1.5, 0])
    assert scene.objects["c"]["radius"] == pytest.approx(2.5)
    assert "label=A" in format_ls(scene)


def test_hex_color_is_not_a_comment(tmp_path):
    scene = run(tmp_path / "s.json", "point A 0 0 color=#112233")
    assert scene.objects["A"]["style"]["color"] == "#112233"


def test_moving_a_point_rebuilds_the_circumcircle(tmp_path):
    path = tmp_path / "s.json"
    run(
        path,
        "point A 0 0",
        "point B 4 0",
        "point C 0 3",
        "circumcircle c A B C color=#ff00ff",
    )
    scene = run(path, "circumcenter O A B C", "segment rad O A", "point C 0 6")
    assert scene.objects["c"]["style"]["color"] == "#ff00ff"
    assert scene.objects["c"]["center"] == pytest.approx([2, 3, 0])
    assert scene.objects["c"]["radius"] == pytest.approx(math.sqrt(13))
    assert scene.objects["rad"]["a"] == pytest.approx(scene.objects["O"]["at"])


def test_intersect_orders_hits_by_coordinates(tmp_path):
    scene = run(
        tmp_path / "s.json",
        "point A 0 0",
        "point B 2 0",
        "point C 1 -1",
        "point D 1 2",
        "line h A B",
        "line v C D",
        "intersect P h v",
        "point O 0 0",
        "point Q 1 0",
        "circle c1 O 1",
        "circle c2 Q 1",
        "intersect low c1 c2 index=0",
        "intersect high c1 c2 index=1",
    )
    assert scene.objects["P"]["at"] == pytest.approx([1, 0, 0])
    assert scene.objects["low"]["at"][1] < 0
    assert scene.objects["high"]["at"] == pytest.approx([0.5, math.sqrt(3) / 2, 0])


def test_failed_batch_does_not_save(tmp_path):
    path = tmp_path / "s.json"
    run(path, "point A 0 0")
    before = path.read_text(encoding="utf-8")
    assert main(["--scene", str(path), "do", "point B 1 0", "point C 2 0", "circumcircle c A B C"]) == 1
    assert path.read_text(encoding="utf-8") == before


def test_delete_is_refused_while_something_uses_the_point(tmp_path):
    path = tmp_path / "s.json"
    run(path, "point A 0 0", "point B 1 0", "segment AB A B")
    assert main(["--scene", str(path), "do", "delete A"]) == 1
    assert "A" in Scene.load(path).objects
    assert main(["--scene", str(path), "do", "delete AB A"]) == 0
    assert Scene.load(path).order == ["B"]


def test_point_update_keeps_its_label(tmp_path):
    scene = run(tmp_path / "s.json", "point A 0 0 label=A", "point A 2 3")
    assert scene.objects["A"]["at"] == pytest.approx([2, 3, 0])
    assert scene.objects["A"]["style"]["label"] == "A"


def test_examples_and_svg_export(tmp_path):
    flat = tmp_path / "flat.json"
    solid = tmp_path / "solid.json"
    assert main(["--scene", str(flat), "do", str(ROOT / "examples" / "circumcircle.geo")]) == 0
    assert main(["--scene", str(solid), "do", str(ROOT / "examples" / "tetrahedron.geo")]) == 0
    scene = Scene.load(flat)
    assert scene.objects["c"]["style"]["highlight"] is True
    assert scene.objects["alpha"]["step"] == 1
    svg_path = tmp_path / "figure.svg"
    assert main(["--scene", str(flat), "export", "-o", str(svg_path)]) == 0
    svg = svg_path.read_text(encoding="utf-8")
    assert "<circle" in svg
    assert ">A<" in svg
    assert main(["--scene", str(solid), "export", "-o", str(tmp_path / "nope.svg")]) == 1
    assert Scene.load(solid).objects["t"]["type"] == "polyhedron"


def test_validate_and_help(tmp_path, capsys):
    path = tmp_path / "s.json"
    run(path, "view 3d", "point A 0 0 0", "point B 1 0 0", "point C 0 1 0", "box cube 0 0 0 1 1 1")
    assert main(["--scene", str(path), "validate"]) == 0
    assert main(["help"]) == 0
    assert "circumcircle" in capsys.readouterr().out


def test_serve_returns_the_viewer_and_scene(tmp_path):
    import json
    import threading
    import urllib.request

    path = tmp_path / "s.json"
    run(path, "point A 1 2 label=A")
    httpd = make_server(path, 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        page = urllib.request.urlopen(f"http://127.0.0.1:{port}/").read().decode("utf-8")
        script = urllib.request.urlopen(f"http://127.0.0.1:{port}/camera.js").read().decode("utf-8")
        body = json.loads(urllib.request.urlopen(f"http://127.0.0.1:{port}/scene").read().decode("utf-8"))
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert "GeoVision" in page
    assert 'id="edit-toggle"' in page
    assert "initCamera" in script
    assert body["objects"][0]["id"] == "A"


def test_clear_drops_step_names(tmp_path):
    path = tmp_path / "s.json"
    scene = run(path, "point A 0 0", "step-name 0 Given", "clear", "point B 1 0")
    assert scene.step_names == {}
    assert list(scene.objects) == ["B"]


def test_plot_and_a_user_sketch_are_readable(tmp_path):
    scene = run(
        tmp_path / "s.json",
        'plot f "x^2" domain=-2,2 by=user',
        "stroke s 0,0 1,1 1,0 by=user",
    )
    assert scene.objects["f"]["type"] == "curve"
    assert scene.objects["f"]["author"] == "user"
    assert scene.objects["f"]["style"]["color"] == "#0f766e"
    assert "by=user" not in scene.objects["f"]["style"]
    listed = format_ls(scene)
    assert "y=x^2" in listed
    assert "by=user" in listed
    assert scene.objects["s"]["author"] == "user"
    assert main(["--scene", str(tmp_path / "s.json"), "do", 'plot bad "__import__(\'os\')"']) == 1


def test_plot_requires_a_2d_view(tmp_path):
    path = tmp_path / "s.json"
    run(path, "view 3d", "point A 0 0 0")
    assert main(["--scene", str(path), "do", 'plot f "x^2"']) == 1
    assert "f" not in Scene.load(path).objects
    scene = run(path, "view 2d", 'plot f "x^2" domain=-1,1')
    assert scene.mode == "2d"
    assert scene.objects["f"]["type"] == "curve"


def test_viewer_can_add_a_shape(tmp_path):
    import json
    import threading
    import urllib.request

    path = tmp_path / "s.json"
    run(path, "view 2d")
    httpd = make_server(path, 0)
    port = httpd.server_address[1]
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        payload = json.dumps({"commands": "point u1 1 2 label=u1 by=user"}).encode("utf-8")
        request = urllib.request.Request(
            f"http://127.0.0.1:{port}/command",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        body = json.loads(urllib.request.urlopen(request).read().decode("utf-8"))
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert body["objects"][0]["id"] == "u1"
    assert body["objects"][0]["author"] == "user"
    assert Scene.load(path).objects["u1"]["at"] == pytest.approx([1, 2, 0])


def test_apply_lines_reports_the_line_number():
    scene = Scene()
    with pytest.raises(CommandError, match="line 2"):
        apply_lines(scene, ["point A 0 0", "circumcircle c A B C"])
