import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from app.storage.database import Store
from app.server import create_app
from app.config import Settings
from app.sessions import SessionManager
from app.timelapse import DisabledRecorder

class PersonAnalyticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'a.db';self.store=Store(self.path)
    def tearDown(self):self.temp.cleanup()
    def session(self,duration=25):
        sid=self.store.start_session('EXAM','2026-01-01T00:00:00+00:00',source_type='VIDEO')
        self.store.write_observation(sid,[],{1:(2,duration)},(duration,1));return sid
    def test_short_and_long_buckets(self):
        for seconds,step in [(25,5),(2700,60),(100000,1140)]:
            sid=self.session(seconds);a=self.store.session_analytics(sid)
            self.assertEqual(a['bucket_seconds'],step);self.assertLessEqual(len(a['people_over_time']),100)
            self.assertGreater(len(a['events_over_time']),1)
    def test_session_local_spans_counts_and_lazy_api(self):
        a=self.session();b=self.session(100)
        self.store.add_events(a,[{'occurred_at':'2026-01-01T00:00:03+00:00','track_id':1,'event_type':'LOOKING_LEFT','session_offset_s':3}])
        self.store.add_events(b,[{'occurred_at':'2026-01-01T00:00:09+00:00','track_id':1,'event_type':'WRITING','session_offset_s':9}])
        pa=self.store.person_detail(a,1);pb=self.store.person_detail(b,1)
        self.assertEqual(pa['event_counts'],{'LOOKING_LEFT':1});self.assertEqual(pb['event_counts'],{'WRITING':1})
        self.assertEqual((pa['first_seen_s'],pa['last_seen_s'],pa['observed_span_s']),(2,25,23))
        settings=Settings(database=self.path,sessions_dir=Path(self.temp.name),timelapse_enabled=False)
        client=create_app(settings).test_client()
        self.assertEqual(client.get(f'/api/sessions/{a}/people/1').get_json()['events']['items'][0]['offset_s'],3)
        self.assertEqual(client.get(f'/api/sessions/{a}/people/999').status_code,404)
        self.assertEqual(client.get(f'/api/sessions/{a}/events?page=1&track=1&type=WRITING').get_json()['items'],[])
    def test_large_payload_bounded_and_pagination(self):
        sid=self.session(2700)
        self.store.add_events(sid,[{'occurred_at':'2026-01-01T00:00:00+00:00','track_id':i%30+1,
            'event_type':'LOOKING_LEFT','session_offset_s':i/5} for i in range(12000)])
        with closing(self.store.connect()) as db:
            db.executemany('INSERT OR REPLACE INTO visibility_samples VALUES (?,?,?)',[(sid,i,30) for i in range(2700)]);db.commit()
        a=self.store.session_analytics(sid)
        self.assertLessEqual(len(a['people_over_time']),100);self.assertEqual(len(a['event_timeline']),100)
        self.assertEqual(a['event_page']['total'],12000);self.assertEqual(len(a['people']),30)
        first=self.store.event_page(sid,track_id=1);second=self.store.event_page(sid,track_id=1,offset=100)
        self.assertFalse({e['id'] for e in first['items']}&{e['id'] for e in second['items']})
        self.assertEqual(first['total'],400)
    def test_empty_and_legacy_bounds(self):
        sid=self.store.start_session('LESSON','2026-01-01T00:00:00+00:00',source_type='VIDEO')
        self.assertEqual(self.store.session_analytics(sid)['people'],[])
        self.store.add_visibility_sample(sid,1,[3])
        p=self.store.person_detail(sid,3)
        self.assertIsNone(p['first_seen_s']);self.assertIsNone(p['observed_span_s'])

    def test_default_role_is_unknown(self):
        self.assertEqual(self.store.person_detail(self.session(),1)['role'],'UNKNOWN')

    def test_student_teacher_unknown_exam_aggregation(self):
        sid=self.session();self.store.write_observation(sid,[],{2:(0,10),3:(0,10)},(10,2))
        self.store.add_events(sid,[
            {'occurred_at':'2026-01-01T00:00:01+00:00','track_id':1,'event_type':'READING','session_offset_s':1,'review_priority':'REVIEW'},
            {'occurred_at':'2026-01-01T00:00:02+00:00','track_id':2,'event_type':'LOOKING_LEFT','session_offset_s':2,'review_priority':'HIGH_REVIEW'},
            {'occurred_at':'2026-01-01T00:00:03+00:00','track_id':3,'event_type':'LOOKING_RIGHT','session_offset_s':3,'review_priority':'REVIEW'}])
        self.store.set_person_role(sid,1,'STUDENT');self.store.set_person_role(sid,2,'TEACHER')
        a=self.store.session_analytics(sid)
        self.assertEqual(a['student_exam']['person_ids'],[1]);self.assertEqual(a['student_exam']['review_moments'],1)
        self.assertEqual(a['teacher_exam']['person_ids'],[2]);self.assertEqual(a['unknown_exam']['person_ids'],[3])

    def test_role_change_keeps_historical_events(self):
        sid=self.session();self.store.add_events(sid,[{'occurred_at':'2026-01-01T00:00:01+00:00','track_id':1,'event_type':'READING','session_offset_s':1}])
        self.store.set_person_role(sid,1,'STUDENT');self.store.set_person_role(sid,1,'TEACHER')
        self.assertEqual(len(self.store.events(sid)),1);self.assertEqual(self.store.session_analytics(sid)['student_exam']['event_count'],0)

    def test_role_is_session_local(self):
        first=self.session();second=self.session();self.store.set_person_role(first,1,'STUDENT')
        self.assertEqual(self.store.person_detail(first,1)['role'],'STUDENT');self.assertEqual(self.store.person_detail(second,1)['role'],'UNKNOWN')

    def test_invalid_role_rejected(self):
        with self.assertRaises(ValueError): self.store.set_person_role(self.session(),1,'SUSPICIOUS')

    def test_reassociation_keeps_public_role(self):
        sid=self.session();self.store.set_person_role(sid,1,'STUDENT');self.store.write_observation(sid,[],{1:(0,3)},(3,1))
        self.assertEqual(self.store.person_detail(sid,1)['role'],'STUDENT')

    def test_temporary_disappearance_keeps_public_role(self):
        sid=self.session();self.store.set_person_role(sid,1,'STUDENT');self.store.write_observation(sid,[],{1:(0,1)},(1,1));self.store.write_observation(sid,[],{1:(5,8)},(8,1))
        self.assertEqual(self.store.person_detail(sid,1)['role'],'STUDENT')

    def test_live_teacher_is_not_student_observation(self):
        manager=SessionManager(self.store,DisabledRecorder());session=manager.start('EXAM');self.store.set_person_role(session['id'],1,'TEACHER')
        manager.observe([{'track_id':1,'attributes':[]}],1);self.assertFalse(manager.live_observations([1])[1]['student_included']);manager.stop()

if __name__=='__main__':unittest.main()
