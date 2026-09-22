"""Anonymous global assignment with bounded motion memory and decision diagnostics."""
from collections import Counter, deque
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from .types import Track


def center(b): return (np.asarray(b[:2])+np.asarray(b[2:]))/2
def size(b): return np.maximum(1,np.subtract(b[2:],b[:2]))
def _iou(a,b):
    intersection=float(np.prod(np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]))))
    union=float(np.prod(size(a))+np.prod(size(b)))-intersection
    return intersection/union if union else 0.
def _distance(a,b): return float(np.linalg.norm(center(a)-center(b))/max(*size(a),*size(b)))

def _overlap_min(a,b):
    intersection=float(np.prod(np.maximum(0,np.minimum(a[2:],b[2:])-np.maximum(a[:2],b[:2]))))
    smallest=min(float(np.prod(size(a))),float(np.prod(size(b))))
    return intersection/smallest if smallest else 0.

def _bbox_ratio(a,b):
    sa=size(a); sb=size(b)
    return float(max(*(sa/sb),*(sb/sa)))

def _duplicate_detection(a,b):
    """Conservative duplicate suppression for one physical detection."""

    if (
        a.source_id is not None
        and b.source_id is not None
        and a.source_id == b.source_id
    ):
        return True

    iou=_iou(a.bbox,b.bbox)
    iom=_overlap_min(a.bbox,b.bbox)
    dist=_distance(a.bbox,b.bbox)
    ratio=_bbox_ratio(a.bbox,b.bbox)

    ka=np.asarray(a.keypoints)
    kb=np.asarray(b.keypoints)

    pose=None

    if (
        ka.ndim == 2
        and kb.ndim == 2
        and ka.shape == kb.shape
        and ka.shape[1] >= 3
    ):
        valid=(ka[:,2]>=.40)&(kb[:,2]>=.40)

        if int(valid.sum()) >= 4:
            scale=max(*size(a.bbox),*size(b.bbox))

            pose=float(
                np.median(
                    np.linalg.norm(
                        ka[valid,:2]-kb[valid,:2],
                        axis=1
                    )
                ) / scale
            )

    # Two detections of the same person normally have almost
    # identical box AND almost identical skeleton.
    if (
        iou >= .78
        and pose is not None
        and pose <= .040
    ):
        return True

    # Nested duplicate boxes.
    if (
        iom >= .94
        and dist <= .25
        and ratio <= 2.20
        and pose is not None
        and pose <= .050
    ):
        return True

    # Very rare fallback if pose confidence is poor.
    if (
        pose is None
        and iou >= .94
        and dist <= .12
        and ratio <= 1.35
    ):
        return True

    return False


class TrackManager:
    def __init__(self,max_missed=None,max_gap_s=2.5,max_center_distance=1.25,
                 stationary_prior=True,home_alpha=.015,ambiguity_margin=.08,max_assignment_cost=.65):
        self.max_missed=max_missed; self.max_gap_s=max_gap_s; self.max_center_distance=max_center_distance
        self.stationary_prior=stationary_prior; self.home_alpha=home_alpha; self.ambiguity_margin=ambiguity_margin
        self.max_assignment_cost=max_assignment_cost
        self.recovery_ttl_s=8.0
        self.frame_size=np.ones(2)

        self.next_id=1
        self.tracks={}
        self.memory={}
        self.source_to_id={}

        # Expired tracks are not visible/active, but their public ID
        # can be restored for a short time if the same detector source
        # comes back.
        self.dormant={}
        self.dormant_source_to_id={}
        self.expired=[]; self.reassociations=[]; self.debug_events=[]; self.frame_index=0
        self.counters=Counter({k:0 for k in ('stable_ids_created','successful_reassociations','failed_reassociations','tracker_id_changes','detector_gaps','possible_id_switches')})
        self.longest_gap=0.; self.rejection_reasons=Counter(); self.internal_ids=set()

    def _candidate(self,tid,det,timestamp):
        track=self.tracks[tid]; mem=self.memory[tid]; gap=max(0.,timestamp-track.last_seen)
        typical=np.median(np.array(mem['sizes']),axis=0); scale=max(*typical,*size(det.bbox))
        current=center(det.bbox); predicted=center(track.bbox)+mem['velocity']*min(gap,.75)
        dist=float(np.linalg.norm(current-center(track.bbox))/scale)
        pdist=float(np.linalg.norm(current-predicted)/scale)
        home=float(np.linalg.norm(current-mem['home'])/scale)
        ratio=float(max(*(size(det.bbox)/typical),*(typical/size(det.bbox))))
        overlap=_iou(track.bbox,det.bbox)
        a=np.asarray(track.keypoints); b=np.asarray(det.keypoints)
        valid=(a[:,2]>=.5)&(b[:,2]>=.5); valid[:5]=False
        pose=float(np.median(np.linalg.norm((a[valid,:2]-center(track.bbox))-(b[valid,:2]-current),axis=1))/scale) if sum(valid)>=3 else None
        position=min(pdist,home) if self.stationary_prior else pdist
        reason='PASS'
        if gap>self.max_gap_s: reason='MAX_GAP_EXCEEDED'
        elif ratio>2.2: reason='BBOX_SIZE_GATE'
        elif position>self.max_center_distance and overlap<.10: reason='PREDICTED_POSITION_GATE'
        cost=.45*position+.15*dist+.1*abs(math.log(ratio))+.15*(1-overlap)+.1*(pose or 0)+.05*gap/self.max_gap_s
        if det.source_id is not None and det.source_id==track.source_id: cost-=.12
        if reason=='PASS' and cost>=self.max_assignment_cost:reason='ASSIGNMENT_COST_GATE'
        return dict(stable_person_id=tid,old_internal_track_id=track.source_id,new_internal_track_id=det.source_id,
                    gap_s=gap,iou=overlap,normalized_center_distance=dist,bbox_size_ratio=ratio,
                    predicted_center_distance=pdist,home_center_distance=home,pose_distance=pose,
                    cost=cost,gate_pass=reason=='PASS',reason=reason)

    def _log(self,kind,timestamp,**values):
        self.debug_events.append(dict(kind=kind,timestamp=timestamp,frame_index=self.frame_index,**values))

    def update(self,detections,timestamp,frame_index=None,frame_shape=None):
        self.frame_index=self.frame_index+1 if frame_index is None else frame_index
        if frame_shape is not None:self.frame_size=np.array([frame_shape[1],frame_shape[0]],dtype=float)
        self.debug_events=[]; self.reassociations=[]; self.expired=[]

        raw_detections=list(detections)
        detections=[]

        # YOLO/pose can occasionally return two overlapping observations
        # for the same physical student. Never let both enter public-ID
        # assignment.
        for det in sorted(
            raw_detections,
            key=lambda d: float(getattr(d,"confidence",0.0)),
            reverse=True
        ):
            duplicate_of=None

            for kept_index,kept in enumerate(detections):
                if _duplicate_detection(det,kept):
                    duplicate_of=kept_index
                    break

            if duplicate_of is not None:
                self.counters["duplicate_detections_suppressed"]+=1
                self._log(
                    "deduplicated",
                    timestamp,
                    duplicate_source_id=det.source_id,
                    kept_source_id=detections[duplicate_of].source_id,
                    reason="SAME_PHYSICAL_DETECTION"
                )
                continue

            detections.append(det)

        # Purge stale dormant IDs.
        for dormant_tid,rec in list(self.dormant.items()):
            if timestamp-rec["expired_at"] > self.recovery_ttl_s:

                for sid in list(rec["source_ids"]):
                    if self.dormant_source_to_id.get(sid) == dormant_tid:
                        del self.dormant_source_to_id[sid]

                del self.dormant[dormant_tid]


        # Exact internal-ID recovery.
        #
        # This does NOT keep the person active/visible. It only restores
        # the previous public ID when the same detector track returns.
        remaining=[]

        for det in detections:

            dormant_tid=(
                self.dormant_source_to_id.get(det.source_id)
                if det.source_id is not None
                else None
            )

            recovered=False

            if (
                dormant_tid is not None
                and dormant_tid in self.dormant
            ):

                rec=self.dormant[dormant_tid]
                old_track=rec["track"]
                mem=rec["memory"]

                typical=np.median(
                    np.array(mem["sizes"]),
                    axis=0
                )

                scale=max(
                    *typical,
                    *size(det.bbox)
                )

                current=center(det.bbox)

                last_dist=float(
                    np.linalg.norm(
                        current-center(old_track.bbox)
                    ) / scale
                )

                home_dist=float(
                    np.linalg.norm(
                        current-mem["home"]
                    ) / scale
                )

                ratio=float(
                    max(
                        *(size(det.bbox)/typical),
                        *(typical/size(det.bbox))
                    )
                )

                gap=max(
                    0.0,
                    timestamp-old_track.last_seen
                )

                # Exact source ID is strong evidence, but still apply
                # a geometric sanity check in case the underlying
                # detector ever reuses IDs.
                if (
                    gap <= self.max_gap_s + self.recovery_ttl_s
                    and ratio <= 2.8
                    and min(last_dist,home_dist) <= 1.50
                ):

                    if gap > 0:
                        velocity=(
                            current-center(old_track.bbox)
                        ) / gap

                        speed=float(
                            np.linalg.norm(velocity)
                        )

                        limit=max(
                            *size(old_track.bbox)
                        )

                        if speed > limit:
                            velocity*=limit/speed

                        mem["velocity"]=(
                            .7*mem["velocity"]
                            +
                            .3*velocity
                        )

                    mem["centers"].append(
                        current
                    )

                    mem["sizes"].append(
                        size(det.bbox)
                    )

                    mem["home"]=(
                        (1-self.home_alpha)*mem["home"]
                        +
                        self.home_alpha*current
                    )

                    mem["home_normalized"]=(
                        mem["home"]/self.frame_size
                    )

                    self.tracks[dormant_tid]=Track(
                        dormant_tid,
                        det.bbox,
                        det.keypoints,
                        det.confidence,
                        timestamp,
                        0,
                        det.source_id,
                        True
                    )

                    self.memory[dormant_tid]=mem

                    for sid in rec["source_ids"]:
                        self.source_to_id[sid]=dormant_tid

                    if det.source_id is not None:
                        self.source_to_id[
                            det.source_id
                        ]=dormant_tid

                    for sid in list(
                        rec["source_ids"]
                    ):
                        if (
                            self.dormant_source_to_id.get(sid)
                            ==
                            dormant_tid
                        ):
                            del self.dormant_source_to_id[sid]

                    del self.dormant[dormant_tid]

                    self.counters[
                        "dormant_recoveries"
                    ]+=1

                    self.counters[
                        "successful_reassociations"
                    ]+=1

                    self.longest_gap=max(
                        self.longest_gap,
                        gap
                    )

                    self._log(
                        "dormant_recovery",
                        timestamp,
                        stable_person_id=dormant_tid,
                        old_internal_track_id=old_track.source_id,
                        new_internal_track_id=det.source_id,
                        gap_s=gap,
                        reason="EXACT_SOURCE_ID_RECOVERY"
                    )

                    recovered=True

                else:
                    # Geometry contradicts the old owner: treat this
                    # detector source as potentially reused.
                    if (
                        det.source_id is not None
                        and
                        self.dormant_source_to_id.get(
                            det.source_id
                        ) == dormant_tid
                    ):
                        del self.dormant_source_to_id[
                            det.source_id
                        ]

                    rec["source_ids"].discard(
                        det.source_id
                    )


            if not recovered:
                remaining.append(det)


        detections=remaining

        ids=list(self.tracks)
        n=len(ids)
        m=len(detections)

        self.internal_ids.update(
            d.source_id
            for d in detections
            if d.source_id is not None
        )

        # Persistent ownership:
        # one detector/internal source ID may change away and later return,
        # but while its public track is alive it should map back to that
        # same stable public ID.
        row_by_tid={tid:i for i,tid in enumerate(ids)}
        source_locks={}

        for col,det in enumerate(detections):
            if det.source_id is None:
                continue

            tid=self.source_to_id.get(det.source_id)

            if tid is None or tid not in self.tracks:
                continue

            row=row_by_tid.get(tid)

            if row is None or row in source_locks:
                continue

            info=self._candidate(tid,det,timestamp)

            # Sanity gate prevents blindly trusting a detector-ID swap
            # to a completely different person.
            nearby=min(
                info["normalized_center_distance"],
                info["predicted_center_distance"],
                info["home_center_distance"]
            )

            if (
                info["gap_s"] <= self.max_gap_s
                and info["bbox_size_ratio"] <= 2.8
                and nearby <= 1.50
            ):
                source_locks[row]=col

        costs=np.full((n,m+n),10000.); candidates={}
        for row,tid in enumerate(ids):
            costs[row,m+row]=self.max_assignment_cost
            for col,det in enumerate(detections):
                info=self._candidate(tid,det,timestamp); candidates[row,col]=info
                if info['gate_pass']: costs[row,col]=info['cost']

        # Reserve reliable internal-ID ownership before global assignment.
        locked_pairs=set()

        for row,col in source_locks.items():
            costs[row,:]=10000.
            costs[:,col]=10000.
            costs[row,col]=-1.0
            locked_pairs.add((row,col))

            if (row,col) in candidates:
                candidates[row,col]["gate_pass"]=True
                candidates[row,col]["reason"]="SOURCE_ID_LOCK"

        matches=[]; used=set(); ambiguous=set()
        if n and m:
            rr,cc=linear_sum_assignment(costs)
            optimum=float(costs[rr,cc].sum())
            for row,col in zip(rr,cc):
                if col>=m or costs[row,col]>=self.max_assignment_cost: continue
                info=candidates[row,col]

                if (row,col) in locked_pairs:
                    matches.append((ids[row],col))
                    used.add(col)
                    info["reason"]="ASSIGNED_SOURCE_ID_LOCK"
                    continue

                alternate=costs.copy();alternate[row,col]=10000.
                ar,ac=linear_sum_assignment(alternate)
                if float(alternate[ar,ac].sum())-optimum<self.ambiguity_margin:
                    info.update(gate_pass=False,reason='AMBIGUOUS_ASSIGNMENT'); self.counters['possible_id_switches']+=1
                    ambiguous.add(col)
                    continue
                matches.append((ids[row],col)); used.add(col); info['reason']='ASSIGNED'
        for (row,col),info in candidates.items():
            if info['reason']=='PASS': info['reason']='GLOBAL_ASSIGNMENT_OTHER'
            self._log('candidate',timestamp,detection_index=col,**info)
            if not info['gate_pass']: self.rejection_reasons[info['reason']]+=1
        matched_ids={tid for tid,_ in matches}
        for tid,col in matches:
            old=self.tracks[tid]; det=detections[col]; mem=self.memory[tid]; dt=timestamp-old.last_seen
            reassociated=old.missed>0 or (det.source_id is not None and old.source_id!=det.source_id)
            if reassociated:
                self.counters['successful_reassociations']+=1; self.longest_gap=max(self.longest_gap,dt)
                if det.source_id!=old.source_id:self.counters['tracker_id_changes']+=1
                info=self._candidate(tid,det,timestamp); self.reassociations.append(info); self._log('reassociation',timestamp,**info)
            if dt>0:
                velocity=(center(det.bbox)-center(old.bbox))/dt; speed=float(np.linalg.norm(velocity)); limit=max(size(old.bbox))
                if speed>limit:velocity*=limit/speed
                mem['velocity']=.7*mem['velocity']+.3*velocity
            mem['centers'].append(center(det.bbox)); mem['sizes'].append(size(det.bbox))
            mem['home']=(1-self.home_alpha)*mem['home']+self.home_alpha*center(det.bbox)
            mem['home_normalized']=mem['home']/self.frame_size

            if det.source_id is not None:
                owner=self.source_to_id.get(det.source_id)

                if owner is None or owner == tid or owner not in self.tracks:
                    self.source_to_id[det.source_id]=tid

            self.tracks[tid]=Track(tid,det.bbox,det.keypoints,det.confidence,timestamp,0,det.source_id,reassociated)
        for col,det in enumerate(detections):
            if col in used:continue
            if col in ambiguous:
                self._log('deferred',timestamp,new_internal_track_id=det.source_id,detection_index=col,reason='AMBIGUOUS_NO_PUBLIC_ID')
                continue

            # Defensive check after assignment. If another detection for the
            # same physical person survived detector dedupe, and that person
            # already has a visible public track this frame, do not mint a
            # second public ID.
            duplicate_tid=None

            for existing_tid,existing in self.tracks.items():
                if existing.last_seen != timestamp:
                    continue

                # Use the same conservative duplicate test as detector dedupe.
                # Strong bbox overlap alone is NOT enough because two real
                # students can overlap heavily in classroom footage.
                if _duplicate_detection(existing,det):
                    duplicate_tid=existing_tid
                    break

            if duplicate_tid is not None:
                self.counters["duplicate_new_ids_suppressed"]+=1
                self._log(
                    "deferred",
                    timestamp,
                    stable_person_id=duplicate_tid,
                    new_internal_track_id=det.source_id,
                    detection_index=col,
                    reason="DUPLICATE_OF_VISIBLE_TRACK"
                )
                continue

            if det.source_id is not None:
                owner=self.source_to_id.get(det.source_id)

                if owner is not None and owner in self.tracks:
                    info=self._candidate(owner,det,timestamp)

                    nearby=min(
                        info["normalized_center_distance"],
                        info["predicted_center_distance"],
                        info["home_center_distance"]
                    )

                    if (
                        info["gap_s"] <= self.max_gap_s
                        and info["bbox_size_ratio"] <= 2.8
                        and nearby <= 1.50
                    ):
                        self.counters["owned_source_new_id_suppressed"]+=1
                        self._log(
                            "deferred",
                            timestamp,
                            stable_person_id=owner,
                            new_internal_track_id=det.source_id,
                            detection_index=col,
                            reason="SOURCE_ID_ALREADY_OWNED"
                        )
                        continue

            tid=self.next_id; self.next_id+=1; self.counters['stable_ids_created']+=1
            if ids:self.counters['failed_reassociations']+=1
            self._log('new_id',timestamp,new_internal_track_id=det.source_id,new_stable_person_id=tid,
                      bbox=list(det.bbox),detection_index=col,number_of_recent_lost_tracks=sum(self.tracks[t].missed>0 for t in ids),
                      reason='NO_PRIOR_TRACK' if not ids else 'NO_UNAMBIGUOUS_MATCH')
            self.tracks[tid]=Track(tid,det.bbox,det.keypoints,det.confidence,timestamp,0,det.source_id)

            if det.source_id is not None:
                self.source_to_id[det.source_id]=tid

            self.memory[tid]=dict(home=center(det.bbox),velocity=np.zeros(2),centers=deque([center(det.bbox)],maxlen=30),sizes=deque([size(det.bbox)],maxlen=30))
            self.memory[tid]['home_normalized']=center(det.bbox)/self.frame_size
        for tid in ids:
            if tid in matched_ids:continue
            track=self.tracks[tid]; gap=timestamp-track.last_seen
            if track.missed==0:self.counters['detector_gaps']+=1
            track.missed+=1; self.longest_gap=max(self.longest_gap,gap)
            if gap>self.max_gap_s or (self.max_missed is not None and track.missed>self.max_missed):
                self._log('expired',timestamp,stable_person_id=tid,old_internal_track_id=track.source_id,gap_s=gap,reason='MAX_GAP_EXCEEDED' if gap>self.max_gap_s else 'LEGACY_FRAME_LIMIT')
                self.expired.append(tid)

                owned_sources={
                    source_id
                    for source_id,owner
                    in self.source_to_id.items()
                    if owner == tid
                }

                if owned_sources:

                    self.dormant[tid]={
                        "track":track,
                        "memory":self.memory[tid],
                        "expired_at":timestamp,
                        "source_ids":set(owned_sources)
                    }

                    for source_id in owned_sources:
                        self.dormant_source_to_id[
                            source_id
                        ]=tid


                for source_id,owner in list(
                    self.source_to_id.items()
                ):
                    if owner == tid:
                        del self.source_to_id[
                            source_id
                        ]


                del self.tracks[tid]
                del self.memory[tid]

        # Keep historical internal IDs for every still-alive public track.
        self.source_to_id={
            source_id:tid
            for source_id,tid in self.source_to_id.items()
            if tid in self.tracks
        }

        return [t for t in self.tracks.values() if t.last_seen==timestamp and not t.missed]

    def summary(self):
        return dict(self.counters,unique_internal_tracker_ids=len(self.internal_ids),longest_detector_gap_s=self.longest_gap,top_rejection_reasons=dict(self.rejection_reasons))
