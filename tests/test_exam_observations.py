import tempfile
import threading
import time
import unittest
from pathlib import Path
from app.events import EventEngine,EXAM_OBSERVATIONS
from app.sessions import SessionManager
from app.storage.database import Store
from app.timelapse import DisabledRecorder

def track(tid,*states):
    return {'track_id':tid,'attributes':[{'name':s,'confidence':.85 if s in {'READING','WRITING'} else None,
        'source':'action_model' if s in {'READING','WRITING'} else 'head_model' if s.startswith('LOOKING') else 'geometry'} for s in states]}

class ExamObservationTests(unittest.TestCase):
    def setUp(self):
        self.engine=EventEngine(1,4);self.engine.reset('EXAM')
    def confirm(self,states,at,tid=3):
        self.engine.update([track(tid,*states)],at)
        return self.engine.update([track(tid,*states)],at+1.01)
    def test_hold_left_emits_once(self):
        events=self.confirm(['LOOKING_LEFT'],0)
        for second in range(2,20):events+=self.engine.update([track(3,'LOOKING_LEFT')],second)
        self.assertEqual([(e['track_id'],e['event_type']) for e in events],[(3,'LOOKING_LEFT')])
    def test_forward_left_forward_left(self):
        self.assertEqual(self.confirm(['LOOKING_FORWARD'],0),[])
        one=self.confirm(['LOOKING_LEFT'],2)
        self.confirm(['LOOKING_FORWARD'],4)
        two=self.confirm(['LOOKING_LEFT'],7)
        self.assertEqual(len(one+two),2)
    def test_left_right_and_all_required_states(self):
        events=self.confirm(['LOOKING_LEFT'],0)+self.confirm(['LOOKING_RIGHT'],2)
        self.assertEqual([e['event_type'] for e in events],['LOOKING_LEFT','LOOKING_RIGHT'])
        for i,state in enumerate(sorted(EXAM_OBSERVATIONS-{'LOOKING_LEFT','LOOKING_RIGHT'})):
            result=self.confirm([state],5+i*3)
            self.assertIn(state,[e['event_type'] for e in result])
    def test_unknown_and_brief_fluctuations_do_not_rearm(self):
        self.confirm(['LOOKING_LEFT'],0)
        self.engine.update([track(3,'LOOKING_RIGHT')],2)
        self.assertEqual(self.engine.update([track(3,'LOOKING_LEFT')],2.2),[])
        self.engine.update([],3);self.engine.update([],10)
        self.assertEqual(self.confirm(['LOOKING_LEFT'],11),[])
    def test_two_tracks_and_multilabel(self):
        tracks=[track(1,'LOOKING_LEFT','WRITING'),track(2,'LOOKING_DOWN','HAND_RAISED')]
        self.engine.update(tracks,0);events=self.engine.update(tracks[::-1],1.1)
        self.assertEqual({(e['track_id'],e['event_type']) for e in events},
            {(1,'LOOKING_LEFT'),(1,'WRITING'),(2,'LOOKING_DOWN'),(2,'HAND_RAISED')})
        self.assertIsNone(next(e['confidence'] for e in events if e['event_type']=='LOOKING_LEFT'))
        self.assertEqual(next(e['confidence'] for e in events if e['event_type']=='WRITING'),.85)
    def test_lesson_policy_separate(self):
        self.assertEqual(self.confirm(['SITTING','LOOKING_FORWARD'],0),[])
        self.engine.reset('LESSON')
        self.assertEqual({e['event_type'] for e in self.confirm(['SITTING','LOOKING_FORWARD'],0)}, {'SITTING','LOOKING_FORWARD'})
    def test_scores_are_not_invented(self):
        self.assertIsNone(EventEngine.score({'name':'LOOKING_DOWN','source':'head_model','confidence':.99}))
        self.assertIsNone(EventEngine.score({'name':'READING','source':'action_model','confidence':float('nan')}))
    def test_async_persistence_and_timestamps(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'events.db');manager=SessionManager(store,DisabledRecorder(),1,4)
            session=manager.start('EXAM',source_type='VIDEO')
            manager.observe([track(7,'LOOKING_DOWN')],3,3)
            rows=manager.observe([track(7,'LOOKING_DOWN')],4.1,4.1)
            self.assertEqual(rows[0]['session_id'],session['id']);self.assertEqual(rows[0]['session_offset_s'],4.1)
            self.assertIsNotNone(rows[0]['occurred_at']);self.assertIsNone(rows[0]['confidence'])
            manager.stop()
            saved=store.event_page(session['id'])['items'][0]
            self.assertEqual(saved['offset_s'],4.1)
            p=store.person_detail(session['id'],7)
            self.assertEqual((p['first_seen_s'],p['last_seen_s']),(3,4.1))
    def test_slow_writer_does_not_block_observe(self):
        with tempfile.TemporaryDirectory() as directory:
            store=Store(Path(directory)/'events.db');started=threading.Event();release=threading.Event()
            write=store.write_observation
            def slow(*args):started.set();release.wait(3);write(*args)
            store.write_observation=slow
            manager=SessionManager(store,DisabledRecorder());manager.start('EXAM')
            try:
                manager.observe([track(1)],time.time());self.assertTrue(started.wait(1))
                before=time.perf_counter();manager.observe([track(1)],time.time())
                self.assertLess(time.perf_counter()-before,.1)
            finally:release.set();manager.stop()

if __name__=='__main__':unittest.main()
