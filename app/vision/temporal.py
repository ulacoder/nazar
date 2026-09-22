"""Per-track multi-label histories; reference constants with guarded initial posture."""
from collections import Counter,deque
import numpy as np
from .geometry import pose_body_state,hand_raised_state,turned_back_candidate,shoulder_anchor_y,face_visible,KEYPOINT_CONF

class PersonTemporalState:
    def __init__(self,writing_model_min=.45,writing_motion_min=.025,writing_temporal_min=.52):
        self.body=deque(maxlen=7);self.pose_history=deque(maxlen=7)
        self.hand=deque(maxlen=7);self.turned_back=deque(maxlen=7)
        self.reading=deque(maxlen=7);self.writing=deque(maxlen=7)
        self.head_directions=deque(maxlen=5)
        self.body_calibration=deque(maxlen=15);self.body_motion=deque(maxlen=7)
        self.baseline_y=None;self.baseline_h=None;self.body_current=None
        self.action_ema=None;self.head_ema=None
        self.writing_model_min=float(writing_model_min);self.writing_motion_min=float(writing_motion_min);self.writing_temporal_min=float(writing_temporal_min)
        self.writing_evidence=deque(maxlen=12);self.previous_wrists=None

    def clear_head(self):
        self.head_ema=None;self.head_directions.clear()

    def _body_state(self,keypoints,box,pose_body):
        anchor=shoulder_anchor_y(keypoints)
        person_h=max(float(box[3]-box[1]),1.0)
        if anchor is None: return self.body_current
        if self.baseline_y is None:
            self.body_calibration.append((anchor,person_h))
            if len(self.body_calibration)<15: return None
            self.baseline_y=float(np.median([x[0] for x in self.body_calibration]))
            self.baseline_h=float(np.median([x[1] for x in self.body_calibration]))
            # The reference assumed every initial track was sitting. Production
            # requires repeated visible sitting pose evidence before saying so.
            if list(self.pose_history).count("SITTING")>=4:
                self.body_current="SITTING"
            elif list(self.pose_history).count("STANDING")>=4:
                self.body_current="STANDING"
            return self.body_current
        if pose_body=="SITTING":
            self.body_motion.append("SITTING")
        elif self.body_current is None and pose_body=="STANDING":
            # A person may enter already standing. Repeated full-leg evidence
            # can establish that state without inventing a seated baseline.
            self.body_motion.append("STANDING")
        else:
            rise=(self.baseline_y-anchor)/max(self.baseline_h,1)
            height_ratio=person_h/max(self.baseline_h,1)
            lower_visible=any(keypoints[i,2]>=KEYPOINT_CONF for i in (11,12)) and any(keypoints[i,2]>=KEYPOINT_CONF for i in (13,14))
            if rise>=.12 and height_ratio>=1.06:
                if lower_visible and pose_body=="STANDING" and self.body_current=="SITTING":
                    self.body_motion.append("STANDING")
                else:
                    self.body_current=None;self.body_motion.clear();return None
            elif abs(rise)<=.07 and .85<=height_ratio<=1.15:
                if pose_body=="SITTING": self.body_motion.append("SITTING")
        if self.body_motion.count("STANDING")>=4: self.body_current="STANDING"
        elif self.body_motion.count("SITTING")>=4:
            self.body_current="SITTING"
            self.baseline_y=.98*self.baseline_y+.02*anchor
            self.baseline_h=.98*self.baseline_h+.02*person_h
        return self.body_current

    def update(self,track,action_scores,head_angles,head_classifier,action_thresholds,timestamp=None):
        kp=track.keypoints;box=track.bbox
        pose_body=pose_body_state(kp)
        self.pose_history.append(pose_body)
        body=self._body_state(kp,box,pose_body)
        if body: self.body.append(body)
        raised=hand_raised_state(kp,max(float(box[3]-box[1]),1))
        if raised is None: self.hand.clear()
        else: self.hand.append(raised)
        self.turned_back.append(turned_back_candidate(kp))
        turned=len(self.turned_back)>=5 and sum(self.turned_back)>=5
        attributes=[]
        wrist_motion=0.0
        wrists=[kp[i,:2] for i in (9,10) if kp[i,2]>=KEYPOINT_CONF]
        if self.previous_wrists is not None and wrists:
            n=min(len(wrists),len(self.previous_wrists)); person_h=max(float(box[3]-box[1]),1.0)
            wrist_motion=min(1.0,float(np.mean([np.linalg.norm(wrists[i]-self.previous_wrists[i])/person_h for i in range(n)]))/0.08)
        if wrists:self.previous_wrists=[w.copy() for w in wrists]
        if body in {"SITTING","STANDING"} and self.body.count(body)>=4:
            attributes.append({"name":body,"confidence":None,"source":"geometry"})
        if self.hand and sum(self.hand)/len(self.hand)>=.5:
            attributes.append({"name":"HAND_RAISED","confidence":None,"source":"geometry"})
        if turned: attributes.append({"name":"TURNED_BACK","confidence":None,"source":"geometry"})
        if action_scores is None:
            self.action_ema=None;self.reading.clear();self.writing.clear()
        else:
            scores=np.asarray(action_scores,dtype=np.float32)
            self.action_ema=scores.copy() if self.action_ema is None else .25*scores+.75*self.action_ema
            self.writing_evidence.append((float(self.action_ema[1]),wrist_motion,body))
            for i,(name,history) in enumerate((("READING",self.reading),("WRITING",self.writing))):
                threshold=action_thresholds[name]
                history.append(bool(self.action_ema[i]>=threshold))
                fusion_ok=False
                if name=="WRITING" and self.writing_evidence:
                    recent=list(self.writing_evidence)
                    avg_prob=float(np.mean([x[0] for x in recent])); avg_motion=float(np.mean([x[1] for x in recent]))
                    motion_frames=sum(x[1]>=self.writing_motion_min for x in recent)
                    temporal_score=.65*avg_prob+.35*min(1.0,motion_frames/max(1,len(recent)))
                    fusion_ok=avg_prob>=self.writing_model_min and avg_motion>=self.writing_motion_min and temporal_score>=self.writing_temporal_min
                strong_raw=(self.action_ema[i]>=min(1.0,threshold+.15))
                if len(history)>=5 and sum(history)>=5 and (name!="WRITING" or strong_raw or fusion_ok):
                    attributes.append({"name":name,"confidence":float(self.action_ema[i]),"source":"action_model"})
        head="UNKNOWN_HEAD";pitch=yaw=None
        if turned or head_angles is None or not face_visible(kp):
            self.clear_head()
        else:
            angles=np.asarray(head_angles,dtype=np.float32)
            self.head_ema=angles.copy() if self.head_ema is None else .25*angles+.75*self.head_ema
            pitch,yaw=map(float,self.head_ema)
            raw=head_classifier(pitch,yaw)
            self.head_directions.append(raw)
            if len(self.head_directions)>=3:
                head=Counter(self.head_directions).most_common(1)[0][0]
        if head!="UNKNOWN_HEAD": attributes.append({"name":head,"confidence":None,"source":"head_model"})
        recent=list(self.writing_evidence)
        avg_prob=float(np.mean([x[0] for x in recent])) if recent else 0.0
        avg_motion=float(np.mean([x[1] for x in recent])) if recent else 0.0
        temporal_score=.65*avg_prob+.35*min(1.0,sum(x[1]>=self.writing_motion_min for x in recent)/max(1,len(recent))) if recent else 0.0
        final_names={a["name"] for a in attributes}
        return {"track_id":track.track_id,"bbox":[float(x) for x in box],"keypoints":kp.tolist(),"attributes":attributes,"head":{"label":head,"pitch":pitch,"yaw":yaw},"pose_body":pose_body,"turned_back":turned,
                "actions_temporal":{"raw_reading_probability":float(self.action_ema[0]) if self.action_ema is not None else None,"raw_writing_probability":float(self.action_ema[1]) if self.action_ema is not None else None,"writing_motion_score":avg_motion,"writing_temporal_score":temporal_score,"final_reading":"READING" in final_names,"final_writing":"WRITING" in final_names}}
