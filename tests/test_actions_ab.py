import tempfile
import unittest
from pathlib import Path
import numpy as np

from app.config import Settings
from app.pipeline import VisionPipeline
from app.vision.ab import AsyncABLogger
from tests.test_pipeline import FakePose, FakeActions, FakeHead


class FakeShadow:
    enabled = True
    loaded = True
    latency_ms = 2.0
    thresholds = {"READING": .5, "WRITING": .5}
    def __init__(self):
        self.crops = None
        self.logger = type("L", (), {"record": lambda *_a, **_k: None, "summary": lambda _s: {}, "close": lambda _s: None})()
    def load(self): pass
    def infer(self, crops):
        self.crops = crops
        return np.tile([[.9, .8]], (len(crops), 1)).astype(np.float32)
    def close(self): pass


class ABTests(unittest.TestCase):
    def test_same_crops_and_shadow_does_not_change_production_attributes(self):
        settings = Settings(actions_ab_enabled=True)
        shadow = FakeShadow()
        pipeline = VisionPipeline(settings, FakePose(), FakeActions(), FakeHead(), actions_ab=shadow)
        frame = np.zeros((120, 200, 3), dtype=np.uint8)
        tracks = pipeline.process(frame, 1.0)
        # V6.1 assigns the first public identity immediately and keeps the
        # simultaneous second detection pending until there is count evidence.
        self.assertEqual(len(shadow.crops), 1)
        self.assertTrue(all("actions_ab" in t for t in tracks))
        self.assertFalse(any(a["source"] == "shadow" for t in tracks for a in t["attributes"]))

    def test_async_logger_writes_rows_and_throttles_disagreement_crops(self):
        with tempfile.TemporaryDirectory() as d:
            logger = AsyncABLogger(Path(d)); logger.set_session("s1")
            crop = np.zeros((20, 20, 3), np.uint8)
            for timestamp in (0.0, 1.0, 2.1):
                logger.record(timestamp, 3, crop, [.1, .1], [.9, .9], {"READING": .5, "WRITING": .5})
            logger.close()
            self.assertEqual(len(list((Path(d) / "s1" / "disagreements").glob("*.jpg"))), 4)
            self.assertIn("v1_reading_probability", (Path(d) / "s1_actions_ab.csv").read_text())
            self.assertEqual(logger.summary()["classes"]["READING"]["disagreement"], 3)


if __name__ == "__main__":
    unittest.main()
