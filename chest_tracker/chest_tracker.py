#!/usr/bin/env python3
"""Chest tracker: counts chest opens and chest breaks by watching a screen region.

It only reads pixels. Each event is detected by template matching a small
image you cropped from the game (for example the "chest opened" feedback),
and the counters are written to counts/counts.txt for OBS or any text reader.
"""

import argparse
import json
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent

DEFAULT_CONFIG = {
    # Screen area to scan: [left, top, width, height] in pixels of the monitor.
    "region": [660, 300, 600, 300],
    "fps": 5,
    # Port for the counter page on your phone/iPad (same Wi-Fi). 0 turns it off.
    "web_port": 8765,
    # Minimum match score (0..1) to count a hit. Raise it if you get false positives.
    "threshold": 0.85,
    # Seconds a template must stay off screen or wait before it can count again.
    "cooldown_seconds": 3.0,
    "templates": {
        "chest_open": "templates/chest_open.png",
        "chest_break": "templates/chest_break.png",
    },
    "output_dir": "counts",
}

LABELS = {
    "chest_open": "Chest opens",
    "chest_break": "Chest breaks",
}


def load_config(path: Path) -> dict:
    cfg = json.loads(json.dumps(DEFAULT_CONFIG))
    if path.exists():
        text = path.read_text(encoding="utf-8").strip()
        if text:
            cfg.update(json.loads(text))
    return cfg


def load_templates(cfg: dict, base: Path) -> dict:
    templates = {}
    for name, rel in cfg["templates"].items():
        path = (base / rel).resolve()
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is None:
            raise FileNotFoundError(
                f"Template for '{name}' not found or unreadable: {path}\n"
                "Create it with: python chest_tracker.py crop <screenshot> x y w h <out>"
            )
        templates[name] = img
    return templates


def best_score(frame_gray: np.ndarray, template_gray: np.ndarray) -> float:
    """Highest normalized correlation of the template anywhere in the frame."""
    fh, fw = frame_gray.shape[:2]
    th, tw = template_gray.shape[:2]
    if th > fh or tw > fw:
        return 0.0
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    result = np.nan_to_num(result, nan=0.0, neginf=0.0)
    return float(result.max())


class EdgeDetector:
    """Fires once when a match appears, then waits until it disappears and the cooldown passes."""

    def __init__(self, threshold: float, cooldown: float):
        self.threshold = threshold
        self.cooldown = cooldown
        self.visible = False
        self.last_fire = float("-inf")

    def update(self, score: float, now: float) -> bool:
        hit = score >= self.threshold
        fire = hit and not self.visible and (now - self.last_fire) >= self.cooldown
        self.visible = hit
        if fire:
            self.last_fire = now
        return fire


class ChestCounter:
    def __init__(self, templates: dict, threshold: float, cooldown: float, counts=None):
        self.templates = templates
        self.detectors = {n: EdgeDetector(threshold, cooldown) for n in templates}
        self.counts = {n: 0 for n in templates}
        if counts:
            self.counts.update({k: int(v) for k, v in counts.items() if k in self.counts})

    def process(self, frame_gray: np.ndarray, now: float) -> list:
        fired = []
        for name, tpl in self.templates.items():
            score = best_score(frame_gray, tpl)
            if self.detectors[name].update(score, now):
                self.counts[name] += 1
                fired.append(name)
        return fired


def write_outputs(out_dir: Path, counts: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"{LABELS.get(k, k)}: {v}" for k, v in counts.items()]
    (out_dir / "counts.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out_dir / "counts.json").write_text(json.dumps(counts, indent=2), encoding="utf-8")


def read_saved_counts(out_dir: Path) -> dict:
    path = out_dir / "counts.json"
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    return {}


WEB_PAGE = """<!doctype html>
<html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="Cofres">
<title>Contador de cofres</title>
<style>
  :root { color-scheme: dark; }
  html, body { margin: 0; height: 100%; background: #0d1117; color: #e6edf3;
    font-family: -apple-system, system-ui, sans-serif; }
  body { display: flex; flex-direction: column; justify-content: center; align-items: center;
    gap: 28px; padding: 24px; box-sizing: border-box; }
  .card { width: min(560px, 100%); background: #161b22; border-radius: 24px; padding: 28px 24px;
    text-align: center; box-shadow: 0 6px 24px rgba(0,0,0,.35); }
  .label { font-size: 22px; color: #8b949e; letter-spacing: .02em; }
  .num { font-size: clamp(96px, 26vw, 180px); font-weight: 800; line-height: 1.05;
    font-variant-numeric: tabular-nums; }
  .open .num { color: #3fb950; }
  .break .num { color: #f0883e; }
  .status { font-size: 15px; color: #6e7681; }
</style></head>
<body>
  <div class="card open"><div class="label">Cofres abiertos</div><div class="num" id="open">0</div></div>
  <div class="card break"><div class="label">Cofres rotos</div><div class="num" id="break">0</div></div>
  <div class="status" id="status">Conectando…</div>
<script>
  async function refresh() {
    try {
      const r = await fetch('/counts.json', { cache: 'no-store' });
      const c = await r.json();
      document.getElementById('open').textContent = c.chest_open ?? 0;
      document.getElementById('break').textContent = c.chest_break ?? 0;
      document.getElementById('status').textContent = 'En vivo · ' + new Date().toLocaleTimeString();
    } catch (e) {
      document.getElementById('status').textContent = 'Sin conexión con la PC';
    }
  }
  refresh();
  setInterval(refresh, 1000);
</script>
</body></html>
"""


class CountsHandler(BaseHTTPRequestHandler):
    out_dir: Path = Path(".")

    def do_GET(self):
        if self.path.split("?")[0] == "/counts.json":
            body = json.dumps(read_saved_counts(self.out_dir)).encode("utf-8")
            ctype = "application/json; charset=utf-8"
        else:
            body = WEB_PAGE.encode("utf-8")
            ctype = "text/html; charset=utf-8"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):  # keep the console for tracker events
        pass


def start_web_server(out_dir: Path, port: int) -> ThreadingHTTPServer:
    handler = type("BoundCountsHandler", (CountsHandler,), {"out_dir": out_dir})
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def lan_ip() -> str:
    """The address other devices on your Wi-Fi can reach this PC at."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))  # no packets are sent; this just picks the route
            return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"


def cmd_run(cfg: dict, base: Path) -> int:
    import mss  # imported here so the other commands work without a display

    templates = load_templates(cfg, base)
    out_dir = (base / cfg["output_dir"]).resolve()
    counter = ChestCounter(
        templates, cfg["threshold"], cfg["cooldown_seconds"],
        counts=read_saved_counts(out_dir),
    )
    write_outputs(out_dir, counter.counts)

    if cfg.get("web_port"):
        port = int(cfg["web_port"])
        try:
            start_web_server(out_dir, port)
            print(f"Counter page for iPad/iPhone (same Wi-Fi): http://{lan_ip()}:{port}")
            print("If it does not load, allow Python through Windows Firewall on private networks.")
        except OSError as exc:
            print(f"Could not start counter page on port {port}: {exc}", file=sys.stderr)

    left, top, width, height = cfg["region"]
    monitor = {"left": left, "top": top, "width": width, "height": height}
    interval = 1.0 / float(cfg["fps"])

    print(f"Tracking region {monitor} at {cfg['fps']} fps. Ctrl+C to stop.")
    print(f"Current totals: {counter.counts}")
    with mss.mss() as sct:
        try:
            while True:
                t0 = time.monotonic()
                shot = np.array(sct.grab(monitor))
                gray = cv2.cvtColor(shot, cv2.COLOR_BGRA2GRAY)
                for name in counter.process(gray, t0):
                    print(f"[{time.strftime('%H:%M:%S')}] +1 {LABELS.get(name, name)} "
                          f"-> {counter.counts[name]}")
                    write_outputs(out_dir, counter.counts)
                time.sleep(max(0.0, interval - (time.monotonic() - t0)))
        except KeyboardInterrupt:
            print("\nStopped. Final totals:")
            for name, value in counter.counts.items():
                print(f"  {LABELS.get(name, name)}: {value}")
    return 0


def cmd_snapshot(cfg: dict, base: Path, out: str) -> int:
    import mss

    left, top, width, height = cfg["region"]
    monitor = {"left": left, "top": top, "width": width, "height": height}
    with mss.mss() as sct:
        shot = np.array(sct.grab(monitor))
    path = Path(out)
    cv2.imwrite(str(path), cv2.cvtColor(shot, cv2.COLOR_BGRA2BGR))
    print(f"Saved region screenshot to {path.resolve()}")
    return 0


def cmd_crop(image: str, x: int, y: int, w: int, h: int, out: str) -> int:
    img = cv2.imread(image, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Cannot read image: {image}", file=sys.stderr)
        return 1
    crop = img[y:y + h, x:x + w]
    if crop.size == 0:
        print("Crop is empty: check x, y, w, h against the image size "
              f"{img.shape[1]}x{img.shape[0]}", file=sys.stderr)
        return 1
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(out, crop)
    print(f"Wrote template {Path(out).resolve()} ({w}x{h})")
    return 0


def cmd_select(image: str, out: str) -> int:
    """Open the screenshot and let you drag a box with the mouse to save it as a template."""
    img = cv2.imread(image, cv2.IMREAD_COLOR)
    if img is None:
        print(f"Cannot read image: {image}", file=sys.stderr)
        return 1
    print("Drag a box around the chest notification, then press ENTER (or SPACE). ESC cancels.")
    x, y, w, h = cv2.selectROI("Select template", img, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()
    if w == 0 or h == 0:
        print("Nothing selected.", file=sys.stderr)
        return 1
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(out, img[y:y + h, x:x + w])
    print(f"Saved template {Path(out).resolve()} ({w}x{h})")
    return 0


def cmd_check(cfg: dict, base: Path, image: str) -> int:
    """Print match scores for each template against a screenshot, to calibrate the threshold."""
    frame = cv2.imread(image, cv2.IMREAD_GRAYSCALE)
    if frame is None:
        print(f"Cannot read image: {image}", file=sys.stderr)
        return 1
    templates = load_templates(cfg, base)
    for name, tpl in templates.items():
        score = best_score(frame, tpl)
        verdict = "MATCH" if score >= cfg["threshold"] else "no match"
        print(f"{LABELS.get(name, name):<14} score={score:.3f}  {verdict} "
              f"(threshold {cfg['threshold']})")
    return 0


def cmd_reset(cfg: dict, base: Path) -> int:
    out_dir = (base / cfg["output_dir"]).resolve()
    counts = {name: 0 for name in cfg["templates"]}
    write_outputs(out_dir, counts)
    print(f"Counters reset in {out_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--config", default=str(HERE / "config.json"), help="path to config.json")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("run", help="track live from the screen region")
    s = sub.add_parser("snapshot", help="save a screenshot of the scan region (to crop templates from)")
    s.add_argument("out", nargs="?", default=str(HERE / "templates" / "region.png"))
    c = sub.add_parser("crop", help="cut a template out of a screenshot")
    c.add_argument("image")
    for field in ("x", "y", "w", "h"):
        c.add_argument(field, type=int)
    c.add_argument("out")
    sel = sub.add_parser("select", help="drag a box on a screenshot to save a template")
    sel.add_argument("image")
    sel.add_argument("out")
    k = sub.add_parser("check", help="show match scores for an image without counting")
    k.add_argument("image")
    sub.add_parser("reset", help="set all counters back to 0")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    config_path = Path(args.config).resolve()
    cfg = load_config(config_path)
    base = config_path.parent

    if args.command == "run":
        return cmd_run(cfg, base)
    if args.command == "snapshot":
        return cmd_snapshot(cfg, base, args.out)
    if args.command == "crop":
        return cmd_crop(args.image, args.x, args.y, args.w, args.h, args.out)
    if args.command == "select":
        return cmd_select(args.image, args.out)
    if args.command == "check":
        return cmd_check(cfg, base, args.image)
    if args.command == "reset":
        return cmd_reset(cfg, base)
    return 1


if __name__ == "__main__":
    sys.exit(main())
