import tempfile
import time
import unittest
from pathlib import Path
import numpy as np
from app.sessions import SessionManager
from app.storage.database import Store
from app.timelapse import TimelapseRecorder

class FakeCamera:
    def __init__(self): self.sequence=0
    def latest(self):
        self.sequence+=1
        return self.sequence,time.time(),np.zeros((64,96,3),dtype=np.uint8)

class FailingRecorder:
    def start(self,session_id): raise RuntimeError("encoder unavailable")
    def stop(self): raise RuntimeError("encoder unavailable")

class StorageSessionTests(unittest.TestCase):
    def test_exam_metadata_survives_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"test.sqlite3"
            manager=SessionManager(Store(path),FailingRecorder())
            active=manager.start("EXAM",metadata={"teacher":" Proctor ","class_name":"11A","subject":"Physics","notes":"Final"})
            manager.stop()
            reloaded=Store(path).session(active["id"])
            self.assertEqual((reloaded["teacher"],reloaded["class_name"],reloaded["subject"],reloaded["notes"]),
                ("Proctor","11A","Physics","Final"))

    def test_session_events_and_timelapse(self):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory)
            store=Store(base/"test.sqlite3")
            recorder=TimelapseRecorder(FakeCamera(),base/"sessions",interval=.03,fps=12)
            manager=SessionManager(store,recorder,event_min_duration=.01)
            active=manager.start("LESSON")
            track={"track_id":2,"attributes":[{"name":"HAND_RAISED","confidence":None}]}
            manager.observe([track],time.time())
            time.sleep(.08)
            manager.observe([track],time.time())
            result=manager.stop()
            self.assertEqual(result["mode"],"LESSON")
            self.assertEqual(result["track_count"],1)
            self.assertEqual(result["event_count"],1)
            self.assertTrue(result["timelapse_available"])
            self.assertGreater(result["timelapse_frames"],0)
            self.assertTrue(Path(result["timelapse_path"]).is_file())
            self.assertEqual(len(store.events(session_id=active["id"])),1)

    def test_one_active_session_and_recording_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/"test.sqlite3")
            manager=SessionManager(store,FailingRecorder())
            manager.start("EXAM")
            with self.assertRaises(RuntimeError): manager.start("LESSON")
            result=manager.stop()
            self.assertFalse(result["timelapse_available"])
            self.assertEqual(result["timelapse_error"],"encoder unavailable")

if __name__=="__main__": unittest.main()
