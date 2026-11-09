"""Visual detection: template matching with edge detection, so one on-screen event counts once.

Templates are small crops of the chest notification, saved by the calibration dialog.
Nothing here reads game memory or sends input to the game.
"""

from pathlib import Path

import cv2
import numpy as np

KINDS = ("chest_open", "chest_break")
LABELS = {"chest_open": "Cofre abierto", "chest_break": "Cofre destruido"}


def best_score(frame_gray: np.ndarray, template_gray: np.ndarray) -> float:
    fh, fw = frame_gray.shape[:2]
    th, tw = template_gray.shape[:2]
    if th > fh or tw > fw or th == 0 or tw == 0:
        return 0.0
    result = cv2.matchTemplate(frame_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    result = np.nan_to_num(result, nan=0.0, neginf=0.0)
    return float(result.max())


class EdgeDetector:
    """Fires once when a match appears; waits for it to disappear and for the cooldown."""

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


def load_templates(paths: dict) -> dict:
    """Load grayscale templates for every kind whose file exists and is readable."""
    templates = {}
    for kind, path in paths.items():
        path = Path(path)
        if not path.exists():
            continue
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if img is not None and img.size:
            templates[kind] = img
    return templates


class Detector:
    def __init__(self, templates: dict, threshold: float, cooldown: float):
        self.templates = dict(templates)
        self.detectors = {k: EdgeDetector(threshold, cooldown) for k in self.templates}

    def scores(self, frame_gray: np.ndarray) -> dict:
        return {k: best_score(frame_gray, tpl) for k, tpl in self.templates.items()}

    def process(self, frame_gray: np.ndarray, now: float) -> list:
        """Returns [(kind, score)] for events that start on this frame."""
        fired = []
        for kind, tpl in self.templates.items():
            score = best_score(frame_gray, tpl)
            if self.detectors[kind].update(score, now):
                fired.append((kind, score))
        return fired


def scan_video(path, templates: dict, threshold: float, cooldown: float,
               every_n: int = 1, progress=None) -> list:
    """Run the detector over a video file. Returns [(seconds, kind, score)]."""
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise OSError(f"No se pudo abrir el video: {path}")
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    detector = Detector(templates, threshold, cooldown)
    events = []
    index = 0
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            if index % every_n == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                seconds = index / fps
                for kind, score in detector.process(gray, seconds):
                    events.append((seconds, kind, score))
            index += 1
            if progress and total and index % 60 == 0:
                progress(index / total)
    finally:
        cap.release()
    return events
