"""Command line interface for GeoVision."""

from __future__ import annotations

import argparse
import json
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from geovision.commands import (
    HELP,
    CommandError,
    apply_lines,
    format_get,
    format_ls,
)
from geovision.export_svg import scene_to_svg
from geovision.geom import GeometryError
from geovision.scene import Scene

DEFAULT_SCENE = Path("scenes/current.json")


def viewer_dir() -> Path:
    packaged = Path(__file__).resolve().parent / "viewer"
    if (packaged / "index.html").is_file():
        return packaged
    root = Path(__file__).resolve().parents[2] / "viewer"
    if (root / "index.html").is_file():
        return root
    raise SystemExit("viewer assets not found")


def make_handler(scene_path: Path, assets: Path):
    write_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path == "/scene":
                if scene_path.exists():
                    body = scene_path.read_bytes()
                else:
                    body = (json.dumps(Scene().to_dict(), indent=2) + "\n").encode("utf-8")
                self._send(200, "application/json; charset=utf-8", body)
                return
            files = {
                "/": assets / "index.html",
                "/index.html": assets / "index.html",
                "/viewer.js": assets / "viewer.js",
                "/draw.js": assets / "draw.js",
                "/camera.js": assets / "camera.js",
                "/style.css": assets / "style.css",
            }
            file = files.get(path)
            if file is None or not file.is_file():
                self._send(404, "text/plain; charset=utf-8", b"not found\n")
                return
            kind = {
                ".html": "text/html; charset=utf-8",
                ".js": "text/javascript; charset=utf-8",
                ".css": "text/css; charset=utf-8",
            }[file.suffix]
            self._send(200, kind, file.read_bytes())

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/command":
                self._send(404, "text/plain; charset=utf-8", b"not found\n")
                return
            try:
                length = int(self.headers.get("Content-Length") or "0")
            except ValueError:
                length = 0
            if length < 0 or length > 1_000_000:
                self._send(400, "text/plain; charset=utf-8", b"request too large\n")
                return
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
                commands = payload["commands"]
                if not isinstance(commands, str) or not commands.strip():
                    raise ValueError
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError, KeyError):
                self._send(400, "text/plain; charset=utf-8", b'expected {"commands": "..."}\n')
                return
            with write_lock:
                scene = Scene.load(scene_path)
                try:
                    apply_lines(scene, commands.splitlines())
                except (CommandError, GeometryError) as exc:
                    message = (str(exc) + "\n").encode("utf-8")
                    self._send(400, "text/plain; charset=utf-8", message)
                    return
                scene.save(scene_path)
                body = (json.dumps(scene.to_dict(), indent=2) + "\n").encode("utf-8")
            self._send(200, "application/json; charset=utf-8", body)

        def _send(self, status: int, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            return

    return Handler


def make_server(scene_path: Path, port: int) -> ThreadingHTTPServer:
    handler = make_handler(scene_path, viewer_dir())
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def serve(scene_path: Path, port: int, open_browser: bool) -> int:
    try:
        httpd = make_server(scene_path, port)
    except OSError as exc:
        print(f"error: could not listen on {port}: {exc}", file=sys.stderr)
        return 1
    bound = httpd.server_address[1]
    url = f"http://127.0.0.1:{bound}"
    print(f"GeoVision  {url}", flush=True)
    print(f"scene      {scene_path}", flush=True)
    if open_browser:
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
    return 0


def collect_lines(items: list[str]) -> list[str]:
    if not items:
        if sys.stdin.isatty():
            raise CommandError(
                'usage: geovision do "point A 0 0 label=A" ...\n'
                "   or: geovision do examples/circumcircle.geo"
            )
        return sys.stdin.read().splitlines()
    if len(items) == 1 and Path(items[0]).is_file():
        return Path(items[0]).read_text(encoding="utf-8").splitlines()
    lines: list[str] = []
    for item in items:
        lines.extend(item.splitlines())
    return lines


def do_commands(scene_path: Path, items: list[str]) -> int:
    scene = Scene.load(scene_path)
    apply_lines(scene, collect_lines(items))
    scene.save(scene_path)
    print(f"ok {len(scene.order)} objects -> {scene_path}", flush=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="geovision", description="Agent-driven 2D and 3D geometry viewer")
    parser.add_argument("--scene", default=str(DEFAULT_SCENE), help="scene file (default: scenes/current.json)")
    sub = parser.add_subparsers(dest="command", required=True)

    do = sub.add_parser("do", help="apply commands from arguments, a file, or stdin")
    do.add_argument("lines", nargs="*")

    sub.add_parser("ls", help="list objects in the scene")

    get = sub.add_parser("get", help="show one object")
    get.add_argument("id")

    sub.add_parser("help", help="show the command language")

    serve_cmd = sub.add_parser("serve", help="open the viewer and watch the scene file")
    serve_cmd.add_argument("--port", type=int, default=8765)
    serve_cmd.add_argument("--open", action="store_true", help="open a browser")

    sub.add_parser("validate", help="check the scene file")

    export = sub.add_parser("export", help="write a 2D scene to SVG")
    export.add_argument("-o", "--output", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    raw = list(sys.argv[1:] if argv is None else argv)
    scene = None
    cleaned: list[str] = []
    index = 0
    while index < len(raw):
        if raw[index] == "--scene" and index + 1 < len(raw):
            scene = raw[index + 1]
            index += 2
            continue
        cleaned.append(raw[index])
        index += 1
    args = parser.parse_args(cleaned)
    if scene is not None:
        args.scene = scene
    scene_path = Path(args.scene)
    try:
        if args.command == "help":
            print(HELP)
            return 0
        if args.command == "do":
            return do_commands(scene_path, args.lines)
        if args.command == "ls":
            print(format_ls(Scene.load(scene_path)))
            return 0
        if args.command == "get":
            print(format_get(Scene.load(scene_path), args.id))
            return 0
        if args.command == "serve":
            return serve(scene_path, args.port, args.open)
        if args.command == "validate":
            if not scene_path.exists():
                raise CommandError(f"no scene at {scene_path}")
            errors = Scene.load(scene_path).validate()
            if errors:
                for error in errors:
                    print(f"error: {error}", file=sys.stderr)
                return 1
            print("ok")
            return 0
        if args.command == "export":
            if not scene_path.exists():
                raise CommandError(f"no scene at {scene_path}")
            svg = scene_to_svg(Scene.load(scene_path))
            output = Path(args.output)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(svg, encoding="utf-8")
            print(f"ok {output}")
            return 0
    except (CommandError, GeometryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
