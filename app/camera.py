"""Camera capture is independent of AI and readers see only the latest frame."""
import logging
import threading
import time
import cv2

log=logging.getLogger(__name__)

class CameraSource:
    def __init__(self,index=0,width=1280,height=720,fps=30,device_id=''):
        self.index=index;self.device_id=device_id or f'index:{index}';self.width=width;self.height=height;self.requested_fps=fps
        self.lock=threading.Lock();self.stop_event=threading.Event();self.thread=None
        self.frame=None;self.sequence=0;self.timestamp=0.0
        self.connected=False;self.actual_fps=0.0;self.error=None

    def start(self):
        if self.thread and self.thread.is_alive(): return
        self.stop_event.clear()
        self.thread=threading.Thread(target=self._run,name="nazar-camera",daemon=True)
        self.thread.start()

    def close(self):
        self.stop_event.set()
        if self.thread: self.thread.join(timeout=4)

    def latest(self):
        with self.lock:
            return self.sequence,self.timestamp,None if self.frame is None else self.frame.copy()

    def status(self):
        with self.lock:
            shape=self.frame.shape if self.frame is not None else None
            return {"source":"CAMERA","connected":self.connected,"resolution":[shape[1],shape[0]] if shape else None,
                "requested_fps":self.requested_fps,"actual_fps":round(self.actual_fps,1),"error":self.error,"device_id":self.device_id,
                "position_s":None,"duration_s":None,"ended":False}

    def _run(self):
        while not self.stop_event.is_set():
            backend=cv2.CAP_DSHOW if hasattr(cv2,"CAP_DSHOW") and __import__("sys").platform=="win32" else cv2.CAP_ANY
            cap=cv2.VideoCapture(self.index,backend)
            if not cap.isOpened():
                with self.lock: self.connected=False;self.error=f"Camera {self.index} unavailable"
                cap.release();self.stop_event.wait(2);continue
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,self.width)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT,self.height)
            cap.set(cv2.CAP_PROP_FPS,self.requested_fps)
            log.info("Camera %s connected",self.index)
            previous=None
            while not self.stop_event.is_set():
                ok,frame=cap.read()
                if not ok: break
                clock=time.monotonic()
                with self.lock:
                    self.frame=frame;self.sequence+=1;self.timestamp=time.time()
                    self.connected=True;self.error=None
                    if previous is not None:
                        current_fps=1/max(.001,clock-previous)
                        self.actual_fps=current_fps if self.actual_fps==0 else .85*self.actual_fps+.15*current_fps
                previous=clock
            cap.release()
            with self.lock: self.connected=False;self.error="Camera disconnected"
            if not self.stop_event.is_set(): log.warning("Camera disconnected; reconnecting")
            self.stop_event.wait(1)
