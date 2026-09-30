# GeoVision

GeoVision is a local 2D and 3D geometry viewer for coding agents. The agent sends short commands. The program computes the constructions, writes a scene file, and the viewer redraws it.

## Install

```bash
pip install -e ".[dev]"
```

Python 3.11 or newer. The viewer has no build step. If `geovision` is not on PATH, use `py -3 -m geovision` in the commands below.

## Draw a figure

```bash
geovision serve
geovision do examples/circumcircle.geo
```

Open http://127.0.0.1:8765. Drag to pan and scroll to zoom. `examples/tetrahedron.geo` is the same idea in 3D: drag to orbit, and use the step slider when a figure has steps.

A follow-up is another short batch, not a new program:

```bash
geovision do "highlight O" "style c color=#c2410c"
geovision ls
geovision export -o figure.svg
```

`geovision help` prints the command language. Moving a point rebuilds circles, centers, and anything else made from it.

The viewer toolbar can place points, segments, polygons, circles, and sketches, and it can plot `y` as an expression in `x`. Those marks are saved into the scene. An agent sees them, marked `by=user`, the next time it lists the figure. Graphs from the command line use the same plot command:

```bash
geovision do "view 2d" "plot f \"x^2 - 1\" domain=-4,4"
```

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
