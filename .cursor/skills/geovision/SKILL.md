---
name: geovision
description: >-
  Draws 2D and 3D geometry figures the user can see. Use when the user asks
  for a geometry diagram, construction, figure, sketch, triangle, circle,
  angle, polygon, polyhedron, vector, plane, or a 2D or 3D picture of a
  geometry problem.
---

# GeoVision

GeoVision is a local viewer. Drive it with `geovision` commands from the repository root. Do not write a Python script for the figure, and do not compute intersections, centers, or radii yourself.

After `pip install -e .`, run commands from the repository root. If `geovision` is not on PATH, use `py -3 -m geovision` instead.

1. Start `geovision serve` once, and tell the user to open http://127.0.0.1:8765.
2. Send the whole figure in one `geovision do` call. Start that call with `clear` when the figure is new. Each command is one quoted argument.
3. Change it later with a shorter `geovision do` call. Moving a point rebuilds objects made from it.
4. Run `geovision ls` to read ids and coordinates. Do this before answering if the user may have drawn or moved anything. Objects they added are marked `by=user`. Run `geovision help` only when a command is unfamiliar.
5. After a 2D change, look at the viewer or run `geovision export -o figure.svg`.

```
geovision do "clear" "view 2d" "title Circumcircle" "point A 0 0 label=A" "point B 4 0 label=B" "point C 1 3 label=C" "polygon tri A B C" "circumcircle c A B C" "highlight c"
```

A 3D figure starts with `view 3d`. Aim it with `camera pos=4,-5,3 target=0,0,0`.

Keep ids stable. Given objects default to blue and constructions to orange. Label every vertex. Use `step` and `step-name` when the explanation has an order, and `highlight` the object under discussion.

Commands you will use most: `point`, `segment`, `line`, `ray`, `vector`, `polygon`, `circle`, `regular`, `midpoint`, `perpendicular`, `parallel`, `intersect`, `circumcircle`, `circumcenter`, `centroid`, `orthocenter`, `bisector`, `project`, `angle`, `right`, `plane`, `sphere`, `box`, `tetra`, `pyramid`, `prism`, `plot`, `style`, `highlight`, `delete`.

A graph is `plot f "x^2 - 1" domain=-4,4`, and only in a 2D view. The expression is in `x`. Use `^` for powers. Do not sample the curve yourself. The user can switch the figure between 2D and 3D; `view 2d` and `view 3d` do the same thing.

Coordinates are x right, y forward, z up. A tilted circle is `circumcircle` of three points, not `circle`.
