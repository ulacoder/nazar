"""Repeatable local profiling: synthetic history plus the production video runtime."""
import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
from contextlib import closing
from datetime import datetime,timedelta,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.storage.database import Store
from app.runtime import Runtime
from app.server import create_app
from app.system import hardware_status

def timed(fn,n=8):
    samples=[]
    for _ in range(n):
        start=time.perf_counter();value=fn();samples.append((time.perf_counter()-start)*1000)
    return {'median_ms':round(statistics.median(samples),3),'max_ms':round(max(samples),3)},value

def run(output,video):
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);store=Store(root/'test.sqlite3')
        start=datetime(2026,1,1,tzinfo=timezone.utc)
        sid=store.start_session('EXAM',start.isoformat())
        # Fixed 45-minute, 30-track, 12000-event fixture, identical in both runs.
        rows=[{'occurred_at':(start+timedelta(seconds=i*2699/11999)).isoformat(),
               'source_offset_s':i*2699/11999,'track_id':i%30+1,
               'event_type':['WRITING','READING','LOOKING_LEFT','LOOKING_DOWN'][i%4],
               'confidence':.8 if i%4<2 else None} for i in range(12000)]
        store.add_events(sid,rows)
        with closing(store.connect()) as db:
            db.executemany('INSERT INTO visibility_samples VALUES (?,?,?)',[(sid,i,30) for i in range(2700)])
            db.executemany('INSERT OR IGNORE INTO session_tracks(session_id,track_id) VALUES (?,?)',[(sid,i) for i in range(1,31)])
            db.commit()
        store.stop_session(sid,(start+timedelta(minutes=45)).isoformat(),30,{})
        settings=Settings(database=store.path,sessions_dir=root/'sessions',timelapse_enabled=False)
        runtime=Runtime(settings,store=store);client=create_app(settings,runtime).test_client()
        report={'fixture':{'duration_s':2700,'tracks':30,'events':12000,'visibility_samples':2700}}
        report['analytics_query'],analytics=timed(lambda:store.session_analytics(sid))
        report['event_query'],_=timed(lambda:store.events(session_id=sid))
        report['analytics_api'],response=timed(lambda:client.get(f'/api/sessions/{sid}/analytics'))
        report['analytics_payload_bytes']=len(response.data)
        report['chart_points']={key:len(analytics[key]) for key in ('people_over_time','events_over_time')}
        report['state_api'],_=timed(lambda:client.get('/api/state'))
        report['events_api'],_=timed(lambda:client.get('/api/events'))
        report['status_api'],_=timed(lambda:client.get('/api/status'),3)
        # Time synchronous observation work separately from inference.
        active=runtime.start_session('EXAM');track={'track_id':1,'attributes':[]}
        report['observe'],_=timed(lambda:runtime.sessions.observe([track],time.time()))
        runtime.stop_session()
        if video:
            runtime.settings.input_source='VIDEO';runtime.settings.video_path=str(Path(video).resolve())
            runtime.camera=runtime._make_source()
            import cv2
            cap=cv2.VideoCapture(str(video));ok,frame=cap.read();cap.release()
            runtime.pipeline.load()
            if ok:
                for i in range(3):runtime.pipeline.process(frame,float(i))
                runtime.pipeline.reset_tracks()
            commits=[0];original_connect=store.connect
            def counted_connect():
                db=original_connect()
                db.set_trace_callback(lambda sql: commits.__setitem__(0,commits[0]+1) if sql=='COMMIT' else None)
                return db
            store.connect=counted_connect
            runtime.start()
            runtime.start_session('EXAM')
            sse=[0];done=threading.Event()
            def read_sse():
                for _ in runtime.events_stream():
                    sse[0]+=1
                    if done.is_set():break
            thread=threading.Thread(target=read_sse,daemon=True);thread.start()
            samples=[];began=time.perf_counter();last_frame=runtime.pipeline.frames;initial_frames=last_frame
            while time.perf_counter()-began<20:
                time.sleep(.2)
                if runtime.pipeline.frames!=last_frame:
                    last_frame=runtime.pipeline.frames
                    samples.append({'camera_fps':runtime.camera.status().get('actual_fps'),
                        'ai_fps':runtime.ai_fps,**runtime.pipeline.latency.copy()})
                if runtime.camera.status().get('ended'):break
            elapsed=time.perf_counter()-began
            report['runtime']={'source':'prerecorded video','elapsed_s':round(elapsed,2),'frames':runtime.pipeline.frames-initial_frames,
                'processed_fps':round((runtime.pipeline.frames-initial_frames)/elapsed,2),
                'sse_messages':sse[0],'sse_hz':round(sse[0]/elapsed,2),
                'mean':{key:round(statistics.mean(x[key] for x in samples if x[key] is not None),3)
                    for key in samples[0]} if samples else {},'hardware':hardware_status(),
                'model_errors':runtime.pipeline.errors,'database_commits':commits[0],'database_commits_per_s':round(commits[0]/elapsed,2)}
            runtime.stop_session();done.set();runtime.close()
        report['camera_capture_fps']=None
        report['camera_note']='Webcam not opened; runtime measurement uses the same prerecorded clip.'
        output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
        output.write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--video')
    args=parser.parse_args();run(args.output,args.video)
