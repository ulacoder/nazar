"""Isolated synthetic UI fixture. Never opens a webcam or production database."""
import sys
import tempfile
from pathlib import Path
from datetime import datetime,timedelta,timezone
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.config import Settings
from app.server import create_app
from app.runtime import Runtime

def main():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory);settings=Settings(database=root/'ui.db',sessions_dir=root/'sessions',timelapse_enabled=False)
        runtime=Runtime(settings);store=runtime.store
        for duration in (25,2700):
            start=datetime(2026,1,1,tzinfo=timezone.utc)
            sid=store.start_session('EXAM',start.isoformat(),source_type='VIDEO',metadata={'subject':f'Synthetic UI test · {duration}s'})
            count=250 if duration==2700 else 8
            rows=[{'track_id':i%3+1,'event_type':['LOOKING_LEFT','LOOKING_RIGHT','LOOKING_DOWN','TURNED_BACK'][i%4],
                'session_offset_s':i*duration/count,'occurred_at':(start+timedelta(seconds=i*duration/count)).isoformat()} for i in range(count)]
            store.write_observation(sid,rows,{1:(0,duration),2:(2,duration-1),3:(4,duration-2)},None)
            for second in range(0,duration,5):store.add_visibility_sample(sid,second,[1,2,3])
            store.stop_session(sid,(start+timedelta(seconds=duration)).isoformat(),3,{})
        try:create_app(settings,runtime).run(host='127.0.0.1',port=8770,use_reloader=False)
        finally:runtime.close()

if __name__=='__main__':main()
