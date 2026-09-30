"""Line-oriented commands that upsert a scene."""

from __future__ import annotations

import re
import shlex

from geovision.geom import GeometryError
from geovision.scene import Scene

ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
STYLE_KEYS = {"color", "fill", "width", "dash", "opacity", "label", "highlight"}
LINEISH = {"line", "segment", "ray", "vector"}

NAMES = {
    "red": "#dc2626",
    "blue": "#1d4ed8",
    "green": "#15803d",
    "orange": "#c2410c",
    "black": "#1c1917",
    "white": "#ffffff",
    "gray": "#57534e",
    "grey": "#57534e",
    "yellow": "#ca8a04",
    "purple": "#7e22ce",
    "teal": "#0f766e",
}

HELP = """
GeoVision commands. One per line. # starts a comment. Options are key=value.
Ids start with a letter and contain letters, digits, and underscores.

Build a figure in one call:
  geovision do "view 2d" "point A 0 0 label=A" "point B 4 0 label=B"

Repeating a command updates that id. Moving a point rebuilds objects made from it.
Run geovision ls to see coordinates. Coordinates: x right, y forward, z up.

View
  view 2d|3d
  title <text>
  bounds <minx> <miny> <maxx> <maxy>
  camera pos=x,y,z target=x,y,z

Objects
  point <id> x y [z]
  segment <id> <a> <b>
  line <id> <a> <b>
  ray <id> <a> <b>
  vector <id> <from> <to>
  vector <id> <from> dx dy [dz]
  polyline <id> <point>...
  polygon <id> <point>...
  label <id> x y [z] <text>
  circle <id> <center> <radius>
  circle <id> <center> <point-on>
  regular <id> <n> <center> <radius> [rotate=degrees]

Constructions
  midpoint <id> <a> <b>
  perpendicular <id> <through> <line>
  parallel <id> <through> <line>
  intersect <id> <obj> <obj> [index=0]
  circumcircle <id> <a> <b> <c>
  circumcenter <id> <a> <b> <c>
  centroid <id> <point>...
  orthocenter <id> <a> <b> <c>
  bisector <id> <a> <vertex> <c>
  project <id> <point> <line-or-plane>
  angle <id> <arm> <vertex> <arm>
  right <id> <arm> <vertex> <arm>
  plane <id> <a> <b> <c>
  sphere <id> <center> <radius>
  box <id> x y z dx dy dz
  tetra <id> <a> <b> <c> <d>
  pyramid <id> <base...> <apex>
  prism <id> <base...> dx dy dz

Graphs
  plot <id> <expr> [domain=min,max] [samples=240]
  stroke <id> x,y x,y ...

expr uses x, pi, e, and sin cos tan asin acos atan sqrt abs ln log exp floor ceil.
^ means power. A graph breaks at gaps such as 1/x or tan(x).
plot is 2D only. In a 3D view, run view 2d first.
Shapes drawn in the viewer are marked by=user. Run ls to read them.

Style, on a create line or with style
  color= fill= width= dash= opacity= label= highlight= step=
  style <id> <options>
  highlight <id>...
  unhighlight <id>...
  step <n> <id>...
  step-name <n> <text>
  delete <id>...
  clear

Colors: #rgb, #rrggbb, #rrggbbaa, or red blue green orange black white
gray yellow purple teal. fill=none leaves a shape unfilled.
intersect index 0 is the hit with the smallest x, then y, then z.
A tilted circle is circumcircle of three points, not circle.
""".strip()


class CommandError(ValueError):
    pass


def strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, char in enumerate(line):
        if char == "'" and not in_double:
            in_single = not in_single
        elif char == '"' and not in_single:
            in_double = not in_double
        elif char == "#" and not in_single and not in_double and (i == 0 or line[i - 1].isspace()):
            return line[:i]
    return line


def parse_line(line: str) -> tuple[str, list[str], dict[str, str]] | None:
    raw = strip_comment(line).strip()
    if not raw:
        return None
    try:
        tokens = shlex.split(raw, posix=True)
    except ValueError as exc:
        raise CommandError(f"could not parse line: {exc}") from exc
    if not tokens:
        return None
    args: list[str] = []
    opts: dict[str, str] = {}
    for token in tokens[1:]:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]* =", token) or (
            "=" in token and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", token.split("=", 1)[0])
        ):
            key, value = token.split("=", 1)
            opts[key] = value
        else:
            args.append(token)
    return tokens[0], args, opts


def require_id(value: str) -> str:
    if not ID_RE.match(value):
        raise CommandError(f"invalid id {value!r}")
    return value


def num(token: str, what: str = "number") -> float:
    try:
        return float(token)
    except ValueError as exc:
        raise CommandError(f"expected a {what}, got {token!r}") from exc


def parse_bool(value: str) -> bool:
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise CommandError(f"expected yes or no, got {value!r}")


def parse_color(value: str) -> str:
    if value.lower() == "none":
        return "none"
    named = NAMES.get(value.lower())
    if named:
        return named
    if re.fullmatch(r"#[0-9a-fA-F]{3}", value) or re.fullmatch(r"#[0-9a-fA-F]{6}", value) or re.fullmatch(
        r"#[0-9a-fA-F]{8}", value
    ):
        return value.lower()
    raise CommandError(f"unknown color {value!r}")


def parse_vec(value: str) -> list[float]:
    parts = value.split(",")
    if len(parts) not in {2, 3}:
        raise CommandError(f"expected x,y or x,y,z, got {value!r}")
    coords = [num(part) for part in parts]
    if len(coords) == 2:
        coords.append(0.0)
    return coords


def take_style(opts: dict[str, str], extra_ok: set[str] | None = None) -> tuple[dict, int | None, dict[str, str]]:
    style: dict = {}
    step = None
    rest: dict[str, str] = {}
    allowed = extra_ok or set()
    for key, value in opts.items():
        if key == "step":
            step = int(num(value, "step"))
        elif key == "color" or key == "fill":
            style[key] = parse_color(value)
        elif key in {"width", "opacity"}:
            style[key] = num(value, key)
        elif key in {"dash", "highlight"}:
            style[key] = parse_bool(value)
        elif key == "label":
            style[key] = value
        elif key == "by":
            if value not in {"user", "agent"}:
                raise CommandError("by=user or by=agent")
            style["by"] = value
        elif key in allowed:
            rest[key] = value
        elif key in STYLE_KEYS:
            style[key] = value
        else:
            raise CommandError(f"unknown option {key}")
    return style, step, rest


def require_obj(scene: Scene, id_: str) -> dict:
    require_id(id_)
    obj = scene.objects.get(id_)
    if obj is None:
        raise CommandError(f"unknown object {id_}")
    return obj


def require_point(scene: Scene, id_: str) -> dict:
    obj = require_obj(scene, id_)
    if obj.get("type") != "point":
        raise CommandError(f"{id_} is not a point")
    return obj


def require_line(scene: Scene, id_: str) -> dict:
    obj = require_obj(scene, id_)
    if obj.get("type") not in LINEISH:
        raise CommandError(f"{id_} is not a line")
    return obj


def _points(scene: Scene, ids: list[str]) -> None:
    for id_ in ids:
        require_point(scene, id_)


def cmd_view(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if args not in (["2d"], ["3d"]):
        raise CommandError("view 2d|3d")
    scene.mode = args[0]


def cmd_title(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if not args:
        raise CommandError("title <text>")
    scene.title = " ".join(args)


def cmd_bounds(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if len(args) != 4:
        raise CommandError("bounds <minx> <miny> <maxx> <maxy>")
    scene.bounds = [num(arg) for arg in args]


def cmd_camera(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    _style, step, rest = take_style(opts, {"pos", "target"})
    if args or step is not None or _style:
        raise CommandError("camera pos=x,y,z target=x,y,z")
    if "pos" not in rest and "target" not in rest:
        raise CommandError("camera pos=x,y,z target=x,y,z")
    if "pos" in rest:
        scene.camera_position = parse_vec(rest["pos"])
    if "target" in rest:
        scene.camera_target = parse_vec(rest["target"])


def cmd_point(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) not in {3, 4}:
        raise CommandError("point <id> x y [z]")
    id_ = require_id(args[0])
    at = [num(args[1]), num(args[2]), num(args[3]) if len(args) == 4 else 0.0]
    scene.put(id_, type_name="point", geom={"type": "point", "at": at}, style=style, step=step)


def cmd_two_points(kind: str, usage: str):
    def handler(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
        style, step, _rest = take_style(opts)
        if len(args) != 3:
            raise CommandError(usage)
        id_ = require_id(args[0])
        _points(scene, args[1:])
        scene.put(
            id_,
            type_name=kind,
            recipe={"op": kind, "args": args[1:]},
            style=style,
            step=step,
        )

    return handler


def cmd_vector(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 3:
        raise CommandError("vector <id> <from> <to>  or  vector <id> <from> dx dy [dz]")
    id_ = require_id(args[0])
    require_point(scene, args[1])
    rest = args[2:]
    if len(rest) == 1 and ID_RE.match(rest[0]):
        require_point(scene, rest[0])
        recipe = {"op": "vector", "args": [args[1], rest[0]]}
    elif len(rest) in {2, 3} and all(_is_number(token) for token in rest):
        delta = [num(rest[0]), num(rest[1]), num(rest[2]) if len(rest) == 3 else 0.0]
        recipe = {"op": "vector", "args": [args[1]], "delta": delta}
    else:
        raise CommandError("vector <id> <from> <to>  or  vector <id> <from> dx dy [dz]")
    scene.put(id_, type_name="vector", recipe=recipe, style=style, step=step)


def cmd_chain(kind: str, minimum: int, usage: str):
    def handler(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
        style, step, _rest = take_style(opts)
        if len(args) < minimum + 1:
            raise CommandError(usage)
        id_ = require_id(args[0])
        _points(scene, args[1:])
        scene.put(
            id_,
            type_name=kind,
            recipe={"op": kind, "args": args[1:]},
            style=style,
            step=step,
        )

    return handler


def cmd_label(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 4:
        raise CommandError('label <id> x y [z] <text>')
    id_ = require_id(args[0])
    x, y = num(args[1]), num(args[2])
    if len(args) >= 5 and _is_number(args[3]):
        z = num(args[3])
        text = " ".join(args[4:])
    else:
        z = 0.0
        text = " ".join(args[3:])
    if not text:
        raise CommandError('label <id> x y [z] <text>')
    style.setdefault("label", text)
    scene.put(
        id_,
        type_name="label",
        geom={"type": "label", "at": [x, y, z], "text": text},
        style=style,
        step=step,
    )


def cmd_circle(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 3:
        raise CommandError("circle <id> <center> <radius>  or  circle <id> <center> <point-on>")
    id_ = require_id(args[0])
    require_point(scene, args[1])
    if _is_number(args[2]):
        recipe = {"op": "circle", "args": [args[1]], "radius": num(args[2])}
    else:
        require_point(scene, args[2])
        recipe = {"op": "circle", "args": [args[1], args[2]]}
    scene.put(id_, type_name="circle", recipe=recipe, style=style, step=step)


def cmd_regular(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, rest = take_style(opts, {"rotate"})
    if len(args) != 4:
        raise CommandError("regular <id> <n> <center> <radius>")
    id_ = require_id(args[0])
    require_point(scene, args[2])
    recipe = {
        "op": "regular",
        "args": [args[2]],
        "n": int(num(args[1], "side count")),
        "radius": num(args[3], "radius"),
        "rotate": num(rest["rotate"]) if "rotate" in rest else 0.0,
    }
    scene.put(id_, type_name="polygon", recipe=recipe, style=style, step=step)


def cmd_midpoint(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    _binary_point(scene, args, opts, "midpoint", "midpoint <id> <a> <b>")


def _binary_point(scene: Scene, args: list[str], opts: dict[str, str], op: str, usage: str) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 3:
        raise CommandError(usage)
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="point", recipe={"op": op, "args": args[1:]}, style=style, step=step)


def cmd_line_through(op: str, usage: str):
    def handler(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
        style, step, _rest = take_style(opts)
        if len(args) != 3:
            raise CommandError(usage)
        id_ = require_id(args[0])
        require_point(scene, args[1])
        require_line(scene, args[2])
        scene.put(
            id_,
            type_name="line",
            recipe={"op": op, "args": [args[1], args[2]]},
            style=style,
            step=step,
        )

    return handler


def cmd_intersect(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, rest = take_style(opts, {"index"})
    if len(args) != 3:
        raise CommandError("intersect <id> <obj> <obj>")
    id_ = require_id(args[0])
    for ref in args[1:]:
        obj = require_obj(scene, ref)
        if obj.get("type") not in LINEISH | {"circle"}:
            raise CommandError(f"{ref} cannot be intersected")
    recipe = {"op": "intersect", "args": args[1:], "index": int(num(rest.get("index", "0"), "index"))}
    scene.put(id_, type_name="point", recipe=recipe, style=style, step=step)


def cmd_triple_point(op: str, usage: str):
    def handler(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
        style, step, _rest = take_style(opts)
        if len(args) != 4:
            raise CommandError(usage)
        id_ = require_id(args[0])
        _points(scene, args[1:])
        scene.put(id_, type_name="point", recipe={"op": op, "args": args[1:]}, style=style, step=step)

    return handler


def cmd_circumcircle(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 4:
        raise CommandError("circumcircle <id> <a> <b> <c>")
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="circle", recipe={"op": "circumcircle", "args": args[1:]}, style=style, step=step)


def cmd_centroid(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 3:
        raise CommandError("centroid <id> <point>...")
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="point", recipe={"op": "centroid", "args": args[1:]}, style=style, step=step)


def cmd_bisector(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 4:
        raise CommandError("bisector <id> <a> <vertex> <c>")
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="ray", recipe={"op": "bisector", "args": args[1:]}, style=style, step=step)


def cmd_project(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 3:
        raise CommandError("project <id> <point> <line-or-plane>")
    id_ = require_id(args[0])
    require_point(scene, args[1])
    target = require_obj(scene, args[2])
    if target.get("type") not in LINEISH | {"plane"}:
        raise CommandError(f"{args[2]} is not a line or a plane")
    scene.put(
        id_,
        type_name="point",
        recipe={"op": "project", "args": [args[1], args[2]]},
        style=style,
        step=step,
    )


def cmd_mark(op: str, type_name: str, usage: str):
    def handler(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
        style, step, _rest = take_style(opts)
        if len(args) != 4:
            raise CommandError(usage)
        id_ = require_id(args[0])
        _points(scene, args[1:])
        scene.put(id_, type_name=type_name, recipe={"op": op, "args": args[1:]}, style=style, step=step)

    return handler


def cmd_plane(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 4:
        raise CommandError("plane <id> <a> <b> <c>")
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="plane", recipe={"op": "plane", "args": args[1:]}, style=style, step=step)


def cmd_sphere(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 3:
        raise CommandError("sphere <id> <center> <radius>")
    id_ = require_id(args[0])
    require_point(scene, args[1])
    recipe = {"op": "sphere", "args": [args[1]], "radius": num(args[2], "radius")}
    scene.put(id_, type_name="sphere", recipe=recipe, style=style, step=step)


def cmd_box(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 7:
        raise CommandError("box <id> x y z dx dy dz")
    id_ = require_id(args[0])
    origin = [num(args[1]), num(args[2]), num(args[3])]
    size = [num(args[4]), num(args[5]), num(args[6])]
    scene.put(
        id_,
        type_name="polyhedron",
        recipe={"op": "box", "args": [], "origin": origin, "size": size},
        style=style,
        step=step,
    )


def cmd_tetra(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 5:
        raise CommandError("tetra <id> <a> <b> <c> <d>")
    id_ = require_id(args[0])
    _points(scene, args[1:])
    scene.put(id_, type_name="polyhedron", recipe={"op": "tetra", "args": args[1:]}, style=style, step=step)


def cmd_pyramid(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 5:
        raise CommandError("pyramid <id> <base...> <apex>")
    id_ = require_id(args[0])
    refs = args[1:]
    _points(scene, refs)
    scene.put(id_, type_name="polyhedron", recipe={"op": "pyramid", "args": refs}, style=style, step=step)


def cmd_prism(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 7:
        raise CommandError("prism <id> <base...> dx dy dz")
    id_ = require_id(args[0])
    delta = [num(args[-3]), num(args[-2]), num(args[-1])]
    base = args[1:-3]
    if len(base) < 3:
        raise CommandError("prism needs at least 3 base points")
    _points(scene, base)
    scene.put(
        id_,
        type_name="polyhedron",
        recipe={"op": "prism", "args": base, "delta": delta},
        style=style,
        step=step,
    )


def cmd_plot(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    if scene.mode == "3d":
        raise CommandError("plot is only available in 2D; run view 2d")
    style, step, rest = take_style(opts, {"domain", "samples"})
    if len(args) < 2:
        raise CommandError('plot <id> <expr> [domain=min,max]')
    id_ = require_id(args[0])
    expr = " ".join(args[1:]).strip()
    if "domain" in rest:
        parts = rest["domain"].split(",")
        if len(parts) != 2:
            raise CommandError("domain=min,max")
        domain = [num(parts[0], "domain"), num(parts[1], "domain")]
    else:
        domain = [-5.0, 5.0]
    if domain[1] <= domain[0]:
        raise CommandError("domain max must be greater than min")
    samples = int(num(rest["samples"], "samples")) if "samples" in rest else 240
    if samples < 2:
        raise CommandError("samples must be at least 2")
    recipe = {"op": "plot", "args": [], "expr": expr, "domain": domain, "samples": samples}
    scene.put(id_, type_name="curve", recipe=recipe, style=style, step=step)


def cmd_stroke(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) < 3:
        raise CommandError("stroke <id> x,y x,y ...")
    id_ = require_id(args[0])
    points = [parse_vec(token) for token in args[1:]]
    scene.put(
        id_,
        type_name="polyline",
        geom={"type": "polyline", "points": points},
        style=style,
        step=step,
    )


def cmd_style(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    style, step, _rest = take_style(opts)
    if len(args) != 1 or (not style and step is None):
        raise CommandError("style <id> color= fill= width= dash= opacity= label= highlight= step=")
    obj = require_obj(scene, args[0])
    obj.setdefault("style", {}).update(style)
    if step is not None:
        obj["step"] = step


def cmd_highlight(scene: Scene, args: list[str], opts: dict[str, str], *, on: bool) -> None:
    take_style(opts)
    if not args:
        raise CommandError("highlight <id>..." if on else "unhighlight <id>...")
    for id_ in args:
        obj = require_obj(scene, id_)
        obj.setdefault("style", {})["highlight"] = on


def cmd_step(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if len(args) < 2:
        raise CommandError("step <n> <id>...")
    step = int(num(args[0], "step"))
    for id_ in args[1:]:
        require_obj(scene, id_)["step"] = step


def cmd_step_name(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if len(args) < 2:
        raise CommandError("step-name <n> <text>")
    scene.step_names[int(num(args[0], "step"))] = " ".join(args[1:])


def cmd_delete(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if not args:
        raise CommandError("delete <id>...")
    ids = {require_id(id_) for id_ in args}
    for id_ in ids:
        if id_ not in scene.objects:
            raise CommandError(f"unknown object {id_}")
    used = scene.users_of(ids)
    if used:
        arg, owner = used[0]
        raise CommandError(f"cannot delete {arg}; still used by {owner}")
    for id_ in args:
        scene.remove(id_)


def cmd_clear(scene: Scene, args: list[str], opts: dict[str, str]) -> None:
    take_style(opts)
    if args:
        raise CommandError("clear takes no arguments")
    scene.clear_objects()
    scene.step_names.clear()


def _is_number(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


HANDLERS = {
    "view": cmd_view,
    "title": cmd_title,
    "bounds": cmd_bounds,
    "camera": cmd_camera,
    "point": cmd_point,
    "segment": cmd_two_points("segment", "segment <id> <a> <b>"),
    "line": cmd_two_points("line", "line <id> <a> <b>"),
    "ray": cmd_two_points("ray", "ray <id> <a> <b>"),
    "vector": cmd_vector,
    "polyline": cmd_chain("polyline", 2, "polyline <id> <point>..."),
    "polygon": cmd_chain("polygon", 3, "polygon <id> <point>..."),
    "label": cmd_label,
    "circle": cmd_circle,
    "regular": cmd_regular,
    "midpoint": cmd_midpoint,
    "perpendicular": cmd_line_through("perpendicular", "perpendicular <id> <through> <line>"),
    "parallel": cmd_line_through("parallel", "parallel <id> <through> <line>"),
    "intersect": cmd_intersect,
    "circumcircle": cmd_circumcircle,
    "circumcenter": cmd_triple_point("circumcenter", "circumcenter <id> <a> <b> <c>"),
    "centroid": cmd_centroid,
    "orthocenter": cmd_triple_point("orthocenter", "orthocenter <id> <a> <b> <c>"),
    "bisector": cmd_bisector,
    "project": cmd_project,
    "angle": cmd_mark("angle", "angle", "angle <id> <arm> <vertex> <arm>"),
    "right": cmd_mark("right", "right_angle", "right <id> <arm> <vertex> <arm>"),
    "plane": cmd_plane,
    "sphere": cmd_sphere,
    "box": cmd_box,
    "tetra": cmd_tetra,
    "pyramid": cmd_pyramid,
    "prism": cmd_prism,
    "plot": cmd_plot,
    "stroke": cmd_stroke,
    "style": cmd_style,
    "step": cmd_step,
    "step-name": cmd_step_name,
    "delete": cmd_delete,
    "clear": cmd_clear,
}


def apply_line(scene: Scene, line: str) -> None:
    parsed = parse_line(line)
    if parsed is None:
        return
    cmd, args, opts = parsed
    if cmd == "highlight":
        cmd_highlight(scene, args, opts, on=True)
        return
    if cmd == "unhighlight":
        cmd_highlight(scene, args, opts, on=False)
        return
    handler = HANDLERS.get(cmd)
    if handler is None:
        raise CommandError(f"unknown command {cmd!r}; run geovision help")
    handler(scene, args, opts)


def apply_lines(scene: Scene, lines: list[str]) -> None:
    for lineno, line in enumerate(lines, 1):
        try:
            apply_line(scene, line)
        except (CommandError, GeometryError) as exc:
            detail = line.strip() or "(blank)"
            raise CommandError(f"line {lineno}: {exc}\n  {detail}") from exc


def fmt_num(value: float) -> str:
    number = float(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.6g}"


def fmt_point(point) -> str:
    if len(point) < 3 or abs(float(point[2])) < 1e-9:
        return f"({fmt_num(point[0])}, {fmt_num(point[1])})"
    return f"({fmt_num(point[0])}, {fmt_num(point[1])}, {fmt_num(point[2])})"


def recipe_brief(recipe: dict) -> str:
    parts = [str(recipe.get("op"))]
    parts.extend(str(arg) for arg in recipe.get("args") or [])
    for key in ("radius", "index", "n", "rotate", "delta", "origin", "size", "expr", "samples"):
        if key in recipe and not (key == "index" and recipe[key] == 0 and recipe.get("op") == "intersect"):
            if key == "samples" and recipe.get("op") == "plot" and recipe[key] == 240:
                continue
            parts.append(f"{key}={recipe[key]}")
    if recipe.get("domain"):
        parts.append("domain=" + ",".join(fmt_num(value) for value in recipe["domain"]))
    return "from " + " ".join(parts)


def summarize(obj: dict) -> str:
    kind = obj.get("type")
    bits = [obj["id"], kind]
    if kind == "point":
        bits.append(fmt_point(obj["at"]))
    elif kind == "circle":
        bits.append(f"center={fmt_point(obj['center'])} r={fmt_num(obj['radius'])}")
    elif kind in LINEISH:
        bits.append(f"{fmt_point(obj['a'])} -> {fmt_point(obj['b'])}")
    elif kind == "sphere":
        bits.append(f"center={fmt_point(obj['center'])} r={fmt_num(obj['radius'])}")
    elif kind == "curve":
        expr = obj.get("expr") or (obj.get("from") or {}).get("expr")
        if expr:
            bits.append(f"y={expr}")
    elif kind == "polyline" and obj.get("author") == "user":
        pts = obj.get("points") or []
        bits.append(f"{len(pts)} pts")
        if pts:
            step = max(1, len(pts) // 8)
            sample = pts[::step][:8]
            if sample[-1] != pts[-1]:
                sample.append(pts[-1])
            bits.append("through " + " ".join(fmt_point(point) for point in sample))
    elif kind in {"polygon", "polyline", "angle", "right_angle"}:
        bits.append(f"{len(obj.get('points') or [])} pts")
    elif kind == "polyhedron":
        bits.append(f"{len(obj.get('vertices') or [])} vertices")
    elif kind == "label":
        bits.append(fmt_point(obj["at"]))
    label = (obj.get("style") or {}).get("label")
    if label:
        bits.append(f"label={label}")
    if (obj.get("style") or {}).get("highlight"):
        bits.append("highlight")
    if obj.get("step"):
        bits.append(f"step={obj['step']}")
    if obj.get("from"):
        bits.append(recipe_brief(obj["from"]))
    if obj.get("author") == "user":
        bits.append("by=user")
    return " ".join(bits)


def format_ls(scene: Scene) -> str:
    lines = []
    if scene.title:
        lines.append(f"title {scene.title}")
    lines.append(f"view {scene.mode}")
    if scene.mode == "3d":
        pos = ",".join(fmt_num(v) for v in scene.camera_position)
        target = ",".join(fmt_num(v) for v in scene.camera_target)
        lines.append(f"camera pos={pos} target={target}")
    if not scene.order:
        lines.append("(empty)")
    else:
        lines.extend(summarize(scene.objects[id_]) for id_ in scene.order)
    return "\n".join(lines)


def format_get(scene: Scene, id_: str) -> str:
    obj = scene.objects.get(id_)
    if obj is None:
        raise CommandError(f"unknown object {id_}")
    lines = [summarize(obj)]
    style = obj.get("style") or {}
    shown = {key: value for key, value in style.items() if key != "label"}
    if shown:
        bits = []
        for key, value in shown.items():
            bits.append(f"{key}={value}")
        lines.append("style " + " ".join(bits))
    return "\n".join(lines)
