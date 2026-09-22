import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch
from pathlib import Path
import cv2
import numpy as np
from app.config import Settings
from app.runtime import Runtime
from app.storage.database import Store
from app.video import VideoFileSource,media_timestamp
from app.videos import imported_filename,inspect_video

class VideoSourceTests(unittest.TestCase):
    def test_imported_video_metadata_and_filename_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'lesson.mp4'
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'mp4v'),10,(64,48))
            self.assertTrue(writer.isOpened())
            for _ in range(3): writer.write(np.zeros((48,64,3),dtype=np.uint8))
            writer.release()
            metadata=inspect_video(path)
            self.assertEqual(metadata['resolution'],[64,48]);self.assertAlmostEqual(metadata['duration_s'],.3,delta=.12)
            self.assertEqual(imported_filename('../lesson.mp4'),'lesson.mp4')
            with self.assertRaises(ValueError): imported_filename('notes.txt')
    def test_explicit_source_environment_overrides_saved_setting(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);store=Store(root/"state.sqlite3")
            store.save_settings({"input_source":"CAMERA","video_path":"old.mp4"})
            settings=Settings(input_source="VIDEO",video_path="new.mp4",database=store.path,
                sessions_dir=root/"sessions",timelapse_enabled=False)
            with patch.dict("os.environ",{"NAZAR_INPUT_SOURCE":"VIDEO","NAZAR_VIDEO_PATH":"new.mp4"}):
                runtime=Runtime(settings,store=store)
            self.assertEqual(runtime.settings.input_source,"VIDEO")
            self.assertEqual(runtime.camera.path.name,"new.mp4")

    def test_runtime_replays_video_through_same_pipeline_for_session(self):
        class CountingPipeline:
            def __init__(self): self.calls=0;self.resets=0
            def load(self): pass
            def process(self,frame,timestamp):
                self.calls+=1
                return [{"track_id":1,"attributes":[]}]
            def reset_tracks(self): self.resets+=1
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/"sample.mp4"
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),10,(64,48))
            self.assertTrue(writer.isOpened())
            for i in range(5): writer.write(np.full((48,64,3),i*30,dtype=np.uint8))
            writer.release()
            pipeline=CountingPipeline()
            settings=Settings(input_source="VIDEO",video_path=str(path),database=root/"state.sqlite3",
                sessions_dir=root/"sessions",timelapse_enabled=False)
            runtime=Runtime(settings,pipeline=pipeline)
            try:
                runtime.start()
                deadline=time.time()+3
                while time.time()<deadline and not runtime.camera.status()["ended"]: time.sleep(.02)
                self.assertTrue(runtime.camera.status()["ended"])
                first_pass=pipeline.calls
                self.assertGreater(first_pass,0)
                deadline=time.time()+5
                while time.time()<deadline and runtime.state()["visible_people"]: time.sleep(.02)
                self.assertEqual(runtime.state()["visible_people"],0)
                session=runtime.start_session("LESSON")
                deadline=time.time()+3
                while time.time()<deadline and not runtime.camera.status()["ended"]: time.sleep(.02)
                self.assertTrue(runtime.camera.status()["ended"])
                self.assertGreater(pipeline.calls,first_pass)
                self.assertGreaterEqual(pipeline.resets,1)
                deadline=time.time()+5
                while time.time()<deadline and runtime.state()["visible_people"]: time.sleep(.02)
                self.assertEqual(runtime.state()["visible_people"],0)
                saved=runtime.stop_session()
                self.assertEqual(saved["id"],session["id"])
                self.assertEqual(saved["source_type"],"VIDEO")
                self.assertEqual(saved["source_name"],"sample.mp4")
            finally:
                runtime.close()

    def test_video_source_preserves_media_time_and_ends(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"sample.mp4"
            writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),10,(64,48))
            self.assertTrue(writer.isOpened())
            for i in range(5): writer.write(np.full((48,64,3),i*30,dtype=np.uint8))
            writer.release()
            source=VideoFileSource(path);source.start()
            until=time.time()+3
            while time.time()<until and not source.status()["ended"]: time.sleep(.05)
            status=source.status();sequence,timestamp,frame=source.latest()
            source.close()
            self.assertTrue(status["ended"])
            self.assertEqual(sequence,5)
            self.assertAlmostEqual(timestamp,.4,delta=.12)
            self.assertEqual(frame.shape,(48,64,3))

    def test_database_migrates_existing_v1_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/"old.sqlite3"
            db=sqlite3.connect(path)
            db.execute("CREATE TABLE sessions(id INTEGER PRIMARY KEY,mode TEXT,started_at TEXT,ended_at TEXT,track_count INTEGER DEFAULT 0,summary_json TEXT DEFAULT '{}')")
            db.execute("CREATE TABLE events(id INTEGER PRIMARY KEY,session_id INTEGER,occurred_at TEXT,track_id INTEGER,event_type TEXT,confidence REAL)")
            db.execute("INSERT INTO sessions(id,mode,started_at) VALUES (1,'LESSON','2026-01-01T00:00:00+00:00')")
            db.commit();db.close()
            store=Store(path)
            item=store.session(1)
            self.assertEqual(item["source_type"],"CAMERA")
            self.assertIsNone(item["source_name"])
            self.assertIsNone(item["teacher"])
            self.assertIsNone(item["class_name"])
            self.assertIsNone(item["subject"])
            self.assertIsNone(item["notes"])
            self.assertEqual(store.session_analytics(1)["event_timeline"],[])
            check=sqlite3.connect(path)
            try:
                self.assertEqual(check.execute('PRAGMA user_version').fetchone()[0],4)
            finally:
                check.close()

if __name__=='__main__': unittest.main()
