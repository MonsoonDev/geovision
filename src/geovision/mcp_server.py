"""Desktop connector so Claude and ChatGPT can draw with GeoVision.

Speak MCP on stdin and stdout. Logs and browser noise stay off stdout.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from geovision.commands import HELP, CommandError, apply_lines, format_ls
from geovision.scene import Scene

VIEWER_PORT = 8765
_LOCK = threading.Lock()
_owned: ThreadingHTTPServer | None = None
_owned_port: int | None = None
_owned_path: Path | None = None

INSTRUCTIONS = """
GeoVision draws a 2D or 3D geometry figure on this computer and returns a picture.

Use the draw tool. `commands` is one GeoVision command per line.
Start a new figure with `clear`. Coordinates: x right, y forward, z up.
Do not compute intersections, centers, or radii yourself. Ask for them:
circumcircle, circumcenter, centroid, orthocenter, midpoint, intersect,
perpendicular, parallel, project, bisector.
Label every vertex. Given objects are blue and constructions are orange.
Use highlight on the object you are talking about.
A 3D figure starts with `view 3d`. Aim it with `camera pos=6,-8,5 target=0,0,0`.
Call look to read ids and coordinates, including shapes the user drew (marked by=user). Call command_help for the full language.
Plot a graph with plot <id> "expr" domain=min,max, in a 2D view only. The expression is in x, and ^ means power. The user can switch between 2D and 3D.
""".strip()


def scene_path() -> Path:
    env = os.environ.get("GEOVISION_SCENE")
    if env:
        return Path(env).expanduser()
    root = Path(__file__).resolve().parents[2]
    if (root / "scenes").is_dir():
        return root / "scenes" / "current.json"
    return Path.home() / ".geovision" / "current.json"


def _fetch_scene(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/scene", timeout=0.8) as response:
            return json.loads(response.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError, TimeoutError):
        return None


def _port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.3)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _scene_matches(port: int, path: Path) -> bool:
    remote = _fetch_scene(port)
    if remote is None or not path.is_file():
        return False
    try:
        local = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return remote == local


def viewer_url(path: Path) -> str:
    """Use the viewer already showing this file, or start one."""
    global _owned, _owned_port, _owned_path
    resolved = path.resolve()
    if _owned_port is not None and _owned_path == resolved:
        return f"http://127.0.0.1:{_owned_port}"
    if _scene_matches(VIEWER_PORT, path):
        return f"http://127.0.0.1:{VIEWER_PORT}"
    from geovision.cli import make_server

    # Windows lets a second bind to a busy port succeed when reuse is on,
    # and the browser still reaches the server that was already there.
    httpd = None
    ports = [port for port in (VIEWER_PORT, 8766, 8767, 8768) if not _port_busy(port)]
    ports.append(0)
    previous = ThreadingHTTPServer.allow_reuse_address
    ThreadingHTTPServer.allow_reuse_address = False
    try:
        for port in ports:
            try:
                httpd = make_server(path, port)
                break
            except OSError:
                continue
    finally:
        ThreadingHTTPServer.allow_reuse_address = previous
    if httpd is None:
        raise CommandError("could not start the viewer")
    threading.Thread(target=httpd.serve_forever, daemon=True, name="geovision-viewer").start()
    _owned = httpd
    _owned_port = int(httpd.server_address[1])
    _owned_path = resolved
    return f"http://127.0.0.1:{_owned_port}"


def stop_owned_viewer() -> None:
    global _owned, _owned_port, _owned_path
    if _owned is not None:
        _owned.shutdown()
        _owned.server_close()
    _owned = None
    _owned_port = None
    _owned_path = None


def browser_executable() -> Path | None:
    names = ("msedge", "microsoft-edge", "google-chrome", "google-chrome-stable", "chromium", "chrome")
    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found)
    program = os.environ.get("PROGRAMFILES", r"C:\Program Files")
    program86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        Path(program86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(program) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(local) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(program) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(program86) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
    ]
    for path in candidates:
        if path.is_file():
            return path
    return None


def capture_png(url: str) -> bytes | None:
    browser = browser_executable()
    if browser is None:
        return None
    with tempfile.TemporaryDirectory(prefix="geovision-shot-") as folder:
        dest = Path(folder) / "figure.png"
        profile = Path(folder) / "profile"
        command = [
            str(browser),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-extensions",
            "--force-device-scale-factor=1",
            f"--user-data-dir={profile}",
            "--window-size=1400,900",
            "--virtual-time-budget=12000",
            f"--screenshot={dest}",
            url,
        ]
        try:
            subprocess.run(
                command,
                check=False,
                timeout=45,
                cwd=folder,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        shots = [dest, *Path(folder).glob("*.png")]
        for shot in shots:
            if shot.is_file() and shot.stat().st_size > 2000:
                return shot.read_bytes()
    return None


def draw_figure(commands: str, *, capture: bool = True) -> tuple[str, bytes | None]:
    text = commands.strip()
    if not text:
        raise CommandError("draw needs one or more commands, one per line")
    path = scene_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        scene = Scene.load(path)
        apply_lines(scene, text.splitlines())
        scene.save(path)
        summary = format_ls(scene)
        url = viewer_url(path)
        png = capture_png(url) if capture else None
    message = f"Saved {path}\nViewer {url}\n\n{summary}"
    if capture and png is None:
        message += (
            "\n\nThe figure is on the viewer, but this machine did not return a picture. "
            "Install Microsoft Edge or Google Chrome, then draw again."
        )
    return message, png


def look_scene() -> str:
    path = scene_path()
    with _LOCK:
        scene = Scene.load(path)
        return f"{path}\n\n{format_ls(scene)}"


def main() -> None:
    try:
        from mcp.server.mcpserver import Image, MCPServer
    except ImportError:
        print(
            'GeoVision desktop connector needs the MCP package:\n  py -3 -m pip install -e ".[desktop]"',
            file=sys.stderr,
        )
        raise SystemExit(1)

    server = MCPServer(
        "geovision",
        instructions=INSTRUCTIONS,
        log_level="ERROR",
    )

    @server.tool(structured_output=False)
    def draw(commands: str) -> str | list:
        """Draw or edit the geometry figure.

        `commands` is one GeoVision command per line. Start a new figure with clear.
        Returns the object list and a picture of the viewer.
        """
        text, png = draw_figure(commands)
        if png is None:
            return text
        return [text, Image(data=png, format="png")]

    @server.tool()
    def look() -> str:
        """List the current figure: ids, kinds, coordinates, and labels."""
        return look_scene()

    @server.tool()
    def command_help() -> str:
        """Return the full GeoVision command language."""
        return HELP.strip() + "\n"

    server.run(transport="stdio")


if __name__ == "__main__":
    main()
