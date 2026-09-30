"""Render a 2D scene to a standalone SVG."""

from __future__ import annotations

import math

from geovision.geom import (
    GeometryError,
    add,
    as_vec,
    clip_segment,
    grid_step,
    length,
    midpoint,
    mul,
    sub,
)
from geovision.scene import Scene

WIDTH = 960
HEIGHT = 720


def scene_bounds(scene: Scene) -> tuple[float, float, float, float]:
    if scene.bounds and len(scene.bounds) == 4:
        minx, miny, maxx, maxy = (float(v) for v in scene.bounds)
        if maxx > minx and maxy > miny:
            return minx, miny, maxx, maxy
    points: list[tuple[float, float, float]] = []
    for obj in scene.objects.values():
        points.extend(_object_points(obj))
    if not points:
        return -5.0, -5.0, 5.0, 5.0
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    padx = (maxx - minx) * 0.2 + 1.0
    pady = (maxy - miny) * 0.2 + 1.0
    return minx - padx, miny - pady, maxx + padx, maxy + pady


def scene_to_svg(scene: Scene) -> str:
    if scene.mode != "2d":
        raise GeometryError("export supports 2D scenes; this scene is 3d")
    minx, miny, maxx, maxy = scene_bounds(scene)
    spanx = max(maxx - minx, 1e-6)
    spany = max(maxy - miny, 1e-6)
    pixels_per_unit = min(WIDTH / spanx, HEIGHT / spany)
    unit = 1.0 / pixels_per_unit
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" '
        f'viewBox="{_n(minx)} {_n(-maxy)} {_n(spanx)} {_n(spany)}">',
        f'<rect x="{_n(minx)}" y="{_n(-maxy)}" width="{_n(spanx)}" height="{_n(spany)}" fill="{_xml(scene.background)}"/>',
    ]
    if scene.grid:
        parts.extend(_grid(minx, miny, maxx, maxy, unit))
    if scene.axes:
        parts.extend(_axes(minx, miny, maxx, maxy, unit))
    objects = [scene.objects[id_] for id_ in scene.order]
    objects.sort(key=lambda obj: (1 if (obj.get("style") or {}).get("highlight") else 0, _layer(obj)))
    bounds = (minx, miny, maxx, maxy)
    for obj in objects:
        parts.extend(_draw(obj, bounds, unit))
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _object_points(obj: dict) -> list[tuple[float, float, float]]:
    kind = obj.get("type")
    if kind in {"point", "label"}:
        return [as_vec(obj["at"])]
    if kind in {"segment", "line", "ray", "vector"}:
        return [as_vec(obj["a"]), as_vec(obj["b"])]
    if kind == "circle":
        return [as_vec(point) for point in obj.get("samples") or []]
    if kind == "sphere":
        center = as_vec(obj["center"])
        radius = float(obj["radius"])
        return [
            (center[0] - radius, center[1] - radius, center[2]),
            (center[0] + radius, center[1] + radius, center[2]),
        ]
    if kind in {"polygon", "polyline", "angle", "right_angle"}:
        return [as_vec(point) for point in obj.get("points") or []]
    if kind == "curve":
        return [as_vec(point) for path in obj.get("paths") or [] for point in path]
    if kind == "plane":
        return [as_vec(point) for point in obj.get("corners") or []]
    if kind == "polyhedron":
        return [as_vec(point) for point in obj.get("vertices") or []]
    return []


def _layer(obj: dict) -> int:
    kind = obj.get("type")
    if kind in {"plane", "polyhedron", "sphere", "polygon"}:
        return 0
    if kind == "point":
        return 3
    if kind == "label":
        return 4
    return 1


def _grid(minx, miny, maxx, maxy, unit) -> list[str]:
    step = grid_step(max(maxx - minx, maxy - miny))
    lines = []
    x = math.ceil(minx / step) * step
    while x <= maxx + step * 0.01:
        lines.append(_segment((x, miny, 0), (x, maxy, 0), "#e4dcd0", 1, unit))
        x += step
    y = math.ceil(miny / step) * step
    while y <= maxy + step * 0.01:
        lines.append(_segment((minx, y, 0), (maxx, y, 0), "#e4dcd0", 1, unit))
        y += step
    return lines


def _axes(minx, miny, maxx, maxy, unit) -> list[str]:
    lines = []
    if miny <= 0 <= maxy:
        lines.append(_segment((minx, 0, 0), (maxx, 0, 0), "#a8a29e", 1.25, unit))
    if minx <= 0 <= maxx:
        lines.append(_segment((0, miny, 0), (0, maxy, 0), "#a8a29e", 1.25, unit))
    return lines


def _draw(obj: dict, bounds, unit: float) -> list[str]:
    kind = obj.get("type")
    style = obj.get("style") or {}
    color = "#d97706" if style.get("highlight") else style.get("color") or "#1d4ed8"
    width = float(style.get("width") or 2)
    if style.get("highlight"):
        width += 1.5
    dash = bool(style.get("dash"))
    opacity = style.get("opacity")
    items: list[str] = []
    if kind == "point":
        items.append(_dot(obj["at"], color, 6.5 if style.get("highlight") else 4.5, unit, opacity))
    elif kind in {"segment", "line", "ray"}:
        clipped = _clip_linear(kind, obj["a"], obj["b"], bounds)
        if clipped:
            items.append(_segment(clipped[0], clipped[1], color, width, unit, dash, opacity))
    elif kind == "vector":
        clipped = _clip_linear("segment", obj["a"], obj["b"], bounds)
        if clipped:
            items.append(_segment(clipped[0], clipped[1], color, width, unit, dash, opacity))
        if obj.get("head"):
            items.append(_polyline(obj["head"], color, width, unit, dash, opacity, close=False))
    elif kind in {"polyline", "angle", "right_angle"}:
        items.append(_polyline(obj.get("points") or [], color, width, unit, dash, opacity, close=False))
    elif kind == "curve":
        for path in obj.get("paths") or []:
            items.append(_polyline(path, color, width, unit, dash, opacity, close=False))
    elif kind == "polygon":
        items.append(
            _polyline(obj.get("points") or [], color, width, unit, dash, opacity, close=True, fill=style.get("fill"))
        )
    elif kind == "circle":
        items.extend(_circle(obj, color, width, unit, dash, opacity, style.get("fill")))
    elif kind == "sphere":
        items.append(
            _circle_xy(obj["center"], float(obj["radius"]), color, width, unit, dash, opacity, style.get("fill"))
        )
    elif kind == "plane":
        items.append(
            _polyline(obj.get("corners") or [], color, width, unit, dash, opacity, close=True, fill=style.get("fill"))
        )
    elif kind == "polyhedron":
        items.extend(_polyhedron_edges(obj, color, width, unit, dash, opacity))
    label = style.get("label") or (obj.get("text") if kind == "label" else None)
    if label:
        anchor = _label_anchor(obj)
        if anchor is not None:
            items.append(_text(anchor, str(label), unit, kind == "point"))
    return [item for item in items if item]


def _clip_linear(kind: str, a, b, bounds):
    start, end = as_vec(a), as_vec(b)
    span = math.hypot(bounds[2] - bounds[0], bounds[3] - bounds[1])
    if kind == "line":
        direction = sub(end, start)
        if length(direction) < 1e-12:
            return None
        direction = mul(direction, (span * 4) / length(direction))
        mid = midpoint(start, end)
        start, end = sub(mid, direction), add(mid, direction)
    elif kind == "ray":
        direction = sub(end, start)
        if length(direction) < 1e-12:
            return None
        end = add(start, mul(direction, (span * 4) / length(direction)))
    return clip_segment(start, end, bounds)


def _circle(obj, color, width, unit, dash, opacity, fill) -> list[str]:
    normal = obj.get("normal") or [0, 0, 1]
    if abs(normal[0]) < 1e-6 and abs(normal[1]) < 1e-6:
        return [_circle_xy(obj["center"], float(obj["radius"]), color, width, unit, dash, opacity, fill)]
    return [_polyline(obj.get("samples") or [], color, width, unit, dash, opacity, close=True, fill=fill)]


def _polyhedron_edges(obj, color, width, unit, dash, opacity) -> list[str]:
    verts = obj.get("vertices") or []
    seen = set()
    items = []
    for face in obj.get("faces") or []:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            key = (a, b) if a < b else (b, a)
            if key in seen or a >= len(verts) or b >= len(verts):
                continue
            seen.add(key)
            items.append(_segment(verts[a], verts[b], color, width, unit, dash, opacity))
    return items


def _label_anchor(obj):
    if obj.get("labelAt"):
        return obj["labelAt"]
    paths = obj.get("paths") or []
    if paths and paths[0]:
        return paths[0][len(paths[0]) // 2]
    if obj.get("at"):
        return obj["at"]
    if obj.get("center"):
        return obj["center"]
    points = obj.get("points") or obj.get("corners") or obj.get("vertices")
    if points:
        count = len(points)
        return [sum(point[i] for point in points) / count for i in range(3)]
    if obj.get("a") and obj.get("b"):
        return midpoint(as_vec(obj["a"]), as_vec(obj["b"]))
    return None


def _segment(a, b, color, width, unit, dash=False, opacity=None) -> str:
    extra = _stroke_extra(width, unit, dash, opacity)
    return (
        f'<line x1="{_n(a[0])}" y1="{_n(-a[1])}" x2="{_n(b[0])}" y2="{_n(-b[1])}" '
        f'stroke="{color}" {extra}/>'
    )


def _dot(at, color, radius_px, unit, opacity) -> str:
    op = f' fill-opacity="{opacity}"' if opacity is not None else ""
    return (
        f'<circle cx="{_n(at[0])}" cy="{_n(-at[1])}" r="{_n(radius_px * unit)}" '
        f'fill="{color}"{op}/>'
    )


def _circle_xy(center, radius, color, width, unit, dash, opacity, fill) -> str:
    fill_value, fill_opacity = _paint(fill)
    extra = _stroke_extra(width, unit, dash, opacity)
    fill_attr = f' fill="{fill_value}"'
    if fill_opacity is not None:
        fill_attr += f' fill-opacity="{_n(fill_opacity)}"'
    if fill_value == "none":
        fill_attr = ' fill="none"'
    return (
        f'<circle cx="{_n(center[0])}" cy="{_n(-center[1])}" r="{_n(radius)}" '
        f'stroke="{color}"{fill_attr} {extra}/>'
    )


def _polyline(points, color, width, unit, dash, opacity, *, close: bool, fill=None) -> str:
    if len(points) < 2:
        return ""
    commands = []
    for index, point in enumerate(points):
        cmd = "M" if index == 0 else "L"
        commands.append(f"{cmd}{_n(point[0])} {_n(-point[1])}")
    if close:
        commands.append("Z")
    fill_value, fill_opacity = _paint(fill if close else None)
    extra = _stroke_extra(width, unit, dash, opacity)
    fill_attr = f'fill="{fill_value}"'
    if fill_opacity is not None:
        fill_attr += f' fill-opacity="{_n(fill_opacity)}"'
    return f'<path d="{" ".join(commands)}" {fill_attr} stroke="{color}" {extra}/>'


def _text(at, label, unit, beside: bool) -> str:
    anchor = "start" if beside else "middle"
    dx = 8 * unit if beside else 0
    dy = -8 * unit
    size = 15 * unit
    halo = 4 * unit
    return (
        f'<text x="{_n(at[0])}" y="{_n(-at[1])}" dx="{_n(dx)}" dy="{_n(dy)}" '
        f'fill="#1c1917" font-family="Palatino, Georgia, serif" font-size="{_n(size)}" '
        f'text-anchor="{anchor}" stroke="#f4f0e6" stroke-width="{_n(halo)}" paint-order="stroke">'
        f"{_xml(label)}</text>"
    )


def _stroke_extra(width, unit, dash, opacity) -> str:
    bits = [
        f'stroke-width="{_n(width)}"',
        'stroke-linecap="round"',
        'stroke-linejoin="round"',
        'vector-effect="non-scaling-stroke"',
    ]
    if dash:
        bits.append(f'stroke-dasharray="{_n(6 * unit)} {_n(4 * unit)}"')
    if opacity is not None:
        bits.append(f'stroke-opacity="{opacity}"')
    return " ".join(bits)


def _paint(color) -> tuple[str, float | None]:
    if not color or color == "none":
        return "none", None
    h = color.lstrip("#")
    if len(h) == 8:
        return "#" + h[:6], int(h[6:], 16) / 255
    return color, None


def _n(value: float) -> str:
    number = float(value)
    if abs(number) < 1e-9:
        return "0"
    return f"{number:.6g}"


def _xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )

