"""Tracking engine: captures the screen, runs the detector and writes every counted event to storage.

It runs on its own thread, so the window stays responsive. It counts only what the detector
confirms on screen. With no calibrated templates it counts nothing.
"""

import threading
import time

import cv2
import numpy as np
import psutil

from . import config
from . import detector as det


def fortnite_running() -> bool:
    wanted = config.GAME_PROCESS.lower()
    for proc in psutil.process_iter(["name"]):
        try:
            if (proc.info.get("name") or "").lower() == wanted:
                return True
        except psutil.Error:
            continue
    return False


def templates_ready() -> bool:
    return all(config.template_path(k).exists() for k in det.KINDS)


class TrackerEngine:
    def __init__(self, settings: dict, storage):
        self.settings = settings
        self.storage = storage
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self.running = False
        self.status = "Detenido"
        self.detector = None
        self.session_id = None
        self.session_started = None
        self.counts = {k: 0 for k in det.KINDS}
        self.last_event = None

    # ---- setup -------------------------------------------------------------

    def reload_templates(self) -> bool:
        if not templates_ready():
            with self._lock:
                self.detector = None
            return False
        templates = det.load_templates({k: config.template_path(k) for k in det.KINDS})
        if len(templates) < len(det.KINDS):
            with self._lock:
                self.detector = None
            return False
        new_detector = det.Detector(templates, float(self.settings["threshold"]),
                                    float(self.settings["cooldown_seconds"]))
        with self._lock:
            self.detector = new_detector
        return True

    # ---- control -------------------------------------------------------------

    def start(self) -> bool:
        if self.running:
            return True
        if not self.reload_templates():
            self.status = "Calibra el detector primero"
            return False
        self._stop.clear()
        self.running = True
        self.status = "Iniciando…"
        self._thread = threading.Thread(target=self._loop, name="tracker", daemon=True)
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        self.running = False
        self.status = "Detenido"

    # ---- processing ------------------------------------------------------------

    def handle_frame(self, gray: np.ndarray, now: float) -> list:
        with self._lock:
            detector = self.detector
            session_id = self.session_id
        if detector is None or session_id is None:
            return []
        events = detector.process(gray, now)
        for kind, score in events:
            self.storage.add_event(session_id, now, kind, score)
            with self._lock:
                self.counts[kind] += 1
                self.last_event = (kind, now)
        return events

    def _begin_session(self) -> None:
        now = time.time()
        sid = self.storage.start_session(now)
        with self._lock:
            self.session_id = sid
            self.session_started = now
            self.counts = {k: 0 for k in det.KINDS}

    def _end_session(self) -> None:
        with self._lock:
            sid = self.session_id
            self.session_id = None
        if sid is not None:
            self.storage.end_session(sid, time.time())
        with self._lock:
            self.session_started = None

    def _loop(self) -> None:
        import mss  # imported here so the rest of the app works without a display

        interval = 1.0 / max(1, int(self.settings["fps"]))
        need_game = bool(self.settings["require_fortnite"])
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                while not self._stop.is_set():
                    t0 = time.monotonic()
                    if need_game and not fortnite_running():
                        if self.session_id is not None:
                            self._end_session()
                        self.status = "Esperando a Fortnite…"
                        self._stop.wait(5)
                        continue
                    if self.session_id is None:
                        self._begin_session()
                    try:
                        shot = np.array(sct.grab(monitor))
                    except Exception as exc:  # display changed, capture refused, etc.
                        self.status = f"Error de captura: {exc}"
                        self._stop.wait(2)
                        continue
                    self.status = "Grabando pantalla"
                    gray = cv2.cvtColor(shot, cv2.COLOR_BGRA2GRAY)
                    self.handle_frame(gray, time.time())
                    self._stop.wait(max(0.0, interval - (time.monotonic() - t0)))
        except Exception as exc:
            self.status = f"Error del seguimiento: {exc}"
        finally:
            self._end_session()
            self.running = False

    # ---- read-only view for the UI --------------------------------------------------

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "running": self.running,
                "status": self.status,
                "counts": dict(self.counts),
                "session_started": self.session_started,
                "last_event": self.last_event,
                "has_detector": self.detector is not None,
            }
