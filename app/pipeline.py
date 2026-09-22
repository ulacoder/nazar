"""Single-pass pose → stable tracks → batched models → multi-label state."""
import logging
import time
from collections import deque
from .vision.models import PoseAdapter,ActionsAdapter,HeadAdapter
from .vision.ab import ShadowActions
from .vision.crops import make_person_crop,make_head_crop
from .vision.geometry import face_visible
from .vision.tracker_v6_1_final import TrackManager
from .vision.tracking_log import TrackingLog
from .vision.temporal import PersonTemporalState

log=logging.getLogger(__name__)

class VisionPipeline:
    def __init__(self,settings,pose=None,actions=None,head=None,actions_ab=None):
        self.settings=settings
        self.pose=pose if pose is not None else PoseAdapter(settings.pose_weights,settings.pose_conf,settings.device)
        self.actions=actions if actions is not None else ActionsAdapter(settings.action_weights,settings.action_config,settings.device)
        self.head=head if head is not None else HeadAdapter(settings.head_weights,settings.head_config,settings.device)
        self.actions_ab=actions_ab if actions_ab is not None else ShadowActions(settings)
        self.tracker=self._new_tracker()
        self.tracking_log=None
        self.states={}
        self.errors={"pose":None,"actions":None,"head":None,"actions_ab":None}
        self.latency={"pose_ms":0.0,"actions_ms":0.0,"actions_v2_ms":0.0,"actions_ab_ms":0.0,"head_ms":0.0,"total_ms":0.0}
        self.frames=0
        self.last_tracks=[]
        self.model_timestamps={name:deque(maxlen=120) for name in ("pose","actions","actions_ab","head")}

    def _rate(self,name):
        points=self.model_timestamps[name]
        if len(points)<2 or time.perf_counter()-points[-1]>2.0: return 0.0
        return (len(points)-1)/max(.001,points[-1]-points[0])

    def load(self):
        for name,adapter,enabled in (("pose",self.pose,True),("actions",self.actions,self.settings.actions_enabled),("head",self.head,self.settings.head_enabled)):
            if not enabled: continue
            try:
                adapter.load()
                self.errors[name]=None
                log.info("Loaded %s model on %s",name,adapter.device)
            except Exception as exc:
                self.errors[name]=str(exc)
                log.exception("Unable to load %s model",name)
        if self.settings.actions_ab_enabled:
            try:
                self.actions_ab.load(); self.errors["actions_ab"]=None
                log.info("Loaded actions shadow model")
            except Exception as exc:
                self.errors["actions_ab"]=str(exc); log.exception("Unable to load actions shadow model")

    def reset_tracks(self):
        self.tracker=self._new_tracker()
        self.states.clear();self.last_tracks=[]
        if hasattr(self.pose,"reset_tracking"): self.pose.reset_tracking()

    def process(self,frame,timestamp):
        started=time.perf_counter()
        self.latency={"pose_ms":0.0,"actions_ms":0.0,"head_ms":0.0,"total_ms":0.0}
        detections=[]
        if self.errors["pose"] is None:
            try:
                detections=self.pose.infer(frame)
                self.latency["pose_ms"]=self.pose.latency_ms
                self.model_timestamps["pose"].append(time.perf_counter())
            except Exception as exc:
                self.errors["pose"]=str(exc);log.exception("Pose inference failed")
        tracking_started=time.perf_counter()
        tracks=self.tracker.update(detections,timestamp,frame_shape=frame.shape)
        if self.tracking_log:self.tracking_log.record(self.tracker.debug_events)
        self.latency['tracking_ms']=(time.perf_counter()-tracking_started)*1000
        for tid in self.tracker.expired: self.states.pop(tid,None)
        for tid,track in self.tracker.tracks.items():
            if track.missed and tid in self.states:
                self.states[tid].clear_head()
        action_scores={}; action_v2_scores={}; crop_by_id={}; head_angles={}
        if self.settings.actions_enabled and self.errors["actions"] is None:
            crops=[];ids=[]
            for track in tracks:
                crop=make_person_crop(frame,track.bbox)
                if crop is not None: crops.append(crop);ids.append(track.track_id);crop_by_id[track.track_id]=crop
            if crops:
                try:
                    scores=self.actions.infer(crops)
                    action_scores=dict(zip(ids,scores))
                    self.latency["actions_ms"]=self.actions.latency_ms
                    self.model_timestamps["actions"].append(time.perf_counter())
                    if self.settings.actions_ab_enabled and self.errors["actions_ab"] is None:
                        try:
                            scores_v2=self.actions_ab.infer(crops)
                            action_v2_scores=dict(zip(ids,scores_v2))
                            self.latency["actions_v2_ms"]=self.actions_ab.latency_ms
                            self.latency["actions_ab_ms"]=self.latency["actions_ms"]+self.latency["actions_v2_ms"]
                            self.model_timestamps["actions_ab"].append(time.perf_counter())
                        except Exception as exc:
                            self.errors["actions_ab"]=str(exc); log.exception("Actions shadow inference failed")
                except Exception as exc:
                    self.errors["actions"]=str(exc);log.exception("Actions inference failed")
        if self.settings.head_enabled and self.errors["head"] is None:
            crops=[];ids=[]
            for track in tracks:
                # The head model can crop without a face, but the application
                # reports UNKNOWN_HEAD until facial keypoints are visible.
                if not face_visible(track.keypoints): continue
                crop=make_head_crop(frame,track.bbox,track.keypoints)
                if crop is not None: crops.append(crop);ids.append(track.track_id)
            if crops:
                try:
                    angles=self.head.infer(crops)
                    head_angles=dict(zip(ids,angles))
                    self.latency["head_ms"]=self.head.latency_ms
                    self.model_timestamps["head"].append(time.perf_counter())
                except Exception as exc:
                    self.errors["head"]=str(exc);log.exception("Head inference failed")
        thresholds=self.actions.thresholds
        outputs=[]
        for track in tracks:
            state=self.states.setdefault(track.track_id,PersonTemporalState(self.settings.writing_model_min,self.settings.writing_motion_min,self.settings.writing_temporal_min))
            outputs.append(state.update(track,action_scores.get(track.track_id),head_angles.get(track.track_id),self.head.classify,thresholds,timestamp))
            outputs[-1]['internal_track_id']=track.source_id
            outputs[-1]['reassociated']=track.reassociated
        if self.settings.actions_ab_enabled and self.errors["actions_ab"] is None:
            current_total_ms=(time.perf_counter()-started)*1000
            by_id={item["track_id"]:item for item in outputs}
            for tid, scores_v2 in action_v2_scores.items():
                scores_v1=action_scores.get(tid)
                if scores_v1 is None: continue
                item=by_id.get(tid)
                if item is None: continue
                item["actions_ab"]={
                    "label":"SHADOW / EXPERIMENTAL",
                    "v1":{"READING":float(scores_v1[0]),"WRITING":float(scores_v1[1]),"thresholds":dict(self.actions.thresholds)},
                    "v2":{"READING":float(scores_v2[0]),"WRITING":float(scores_v2[1]),"thresholds":dict(self.actions_ab.thresholds)},
                    "delta":{"READING":float(scores_v2[0]-scores_v1[0]),"WRITING":float(scores_v2[1]-scores_v1[1])},
                }
                attrs=item.get("attributes",[])
                body=next((a["name"] for a in attrs if a["name"] in {"SITTING","STANDING"}),"UNKNOWN")
                head=item.get("head",{}).get("label","UNKNOWN_HEAD")
                self.actions_ab.logger.record(timestamp,tid,crop_by_id.get(tid),scores_v1,scores_v2,self.actions_ab.thresholds,body,head,self.latency["actions_ms"],self.latency["actions_v2_ms"],current_total_ms)
        self.last_tracks=outputs
        self.frames+=1
        self.latency["total_ms"]=(time.perf_counter()-started)*1000
        return outputs

    def status(self):
        return {"models":{
            "pose":{"loaded":self.pose.model is not None,"name":self.pose.path.name,"device":str(self.pose.device),"error":self.errors["pose"]},
            "actions":{"loaded":self.actions.model is not None,"name":self.actions.weights.name,"device":str(self.actions.device),"error":self.errors["actions"],"thresholds":self.actions.thresholds,"threshold_source":"supplied V2 config; not validated for V4 checkpoint","checkpoint_threshold":.5},
            "head":{"loaded":self.head.model is not None,"name":self.head.weights.name,"device":str(self.head.device),"error":self.errors["head"]},
            "actions_ab":{"enabled":self.settings.actions_ab_enabled,"loaded":getattr(self.actions_ab,"loaded",False),"name":getattr(getattr(self.actions_ab,"adapter",None),"weights",None).name if getattr(getattr(self.actions_ab,"adapter",None),"weights",None) else None,"error":self.errors["actions_ab"],"thresholds":self.actions_ab.thresholds}},
            "latency_ms":{k:round(v,1) for k,v in self.latency.items()},"frames":self.frames,
            "model_fps":{name:round(self._rate(name),1) for name in self.model_timestamps},
            "active_tracks":len(self.tracker.tracks),"visible_tracks":len(self.last_tracks),"pose_calls":self.pose.calls,
            "tracking":self.tracker.summary(),"tracking_log_error":self.tracking_log.error if self.tracking_log else None}

    def _new_tracker(self):
        return TrackManager(max_gap_s=self.settings.track_max_gap_s,stationary_prior=self.settings.track_stationary_prior,home_alpha=self.settings.track_home_alpha,ambiguity_margin=self.settings.track_ambiguity_margin)

    def set_tracking_session(self,session_id):
        if self.tracking_log:self.tracking_log.close()
        self.tracking_log=TrackingLog(self.settings.tracking_debug_dir/f'{int(session_id)}.csv') if session_id is not None else None

    def actions_ab_summary(self):
        return self.actions_ab.logger.summary()

    def close(self):
        if self.tracking_log:self.tracking_log.close();self.tracking_log=None
        self.actions_ab.close()
