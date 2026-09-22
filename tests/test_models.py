import unittest
import numpy as np
from app.config import Settings
from app.vision.crops import make_person_crop,make_head_crop,tensor_from_bgr
from app.vision.geometry import pose_body_state,hand_raised_state
from app.vision.models import ActionsAdapter,HeadAdapter
from app.vision.models import PoseAdapter,select_device
from app.vision.temporal import PersonTemporalState
from app.vision.tracker import TrackManager
from app.vision.types import Detection,Track

class ModelContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.settings=Settings.from_env()

    def test_crops_and_preprocessing(self):
        frame=np.zeros((100,160,3),dtype=np.uint8)
        frame[:]=[20,80,220]
        box=(0,0,50,90)
        kp=np.zeros((17,3),dtype=np.float32)
        kp[0]=[20,14,.9];kp[1]=[10,12,.9]
        person=make_person_crop(frame,box)
        head=make_head_crop(frame,box,kp)
        self.assertEqual(person.shape,(256,256,3))
        self.assertEqual(head.shape,(256,256,3))
        self.assertEqual(tuple(tensor_from_bgr(person).shape),(3,224,224))
        self.assertTrue(np.array_equal(person[0,0],[20,80,220]))

    def test_checkpoint_architecture_and_order(self):
        action=ActionsAdapter(self.settings.action_weights,self.settings.action_config,device="cpu")
        head=HeadAdapter(self.settings.head_weights,self.settings.head_config,device="cpu")
        action.load();head.load()
        self.assertEqual(action.classes,("READING","WRITING"))
        self.assertEqual(action.thresholds,{"READING":.39,"WRITING":.41})
        self.assertEqual(action.checkpoint["threshold"],.5)
        self.assertEqual((head.pitch_scale,head.yaw_scale),(60,90))
        self.assertEqual(head.classify(15,0),"LOOKING_UP")
        self.assertEqual(head.classify(-15,0),"LOOKING_DOWN")
        self.assertEqual(head.classify(15,-24),"LOOKING_LEFT")
        crop=np.zeros((256,256,3),dtype=np.uint8)
        self.assertEqual(action.infer([crop,crop]).shape,(2,2))
        self.assertEqual(head.infer([crop,crop]).shape,(2,2))

    def test_tracking_detection_reorder(self):
        manager=TrackManager()
        kp=np.zeros((17,3),dtype=np.float32)
        def d(x,source=None): return Detection((x,10,x+30,90),kp,.9,source)
        first=manager.update([d(10),d(110)],1.0)
        second=manager.update([d(112),d(12)],2.0)
        # V6.1 does not mint a second public identity merely because two
        # detections were present in the first frame. The confirmed identity
        # remains stable when detection order changes.
        self.assertEqual([t.track_id for t in first],[1])
        self.assertEqual([t.track_id for t in second],[1])
        self.assertEqual(manager.next_id,2)

    def test_track_expiration_and_cpu_fallback(self):
        manager=TrackManager(max_missed=2)
        kp=np.zeros((17,3),dtype=np.float32)
        manager.update([Detection((10,10,40,90),kp,.9,None)],1)
        manager.update([],2);manager.update([],3);manager.update([],4)
        self.assertEqual(manager.expired,[1])
        self.assertEqual(str(select_device('cpu')),'cpu')

    def test_missing_pose_checkpoint_is_reported(self):
        adapter=PoseAdapter(self.settings.pose_weights.parent/'missing.pt',device='cpu')
        with self.assertRaises(FileNotFoundError): adapter.load()

    def test_initial_standing_not_assumed_sitting(self):
        kp=np.zeros((17,3),dtype=np.float32)
        for i in (5,6,11,12,13,14,15,16): kp[i,2]=.9
        kp[5,:2]=[30,20];kp[6,:2]=[70,20]
        kp[11,:2]=[35,50];kp[12,:2]=[65,50]
        kp[13,:2]=[35,70];kp[14,:2]=[65,70]
        kp[15,:2]=[35,90];kp[16,:2]=[65,90]
        self.assertEqual(pose_body_state(kp),"STANDING")
        state=PersonTemporalState();track=Track(1,(0,0,100,100),kp,.9,0)
        for _ in range(25): result=state.update(track,None,None,lambda p,y:"LOOKING_FORWARD",{"READING":.39,"WRITING":.41})
        self.assertNotIn("SITTING",[a["name"] for a in result["attributes"]])
        self.assertIn("STANDING",[a["name"] for a in result["attributes"]])

    def test_head_clears_on_invalid_and_turned_back(self):
        kp=np.zeros((17,3),dtype=np.float32)
        kp[:7,2]=.9;kp[:7,0]=30;kp[:7,1]=20
        state=PersonTemporalState();track=Track(2,(0,0,100,100),kp,.9,0)
        for _ in range(3): result=state.update(track,None,(0,35),lambda p,y:"LOOKING_RIGHT",{"READING":.39,"WRITING":.41})
        self.assertEqual(result["head"]["label"],"LOOKING_RIGHT")
        result=state.update(track,None,None,lambda p,y:"LOOKING_RIGHT",{"READING":.39,"WRITING":.41})
        self.assertEqual(result["head"]["label"],"UNKNOWN_HEAD")
        self.assertIsNone(state.head_ema)
        kp[:5,2]=0;track.keypoints=kp
        for _ in range(5): result=state.update(track,None,(0,35),lambda p,y:"LOOKING_RIGHT",{"READING":.39,"WRITING":.41})
        self.assertTrue(result["turned_back"])
        self.assertEqual(result["head"]["label"],"UNKNOWN_HEAD")
        self.assertIsNone(state.head_ema)

if __name__=="__main__": unittest.main()
