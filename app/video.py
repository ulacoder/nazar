"""Latest-frame video source with media timestamps for the production runtime."""
import logging
import threading
import time
from pathlib import Path
import cv2
from .config import ROOT

log=logging.getLogger(__name__)

def resolve_video_path(value):
    path=Path(value)
    return path if path.is_absolute() else ROOT/path

def media_timestamp(capture,frame_index,fps,previous=None):
    measured=capture.get(cv2.CAP_PROP_POS_MSEC)/1000.0
    fallback=frame_index/max(fps,1.0)
    value=measured if measured>0 or frame_index==0 else fallback
    if previous is not None and value<=previous: value=fallback
    if previous is not None and value<=previous: value=previous+1/max(fps,1.0)
    return value

class VideoFileSource:
    def __init__(self,path):
        self.path=resolve_video_path(path)
        self.lock=threading.Lock();self.stop_event=threading.Event();self.thread=None
        self.frame=None;self.sequence=0;self.timestamp=0.0
        self.connected=False;self.ended=False;self.error=None
        self.actual_fps=0.0;self.requested_fps=0.0
        self.duration_s=None;self.position_s=0.0;self.frame_index=0

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        self.thread=threading.Thread(target=self._run,name="nazar-video",daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=4)
        with self.lock: self.connected=False;self.frame=None

    def restart(self):
        self.close()
        with self.lock:
            self.ended=False;self.error=None;self.position_s=0.0;self.frame_index=0
        self.start()

    def latest(self):
        with self.lock: return self.sequence,self.timestamp,None if self.frame is None else self.frame.copy()

    def status(self):
        with self.lock:
            shape=self.frame.shape if self.frame is not None else None
            return {"source":"VIDEO","filename":self.path.name,"connected":self.connected,"ended":self.ended,
                "resolution":[shape[1],shape[0]] if shape else None,"requested_fps":round(self.requested_fps,1),
                "actual_fps":round(self.actual_fps,1),"position_s":round(self.position_s,3),
                "duration_s":round(self.duration_s,3) if self.duration_s is not None else None,"error":self.error}

    def _run(self):
        if not self.path.is_file():
            with self.lock: self.error=f"Video file not found: {self.path}";self.ended=True
            return
        capture=cv2.VideoCapture(str(self.path))
        if not capture.isOpened():
            with self.lock: self.error=f"Cannot open video: {self.path}";self.ended=True
            capture.release();return
        fps=capture.get(cv2.CAP_PROP_FPS)
        if fps<=0: fps=25.0
        count=capture.get(cv2.CAP_PROP_FRAME_COUNT)
        with self.lock:
            self.requested_fps=fps;self.duration_s=count/fps if count>0 else None
            self.connected=True
        wall_start=time.monotonic();previous_media=None;previous_wall=None;index=0
        try:
            while not self.stop_event.is_set():
                ok,frame=capture.read()
                if not ok: break
                media_s=media_timestamp(capture,index,fps,previous_media)
                delay=wall_start+media_s-time.monotonic()
                if delay>0 and self.stop_event.wait(delay): break
                wall=time.monotonic()
                with self.lock:
                    self.frame=frame;self.sequence+=1;self.timestamp=media_s
                    self.position_s=media_s;self.frame_index=index+1
                    if previous_wall is not None:
                        value=1/max(.001,wall-previous_wall)
                        self.actual_fps=value if not self.actual_fps else .8*self.actual_fps+.2*value
                previous_media=media_s;previous_wall=wall;index+=1
        except Exception as exc:
            with self.lock: self.error=str(exc)
            log.exception("Video source failed")
        finally:
            capture.release()
            with self.lock: self.connected=False;self.ended=not self.stop_event.is_set()
