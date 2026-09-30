"""Scene file: resolved geometry, style, steps, and construction recipes."""

from __future__ import annotations

import json
from pathlib import Path

from geovision.geom import GeometryError, build

GIVEN_COLOR = "#1d4ed8"
CONSTRUCTED_COLOR = "#c2410c"
MARK_COLOR = "#44403c"
GRAPH_COLOR = "#0f766e"
BACKGROUND = "#f4f0e6"

CONSTRUCTION_OPS = {
    "midpoint",
    "perpendicular",
    "parallel",
    "intersect",
    "circumcircle",
    "circumcenter",
    "centroid",
    "orthocenter",
    "bisector",
    "project",
    "regular",
    "circle",
}
MARK_OPS = {"angle", "right"}
GRAPH_OPS = {"plot"}
SURFACE_TYPES = {"polygon", "polyhedron", "plane", "sphere"}

REQUIRED = {
    "point": ["at"],
    "segment": ["a", "b"],
    "line": ["a", "b"],
    "ray": ["a", "b"],
    "vector": ["a", "b"],
    "polyline": ["points"],
    "polygon": ["points"],
    "circle": ["center", "radius", "normal", "samples"],
    "label": ["at", "text"],
    "angle": ["points"],
    "right_angle": ["points"],
    "sphere": ["center", "radius"],
    "plane": ["corners", "normal"],
    "polyhedron": ["vertices", "faces"],
    "curve": ["paths"],
}


def with_alpha(color: str, alpha: float) -> str:
    h = color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) >= 6:
        h = h[:6]
    else:
        h = "334155"
    return f"#{h}{int(max(0.0, min(1.0, alpha)) * 255):02x}"


def default_color(op: str | None, type_name: str) -> str:
    if op in MARK_OPS or type_name in {"angle", "right_angle"}:
        return MARK_COLOR
    if op in GRAPH_OPS or type_name == "curve":
        return GRAPH_COLOR
    if op in CONSTRUCTION_OPS:
        return CONSTRUCTED_COLOR
    return GIVEN_COLOR


def fill_alpha(type_name: str) -> float:
    if type_name == "polygon":
        return 0.12
    if type_name == "plane":
        return 0.18
    return 0.35


def _compose(old: dict, geom: dict) -> dict:
    out = {"id": old["id"], "type": geom["type"]}
    for key, value in geom.items():
        if key != "type":
            out[key] = value
    out["step"] = int(old.get("step", 0))
    out["style"] = old.setdefault("style", {})
    if old.get("from") is not None:
        out["from"] = old["from"]
    if old.get("author"):
        out["author"] = old["author"]
    return out


class Scene:
    def __init__(self) -> None:
        self.title = ""
        self.mode = "2d"
        self.bounds: list[float] | None = None
        self.camera_position = [6.0, -8.0, 5.0]
        self.camera_target = [0.0, 0.0, 0.0]
        self.grid = True
        self.axes = True
        self.background = BACKGROUND
        self.step_names: dict[int, str] = {}
        self.objects: dict[str, dict] = {}
        self.order: list[str] = []

    @classmethod
    def load(cls, path: str | Path) -> Scene:
        file = Path(path)
        if not file.exists():
            return cls()
        return cls.from_dict(json.loads(file.read_text(encoding="utf-8")))

    @classmethod
    def from_dict(cls, data: dict) -> Scene:
        scene = cls()
        scene.title = str(data.get("title") or "")
        view = data.get("view") or {}
        mode = view.get("mode") or "2d"
        if mode not in {"2d", "3d"}:
            raise GeometryError(f"unknown view mode {mode}")
        scene.mode = mode
        scene.bounds = view.get("bounds")
        camera = view.get("camera") or {}
        if camera.get("position"):
            scene.camera_position = [float(v) for v in camera["position"]]
        if camera.get("target"):
            scene.camera_target = [float(v) for v in camera["target"]]
        scene.grid = bool(view.get("grid", True))
        scene.axes = bool(view.get("axes", True))
        scene.background = view.get("background") or BACKGROUND
        for step in data.get("steps") or []:
            scene.step_names[int(step["index"])] = str(step.get("name") or "")
        for obj in data.get("objects") or []:
            id_ = obj["id"]
            if id_ in scene.objects:
                raise GeometryError(f"duplicate id {id_}")
            scene.objects[id_] = obj
            scene.order.append(id_)
        return scene

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "view": {
                "mode": self.mode,
                "bounds": self.bounds,
                "camera": {
                    "position": self.camera_position,
                    "target": self.camera_target,
                },
                "grid": self.grid,
                "axes": self.axes,
                "background": self.background,
            },
            "steps": [
                {"index": index, "name": name}
                for index, name in sorted(self.step_names.items())
            ],
            "objects": [self.objects[id_] for id_ in self.order],
        }

    def save(self, path: str | Path) -> None:
        file = Path(path)
        file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.to_dict(), indent=2) + "\n"
        temporary = file.with_suffix(file.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(file)

    def put(
        self,
        id_: str,
        *,
        type_name: str,
        recipe: dict | None = None,
        geom: dict | None = None,
        style: dict | None = None,
        step: int | None = None,
    ) -> None:
        new = id_ not in self.objects
        if new:
            self.order.append(id_)
            self.objects[id_] = {"id": id_, "style": {}, "step": 0}
        shell = self.objects[id_]
        if recipe is None:
            shell.pop("from", None)
        else:
            shell["from"] = recipe
        if new:
            op = recipe["op"] if recipe else None
            shell["style"]["color"] = default_color(op, type_name)
            if type_name in SURFACE_TYPES:
                shell["style"]["fill"] = with_alpha(shell["style"]["color"], fill_alpha(type_name))
        if style:
            author = style.pop("by", None)
            if author:
                shell["author"] = author
            if style:
                shell.setdefault("style", {}).update(style)
        if step is not None:
            shell["step"] = step
        if geom is not None:
            self.objects[id_] = _compose(shell, geom)
        self.rebuild()

    def remove(self, id_: str) -> None:
        del self.objects[id_]
        self.order.remove(id_)

    def clear_objects(self) -> None:
        self.objects.clear()
        self.order.clear()

    def users_of(self, ids: set[str]) -> list[tuple[str, str]]:
        found = []
        for obj in self.objects.values():
            if obj["id"] in ids:
                continue
            recipe = obj.get("from") or {}
            for arg in recipe.get("args") or []:
                if arg in ids:
                    found.append((arg, obj["id"]))
        return found

    def rebuild(self) -> None:
        nodes = [id_ for id_ in self.order if self.objects[id_].get("from")]
        incoming: dict[str, set[str]] = {}
        for id_ in nodes:
            args = list(self.objects[id_]["from"].get("args") or [])
            missing = [arg for arg in args if arg not in self.objects]
            if missing:
                raise GeometryError(f"{id_} depends on missing {', '.join(missing)}")
            incoming[id_] = {
                arg for arg in args if arg in self.objects and self.objects[arg].get("from")
            }
        ready = [id_ for id_ in nodes if not incoming[id_]]
        ordered: list[str] = []
        while ready:
            id_ = ready.pop(0)
            ordered.append(id_)
            for other in nodes:
                if id_ in incoming[other]:
                    incoming[other].remove(id_)
                    if not incoming[other] and other not in ordered and other not in ready:
                        ready.append(other)
        if len(ordered) != len(nodes):
            raise GeometryError("cycle in constructions")
        for id_ in ordered:
            old = self.objects[id_]
            geom = build(old["from"], self.objects.get)
            self.objects[id_] = _compose(old, geom)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.mode not in {"2d", "3d"}:
            errors.append(f"unknown view mode {self.mode}")
        try:
            self.rebuild()
        except GeometryError as exc:
            errors.append(str(exc))
        for id_ in self.order:
            obj = self.objects[id_]
            if obj.get("id") != id_:
                errors.append(f"{id_} has a mismatched id")
            kind = obj.get("type")
            if kind not in REQUIRED:
                errors.append(f"{id_} has unknown type {kind}")
                continue
            for field in REQUIRED[kind]:
                if field not in obj:
                    errors.append(f"{id_} is missing {field}")
            if kind == "polyhedron":
                count = len(obj.get("vertices") or [])
                for face in obj.get("faces") or []:
                    if any(index < 0 or index >= count for index in face):
                        errors.append(f"{id_} has a face index out of range")
                        break
            recipe = obj.get("from")
            if recipe:
                for arg in recipe.get("args") or []:
                    if arg not in self.objects:
                        errors.append(f"{id_} depends on missing {arg}")
        return errors
