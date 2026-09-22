"""Stable observable states become transition events after confirmation."""
import math
from collections import deque

EXAM_OBSERVATIONS=frozenset({'LOOKING_LEFT','LOOKING_RIGHT','LOOKING_DOWN','LOOKING_UP',
    'TURNED_BACK','HAND_RAISED','STANDING','READING','WRITING'})
HEAD_STATES=frozenset({'LOOKING_LEFT','LOOKING_RIGHT','LOOKING_DOWN','LOOKING_UP','LOOKING_FORWARD','TURNED_BACK'})

class EventEngine:
    def __init__(self,minimum_s=.8,cooldown_s=4.0):
        self.minimum_s=minimum_s;self.cooldown_s=cooldown_s
        self.pending={};self.active=set();self.last_emit={}
        self.mode='LESSON';self.confirmed_head={};self.head_pending={};self.absent_since={};self.head_occurrences={}

    def reset(self,mode=None):
        self.pending.clear();self.active.clear();self.last_emit.clear()
        self.confirmed_head.clear();self.head_pending.clear();self.absent_since.clear();self.head_occurrences.clear()
        if mode is not None:self.mode=mode

    @staticmethod
    def score(attribute):
        value=attribute.get('confidence')
        if (attribute.get('name') in {'READING','WRITING'} and attribute.get('source')=='action_model'
                and isinstance(value,(int,float)) and math.isfinite(value) and 0<=value<=1):
            return value
        return None

    def _emit(self,key,attribute,timestamp,events,duration=None,reason=None,review_priority="NORMAL"):
        if timestamp-self.last_emit.get(key,float('-inf'))>=self.cooldown_s:
            events.append({'track_id':key[0],'event_type':key[1],'confidence':self.score(attribute),'timestamp':timestamp,'duration_s':duration,'review_priority':review_priority,'reason':reason})
            self.last_emit[key]=timestamp

    def _exam_update(self,tracks,timestamp):
        events=[];seen=set()
        for track in tracks:
            tid=track['track_id'];seen.add(tid)
            attrs={a['name']:a for a in track['attributes']}
            heads=[name for name in HEAD_STATES if name in attrs]
            head='TURNED_BACK' if 'TURNED_BACK' in attrs else heads[0] if len(heads)==1 else None
            # Unknown/missing evidence cannot establish a new direction or rearm
            # the old one. FORWARD confirms a return even though it is not logged.
            if head is None:self.head_pending.pop(tid,None)
            elif head!=self.confirmed_head.get(tid):
                if self.head_pending.get(tid,(None,))[0]!=head:self.head_pending[tid]=(head,timestamp)
                if timestamp-self.head_pending[tid][1]>=self.minimum_s:
                    started=self.head_pending[tid][1]
                    self.confirmed_head[tid]=head;self.head_pending.pop(tid,None)
                    if head in EXAM_OBSERVATIONS:
                        history=self.head_occurrences.setdefault(tid,deque(maxlen=12));history.append((head,timestamp))
                        recent=sum(1 for name,when in history if name in {"LOOKING_LEFT","LOOKING_RIGHT","TURNED_BACK"} and timestamp-when<=30)
                        priority="HIGH_REVIEW" if (head=="TURNED_BACK" and recent>=2) or recent>=4 else "REVIEW"
                        reason=("Repeated backward turn within rolling window" if head=="TURNED_BACK" and priority=="HIGH_REVIEW" else f"Sustained {head.replace('LOOKING_','').lower()} direction")
                        self._emit((tid,head),attrs[head],timestamp,events,duration=timestamp-started,reason=reason,review_priority=priority)
            else:self.head_pending.pop(tid,None)
            for name in EXAM_OBSERVATIONS-HEAD_STATES:
                key=(tid,name)
                if name in attrs:
                    self.absent_since.pop(key,None);self.pending.setdefault(key,timestamp)
                    if key not in self.active and timestamp-self.pending[key]>=self.minimum_s:
                        self.active.add(key);self._emit(key,attrs[name],timestamp,events)
                else:
                    self.pending.pop(key,None)
                    if key in self.active:
                        self.absent_since.setdefault(key,timestamp)
                        if timestamp-self.absent_since[key]>=self.minimum_s:
                            self.active.discard(key);self.absent_since.pop(key,None)
        for tid in list(self.head_pending):
            if tid not in seen:self.head_pending.pop(tid,None)
        for key in list(self.pending):
            if key[0] not in seen:self.pending.pop(key,None)
        for key in list(self.absent_since):
            if key[0] not in seen:self.absent_since.pop(key,None)
        return events

    def update(self,tracks,timestamp):
        if self.mode=='EXAM':return self._exam_update(tracks,timestamp)
        visible={}
        for track in tracks:
            for attribute in track["attributes"]:
                visible[(track["track_id"],attribute["name"])]=attribute
        events=[]
        for key,attribute in visible.items():
            self.pending.setdefault(key,timestamp)
            if key not in self.active and timestamp-self.pending[key]>=self.minimum_s:
                self.active.add(key)
                if timestamp-self.last_emit.get(key,float("-inf"))>=self.cooldown_s:
                    events.append({"track_id":key[0],"event_type":key[1],"confidence":self.score(attribute),"timestamp":timestamp})
                    self.last_emit[key]=timestamp
        for key in list(self.pending):
            if key not in visible:
                self.pending.pop(key,None);self.active.discard(key)
        return events
