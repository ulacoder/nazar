"""Independent camera, AI, timelapse, and browser-facing state."""
import json
import logging
import os
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import datetime,timezone
from pathlib import Path
import cv2
import numpy as np
from .camera import CameraSource
from .pipeline import VisionPipeline
from .sessions import SessionManager,validate_metadata
from .storage.database import Store
from .system import hardware_status
from .timelapse import TimelapseRecorder,DisabledRecorder
from .video import VideoFileSource
from .overlay import draw_overlay
from .evidence import generate_review_clips
from .cameras import CameraManager
from .videos import inspect_video

log=logging.getLogger(__name__)

def _stamp(value): return datetime.fromtimestamp(value,timezone.utc).isoformat()

class Runtime:
    def __init__(self,settings,camera=None,pipeline=None,store=None):
        self.settings=settings
        self.store=store or Store(settings.database)
        self.camera_manager=CameraManager()
        self._restore_settings()
        self.camera=camera or self._make_source()
        self.pipeline=pipeline or VisionPipeline(settings)
        self.recorder=self._new_recorder()
        self.sessions=SessionManager(self.store,self.recorder,settings.event_min_duration,settings.event_cooldown)
        self.sessions.evidence_pre_s=settings.evidence_pre_s; self.sessions.evidence_post_s=settings.evidence_post_s
        self.lock=threading.RLock();self.condition=threading.Condition(self.lock)
        self.processing_lock=threading.Lock()
        self.source_epoch=0
        self.stop_event=threading.Event();self.ai_thread=None
        self.tracks=[];self.recent_events=deque(maxlen=12)
        self.state_version=0;self.last_ai_timestamp=None;self.ai_fps=0.0;self.last_error=None

    def _make_source(self):
        if self.settings.input_source=="VIDEO": return VideoFileSource(self.settings.video_path)
        if self.settings.input_source=="CAMERA":
            return CameraSource(self.settings.camera_index,self.settings.camera_width,self.settings.camera_height,self.settings.camera_fps,self.settings.camera_device_id)
        raise ValueError("NAZAR_INPUT_SOURCE must be CAMERA or VIDEO")

    def _new_recorder(self):
        if not self.settings.timelapse_enabled: return DisabledRecorder()
        overlay=(lambda frame:self.draw_overlay(frame)) if self.settings.timelapse_overlay else None
        return TimelapseRecorder(self.camera,self.settings.sessions_dir,self.settings.timelapse_interval,self.settings.timelapse_fps,overlay)

    def _restore_settings(self):
        env_names={"input_source":"NAZAR_INPUT_SOURCE","video_path":"NAZAR_VIDEO_PATH",
            "camera_device_id":"NAZAR_CAMERA_DEVICE_ID","camera_index":"NAZAR_CAMERA_INDEX","camera_width":"NAZAR_CAMERA_WIDTH",
            "camera_height":"NAZAR_CAMERA_HEIGHT","camera_fps":"NAZAR_CAMERA_FPS",
            "ai_interval":"NAZAR_AI_INTERVAL","pose_conf":"NAZAR_POSE_CONF",
            "actions_enabled":"NAZAR_ACTIONS_ENABLED","head_enabled":"NAZAR_HEAD_ENABLED",
            "actions_ab_enabled":"NAZAR_ACTIONS_AB_ENABLED",
            "timelapse_enabled":"NAZAR_TIMELAPSE_ENABLED","timelapse_interval":"NAZAR_TIMELAPSE_INTERVAL",
            "timelapse_fps":"NAZAR_TIMELAPSE_OUTPUT_FPS","timelapse_overlay":"NAZAR_TIMELAPSE_OVERLAY"}
        for key,value in self.store.load_settings().items():
            if env_names.get(key) and env_names[key] in os.environ: continue
            if hasattr(self.settings,key) and not key.endswith(("weights","config","database","dir")):
                setattr(self.settings,key,value)

    def start(self):
        if self.ai_thread and self.ai_thread.is_alive(): return
        self.pipeline.load()
        self.camera.start()
        self.stop_event.clear()
        self.ai_thread=threading.Thread(target=self._ai_loop,name="nazar-ai",daemon=True)
        self.ai_thread.start()
        log.info("NAZAR runtime started")

    def close(self):
        self.stop_event.set();self.camera.close()
        if self.ai_thread: self.ai_thread.join(timeout=5)
        if self.sessions.snapshot(): self.stop_session()
        if hasattr(self.pipeline,"close"): self.pipeline.close()
        log.info("NAZAR runtime stopped")

    def _ai_loop(self):
        seen=None;previous=None;cleared_end_epoch=None
        while not self.stop_event.is_set():
            epoch=self.source_epoch
            sequence,timestamp,frame=self.camera.latest()
            if frame is None or (epoch,sequence)==seen:
                if (self.settings.input_source=="VIDEO" and self.camera.status()["ended"]
                        and cleared_end_epoch!=epoch):
                    with self.processing_lock:
                        if epoch==self.source_epoch:
                            self.pipeline.reset_tracks()
                            with self.condition:
                                self.tracks=[];self.ai_fps=0.0
                                self.state_version+=1;self.condition.notify_all()
                            cleared_end_epoch=epoch
                self.stop_event.wait(.02);continue
            seen=(epoch,sequence)
            cleared_end_epoch=None
            try:
                with self.processing_lock:
                    if epoch!=self.source_epoch: continue
                    tracks=self.pipeline.process(frame,timestamp)
                    offset=timestamp if self.settings.input_source=="VIDEO" else None
                    events=self.sessions.observe(tracks,timestamp,source_offset_s=offset)
                clock=time.monotonic()
                with self.condition:
                    self.tracks=tracks;self.recent_events.extendleft(reversed(events))
                    self.last_ai_timestamp=_stamp(time.time());self.last_error=None
                    if previous is not None:
                        fps=1/max(.001,clock-previous)
                        self.ai_fps=fps if not self.ai_fps else .8*self.ai_fps+.2*fps
                    previous=clock;self.state_version+=1;self.condition.notify_all()
            except Exception as exc:
                log.exception("AI worker failed on frame")
                with self.condition: self.last_error=str(exc);self.state_version+=1;self.condition.notify_all()
            if self.settings.ai_interval>0: self.stop_event.wait(self.settings.ai_interval)

    def start_session(self,mode,metadata=None):
        if not isinstance(mode,str) or mode.upper() not in {"LESSON","EXAM"}: raise ValueError("Mode must be LESSON or EXAM")
        metadata=validate_metadata(metadata)
        if self.sessions.snapshot(): raise RuntimeError("A session is already active")
        if self.settings.input_source=="VIDEO" and self.ai_thread and self.ai_thread.is_alive():
            self.camera.close()
            with self.processing_lock:
                self.source_epoch+=1;self.pipeline.reset_tracks()
            with self.condition: self.tracks=[];self.ai_fps=0.0
        source_name=self.camera.path.name if isinstance(self.camera,VideoFileSource) else None
        result=self.sessions.start(mode,self.settings.input_source,source_name,metadata)
        if isinstance(self.camera,VideoFileSource):self.store.set_source_video(result['id'],self.camera.path.resolve())
        with self.processing_lock:
            if hasattr(self.pipeline,'set_tracking_session'):self.pipeline.set_tracking_session(result['id'])
        if hasattr(self.pipeline,"actions_ab"): self.pipeline.actions_ab.set_session(result["id"])
        if self.settings.input_source=="VIDEO" and self.ai_thread and self.ai_thread.is_alive(): self.camera.restart()
        with self.condition:
            self.recent_events.clear();self.state_version+=1;self.condition.notify_all()
        log.info("Session %s started (%s)",result["id"],result["mode"])
        return result

    def stop_session(self):
        result=self.sessions.stop()
        with self.processing_lock:
            if hasattr(self.pipeline,'set_tracking_session'):self.pipeline.set_tracking_session(None)
        if hasattr(self.pipeline,"actions_ab"): self.pipeline.actions_ab.set_session("standalone")
        if result.get('mode')=='EXAM':
            generate_review_clips(result,self.store.events(result['id'],limit=None),self.settings.evidence_dir/str(result['id']))
        with self.condition: self.state_version+=1;self.condition.notify_all()
        log.info("Session %s stopped",result["id"])
        return result

    def cameras(self,rescan=False):
        return self.camera_manager.discover() if rescan or not self.camera_manager.devices else [device.as_dict() for device in self.camera_manager.devices]

    def select_camera(self,payload):
        if self.sessions.snapshot(): raise RuntimeError('End the current session before changing the input source.')
        if not isinstance(payload,dict): raise ValueError('Camera selection must be an object')
        device=self.camera_manager.select(payload.get('device_id'))
        self.settings.input_source='CAMERA';self.settings.camera_device_id=device.device_id;self.settings.camera_index=device.index
        self.store.save_settings({'input_source':'CAMERA','camera_device_id':device.device_id,'camera_index':device.index})
        self._replace_source_if_running()
        return device.as_dict()

    def import_video(self,path):
        if self.sessions.snapshot(): raise RuntimeError('End the current session before changing the input source.')
        metadata=inspect_video(path)
        self.settings.input_source='VIDEO';self.settings.video_path=str(Path(path).resolve())
        self.store.save_settings({'input_source':'VIDEO','video_path':self.settings.video_path})
        self._replace_source_if_running()
        return metadata

    def _replace_source_if_running(self):
        if not (self.ai_thread and self.ai_thread.is_alive()): return
        self.camera.close()
        with self.processing_lock:
            self.source_epoch+=1;self.pipeline.reset_tracks()
        with self.condition:
            self.tracks=[];self.ai_fps=0.0;self.state_version+=1;self.condition.notify_all()
        self.camera=self._make_source();self.camera.start()

    def state(self):
        with self.lock:
            session=self.sessions.snapshot()
            tracks=list(self.tracks)
            roles=self.store.person_roles(session["id"]) if session else {}
            for track in tracks: track["role"]=roles.get(track["track_id"],"UNKNOWN")
            return {"session":session,"tracks":tracks,"person_roles":roles,"recent_events":list(self.recent_events),
                'exam_observations':self.sessions.live_observations([t['track_id'] for t in self.tracks]),
                'persistence_error':self.sessions.persistence_error,
                "visible_people":len(self.tracks),"camera":self.camera.status(),"ai":{"fps":round(self.ai_fps,1),
                "last_frame_at":self.last_ai_timestamp,"error":self.last_error},"timelapse":self.recorder.status(),
                "actions_ab":{"enabled":self.settings.actions_ab_enabled,"summary":self.pipeline.actions_ab_summary() if hasattr(self.pipeline,"actions_ab_summary") else {}},
                "version":self.state_version}

    def set_person_role(self,person_id,role):
        session=self.sessions.snapshot()
        if not session: raise RuntimeError("No active session")
        result=self.store.set_person_role(session["id"],person_id,role)
        if result is None: raise ValueError("Session not found")
        with self.condition: self.state_version+=1; self.condition.notify_all()
        return result

    def status(self):
        return {**self.state(),"pipeline":self.pipeline.status(),"hardware":hardware_status()}

    def events_stream(self):
        previous=-1;last_sent=0
        while not self.stop_event.is_set():
            # Metadata at 5 Hz; the independent MJPEG stream keeps its own cadence.
            delay=.2-(time.monotonic()-last_sent)
            if delay>0 and self.stop_event.wait(delay):break
            with self.condition:
                if self.state_version==previous: self.condition.wait(timeout=15)
                previous=self.state_version
            last_sent=time.monotonic()
            yield "data: "+json.dumps(self.state())+"\n\n"

    def draw_overlay(self,frame,language=None):
        with self.lock: tracks=list(self.tracks);settings=self.settings
        return draw_overlay(frame,tracks,settings.boxes_overlay,settings.skeleton_overlay,settings.attributes_overlay,settings.overlay_debug,language or settings.overlay_language)

    def video_stream(self,language=None):
        previous=-1
        while not self.stop_event.is_set():
            sequence,_,frame=self.camera.latest()
            unavailable=frame is None
            if unavailable:
                frame=np.full((480,720,3),245,dtype=np.uint8)
                cv2.putText(frame,"Source unavailable",(190,240),cv2.FONT_HERSHEY_SIMPLEX,.9,(100,110,115),2)
            elif sequence==previous:
                self.stop_event.wait(.05);continue
            previous=sequence
            view=self.draw_overlay(frame,language)
            ok,encoded=cv2.imencode(".jpg",view,[cv2.IMWRITE_JPEG_QUALITY,78])
            if ok: yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+encoded.tobytes()+b"\r\n"
            if unavailable: self.stop_event.wait(1)

    def settings_view(self):
        names=("input_source","video_path","camera_device_id","camera_index","camera_width","camera_height","camera_fps","ai_interval","pose_conf","actions_enabled","actions_ab_enabled","head_enabled",
            "boxes_overlay","skeleton_overlay","attributes_overlay","event_min_duration","event_cooldown","timelapse_enabled",
            "timelapse_interval","timelapse_fps","timelapse_overlay")
        return {name:getattr(self.settings,name) for name in names}

    def update_settings(self,changes):
        allowed=self.settings_view()
        if not isinstance(changes,dict) or not changes: raise ValueError("No settings supplied")
        invalid=set(changes)-set(allowed)
        if invalid: raise ValueError("Unknown settings: "+", ".join(sorted(invalid)))
        camera_keys={"input_source","video_path","camera_device_id","camera_index","camera_width","camera_height","camera_fps"}
        recorder_keys={"timelapse_enabled","timelapse_interval","timelapse_fps","timelapse_overlay"}
        if self.sessions.snapshot() and set(changes)&(camera_keys|recorder_keys): raise RuntimeError("Stop the session before changing camera or timelapse settings")
        validated={}
        for name,value in changes.items():
            old=allowed[name]
            if isinstance(old,bool):
                if not isinstance(value,bool): raise ValueError(name+" must be boolean")
            elif isinstance(old,str):
                if not isinstance(value,str): raise ValueError(name+" must be text")
                if name=="input_source" and value not in {"CAMERA","VIDEO"}: raise ValueError("input_source must be CAMERA or VIDEO")
            elif isinstance(old,int):
                if not isinstance(value,int) or isinstance(value,bool): raise ValueError(name+" must be integer")
            elif not isinstance(value,(int,float)) or isinstance(value,bool): raise ValueError(name+" must be numeric")
            if isinstance(value,(int,float)) and not isinstance(value,bool):
                if name!="camera_index" and value<=0 and name not in {"ai_interval"}: raise ValueError(name+" must be positive")
                if name=="camera_index" and value<0: raise ValueError(name+" must be nonnegative")
                if name=="pose_conf" and not 0<value<=1: raise ValueError(name+" must be in (0,1]")
            validated[name]=value
        proposed={**allowed,**validated}
        if proposed["input_source"]=="VIDEO" and not proposed["video_path"].strip():
            raise ValueError("video_path is required for VIDEO input")
        for name,value in validated.items():
            setattr(self.settings,name,value)
        self.store.save_settings(changes)
        if "pose_conf" in changes: self.pipeline.pose.conf=self.settings.pose_conf
        if "event_min_duration" in changes: self.sessions.events.minimum_s=self.settings.event_min_duration
        if "event_cooldown" in changes: self.sessions.events.cooldown_s=self.settings.event_cooldown
        if set(changes)&camera_keys:
            self.camera.close()
            with self.processing_lock:
                self.source_epoch+=1;self.pipeline.reset_tracks()
            with self.condition: self.tracks=[]
            self.camera=self._make_source();self.camera.start()
        if set(changes)&(camera_keys|recorder_keys):
            self.recorder=self._new_recorder();self.sessions.recorder=self.recorder
        with self.condition: self.state_version+=1;self.condition.notify_all()
        return self.settings_view()
