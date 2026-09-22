import unittest
import numpy as np
from app.vision.tracker import TrackManager
from app.vision.types import Detection, Track
from app.vision.temporal import PersonTemporalState

class RuntimeFixTests(unittest.TestCase):
    def test_gap_reassociation_keeps_id_but_long_gap_expires(self):
        kp=np.zeros((17,3),np.float32); m=TrackManager(max_missed=99,max_gap_s=2.5)
        first=m.update([Detection((0,0,40,100),kp,.9,17)],0.0)
        m.update([],1.0); returned=m.update([Detection((2,0,42,100),kp,.9,31)],2.0)
        self.assertEqual(returned[0].track_id,first[0].track_id)
        m.update([],3.0);m.update([],6.0)
        self.assertEqual(m.expired,[1])

    def _track(self, wrist_x):
        kp=np.zeros((17,3),np.float32); kp[:,2]=.9
        kp[9,:2]=[wrist_x,55];kp[10,:2]=[wrist_x+8,55]
        return Track(1,(0,0,100,100),kp,.9,0)

    def test_writing_requires_model_and_motion_evidence(self):
        state=PersonTemporalState(); t=self._track(20)
        for i in range(8): state.update(t,[.05,.50],None,lambda p,y:'LOOKING_DOWN',{'READING':.39,'WRITING':.41},i*.2)
        self.assertNotIn('WRITING',[a['name'] for a in state.update(t,[.05,.50],None,lambda p,y:'LOOKING_DOWN',{'READING':.39,'WRITING':.41},2.0)['attributes']])
        for i in range(8,18): state.update(self._track(20+i*2),[.05,.50],None,lambda p,y:'LOOKING_DOWN',{'READING':.39,'WRITING':.41},i*.2)
        result=state.update(self._track(60),[.05,.50],None,lambda p,y:'LOOKING_DOWN',{'READING':.39,'WRITING':.41},3.6)
        self.assertIn('WRITING',[a['name'] for a in result['attributes']])
        self.assertGreater(result['actions_temporal']['writing_motion_score'],0)

if __name__=='__main__': unittest.main()
