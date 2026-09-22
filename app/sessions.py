"""One active Lesson or Exam session and its recording lifecycle."""
import threading
import queue
from collections import deque
from datetime import datetime,timezone
from .events import EventEngine
from .evidence import evidence_window

def utc_now(): return datetime.now(timezone.utc).isoformat()

def validate_metadata(values):
    if values is None: return {key:None for key in ("teacher","class_name","subject","notes")}
    if not isinstance(values,dict): raise ValueError("Session metadata must be an object")
    metadata={}
    for key,limit in (("teacher",120),("class_name",80),("subject",160),("notes",1000)):
        value=values.get(key)
        if value is not None and not isinstance(value,str): raise ValueError(f"{key} must be text")
        if value is not None and (len(value)>limit or any(ord(char)<32 and char not in '\n\t' for char in value)):
            raise ValueError(f"{key} is invalid or too long")
        metadata[key]=value.strip() or None if value is not None else None
    return metadata

class SessionManager:
    def __init__(self,store,recorder,event_min_duration=.8,event_cooldown=4.0):
        self.store=store;self.recorder=recorder
        self.events=EventEngine(event_min_duration,event_cooldown)
        self.lock=threading.RLock();self.active=None
        self.track_ids=set();self.event_counts={};self.last_visibility_sample=None
        self.spans={};self.person_events={};self.person_counts={};self.write_queue=None
        self.writer=None;self.persistence_error=None;self.failed_batches=[];self.stopping=False
        self.evidence_pre_s=3.0;self.evidence_post_s=3.0

    def _write_loop(self):
        while True:
            item=self.write_queue.get()
            try:
                if item is None:return
                try:self.store.write_observation(*item)
                except Exception as exc:
                    self.persistence_error=str(exc);self.failed_batches.append(item)
            finally:self.write_queue.task_done()

    def _enqueue(self,events=None,sample=None):
        self.write_queue.put((self.active['id'],events or [],{tid:tuple(span) for tid,span in self.spans.items()},sample))

    def start(self,mode,source_type="CAMERA",source_name=None,metadata=None):
        mode=mode.upper()
        if mode not in {"LESSON","EXAM"}: raise ValueError("Mode must be LESSON or EXAM")
        metadata=validate_metadata(metadata)
        with self.lock:
            if self.active or self.stopping: raise RuntimeError("A session is already active or stopping")
            started=utc_now();session_id=self.store.start_session(mode,started,source_type,source_name,metadata,
                getattr(self.recorder,"interval",None),getattr(self.recorder,"fps",None))
            self.active={"id":session_id,"mode":mode,"started_at":started,"source_type":source_type,"source_name":source_name,**metadata}
            self.track_ids=set();self.event_counts={};self.last_visibility_sample=None;self.events.reset(mode)
            self.spans={};self.person_events={};self.person_counts={};self.persistence_error=None;self.failed_batches=[]
            self.write_queue=queue.Queue();self.writer=threading.Thread(target=self._write_loop,name='nazar-session-writer',daemon=True);self.writer.start()
            self.recorder.session_started_at=started
            try: self.recorder.start(session_id)
            except Exception as exc: self.recorder.error=str(exc)
            return dict(self.active)

    def stop(self):
        with self.lock:
            if not self.active: raise RuntimeError("No active session")
            active=dict(self.active)
            summary={"event_types":dict(self.event_counts),"tracks_observed":len(self.track_ids)}
            self._enqueue();self.write_queue.put(None)
            self.active=None;self.stopping=True;self.events.reset()
        try:
            # Stop/flush outside the observation lock, so ongoing inference can
            # immediately see that there is no longer an active session.
            self.write_queue.join();self.writer.join()
            while self.failed_batches:
                self.store.write_observation(*self.failed_batches[0]);self.failed_batches.pop(0)
            self.persistence_error=None
            try: recording=self.recorder.stop()
            except Exception as exc: recording={"path":None,"frame_count":0,"available":False,"error":str(exc)}
            self.store.save_timelapse(active["id"],recording)
            self.store.stop_session(active["id"],utc_now(),summary["tracks_observed"],summary)
            return self.store.session(active["id"])
        except Exception as exc:
            self.persistence_error=str(exc)
            raise
        finally:
            self.stopping=False

    def observe(self,tracks,timestamp,source_offset_s=None):
        with self.lock:
            if not self.active: return []
            self.track_ids.update(track["track_id"] for track in tracks)
            offset=source_offset_s if source_offset_s is not None else max(0,timestamp-datetime.fromisoformat(self.active["started_at"]).timestamp())
            for track in tracks:
                span=self.spans.setdefault(track['track_id'],[offset,offset]);span[1]=offset
            sample=None
            if self.last_visibility_sample is None or offset-self.last_visibility_sample>=1.0:
                sample=(round(offset,3),len(tracks))
                self.last_visibility_sample=offset
            generated=self.events.update(tracks,timestamp)
            rows=[]
            for event in generated:
                self.event_counts[event["event_type"]]=self.event_counts.get(event["event_type"],0)+1
                occurred_at=utc_now() if source_offset_s is not None else datetime.fromtimestamp(timestamp,timezone.utc).isoformat()
                duration=event.get("duration_s")
                evidence_start=evidence_end=None
                if self.active['mode']=='EXAM' and event.get('review_priority') in {'REVIEW','HIGH_REVIEW'}:
                    evidence_start,evidence_end=evidence_window(offset,duration,self.evidence_pre_s,self.evidence_post_s)
                row={"session_id":self.active['id'],"occurred_at":occurred_at,"track_id":event["track_id"],"event_type":event["event_type"],"confidence":event["confidence"],"source_offset_s":source_offset_s,'session_offset_s':round(offset,3),"duration_s":duration,"review_priority":event.get("review_priority","NORMAL"),"reason":event.get("reason"),"evidence_start_s":evidence_start,"evidence_end_s":evidence_end}
                rows.append(row)
                self.person_events.setdefault(event['track_id'],deque(maxlen=20)).append(row)
                counts=self.person_counts.setdefault(event['track_id'],{})
                counts[event['event_type']]=counts.get(event['event_type'],0)+1
            if rows or sample is not None:self._enqueue(rows,sample)
            return rows

    def live_observations(self,track_ids):
        with self.lock:
            if not self.active or self.active['mode']!='EXAM':return {}
            roles=self.store.person_roles(self.active['id'])
            result={}
            for tid in track_ids:
                role=roles.get(tid,'UNKNOWN')
                result[tid]={'role':role,'student_included':role=='STUDENT',
                    'count':sum(self.person_counts.get(tid,{}).values()),'counts':dict(self.person_counts.get(tid,{})),
                    'recent':list(self.person_events.get(tid,()))}
            return result

    def snapshot(self):
        with self.lock:
            return dict(self.active) if self.active else None
