#!/usr/bin/env python3
"""Chest tracker: counts chest opens and chest breaks by watching a screen region.

It only reads pixels. Each event is detected by template matching a small
image you cropped from the game (for example the "chest opened" feedback),
and the counters are written to counts/counts.txt for OBS or any text reader.
"""

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent

DEFAULT_CONFIG = {
    # Screen area to scan: [left, top, width, height] in pixels of the monitor.
    "region": [660, 300, 600, 300],
    "fps": 5,
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


def cmd_run(cfg: dict, base: Path) -> int:
    import mss  # imported here so the other commands work without a display

    templates = load_templates(cfg, base)
    out_dir = (base / cfg["output_dir"]).resolve()
    counter = ChestCounter(
        templates, cfg["threshold"], cfg["cooldown_seconds"],
        counts=read_saved_counts(out_dir),
    )
    write_outputs(out_dir, counter.counts)

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
    if args.command == "check":
        return cmd_check(cfg, base, args.image)
    if args.command == "reset":
        return cmd_reset(cfg, base)
    return 1


if __name__ == "__main__":
    sys.exit(main())
