"""Vector math and geometry constructions.

Coordinates are mathematical: x right, y forward, z up.
"""

from __future__ import annotations

import ast
import math

Vec = tuple[float, float, float]

TOL = 1e-8


class GeometryError(ValueError):
    pass


def vec(x: float, y: float, z: float = 0.0) -> Vec:
    return (float(x), float(y), float(z))


def as_vec(p) -> Vec:
    if len(p) == 2:
        return (float(p[0]), float(p[1]), 0.0)
    return (float(p[0]), float(p[1]), float(p[2]))


def add(a: Vec, b: Vec) -> Vec:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a: Vec, s: float) -> Vec:
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a: Vec, b: Vec) -> Vec:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def length(a: Vec) -> float:
    return math.sqrt(dot(a, a))


def dist(a: Vec, b: Vec) -> float:
    return length(sub(b, a))


def norm(a: Vec) -> Vec:
    mag = length(a)
    if mag < TOL:
        raise GeometryError("zero-length vector")
    return mul(a, 1.0 / mag)


def midpoint(a: Vec, b: Vec) -> Vec:
    return mul(add(a, b), 0.5)


def coords(p: Vec) -> list[float]:
    if not all(math.isfinite(c) for c in p):
        raise GeometryError("non-finite coordinate")
    return [float(p[0]), float(p[1]), float(p[2])]


def basis(normal: Vec) -> tuple[Vec, Vec, Vec]:
    n = norm(normal)
    helper = (0.0, 1.0, 0.0) if abs(n[1]) < 0.9 else (1.0, 0.0, 0.0)
    x_axis = norm(cross(helper, n))
    y_axis = cross(n, x_axis)
    return x_axis, y_axis, n


def project_point_to_line(point: Vec, a: Vec, b: Vec) -> Vec:
    ab = sub(b, a)
    denom = dot(ab, ab)
    if denom < TOL:
        raise GeometryError("degenerate line")
    t = dot(sub(point, a), ab) / denom
    return add(a, mul(ab, t))


def project_point_to_plane(point: Vec, origin: Vec, normal: Vec) -> Vec:
    n = norm(normal)
    return sub(point, mul(n, dot(sub(point, origin), n)))


def line_intersection(p1: Vec, d1: Vec, p2: Vec, d2: Vec) -> Vec | None:
    c = cross(d1, d2)
    c2 = dot(c, c)
    scale = max(length(d1), length(d2), 1.0)
    if c2 < (TOL * scale) ** 2:
        return None
    rhs = sub(p2, p1)
    t = dot(cross(rhs, d2), c) / c2
    s = dot(cross(rhs, d1), c) / c2
    a = add(p1, mul(d1, t))
    b = add(p2, mul(d2, s))
    if dist(a, b) > 1e-6 * scale:
        return None
    return midpoint(a, b)


def line_circle(origin: Vec, direction: Vec, center: Vec, radius: float, normal: Vec) -> list[Vec]:
    d = norm(direction)
    n = norm(normal)
    denom = dot(d, n)
    if abs(denom) > 1e-8:
        t = dot(sub(center, origin), n) / denom
        point = add(origin, mul(d, t))
        if abs(dist(point, center) - radius) <= 1e-6:
            return [point]
        return []
    if abs(dot(sub(origin, center), n)) > 1e-6:
        return []
    f = sub(origin, center)
    b = 2.0 * dot(f, d)
    c = dot(f, f) - radius * radius
    disc = b * b - 4.0 * c
    if disc < -1e-8:
        return []
    disc = max(disc, 0.0)
    root = math.sqrt(disc)
    ts = [(-b - root) / 2.0, (-b + root) / 2.0]
    points = [add(origin, mul(d, t)) for t in ts]
    if dist(points[0], points[1]) < 1e-8:
        return [points[0]]
    return points


def circle_circle(
    c1: Vec, r1: float, n1: Vec, c2: Vec, r2: float, n2: Vec
) -> list[Vec]:
    n = norm(n1)
    if abs(abs(dot(n, norm(n2))) - 1.0) > 1e-6:
        raise GeometryError("circles are not in parallel planes")
    if abs(dot(sub(c2, c1), n)) > 1e-6:
        return []
    apart = sub(c2, c1)
    d = length(apart)
    if d < TOL or d > r1 + r2 + 1e-7 or d < abs(r1 - r2) - 1e-7:
        return []
    along = (r1 * r1 - r2 * r2 + d * d) / (2.0 * d)
    height2 = r1 * r1 - along * along
    if height2 < -1e-8:
        return []
    height = math.sqrt(max(height2, 0.0))
    direction = mul(apart, 1.0 / d)
    side = norm(cross(n, direction))
    base = add(c1, mul(direction, along))
    if height < 1e-8:
        return [base]
    return [add(base, mul(side, height)), sub(base, mul(side, height))]


def circumcircle(a: Vec, b: Vec, c: Vec) -> tuple[Vec, float, Vec]:
    ab = sub(b, a)
    ac = sub(c, a)
    normal = cross(ab, ac)
    if dot(normal, normal) < 1e-16:
        raise GeometryError("points are collinear")
    ab2 = dot(ab, ab)
    ac2 = dot(ac, ac)
    abac = dot(ab, ac)
    det = ab2 * ac2 - abac * abac
    if abs(det) < 1e-16:
        raise GeometryError("points are collinear")
    s = (ab2 / 2.0 * ac2 - abac * ac2 / 2.0) / det
    t = (ab2 * ac2 / 2.0 - ab2 / 2.0 * abac) / det
    center = add(a, add(mul(ab, s), mul(ac, t)))
    return center, dist(center, a), norm(normal)


def centroid(points: list[Vec]) -> Vec:
    if not points:
        raise GeometryError("centroid needs a point")
    total = (0.0, 0.0, 0.0)
    for point in points:
        total = add(total, point)
    return mul(total, 1.0 / len(points))


def orthocenter(a: Vec, b: Vec, c: Vec) -> Vec:
    foot_a = project_point_to_line(a, b, c)
    foot_b = project_point_to_line(b, a, c)
    hit = line_intersection(a, sub(foot_a, a), b, sub(foot_b, b))
    if hit is None:
        raise GeometryError("altitudes do not meet")
    return hit


def bisector_ray(a: Vec, vertex: Vec, c: Vec) -> tuple[Vec, Vec]:
    u = norm(sub(a, vertex))
    v = norm(sub(c, vertex))
    direction = add(u, v)
    if length(direction) < 1e-10:
        direction = cross(u, (0.0, 0.0, 1.0))
        if length(direction) < 1e-8:
            direction = cross(u, (1.0, 0.0, 0.0))
    return vertex, add(vertex, norm(direction))


def perpendicular_line(point: Vec, a: Vec, b: Vec) -> tuple[Vec, Vec]:
    foot = project_point_to_line(point, a, b)
    if dist(point, foot) > 1e-8:
        return point, foot
    direction = sub(b, a)
    side = cross(direction, (0.0, 0.0, 1.0))
    if length(side) < 1e-8:
        side = cross(direction, (1.0, 0.0, 0.0))
    return point, add(point, norm(side))


def parallel_line(point: Vec, a: Vec, b: Vec) -> tuple[Vec, Vec]:
    direction = sub(b, a)
    if length(direction) < TOL:
        raise GeometryError("degenerate line")
    return point, add(point, norm(direction))


def circle_samples(center: Vec, radius: float, normal: Vec, count: int = 64) -> list[Vec]:
    x_axis, y_axis, _ = basis(normal)
    samples = []
    for i in range(count):
        angle = 2.0 * math.pi * i / count
        samples.append(
            add(
                center,
                add(mul(x_axis, radius * math.cos(angle)), mul(y_axis, radius * math.sin(angle))),
            )
        )
    return samples


def regular_polygon(n: int, center: Vec, radius: float, rotate_deg: float, normal: Vec | None = None) -> list[Vec]:
    if n < 3:
        raise GeometryError("a regular polygon needs at least 3 sides")
    if radius <= 0:
        raise GeometryError("radius must be positive")
    x_axis, y_axis, _ = basis(normal or (0.0, 0.0, 1.0))
    rotate = math.radians(rotate_deg)
    points = []
    for i in range(n):
        angle = rotate + 2.0 * math.pi * i / n
        points.append(
            add(
                center,
                add(mul(x_axis, radius * math.cos(angle)), mul(y_axis, radius * math.sin(angle))),
            )
        )
    return points


def angle_mark(arm1: Vec, vertex: Vec, arm2: Vec) -> tuple[list[Vec], Vec]:
    u = sub(arm1, vertex)
    v = sub(arm2, vertex)
    if length(u) < TOL or length(v) < TOL:
        raise GeometryError("degenerate angle")
    radius = 0.28 * min(length(u), length(v))
    ua = norm(u)
    uc = norm(v)
    normal = cross(ua, uc)
    if length(normal) < 1e-10:
        normal = (0.0, 0.0, 1.0)
    else:
        normal = norm(normal)
    y_axis = cross(normal, ua)
    signed = math.atan2(dot(uc, y_axis), dot(uc, ua))
    count = 24
    samples = []
    for i in range(count + 1):
        t = signed * i / count
        samples.append(add(vertex, add(mul(ua, radius * math.cos(t)), mul(y_axis, radius * math.sin(t)))))
    mid = samples[len(samples) // 2]
    outward = sub(mid, vertex)
    if length(outward) < TOL:
        label_at = mid
    else:
        label_at = add(mid, mul(norm(outward), radius * 0.45))
    return samples, label_at


def right_mark(arm1: Vec, vertex: Vec, arm2: Vec) -> list[Vec]:
    u = sub(arm1, vertex)
    v = sub(arm2, vertex)
    if length(u) < TOL or length(v) < TOL:
        raise GeometryError("degenerate right angle")
    size = min(0.35, length(u) * 0.22, length(v) * 0.22)
    ua = norm(u)
    ub = norm(v)
    first = add(vertex, mul(ua, size))
    outer = add(first, mul(ub, size))
    second = add(vertex, mul(ub, size))
    return [first, outer, second]


def arrow_head(a: Vec, b: Vec) -> list[Vec]:
    direction = sub(b, a)
    mag = length(direction)
    if mag < TOL:
        raise GeometryError("zero-length vector")
    forward = mul(direction, 1.0 / mag)
    side = cross(forward, (0.0, 0.0, 1.0))
    if length(side) < 1e-8:
        side = cross(forward, (0.0, 1.0, 0.0))
    side = norm(side)
    size = min(0.22, mag * 0.18)
    back = sub(b, mul(forward, size))
    return [add(back, mul(side, size * 0.45)), b, sub(back, mul(side, size * 0.45))]


def on_segment(point: Vec, a: Vec, b: Vec) -> bool:
    ab = sub(b, a)
    denom = dot(ab, ab)
    if denom < TOL:
        return dist(point, a) <= 1e-5
    t = dot(sub(point, a), ab) / denom
    if t < -1e-6 or t > 1.0 + 1e-6:
        return False
    return dist(point, add(a, mul(ab, t))) <= 1e-5


def on_ray(point: Vec, origin: Vec, through: Vec) -> bool:
    direction = sub(through, origin)
    denom = dot(direction, direction)
    if denom < TOL:
        return dist(point, origin) <= 1e-5
    t = dot(sub(point, origin), direction) / denom
    if t < -1e-6:
        return False
    return dist(point, add(origin, mul(direction, t))) <= 1e-5


def clip_segment(a: Vec, b: Vec, bounds: tuple[float, float, float, float]) -> tuple[Vec, Vec] | None:
    minx, miny, maxx, maxy = bounds
    x0, y0, z0 = a
    x1, y1, z1 = b

    def code(x: float, y: float) -> int:
        c = 0
        if x < minx:
            c |= 1
        elif x > maxx:
            c |= 2
        if y < miny:
            c |= 4
        elif y > maxy:
            c |= 8
        return c

    c0, c1 = code(x0, y0), code(x1, y1)
    for _ in range(16):
        if c0 == 0 and c1 == 0:
            return (x0, y0, z0), (x1, y1, z1)
        if c0 & c1:
            return None
        c = c0 or c1
        if c & 1:
            t = (minx - x0) / (x1 - x0)
            x, y, z = minx, y0 + t * (y1 - y0), z0 + t * (z1 - z0)
        elif c & 2:
            t = (maxx - x0) / (x1 - x0)
            x, y, z = maxx, y0 + t * (y1 - y0), z0 + t * (z1 - z0)
        elif c & 4:
            t = (miny - y0) / (y1 - y0)
            x, y, z = x0 + t * (x1 - x0), miny, z0 + t * (z1 - z0)
        else:
            t = (maxy - y0) / (y1 - y0)
            x, y, z = x0 + t * (x1 - x0), maxy, z0 + t * (z1 - z0)
        if c == c0:
            x0, y0, z0, c0 = x, y, z, code(x, y)
        else:
            x1, y1, z1, c1 = x, y, z, code(x, y)
    return None


def grid_step(span: float) -> float:
    raw = span / 8.0
    if raw <= 0:
        return 1.0
    mag = 10 ** math.floor(math.log10(raw))
    for multiplier in (1, 2, 5, 10):
        step = multiplier * mag
        if raw <= step:
            return step
    return 10 * mag


def _point(obj: dict) -> Vec:
    if obj.get("type") != "point" or "at" not in obj:
        raise GeometryError(f"{obj.get('id', 'object')} is not a point")
    return as_vec(obj["at"])


def _lineish(obj: dict) -> tuple[Vec, Vec]:
    if obj.get("type") not in {"line", "segment", "ray", "vector"}:
        raise GeometryError(f"{obj.get('id', 'object')} is not a line")
    return as_vec(obj["a"]), as_vec(obj["b"])


def _accept(obj: dict, point: Vec) -> bool:
    kind = obj.get("type")
    if kind in {"line", "circle"}:
        return True
    if kind in {"segment", "vector"}:
        return on_segment(point, as_vec(obj["a"]), as_vec(obj["b"]))
    if kind == "ray":
        return on_ray(point, as_vec(obj["a"]), as_vec(obj["b"]))
    return False


def intersections(first: dict, second: dict) -> list[Vec]:
    lineish = {"line", "segment", "ray", "vector"}
    t1, t2 = first.get("type"), second.get("type")
    if t1 in lineish and t2 in lineish:
        a1, b1 = _lineish(first)
        a2, b2 = _lineish(second)
        hit = line_intersection(a1, sub(b1, a1), a2, sub(b2, a2))
        points = [hit] if hit is not None else []
    elif t1 == "circle" and t2 == "circle":
        points = circle_circle(
            as_vec(first["center"]),
            float(first["radius"]),
            as_vec(first.get("normal") or (0, 0, 1)),
            as_vec(second["center"]),
            float(second["radius"]),
            as_vec(second.get("normal") or (0, 0, 1)),
        )
    elif t1 == "circle" and t2 in lineish:
        a, b = _lineish(second)
        points = line_circle(
            a, sub(b, a), as_vec(first["center"]), float(first["radius"]), as_vec(first.get("normal") or (0, 0, 1))
        )
    elif t2 == "circle" and t1 in lineish:
        a, b = _lineish(first)
        points = line_circle(
            a, sub(b, a), as_vec(second["center"]), float(second["radius"]), as_vec(second.get("normal") or (0, 0, 1))
        )
    else:
        raise GeometryError(f"cannot intersect {t1} and {t2}")
    kept = [point for point in points if _accept(first, point) and _accept(second, point)]
    kept.sort(key=lambda p: (round(p[0], 9), round(p[1], 9), round(p[2], 9)))
    return kept


def _pts(values: list[Vec]) -> list[list[float]]:
    return [coords(p) for p in values]


def box_solid(origin: Vec, size: Vec) -> tuple[list[Vec], list[list[int]]]:
    dx, dy, dz = size
    if dx == 0 or dy == 0 or dz == 0:
        raise GeometryError("box size must be non-zero")
    x, y, z = origin
    verts = [
        vec(x, y, z),
        vec(x + dx, y, z),
        vec(x + dx, y + dy, z),
        vec(x, y + dy, z),
        vec(x, y, z + dz),
        vec(x + dx, y, z + dz),
        vec(x + dx, y + dy, z + dz),
        vec(x, y + dy, z + dz),
    ]
    faces = [
        [0, 1, 2, 3],
        [4, 5, 6, 7],
        [0, 1, 5, 4],
        [1, 2, 6, 5],
        [2, 3, 7, 6],
        [3, 0, 4, 7],
    ]
    return verts, faces


def prism_solid(base: list[Vec], delta: Vec) -> tuple[list[Vec], list[list[int]]]:
    if len(base) < 3:
        raise GeometryError("prism needs at least 3 base points")
    if length(delta) < TOL:
        raise GeometryError("prism height must be non-zero")
    top = [add(point, delta) for point in base]
    n = len(base)
    verts = list(base) + top
    faces = [list(range(n)), list(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append([i, j, j + n, i + n])
    return verts, faces


def pyramid_solid(base: list[Vec], apex: Vec) -> tuple[list[Vec], list[list[int]]]:
    if len(base) < 3:
        raise GeometryError("pyramid needs at least 3 base points")
    verts = list(base) + [apex]
    apex_i = len(base)
    faces = [list(range(len(base)))]
    for i in range(len(base)):
        j = (i + 1) % len(base)
        faces.append([i, j, apex_i])
    return verts, faces


def tetra_solid(a: Vec, b: Vec, c: Vec, d: Vec) -> tuple[list[Vec], list[list[int]]]:
    if length(cross(sub(b, a), sub(c, a))) < 1e-12:
        raise GeometryError("tetrahedron base is degenerate")
    return [a, b, c, d], [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]]


def plane_corners(a: Vec, b: Vec, c: Vec) -> tuple[list[Vec], Vec]:
    u = sub(b, a)
    v = sub(c, a)
    normal = cross(u, v)
    if length(normal) < TOL:
        raise GeometryError("points do not define a plane")
    origin = add(a, add(mul(u, -0.25), mul(v, -0.25)))
    uu = mul(u, 1.5)
    vv = mul(v, 1.5)
    corners = [origin, add(origin, uu), add(origin, add(uu, vv)), add(origin, vv)]
    return corners, norm(normal)


_FUNCS = {
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "sqrt": math.sqrt,
    "abs": abs,
    "ln": math.log,
    "log": math.log,
    "exp": math.exp,
    "floor": math.floor,
    "ceil": math.ceil,
}
_NAMES = {"x", "pi", "e", "tau", *_FUNCS}
_EXPR_NODES = (
    ast.Expression,
    ast.BinOp,
    ast.UnaryOp,
    ast.Constant,
    ast.Name,
    ast.Call,
    ast.Load,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.Pow,
    ast.Mod,
    ast.UAdd,
    ast.USub,
)


def compile_expr(source: str):
    text = source.strip().replace("^", "**")
    if not text or len(text) > 200:
        raise GeometryError(f"could not parse {source!r}")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise GeometryError(f"could not parse {source!r}") from exc
    for node in ast.walk(tree):
        if not isinstance(node, _EXPR_NODES):
            raise GeometryError(f"unsupported syntax in {source!r}")
        if isinstance(node, ast.Call):
            if node.keywords or not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
                raise GeometryError(f"unsupported function in {source!r}")
        if isinstance(node, ast.Name) and node.id not in _NAMES:
            raise GeometryError(f"unknown name {node.id} in {source!r}")
        if isinstance(node, ast.Constant) and (isinstance(node.value, bool) or not isinstance(node.value, (int, float))):
            raise GeometryError(f"unsupported value in {source!r}")

    def evaluate(x: float) -> float:
        try:
            value = _eval_expr(tree.body, x)
            number = float(value)
        except (TypeError, ValueError, OverflowError, ZeroDivisionError, ArithmeticError):
            return math.nan
        if isinstance(value, complex) or not math.isfinite(number):
            return math.nan
        return number

    return evaluate


def _eval_expr(node: ast.AST, x: float) -> float:
    if isinstance(node, ast.Constant):
        return float(node.value)
    if isinstance(node, ast.Name):
        if node.id == "x":
            return float(x)
        if node.id == "pi":
            return math.pi
        if node.id == "e":
            return math.e
        return math.tau
    if isinstance(node, ast.UnaryOp):
        value = _eval_expr(node.operand, x)
        if isinstance(node.op, ast.USub):
            return -value
        return value
    if isinstance(node, ast.BinOp):
        left = _eval_expr(node.left, x)
        right = _eval_expr(node.right, x)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        return left**right
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        args = [_eval_expr(arg, x) for arg in node.args]
        return _FUNCS[node.func.id](*args)
    raise GeometryError("unsupported syntax")


def sample_curve(expr: str, start: float, end: float, count: int = 240) -> list[list[list[float]]]:
    if end <= start:
        raise GeometryError("domain max must be greater than min")
    evaluate = compile_expr(expr)
    count = max(2, min(int(count), 800))
    paths: list[list[list[float]]] = []
    current: list[list[float]] = []
    previous = None
    for index in range(count):
        x = start + (end - start) * index / (count - 1)
        y = evaluate(x)
        if not math.isfinite(y) or abs(y) > 1e4:
            if len(current) >= 2:
                paths.append(current)
            current = []
            previous = None
            continue
        if previous is not None and y * previous < 0 and abs(y - previous) > 40:
            if len(current) >= 2:
                paths.append(current)
            current = []
        current.append([x, y, 0.0])
        previous = y
    if len(current) >= 2:
        paths.append(current)
    if not paths:
        raise GeometryError(f"{expr!r} has no points on that domain")
    return paths


def build(recipe: dict, get) -> dict:
    op = recipe["op"]
    args = list(recipe.get("args") or [])

    def obj(id_: str) -> dict:
        found = get(id_)
        if found is None:
            raise GeometryError(f"missing object {id_}")
        return found

    def point(id_: str) -> Vec:
        return _point(obj(id_))

    if op in {"segment", "line", "ray"}:
        a, b = point(args[0]), point(args[1])
        if dist(a, b) < TOL:
            raise GeometryError(f"degenerate {op}")
        return {"type": op, "a": coords(a), "b": coords(b)}

    if op == "vector":
        start = point(args[0])
        if recipe.get("delta") is not None:
            end = add(start, as_vec(recipe["delta"]))
        else:
            end = point(args[1])
        return {"type": "vector", "a": coords(start), "b": coords(end), "head": _pts(arrow_head(start, end))}

    if op in {"polyline", "polygon"}:
        pts = [point(id_) for id_ in args]
        if op == "polyline" and len(pts) < 2:
            raise GeometryError("polyline needs at least 2 points")
        if op == "polygon" and len(pts) < 3:
            raise GeometryError("polygon needs at least 3 points")
        return {"type": op, "points": _pts(pts)}

    if op == "circle":
        center = point(args[0])
        if "radius" in recipe:
            radius = float(recipe["radius"])
            if radius <= 0:
                raise GeometryError("radius must be positive")
            normal = (0.0, 0.0, 1.0)
        else:
            other = point(args[1])
            if abs(other[2] - center[2]) > 1e-6:
                raise GeometryError(
                    "point is not in the horizontal plane of the center; use circumcircle for a tilted circle"
                )
            radius = dist(center, other)
            if radius <= TOL:
                raise GeometryError("radius must be positive")
            normal = (0.0, 0.0, 1.0)
        samples = circle_samples(center, radius, normal)
        return {
            "type": "circle",
            "center": coords(center),
            "radius": radius,
            "normal": coords(normal),
            "samples": _pts(samples),
        }

    if op == "midpoint":
        return {"type": "point", "at": coords(midpoint(point(args[0]), point(args[1])))}

    if op == "perpendicular":
        a, b = _lineish(obj(args[1]))
        p, q = perpendicular_line(point(args[0]), a, b)
        return {"type": "line", "a": coords(p), "b": coords(q)}

    if op == "parallel":
        a, b = _lineish(obj(args[1]))
        p, q = parallel_line(point(args[0]), a, b)
        return {"type": "line", "a": coords(p), "b": coords(q)}

    if op == "intersect":
        hits = intersections(obj(args[0]), obj(args[1]))
        index = int(recipe.get("index") or 0)
        if not hits:
            raise GeometryError("no intersection")
        if index < 0 or index >= len(hits):
            raise GeometryError(f"intersect index {index} but only {len(hits)} point(s)")
        return {"type": "point", "at": coords(hits[index])}

    if op == "circumcircle":
        center, radius, normal = circumcircle(point(args[0]), point(args[1]), point(args[2]))
        return {
            "type": "circle",
            "center": coords(center),
            "radius": radius,
            "normal": coords(normal),
            "samples": _pts(circle_samples(center, radius, normal)),
        }

    if op == "circumcenter":
        center, _radius, _normal = circumcircle(point(args[0]), point(args[1]), point(args[2]))
        return {"type": "point", "at": coords(center)}

    if op == "centroid":
        return {"type": "point", "at": coords(centroid([point(id_) for id_ in args]))}

    if op == "orthocenter":
        return {"type": "point", "at": coords(orthocenter(point(args[0]), point(args[1]), point(args[2])))}

    if op == "bisector":
        start, end = bisector_ray(point(args[0]), point(args[1]), point(args[2]))
        return {"type": "ray", "a": coords(start), "b": coords(end)}

    if op == "project":
        target = obj(args[1])
        source = point(args[0])
        if target.get("type") == "plane":
            corners = [as_vec(p) for p in target["corners"]]
            foot = project_point_to_plane(source, corners[0], as_vec(target["normal"]))
        elif target.get("type") in {"line", "segment", "ray", "vector"}:
            a, b = _lineish(target)
            foot = project_point_to_line(source, a, b)
        else:
            raise GeometryError(f"cannot project onto {target.get('type')}")
        return {"type": "point", "at": coords(foot)}

    if op == "regular":
        pts = regular_polygon(
            int(recipe["n"]),
            point(args[0]),
            float(recipe["radius"]),
            float(recipe.get("rotate") or 0),
        )
        return {"type": "polygon", "points": _pts(pts)}

    if op == "angle":
        samples, label_at = angle_mark(point(args[0]), point(args[1]), point(args[2]))
        return {"type": "angle", "points": _pts(samples), "labelAt": coords(label_at)}

    if op == "right":
        return {"type": "right_angle", "points": _pts(right_mark(point(args[0]), point(args[1]), point(args[2])))}

    if op == "plane":
        corners, normal = plane_corners(point(args[0]), point(args[1]), point(args[2]))
        return {"type": "plane", "corners": _pts(corners), "normal": coords(normal)}

    if op == "sphere":
        center = point(args[0])
        radius = float(recipe["radius"])
        if radius <= 0:
            raise GeometryError("radius must be positive")
        return {"type": "sphere", "center": coords(center), "radius": radius}

    if op == "box":
        verts, faces = box_solid(as_vec(recipe["origin"]), as_vec(recipe["size"]))
        return {"type": "polyhedron", "vertices": _pts(verts), "faces": faces}

    if op == "tetra":
        verts, faces = tetra_solid(point(args[0]), point(args[1]), point(args[2]), point(args[3]))
        return {"type": "polyhedron", "vertices": _pts(verts), "faces": faces}

    if op == "pyramid":
        base = [point(id_) for id_ in args[:-1]]
        verts, faces = pyramid_solid(base, point(args[-1]))
        return {"type": "polyhedron", "vertices": _pts(verts), "faces": faces}

    if op == "prism":
        base = [point(id_) for id_ in args]
        verts, faces = prism_solid(base, as_vec(recipe["delta"]))
        return {"type": "polyhedron", "vertices": _pts(verts), "faces": faces}

    if op == "plot":
        domain = recipe.get("domain") or [-5.0, 5.0]
        paths = sample_curve(str(recipe.get("expr") or ""), float(domain[0]), float(domain[1]), int(recipe.get("samples") or 240))
        return {
            "type": "curve",
            "paths": paths,
            "expr": str(recipe.get("expr") or ""),
            "labelAt": paths[0][len(paths[0]) // 2],
        }

    raise GeometryError(f"unknown construction {op}")
