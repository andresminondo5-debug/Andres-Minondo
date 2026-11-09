# language: Python 3, run: python -m unittest discover -s PirateShopTracker/tests -v
import sys
import tempfile
import time
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import detector as det  # noqa: E402
from app.engine import TrackerEngine  # noqa: E402
from app.storage import Storage  # noqa: E402


def noise_frame(seed: int, size=(240, 360)) -> np.ndarray:
    return np.random.default_rng(seed).integers(0, 256, size=size, dtype=np.uint8)


def paste(frame: np.ndarray, tpl: np.ndarray, at=(60, 120)) -> np.ndarray:
    out = frame.copy()
    y, x = at
    out[y:y + tpl.shape[0], x:x + tpl.shape[1]] = tpl
    return out


class StorageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.tmp.name) / "t.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_events_are_totalled_and_split_by_kind(self):
        sid = self.db.start_session(time.time() - 60)
        self.db.add_event(sid, time.time(), "chest_open", 0.9)
        self.db.add_event(sid, time.time(), "chest_open", 0.9)
        self.db.add_event(sid, time.time(), "chest_break", 0.9)
        self.assertEqual(self.db.totals(), {"chest_open": 2, "chest_break": 1})
        self.assertEqual(self.db.counts_since(time.time() - 3600), {"chest_open": 2, "chest_break": 1})

    def test_session_summary_and_active_time(self):
        start = time.time() - 3600
        sid = self.db.start_session(start)
        self.db.add_event(sid, start + 10, "chest_break", 0.9)
        self.db.end_session(sid, start + 1800)
        rows = self.db.sessions(time.time())
        self.assertEqual(rows[0]["break"], 1)
        self.assertEqual(rows[0]["open"], 0)
        self.assertAlmostEqual(rows[0]["duration"], 1800, places=3)
        self.assertAlmostEqual(self.db.active_seconds(time.time()), 1800, places=3)

    def test_reopening_storage_closes_crashed_sessions(self):
        path = Path(self.tmp.name) / "crash.db"
        first = Storage(path)
        sid = first.start_session(time.time() - 100)
        first.add_event(sid, time.time() - 50, "chest_open", 0.9)
        first.close()
        second = Storage(path)
        rows = second.sessions(time.time())
        self.assertFalse(rows[0]["open_now"])
        second.close()


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.tpl_open = np.random.default_rng(1).integers(0, 256, (24, 48), dtype=np.uint8)
        self.tpl_break = np.random.default_rng(2).integers(0, 256, (24, 48), dtype=np.uint8)
        self.templates = {"chest_open": self.tpl_open, "chest_break": self.tpl_break}

    def test_counts_each_event_once_and_keeps_kinds_apart(self):
        d = det.Detector(self.templates, threshold=0.85, cooldown=0.0)
        frames = [
            paste(noise_frame(10), self.tpl_open),
            paste(noise_frame(11), self.tpl_open),   # same notification still visible
            noise_frame(12),
            paste(noise_frame(13), self.tpl_break),
            noise_frame(14),
            paste(noise_frame(15), self.tpl_open),
        ]
        fired = []
        for i, f in enumerate(frames):
            fired += [kind for kind, _ in d.process(f, i * 0.25)]
        self.assertEqual(fired, ["chest_open", "chest_break", "chest_open"])

    def test_pure_noise_never_fires(self):
        d = det.Detector(self.templates, threshold=0.85, cooldown=0.0)
        for i in range(30):
            self.assertEqual(d.process(noise_frame(100 + i), i * 0.2), [])

    def test_load_templates_skips_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            good = Path(tmp) / "open.png"
            cv2.imwrite(str(good), self.tpl_open)
            loaded = det.load_templates({"chest_open": good, "chest_break": Path(tmp) / "nope.png"})
            self.assertEqual(list(loaded), ["chest_open"])

    def test_scan_video_finds_event_in_real_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clip.avi"
            w, h, fps = 360, 240, 10
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), fps, (w, h))
            for i in range(40):
                frame = noise_frame(200 + i)
                if 15 <= i < 20:
                    frame = paste(frame, self.tpl_break)
                writer.write(cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR))
            writer.release()
            events = det.scan_video(path, self.templates, 0.85, 0.0)
            kinds = [k for _, k, _ in events]
            self.assertEqual(kinds, ["chest_break"])
            self.assertAlmostEqual(events[0][0], 1.5, delta=0.2)


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Storage(Path(self.tmp.name) / "t.db")
        self.settings = {"fps": 4, "threshold": 0.85, "cooldown_seconds": 0.0,
                         "require_fortnite": False}
        self.engine = TrackerEngine(self.settings, self.db)
        self.tpl = np.random.default_rng(7).integers(0, 256, (24, 48), dtype=np.uint8)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_no_templates_means_nothing_is_counted(self):
        self.engine.detector = None
        self.engine._begin_session()
        self.assertEqual(self.engine.handle_frame(paste(noise_frame(1), self.tpl), time.time()), [])
        self.assertEqual(self.db.totals(), {})

    def test_detected_events_are_stored_with_session(self):
        self.engine.detector = det.Detector({"chest_open": self.tpl}, 0.85, 0.0)
        self.engine._begin_session()
        self.engine.handle_frame(paste(noise_frame(2), self.tpl), 1000.0)
        self.engine.handle_frame(noise_frame(3), 1001.0)
        self.engine.handle_frame(paste(noise_frame(4), self.tpl), 1002.0)
        snap = self.engine.snapshot()
        self.assertEqual(snap["counts"]["chest_open"], 2)
        self.assertEqual(self.db.totals(), {"chest_open": 2})
        self.engine._end_session()
        self.assertIsNone(self.engine.snapshot()["session_started"])

    def test_fortnite_check_returns_a_bool(self):
        from app.engine import fortnite_running
        self.assertIsInstance(fortnite_running(), bool)


if __name__ == "__main__":
    unittest.main()
