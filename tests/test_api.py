import tempfile
import unittest
from pathlib import Path
from app.config import Settings
from app.server import create_app

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=Path(self.temp.name)
        settings=Settings(database=root/"test.sqlite3",sessions_dir=root/"sessions",timelapse_enabled=False)
        self.app=create_app(settings,start_runtime=False)
        self.client=self.app.test_client()

    def tearDown(self): self.temp.cleanup()

    def test_health_session_events_settings(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(self.client.get('/api/health').status_code,200)
        self.assertEqual(self.client.get('/api/state').status_code,200)
        self.assertEqual(self.client.get('/api/status').status_code,200)
        settings=self.client.get('/api/settings').get_json()
        self.assertEqual(settings['action_thresholds'],{'READING':.39,'WRITING':.41})
        self.assertEqual(self.client.post('/api/settings',json={'boxes_overlay':False}).status_code,200)
        self.assertFalse(self.client.get('/api/settings').get_json()['values']['boxes_overlay'])
        self.assertEqual(self.client.post('/api/settings',json={'input_source':'VIDEO'}).status_code,400)
        self.assertEqual(self.client.post('/api/settings',json={'boxes_overlay':True,'pose_conf':0}).status_code,400)
        self.assertFalse(self.client.get('/api/settings').get_json()['values']['boxes_overlay'])
        created=self.client.post('/api/session/start',json={'mode':'LESSON'})
        self.assertEqual(created.status_code,201)
        session_id=created.get_json()['id']
        self.assertEqual(self.client.post('/api/session/start',json={'mode':'EXAM'}).status_code,409)
        self.assertEqual(self.client.post('/api/session/stop').status_code,200)
        self.assertEqual(self.client.get(f'/api/sessions/{session_id}').status_code,200)
        self.assertEqual(self.client.get('/api/sessions').get_json()[0]['mode'],'LESSON')
        self.assertEqual(self.client.get('/api/events').get_json(),[])
        self.assertEqual(self.client.get('/api/analytics').status_code,404)
        self.assertEqual(self.client.get(f'/api/sessions/{session_id}/analytics').get_json()['event_timeline'],[])
        self.assertEqual(self.client.get(f'/api/sessions/{session_id}/events').get_json(),[])
        self.assertEqual(self.client.get(f'/api/timelapse/{session_id}').status_code,404)

    def test_metadata_and_session_scoped_analytics(self):
        store=self.app.config['NAZAR_RUNTIME'].store
        payload={'mode':'LESSON','teacher':'  Ms A  ','class_name':' 7B ', 'subject':'Math','notes':'Practice'}
        first=self.client.post('/api/session/start',json=payload)
        self.assertEqual(first.status_code,201)
        first_id=first.get_json()['id']
        self.client.post('/api/session/stop')
        second=self.client.post('/api/session/start',json={'mode':'EXAM','subject':'History'})
        self.assertEqual(second.status_code,201)
        second_id=second.get_json()['id']
        self.client.post('/api/session/stop')
        store.add_visibility_sample(first_id,1.0,[3,4])
        store.add_visibility_sample(first_id,2.0,[3])
        store.add_events(first_id,[{'occurred_at':'2026-01-01T00:00:01+00:00','track_id':3,'event_type':'WRITING','confidence':.9,'source_offset_s':1.0}])
        store.add_events(second_id,[{'occurred_at':'2026-01-01T00:00:02+00:00','track_id':8,'event_type':'READING','confidence':.8,'source_offset_s':2.0}])
        store.save_timelapse(first_id,{'path':None,'frame_count':5,'available':False,'error':'encoder unavailable'})
        row=self.client.get(f'/api/sessions/{first_id}').get_json()
        self.assertEqual((row['teacher'],row['class_name'],row['subject'],row['notes']),('Ms A','7B','Math','Practice'))
        self.assertEqual(self.client.get('/api/sessions').get_json()[1]['subject'],'Math')
        result=self.client.get(f'/api/sessions/{first_id}/analytics').get_json()
        self.assertEqual(result['event_distribution'],[{'event_type':'WRITING','count':1}])
        self.assertEqual(result['track_ids'],[3,4])
        self.assertEqual(result['people_over_time'][0]['people_count'],1.5)
        self.assertEqual(result['event_timeline'][0]['offset_s'],1.0)
        self.assertIsNone(result['confirmed_durations'])
        self.assertEqual(len(self.client.get(f'/api/sessions/{first_id}/events').get_json()),1)
        self.assertEqual(self.client.get(f'/api/sessions/{second_id}/analytics').get_json()['track_ids'],[8])
        self.assertEqual(result['session']['timelapse_frames'],5)
        self.assertEqual(self.client.get(f'/api/sessions/{second_id}/analytics').get_json()['session']['timelapse_frames'],0)
        self.assertEqual(self.client.get('/api/sessions/999/analytics').status_code,404)
        self.assertEqual(self.client.get(f'/api/sessions/{first_id}').get_json()['event_count'],1)
        self.assertEqual(self.client.post('/api/session/start',json={'mode':'LESSON','teacher':123}).status_code,400)
        self.assertEqual(self.client.post('/api/session/start',json={'mode':'LESSON','teacher':'x'*121}).status_code,400)
        self.assertEqual(self.client.post('/api/session/start',json={'mode':'LESSON','subject':'bad\u0001'}).status_code,400)

    def test_saved_overlay_settings_restore_on_restart(self):
        runtime=self.app.config['NAZAR_RUNTIME']
        runtime.store.save_settings({'boxes_overlay':False,'skeleton_overlay':True})
        from app.runtime import Runtime
        reopened=Runtime(runtime.settings)
        self.assertFalse(reopened.settings.boxes_overlay)
        self.assertTrue(reopened.settings.skeleton_overlay)

if __name__=='__main__': unittest.main()
