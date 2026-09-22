import unittest
from pathlib import Path
import numpy as np
from app.config import Settings
from app.events import EventEngine
from app.pipeline import VisionPipeline
from app.vision.types import Detection

def keypoints(x):
    kp=np.zeros((17,3),dtype=np.float32)
    for i in range(7): kp[i]=[x+20,20,.95]
    return kp

class FakePose:
    def __init__(self):
        self.calls=0;self.model=object();self.path=Path("pose.pt");self.device="cpu";self.latency_ms=1
    def load(self): pass
    def infer(self,frame):
        self.calls+=1
        detections=[Detection((10,10,70,110),keypoints(10),.9,10),Detection((130,10,190,110),keypoints(130),.9,20)]
        if self.calls<=25:return detections[:1]
        return detections if self.calls%2 else detections[::-1]

class FakeActions:
    def __init__(self):
        self.thresholds={"READING":.39,"WRITING":.41};self.model=object();self.weights=Path("actions.pt");self.device="cpu";self.latency_ms=1
    def load(self): pass
    def infer(self,crops):
        return np.array([[.9,.1] if crop[128,128,2]>crop[128,128,0] else [.1,.9] for crop in crops],dtype=np.float32)

class FakeHead:
    def __init__(self):
        self.model=object();self.weights=Path("head.pt");self.device="cpu";self.latency_ms=1
    def load(self): pass
    def infer(self,crops):
        return np.array([[0,-30] if crop[128,128,2]>crop[128,128,0] else [0,30] for crop in crops],dtype=np.float32)
    def classify(self,pitch,yaw): return "LOOKING_LEFT" if yaw<0 else "LOOKING_RIGHT"

class PipelineTests(unittest.TestCase):
    def test_single_pose_pass_and_multi_person_association(self):
        frame=np.zeros((120,200,3),dtype=np.uint8)
        frame[:,:100]=[10,20,200];frame[:,100:]=[200,20,10]
        pose=FakePose()
        pipeline=VisionPipeline(Settings(),pose,FakeActions(),FakeHead())
        for n in range(25): tracks=pipeline.process(frame,n*.04)
        for n in range(15): tracks=pipeline.process(frame,1+n*.1)
        self.assertEqual(pose.calls,40)
        self.assertEqual({t["track_id"] for t in tracks},{1,2})
        by_id={t["track_id"]:{a["name"] for a in t["attributes"]} for t in tracks}
        self.assertIn("READING",by_id[1]);self.assertNotIn("WRITING",by_id[1])
        self.assertIn("WRITING",by_id[2]);self.assertNotIn("READING",by_id[2])
        self.assertIn("LOOKING_LEFT",by_id[1]);self.assertIn("LOOKING_RIGHT",by_id[2])

    def test_event_confirmation_and_cooldown(self):
        engine=EventEngine(minimum_s=1,cooldown_s=5)
        track={"track_id":1,"attributes":[{"name":"HAND_RAISED","confidence":None}]}
        self.assertEqual(engine.update([track],0),[])
        self.assertEqual(len(engine.update([track],1.2)),1)
        self.assertEqual(engine.update([track],3),[])
        engine.update([],3.5)
        engine.update([track],4)
        self.assertEqual(engine.update([track],5.1),[])
        engine.update([],6)
        engine.update([track],7)
        self.assertEqual(len(engine.update([track],8.1)),1)

    def test_missing_optional_model_does_not_stop_pose(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            missing=Path(directory)/'missing.pt'
            frame=np.zeros((120,200,3),dtype=np.uint8)
            for subsystem in ('actions','head'):
                settings=Settings(device='cpu')
                setattr(settings,subsystem[:-1]+'_weights' if subsystem=='actions' else 'head_weights',missing)
                pose=FakePose()
                pipeline=VisionPipeline(settings,pose=pose)
                with self.assertLogs('app.pipeline',level='ERROR'):
                    pipeline.load()
                self.assertIsNotNone(pipeline.errors[subsystem])
                tracks=pipeline.process(frame,1.0)
                self.assertEqual(pose.calls,1)
                self.assertEqual(len(tracks),1)

if __name__=="__main__": unittest.main()
