# GeoVision

GeoVision is a local 2D and 3D geometry viewer for coding agents. The agent sends short commands. The program computes the constructions, writes a scene file, and the viewer redraws it.

Python 3.11 or newer. The viewer is static HTML, CSS, and JavaScript shipped inside the package, so there is no separate frontend build.

## Install

From a checkout:

```bash
pip install -e .
```

Tests need the dev extra. The desktop connector needs the desktop extra:

```bash
pip install -e ".[dev]"
pip install -e ".[desktop]"
```

If `geovision` is not on PATH, use `py -3 -m geovision` in the commands below.

## Draw a figure

Start the viewer once:

```bash
geovision serve
```

Open http://127.0.0.1:8765. Then apply a figure:

```bash
geovision do examples/circumcircle.geo
```

Drag to pan and scroll to zoom. `examples/tetrahedron.geo` is the same idea in 3D: drag to orbit, and use the step slider when a figure has steps. `examples/cut_pyramid.geo` is another 3D figure.

A follow-up is another short batch:

```bash
geovision do "highlight O" "style c color=#c2410c"
geovision ls
geovision export -o figure.svg
```

`geovision help` prints the command language. `export` writes a 2D scene to SVG. Moving a point rebuilds circles, centers, and anything else made from it.

Coordinates are x right, y forward, z up. Given objects default to blue and constructions to orange. A tilted circle is the circumcircle of three points.

The viewer toolbar can place points, segments, polygons, circles, and sketches, and it can plot `y` as an expression in `x`. Those marks are saved into the scene. An agent sees them, marked `by=user`, the next time it lists the figure. Graphs from the command line use the same plot command, and only in a 2D view:

```bash
geovision do "view 2d" "plot f \"x^2 - 1\" domain=-4,4"
```

## Commands

One command per line. `#` starts a comment. Options are `key=value`. Ids start with a letter and contain letters, digits, and underscores. Repeating a command updates that id.

| Group | Commands |
| --- | --- |
| View | `view`, `title`, `bounds`, `camera` |
| Objects | `point`, `segment`, `line`, `ray`, `vector`, `polyline`, `polygon`, `label`, `circle`, `regular` |
| Constructions | `midpoint`, `perpendicular`, `parallel`, `intersect`, `circumcircle`, `circumcenter`, `centroid`, `orthocenter`, `bisector`, `project`, `angle`, `right`, `plane`, `sphere`, `box`, `tetra`, `pyramid`, `prism` |
| Graphs | `plot`, `stroke` |
| Edit | `style`, `highlight`, `unhighlight`, `step`, `step-name`, `delete`, `clear` |

`geovision ls` lists ids and coordinates. `geovision get <id>` shows one object. `geovision validate` checks the scene file. The default scene is `scenes/current.json`; pass `--scene` to use another file.

## Agent skill

The project skill is [`.cursor/skills/geovision/SKILL.md`](.cursor/skills/geovision/SKILL.md). It loads when this repository is open in Cursor. Copy that folder into the skills directory for Claude Code or Codex to use the same workflow there.

## Claude Desktop and Cowork

Claude Desktop, including Cowork, can draw through a local connector. Regular ChatGPT chat cannot see this computer. ChatGPT’s desktop app can, if the account is allowed to add a local connector.

Install the connector package once:

```bash
py -3 -m pip install -e ".[desktop]"
```

On Windows, Claude reads `%APPDATA%\Claude\claude_desktop_config.json`. Add GeoVision beside any servers already there. Point `GEOVISION_SCENE` at the scene file the open viewer is watching, so a chat updates that window. Use the full path to `python.exe` if Claude cannot find `py`.

```json
{
  "mcpServers": {
    "geovision": {
      "command": "py",
      "args": ["-3", "-m", "geovision.mcp_server"],
      "env": {
        "GEOVISION_SCENE": "C:\\path\\to\\geovision\\scenes\\current.json"
      }
    }
  }
}
```

Quit Claude completely and open it again. In a chat, ask it to draw the figure. The connector runs the same commands as `geovision do`, keeps the viewer at http://127.0.0.1:8765 when that port is free, and sends back a picture when Microsoft Edge or Chrome is installed.

In ChatGPT desktop, add a local MCP connector with that same command and arguments. The picture comes back only in that desktop app.

## Development

```bash
pip install -e ".[dev]"
python -m pytest
```

## License

GeoVision is released under the [MIT License](LICENSE). Copyright (c) 2026 MonsoonDev.
