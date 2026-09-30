import json
import urllib.request

import pytest

from geovision.commands import CommandError
from geovision.mcp_server import draw_figure, look_scene, scene_path, stop_owned_viewer, viewer_url


@pytest.fixture(autouse=True)
def close_viewer():
    yield
    stop_owned_viewer()


def test_scene_path_follows_the_environment(monkeypatch, tmp_path):
    target = tmp_path / "figure.json"
    monkeypatch.setenv("GEOVISION_SCENE", str(target))
    assert scene_path() == target


def test_draw_writes_the_scene_and_lists_it(monkeypatch, tmp_path):
    target = tmp_path / "figure.json"
    monkeypatch.setenv("GEOVISION_SCENE", str(target))
    message, png = draw_figure(
        "clear\nview 2d\npoint A 0 0 label=A\npoint B 4 0 label=B\nsegment AB A B",
        capture=False,
    )
    assert png is None
    assert "A point" in message
    assert "Viewer http://127.0.0.1:" in message
    saved = json.loads(target.read_text(encoding="utf-8"))
    assert [obj["id"] for obj in saved["objects"]] == ["A", "B", "AB"]
    url = next(line.removeprefix("Viewer ") for line in message.splitlines() if line.startswith("Viewer "))
    shown = json.loads(urllib.request.urlopen(url + "/scene", timeout=2).read().decode("utf-8"))
    assert [obj["id"] for obj in shown["objects"]] == ["A", "B", "AB"]
    assert look_scene().splitlines()[0] == str(target)


def test_a_bad_command_does_not_save(monkeypatch, tmp_path):
    target = tmp_path / "figure.json"
    monkeypatch.setenv("GEOVISION_SCENE", str(target))
    draw_figure("point A 0 0 label=A", capture=False)
    before = target.read_text(encoding="utf-8")
    with pytest.raises(CommandError, match="line 2"):
        draw_figure("point B 1 0\ncircumcircle c A B C", capture=False)
    assert target.read_text(encoding="utf-8") == before


def test_an_open_viewer_of_the_same_file_is_reused(monkeypatch, tmp_path):
    target = tmp_path / "figure.json"
    monkeypatch.setenv("GEOVISION_SCENE", str(target))
    draw_figure("point A 1 2 label=A", capture=False)
    first = viewer_url(target)
    assert viewer_url(target) == first
