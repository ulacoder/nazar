"""Independent frame sampler and MP4 writer; no extra model inference."""
import logging
import threading
import csv
from datetime import datetime,timezone
from pathlib import Path
import cv2

log=logging.getLogger(__name__)

def utc_now(): return datetime.now(timezone.utc).isoformat()

class TimelapseRecorder:
    def __init__(self,camera,output_dir,interval=2.0,fps=12.0,overlay=None):
        self.camera=camera;self.output_dir=Path(output_dir)
        self.interval=interval;self.fps=fps;self.overlay=overlay
        self.stop_event=threading.Event();self.thread=None
        self.path=None;self.frame_count=0;self.error=None;self.recording=False
        self.started_at=None;self.ended_at=None;self.codec=None

    def start(self,session_id):
        if self.thread and self.thread.is_alive(): raise RuntimeError("Timelapse already recording")
        self.path=self.output_dir/str(session_id)/"timelapse.mp4"
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.frame_count=0;self.error=None;self.started_at=utc_now();self.ended_at=None;self.codec=None
        self.stop_event.clear();self.recording=True
        self.thread=threading.Thread(target=self._run,name="nazar-timelapse",daemon=True)
        self.thread.start()

    def stop(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=8)
        self.recording=False
        self.ended_at=utc_now()
        available=bool(self.path and self.path.is_file() and self.frame_count>0 and not self.error)
        return {"path":str(self.path) if available else None,"frame_count":self.frame_count,
            "started_at":self.started_at,"ended_at":self.ended_at,
            "file_size":self.path.stat().st_size if available else 0,"available":available,"error":self.error}

    def status(self):
        return {"recording":self.recording,"frames":self.frame_count,"output":str(self.path) if self.path else None,"codec":self.codec,"error":self.error}

    def _run(self):
        writer=None;last_sequence=-1;timing_file=None
        try:
            while not self.stop_event.is_set():
                sequence,source_timestamp,frame=self.camera.latest()
                if frame is not None and sequence!=last_sequence:
                    if self.overlay: frame=self.overlay(frame)
                    if writer is None:
                        h,w=frame.shape[:2]
                        writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*"avc1"),self.fps,(w,h))
                        self.codec="avc1"
                        if not writer.isOpened():
                            writer.release()
                            writer=cv2.VideoWriter(str(self.path),cv2.VideoWriter_fourcc(*"mp4v"),self.fps,(w,h))
                            self.codec="mp4v"
                        if not writer.isOpened(): raise RuntimeError("MP4 writer unavailable")
                        timing_file=self.path.with_suffix('.timestamps.csv').open('w',newline='',encoding='utf-8')
                        timing_writer=csv.writer(timing_file)
                        timing_writer.writerow(['frame_index','session_offset_s','recording_offset_s'])
                    if frame.shape[1]!=w or frame.shape[0]!=h: frame=cv2.resize(frame,(w,h))
                    source_type=self.camera.status().get('source','CAMERA') if hasattr(self.camera,'status') else 'CAMERA'
                    offset=source_timestamp if source_type=='VIDEO' else max(0,source_timestamp-datetime.fromisoformat(getattr(self,'session_started_at',self.started_at)).timestamp())
                    writer.write(frame)
                    timing_writer.writerow([self.frame_count,round(offset,6),self.frame_count/self.fps]);timing_file.flush()
                    self.frame_count+=1;last_sequence=sequence
                self.stop_event.wait(self.interval)
        except Exception as exc:
            self.error=str(exc);log.exception("Timelapse failed")
        finally:
            if writer is not None: writer.release()
            if timing_file is not None:timing_file.close()
            self.recording=False

class DisabledRecorder:
    def __init__(self): self.error=None
    def start(self,session_id): pass
    def stop(self):
        return {"path":None,"frame_count":0,"started_at":None,"ended_at":utc_now(),"file_size":0,"available":False,"error":None}
    def status(self): return {"recording":False,"frames":0,"output":None,"codec":None,"error":None}
