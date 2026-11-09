# language: Python 3, file: test_chest_tracker.py, run: python -m unittest discover -s chest_tracker/tests
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import chest_tracker as ct  # noqa: E402


def make_template(seed: int, h: int = 24, w: int = 48) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.integers(0, 256, size=(h, w), dtype=np.uint8)


def make_frame(template=None, at=(40, 90), size=(220, 320), seed=0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 256, size=size, dtype=np.uint8)
    if template is not None:
        y, x = at
        frame[y:y + template.shape[0], x:x + template.shape[1]] = template
    return frame


class EdgeDetectorTests(unittest.TestCase):
    def test_fires_once_while_match_stays_visible(self):
        d = ct.EdgeDetector(threshold=0.8, cooldown=0.0)
        fires = [d.update(0.95, t) for t in (0.0, 0.2, 0.4, 0.6)]
        self.assertEqual(fires, [True, False, False, False])

    def test_fires_again_after_match_disappears(self):
        d = ct.EdgeDetector(threshold=0.8, cooldown=0.0)
        fires = [d.update(s, t) for s, t in [(0.9, 0), (0.1, 1), (0.9, 2)]]
        self.assertEqual(fires, [True, False, True])

    def test_cooldown_blocks_quick_repeat(self):
        d = ct.EdgeDetector(threshold=0.8, cooldown=3.0)
        fires = [d.update(s, t) for s, t in [(0.9, 0), (0.1, 1), (0.9, 2), (0.1, 3), (0.9, 4)]]
        self.assertEqual(fires, [True, False, False, False, True])


class CounterTests(unittest.TestCase):
    def test_counts_open_and_break_separately(self):
        open_tpl = make_template(1)
        break_tpl = make_template(2)
        counter = ct.ChestCounter(
            {"chest_open": open_tpl, "chest_break": break_tpl},
            threshold=0.85, cooldown=0.0,
        )
        t = 0.0
        frames = [
            make_frame(open_tpl, seed=10),   # open 1
            make_frame(open_tpl, seed=11),   # still visible, no new count
            make_frame(seed=12),             # gone
            make_frame(break_tpl, seed=13),  # break 1
            make_frame(seed=14),
            make_frame(open_tpl, seed=15),   # open 2
        ]
        for f in frames:
            counter.process(f, t)
            t += 0.2
        self.assertEqual(counter.counts, {"chest_open": 2, "chest_break": 1})

    def test_no_false_positive_on_noise(self):
        tpl = make_template(3)
        counter = ct.ChestCounter({"chest_open": tpl}, threshold=0.85, cooldown=0.0)
        for i in range(20):
            counter.process(make_frame(seed=100 + i), i * 0.2)
        self.assertEqual(counter.counts, {"chest_open": 0})

    def test_template_bigger_than_frame_scores_zero(self):
        self.assertEqual(ct.best_score(make_frame(size=(10, 10)), make_template(4)), 0.0)

    def test_initial_counts_are_restored(self):
        tpl = make_template(5)
        counter = ct.ChestCounter({"chest_open": tpl}, 0.85, 0.0, counts={"chest_open": 7})
        counter.process(make_frame(tpl), 0.0)
        self.assertEqual(counter.counts["chest_open"], 8)


class OutputTests(unittest.TestCase):
    def test_writes_readable_text_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "counts"
            ct.write_outputs(out, {"chest_open": 1, "chest_break": 1})
            text = (out / "counts.txt").read_text(encoding="utf-8")
            self.assertEqual(text, "Chest opens: 1\nChest breaks: 1\n")
            self.assertEqual(ct.read_saved_counts(out), {"chest_open": 1, "chest_break": 1})


if __name__ == "__main__":
    unittest.main()
