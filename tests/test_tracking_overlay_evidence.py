import unittest,tempfile,csv,time,json
from pathlib import Path
from unittest.mock import patch
import cv2,numpy as np
from app.vision.tracker import TrackManager
from app.vision.types import Detection
from app.overlay import overlay_lines,panel_layout,draw_overlay
from app.evidence import evidence_items,map_window,merged_windows,generate_review_clips
from app.sessions import SessionManager
from app.storage.database import Store
from app.timelapse import DisabledRecorder

class TrackingAuditTests(unittest.TestCase):
    def det(self,b,source=None):return Detection(b,np.zeros((17,3),np.float32),.9,source)
    def test_zero_iou_bending_and_height_change(self):
        m=TrackManager();m.update([self.det((0,0,40,100),17)],0)
        m.update([], .1)
        t=m.update([self.det((42,0,82,100),31)],.3)
        self.assertEqual(t[0].track_id,1)
        self.assertEqual(m.reassociations[0]['iou'],0)
        t=m.update([self.det((35,0,80,200),32)],.5)
        self.assertEqual(t[0].track_id,1)
    def test_high_fps_gap_not_frame_expiration(self):
        m=TrackManager();m.update([self.det((0,0,40,100),1)],0)
        for i in range(1,61):m.update([],i/30)
        self.assertEqual(m.update([self.det((2,0,42,100),9)],2.1)[0].track_id,1)
    def test_two_desks_global_one_to_one(self):
        m=TrackManager();m.update([self.det((0,0,40,100),1),self.det((110,0,150,100),2)],0)
        m.update([],1)
        result=m.update([self.det((112,0,152,100),20),self.det((2,0,42,100),10)],1.5)
        self.assertEqual({t.track_id:round(t.bbox[0]) for t in result},{1:2})
        self.assertEqual(m.next_id,2)
    def test_ambiguous_deferred_not_merged(self):
        m=TrackManager();m.update([self.det((0,0,40,100)),self.det((80,0,120,100))],0)
        result=m.update([self.det((40,0,80,100))],.1)
        self.assertEqual([t.track_id for t in result],[1])
        self.assertEqual(m.next_id,2)
        self.assertFalse(any(r['kind']=='new_id' for r in m.debug_events))
    def test_long_gap_rejected_with_actual_source_ids(self):
        m=TrackManager();m.update([self.det((0,0,40,100),17)],0)
        result=m.update([self.det((0,0,40,100),31)],3)
        self.assertEqual(result,[])
        self.assertEqual(m.next_id,2)
        reason=next(r for r in m.debug_events if r['kind']=='candidate')
        self.assertEqual((reason['old_internal_track_id'],reason['reason']),(17,'MAX_GAP_EXCEEDED'))

class OverlayAuditTests(unittest.TestCase):
    def track(self):return dict(track_id=3,bbox=[95,75,120,90],attributes=[{'name':'SITTING'},{'name':'WRITING'}],head=dict(label='LOOKING_DOWN',pitch=2.,yaw=3.),internal_track_id=17)
    def test_languages_normal_debug_and_bounds(self):
        track=self.track()
        for lang,title in [('en','PERSON'),('ru','ЧЕЛОВЕК'),('kk','АДАМ')]:
            lines=overlay_lines(track,language=lang);text=' '.join(t for t,_ in lines)
            self.assertIn(title,text);self.assertNotIn('LOOKING_',text);self.assertNotIn('P 2',text)
            (x,y,w,h),_,_=panel_layout(track,(90,120,3),lines)
            self.assertTrue(0<=x and x+w<=120 and 0<=y and y+h<=90)
        self.assertIn('internal 17',str(overlay_lines(track,debug=True)))
        track['role']='STUDENT'
        self.assertIn('УЧЕНИК',str(overlay_lines(track,language='ru')))
        track['role']='TEACHER'
        self.assertIn('МҰҒАЛІМ',str(overlay_lines(track,language='kk')))
        track['head']['label']='UNKNOWN_HEAD';self.assertNotIn('UNKNOWN',str(overlay_lines(track)))

class EvidenceAuditTests(unittest.TestCase):
    def test_actual_timelapse_mapping_and_missing_samples(self):
        rows=[(0,0),(2,1/12),(5,2/12),(9,3/12)]
        self.assertEqual(map_window(2,6,'timelapse',rows,4/12),(1/12,3/12))
        self.assertIsNone(map_window(6,8,'timelapse',rows,4/12))
    def test_overlap_merges_not_duplicate_encoders(self):
        items=[dict(available=True,recording_start_s=0,recording_end_s=4),dict(available=True,recording_start_s=3,recording_end_s=8)]
        groups=merged_windows(items);self.assertEqual(len(groups),1);self.assertEqual(groups[0]['end'],8)
    def test_review_metadata_persists_normal_has_none(self):
        with tempfile.TemporaryDirectory() as d:
            store=Store(Path(d)/'s.db');manager=SessionManager(store,DisabledRecorder(),.8,4);session=manager.start('EXAM','VIDEO')
            track=dict(track_id=2,attributes=[dict(name='LOOKING_LEFT',confidence=None,source='head_model')])
            manager.observe([track],0,0);manager.observe([track],1,1);manager.stop()
            rows=store.events(session['id']);self.assertEqual(len(rows),1)
            self.assertEqual((rows[0]['evidence_start_s'],rows[0]['evidence_end_s']),(0,4))
            self.assertIsNone(rows[0]['confidence'])
            items=evidence_items(store.session(session['id']),rows,Path(d)/'clips');self.assertFalse(items[0]['available'])
            rows[0]['review_priority']='HIGH_REVIEW';self.assertEqual(len(evidence_items(store.session(session['id']),rows,Path(d))),1)
            rows[0]['review_priority']='NORMAL';self.assertEqual(evidence_items(store.session(session['id']),rows,Path(d)),[])
    def test_encoding_dispatched_without_blocking(self):
        import threading
        release=threading.Event()
        with patch('app.evidence._generate',side_effect=lambda *_:release.wait(2)):
            start=time.perf_counter();future=generate_review_clips({},[],'.');elapsed=time.perf_counter()-start
            release.set();future.result(timeout=3);self.assertLess(elapsed,.2)

if __name__=='__main__':unittest.main()

class EvidenceIntegrationTests(unittest.TestCase):
    def test_h264_clip_api_and_shared_window(self):
        from app.config import Settings
        from app.server import create_app
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);video=root/'source.mp4';w=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'mp4v'),10,(96,64))
            self.assertTrue(w.isOpened())
            for i in range(50):w.write(np.full((64,96,3),i*4,np.uint8))
            w.release()
            settings=Settings(database=root/'s.db',sessions_dir=root/'sessions',evidence_dir=root/'evidence',tracking_debug_dir=root/'tracking',timelapse_enabled=False)
            app=create_app(settings);store=app.config['NAZAR_RUNTIME'].store
            sid=store.start_session('EXAM','2026-09-22T00:00:00+00:00','VIDEO');store.set_source_video(sid,video)
            for start,end,priority in [(1,3,'REVIEW'),(2,4,'HIGH_REVIEW')]:
                store.add_events(sid,[dict(occurred_at='2026-09-22T00:00:02+00:00',track_id=2,event_type='TURNED_BACK',confidence=None,session_offset_s=2,review_priority=priority,reason='Confirmed turn',evidence_start_s=start,evidence_end_s=end)])
            session=store.session(sid);events=store.events(sid)
            future=generate_review_clips(session,events,settings.evidence_dir/str(sid));future.result(timeout=30)
            self.assertEqual(len(list((settings.evidence_dir/str(sid)).glob('*.mp4'))),1)
            client=app.test_client();items=client.get(f'/api/sessions/{sid}/evidence').get_json()['items'];self.assertEqual(len(items),2)
            self.assertTrue(all(e['clip_available'] for e in items))
            with client.get(items[0]['clip_url']) as response:self.assertEqual(response.status_code,200)
            with client.get(items[0]['recording_url']) as response:self.assertEqual(response.status_code,200)
            self.assertEqual(client.get(f'/api/sessions/{sid}/evidence?priority=HIGH_REVIEW').get_json()['total'],1)
            manifest=json.loads((settings.evidence_dir/str(sid)/'manifest.json').read_text())
            path=settings.evidence_dir/str(sid)/manifest[str(items[0]['id'])]['filename'];cap=cv2.VideoCapture(str(path))
            self.assertAlmostEqual(cap.get(7)/cap.get(5),3.,delta=.2);cap.release()
