import unittest
import numpy as np
from app.evidence import evidence_window,evidence_items
from app.overlay import draw_overlay

class EvidenceOverlayTests(unittest.TestCase):
    def test_evidence_keeps_role_separate(self):
        session={'id':4,'mode':'EXAM','source_video_path':None,'timelapse_available':False,'timelapse_path':None}
        events=[{'id':1,'track_id':1,'event_type':'READING','review_priority':'REVIEW','evidence_start_s':1,'evidence_end_s':2},
                {'id':2,'track_id':2,'event_type':'READING','review_priority':'REVIEW','evidence_start_s':1,'evidence_end_s':2}]
        items=evidence_items(session,events,'missing-evidence',roles={1:'TEACHER'})
        self.assertEqual([item['role'] for item in items],['TEACHER','UNKNOWN'])
    def test_evidence_window_clamps_and_includes_duration(self):
        self.assertEqual(evidence_window(1.0,2.0), (0.0,4.0))
        self.assertEqual(evidence_window(10.0,2.0,3,3), (5.0,13.0))

    def test_overlay_uses_human_labels_and_debug_is_opt_in(self):
        frame=np.zeros((180,240,3),np.uint8)
        track={'track_id':1,'bbox':[20,40,120,160],'keypoints':np.zeros((17,3)).tolist(),'attributes':[{'name':'SITTING'},{'name':'WRITING'}], 'head':{'label':'LOOKING_FORWARD','pitch':-4.2,'yaw':-1.9}}
        normal=draw_overlay(frame,[track],debug=False)
        debug=draw_overlay(frame,[track],debug=True)
        self.assertEqual(normal.shape,frame.shape);self.assertEqual(debug.shape,frame.shape)
        self.assertFalse(np.array_equal(normal,frame));self.assertFalse(np.array_equal(debug,normal))

if __name__=='__main__':unittest.main()
