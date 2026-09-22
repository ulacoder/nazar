"""Anonymous global assignment with bounded motion memory and decision diagnostics."""
from collections import Counter, deque
import math
import numpy as np
from scipy.optimize import linear_sum_assignment
from .types import Track
from .appearance import appearance_distance


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
    #
    # Some pose detections produce one short upper-body box and one taller
    # full-body box for the same physical person. Keep the original
    # conservative rule, but allow a slightly larger center shift only when
    # torso appearance is also an extremely strong match.
    app=appearance_distance(
        getattr(a,"appearance",None),
        getattr(b,"appearance",None)
    )

    if (
        iom >= .94
        and ratio <= 2.20
        and pose is not None
        and pose <= .050
        and (
            dist <= .25
            or (
                dist <= .30
                and app is not None
                and app <= .06
            )
        )
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

        # Active tracks disappear normally after max_gap_s.
        # Their anonymous appearance/geometry memory lives slightly
        # longer for safe recovery after an occlusion or tracker-ID reset.
        self.recovery_ttl_s=8.0

        self.frame_size=np.ones(2)
        self.next_id=1
        self.tracks={}
        self.memory={}
        self.source_to_id={}
        self.dormant={}

        # V5: people-count prior + pending public IDs.
        #
        # An unmatched detection is not immediately allowed to create
        # Person #N. It first becomes a short-lived pending candidate.
        # V6: long-term, session-local anonymous identity archive.
        # No face recognition: torso appearance + spatial region only.
        self.session_archive={}
        self.last_frame_shape=None

        self.pending={}
        self.next_pending_id=1

        # Timestamp-based history works both at 30 FPS on PC and
        # lower AI rates on Raspberry Pi.
        self.count_history=deque(maxlen=240)
        self.last_observed_people_count=0
        self.last_expected_people_count=0
        self.expired=[]; self.reassociations=[]; self.debug_events=[]; self.frame_index=0
        self.counters=Counter({k:0 for k in ('stable_ids_created','successful_reassociations','failed_reassociations','tracker_id_changes','detector_gaps','possible_id_switches')})
        self.longest_gap=0.; self.rejection_reasons=Counter(); self.internal_ids=set()

    def _appearance_gallery_distance(self,mem,appearance):
        if appearance is None:
            return None

        new=np.asarray(appearance,dtype=np.float32)

        norm=float(np.linalg.norm(new))
        if norm < 1e-6:
            return None

        new=new/norm

        samples=list(mem.get("appearance_gallery") or [])

        old=mem.get("appearance")
        if old is not None:
            samples.append(old)

        distances=[]

        for sample in samples:
            d=appearance_distance(sample,new)
            if d is not None:
                distances.append(float(d))

        return min(distances) if distances else None


    def _update_appearance(self,mem,appearance):
        if appearance is None:
            return

        new=np.asarray(appearance,dtype=np.float32)

        norm=float(np.linalg.norm(new))
        if norm < 1e-6:
            return

        new=new/norm

        gallery=mem.get("appearance_gallery")

        if gallery is None:
            gallery=deque(maxlen=12)
            mem["appearance_gallery"]=gallery

        old=mem.get("appearance")

        if old is None:
            mem["appearance"]=new.copy()
            gallery.append(new.copy())
            return

        gallery_dist=self._appearance_gallery_distance(
            mem,
            new
        )

        # Keep several legitimate views of one person.
        # Do not accept a wildly different descriptor into the gallery.
        if (
            gallery_dist is None
            or gallery_dist <= .17
        ):
            # Avoid filling the gallery with almost identical frames.
            if (
                gallery_dist is None
                or gallery_dist >= .012
            ):
                gallery.append(new.copy())

        dist=appearance_distance(old,new)

        # The running average remains conservative.
        if dist is not None and dist > .14:
            return

        combined=(
            .85*np.asarray(old,dtype=np.float32)
            +
            .15*new
        )

        norm=float(np.linalg.norm(combined))

        if norm > 1e-6:
            mem["appearance"]=combined/norm


    def _candidate(self,tid,det,timestamp):
        track=self.tracks[tid]
        mem=self.memory[tid]

        gap=max(0.,timestamp-track.last_seen)

        typical=np.median(
            np.array(mem["sizes"]),
            axis=0
        )

        scale=max(
            *typical,
            *size(det.bbox)
        )

        current=center(det.bbox)

        predicted=(
            center(track.bbox)
            +
            mem["velocity"]*min(gap,.75)
        )

        dist=float(
            np.linalg.norm(
                current-center(track.bbox)
            ) / scale
        )

        pdist=float(
            np.linalg.norm(
                current-predicted
            ) / scale
        )

        home=float(
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

        overlap=_iou(
            track.bbox,
            det.bbox
        )

        a=np.asarray(track.keypoints)
        b=np.asarray(det.keypoints)

        valid=(
            (a[:,2]>=.5)
            &
            (b[:,2]>=.5)
        )

        valid[:5]=False

        pose=(
            float(
                np.median(
                    np.linalg.norm(
                        (a[valid,:2]-center(track.bbox))
                        -
                        (b[valid,:2]-current),
                        axis=1
                    )
                ) / scale
            )
            if sum(valid)>=3
            else None
        )

        position=(
            min(pdist,home)
            if self.stationary_prior
            else pdist
        )

        app=self._appearance_gallery_distance(
            mem,
            getattr(det,"appearance",None)
        )

        strong_app=(
            app is not None
            and app <= .10
        )

        reason="PASS"

        if gap > self.max_gap_s:
            reason="MAX_GAP_EXCEEDED"

        elif ratio > 2.2:
            # Sitting/standing can strongly change bbox height.
            # Only a very strong torso match may relax this gate.
            if not (
                strong_app
                and ratio <= 3.4
                and position <= .85
            ):
                reason="BBOX_SIZE_GATE"

        elif (
            position > self.max_center_distance
            and overlap < .10
        ):
            # Appearance may rescue moderate motion, but never arbitrary
            # jumps across the classroom.
            if not (
                strong_app
                and position <= 1.65
                and ratio <= 2.6
            ):
                reason="PREDICTED_POSITION_GATE"


        cost=(
            .38*position
            +
            .12*dist
            +
            .08*abs(math.log(ratio))
            +
            .12*(1-overlap)
            +
            .08*(pose or 0)
            +
            .04*gap/self.max_gap_s
        )

        if app is not None:
            # Calibration:
            # same-person p95 ~= .088
            # different-person p10 ~= .173
            cost += .18*min(1.5,app/.18)
        else:
            # Missing appearance is allowed but receives a small penalty.
            cost += .05

        # ByteTrack source ID is useful evidence, but not identity.
        # Keep only a weak bonus because source IDs can switch.
        if (
            det.source_id is not None
            and det.source_id==track.source_id
        ):
            cost-=.04

        if (
            reason=="PASS"
            and cost>=self.max_assignment_cost
        ):
            reason="ASSIGNMENT_COST_GATE"

        return dict(
            stable_person_id=tid,
            old_internal_track_id=track.source_id,
            new_internal_track_id=det.source_id,
            gap_s=gap,
            iou=overlap,
            normalized_center_distance=dist,
            bbox_size_ratio=ratio,
            predicted_center_distance=pdist,
            home_center_distance=home,
            pose_distance=pose,
            appearance_distance=app,
            cost=cost,
            gate_pass=reason=="PASS",
            reason=reason
        )


    def _purge_dormant(self,timestamp):
        for tid,rec in list(self.dormant.items()):

            if (
                timestamp-rec["expired_at"]
                >
                self.recovery_ttl_s
            ):
                # Do not forget the public identity for the rest
                # of the current session. Move it into a stricter
                # long-term archive instead.
                self.session_archive[tid]={
                    "track":rec["track"],
                    "memory":rec["memory"],
                    "archived_at":timestamp
                }

                del self.dormant[tid]

                self.counters[
                    "session_archive_stored"
                ]+=1


    def _dormant_candidate(self,tid,det,timestamp):
        rec=self.dormant[tid]
        track=rec["track"]
        mem=rec["memory"]

        gap=max(
            0.,
            timestamp-track.last_seen
        )

        if gap > self.max_gap_s+self.recovery_ttl_s:
            return None

        app=appearance_distance(
            mem.get("appearance"),
            getattr(det,"appearance",None)
        )

        # Dormant recovery is deliberately strict:
        # appearance must be stronger than the empirical gap between
        # same-person and different-person distributions.
        if app is None or app > .12:
            return None

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
                current-center(track.bbox)
            ) / scale
        )

        home_dist=float(
            np.linalg.norm(
                current-mem["home"]
            ) / scale
        )

        position=min(
            last_dist,
            home_dist
        )

        ratio=float(
            max(
                *(size(det.bbox)/typical),
                *(typical/size(det.bbox))
            )
        )

        if ratio > 3.4:
            return None

        if position > 1.75:
            return None

        score=(
            .50*(app/.12)
            +
            .25*(position/1.75)
            +
            .10*min(
                1.,
                abs(math.log(ratio))
                /
                abs(math.log(3.4))
            )
            +
            .15*min(
                1.,
                gap/(self.max_gap_s+self.recovery_ttl_s)
            )
        )

        return dict(
            stable_person_id=tid,
            appearance_distance=app,
            normalized_center_distance=last_dist,
            home_center_distance=home_dist,
            bbox_size_ratio=ratio,
            gap_s=gap,
            recovery_score=score
        )


    def _restore_dormant(self,tid,det,timestamp):
        rec=self.dormant.pop(tid)

        old=rec["track"]
        mem=rec["memory"]

        dt=max(
            0.,
            timestamp-old.last_seen
        )

        if dt > 0:
            velocity=(
                center(det.bbox)
                -
                center(old.bbox)
            ) / dt

            speed=float(
                np.linalg.norm(velocity)
            )

            limit=max(
                size(old.bbox)
            )

            if speed > limit:
                velocity*=limit/speed

            mem["velocity"]=(
                .7*mem["velocity"]
                +
                .3*velocity
            )

        mem["centers"].append(
            center(det.bbox)
        )

        mem["sizes"].append(
            size(det.bbox)
        )

        mem["home"]=(
            (1-self.home_alpha)*mem["home"]
            +
            self.home_alpha*center(det.bbox)
        )

        mem["home_normalized"]=(
            mem["home"]/self.frame_size
        )

        self._update_appearance(
            mem,
            getattr(det,"appearance",None)
        )

        changed=(
            det.source_id is not None
            and det.source_id != old.source_id
        )

        self.tracks[tid]=Track(
            tid,
            det.bbox,
            det.keypoints,
            det.confidence,
            timestamp,
            0,
            det.source_id,
            True
        )

        self.memory[tid]=mem

        self.counters[
            "dormant_appearance_recoveries"
        ]+=1

        self.counters[
            "successful_reassociations"
        ]+=1

        if changed:
            self.counters[
                "tracker_id_changes"
            ]+=1

        self.longest_gap=max(
            self.longest_gap,
            dt
        )

        info=self._dormant_log_info(
            old,
            det,
            mem,
            dt
        )

        self._log(
            "dormant_recovery",
            timestamp,
            stable_person_id=tid,
            old_internal_track_id=old.source_id,
            new_internal_track_id=det.source_id,
            **info,
            reason="APPEARANCE_GEOMETRY_RECOVERY"
        )


    def _dormant_log_info(self,old,det,mem,gap):
        app=appearance_distance(
            mem.get("appearance"),
            getattr(det,"appearance",None)
        )

        return dict(
            gap_s=gap,
            appearance_distance=app
        )


    def _expected_people_count(self,timestamp):
        """Robust physical-detection count from roughly the previous second."""
        values=[
            count
            for ts,count in self.count_history
            if 0 <= timestamp-ts <= 1.0
        ]

        if not values:
            return None

        return int(round(float(np.median(values))))


    def _purge_pending(self,timestamp):
        # If a pending person disappears for >0.65 s, forget the
        # unconfirmed candidate. No public ID was consumed.
        for pid,rec in list(self.pending.items()):
            if timestamp-rec["last_seen"] > .65:
                del self.pending[pid]
                self.counters["pending_expired"]+=1


    def _pending_match(self,det):
        """Find an existing unconfirmed candidate for this detection."""
        best=None

        for pid,rec in self.pending.items():

            geom=_distance(
                rec["bbox"],
                det.bbox
            )

            app=appearance_distance(
                rec.get("appearance"),
                getattr(det,"appearance",None)
            )

            same_source=(
                det.source_id is not None
                and rec.get("source_id") is not None
                and det.source_id == rec["source_id"]
            )

            # Never allow source_id alone to jump across the room.
            if geom > 2.0:
                continue

            if app is not None:
                if app > .16 and not same_source:
                    continue

                if geom > 1.50 and not same_source:
                    continue

                app_term=app
            else:
                if geom > .60 and not same_source:
                    continue

                app_term=.12

            score=(
                3.0*app_term
                +
                .25*geom
                -
                (.08 if same_source else 0.0)
            )

            if best is None or score < best[0]:
                best=(score,pid)

        return None if best is None else best[1]


    def _update_pending(self,pid,det,timestamp):
        rec=self.pending[pid]

        rec["bbox"]=det.bbox
        rec["last_seen"]=timestamp
        rec["hits"]+=1

        if det.source_id is not None:
            rec["source_id"]=det.source_id

        new=getattr(det,"appearance",None)

        if new is not None:
            new=np.asarray(new,dtype=np.float32)
            norm=float(np.linalg.norm(new))

            if norm > 1e-6:
                new=new/norm

                old=rec.get("appearance")

                if old is None:
                    rec["appearance"]=new.copy()
                else:
                    combined=.80*np.asarray(old,dtype=np.float32)+.20*new
                    norm=float(np.linalg.norm(combined))

                    if norm > 1e-6:
                        rec["appearance"]=combined/norm


    def _start_pending(self,det,timestamp):
        pid=self.next_pending_id
        self.next_pending_id+=1

        appearance=getattr(det,"appearance",None)

        if appearance is not None:
            appearance=np.asarray(
                appearance,
                dtype=np.float32
            ).copy()

        self.pending[pid]={
            "first_seen":timestamp,
            "last_seen":timestamp,
            "hits":1,
            "bbox":det.bbox,
            "source_id":det.source_id,
            "appearance":appearance
        }

        self.counters["pending_started"]+=1

        return pid


    def _bbox_is_edge(self,bbox,frame_shape):
        if frame_shape is None:
            return False

        try:
            h=float(frame_shape[0])
            w=float(frame_shape[1])
        except Exception:
            return False

        if h <= 0 or w <= 0:
            return False

        x1,y1,x2,y2=map(float,bbox)

        mx=.05*w
        my=.05*h

        return (
            x1 <= mx
            or x2 >= w-mx
            or y1 <= my
            or y2 >= h-my
        )


    def _session_archive_candidate(
        self,
        tid,
        det,
        frame_shape
    ):
        rec=self.session_archive[tid]

        old=rec["track"]
        mem=rec["memory"]

        appearance=getattr(det,"appearance",None)

        app=self._appearance_gallery_distance(
            mem,
            appearance
        )

        if app is None:
            return None

        shape=(
            frame_shape
            if frame_shape is not None
            else self.last_frame_shape
        )

        old_center=center(old.bbox)
        new_center=center(det.bbox)

        if shape is not None:
            h=float(shape[0])
            w=float(shape[1])

            diagonal=max(
                float(np.hypot(w,h)),
                1.
            )

            region=float(
                np.linalg.norm(
                    new_center-old_center
                ) / diagonal
            )

            edge_pair=(
                self._bbox_is_edge(old.bbox,shape)
                and
                self._bbox_is_edge(det.bbox,shape)
            )

        else:
            scale=max(
                *size(old.bbox),
                *size(det.bbox),
                1.
            )

            region=float(
                np.linalg.norm(
                    new_center-old_center
                ) / scale
            )

            edge_pair=False

        ratio=_bbox_ratio(
            old.bbox,
            det.bbox
        )

        # Edge detections are naturally less stable because part
        # of the body is outside the image. Allow the empirically
        # measured 0.15-0.16 appearance range only when BOTH the
        # old and new boxes are at the image edge and in the same
        # spatial region.
        if edge_pair:
            app_limit=.16
            region_limit=.12
            ratio_limit=3.0
        else:
            app_limit=.10
            region_limit=.08
            ratio_limit=2.5

        if app > app_limit:
            return None

        if region > region_limit:
            return None

        if ratio > ratio_limit:
            return None

        ratio_term=min(
            1.,
            abs(np.log(max(ratio,1e-6)))
            /
            max(np.log(ratio_limit),1e-6)
        )

        score=(
            .70*(app/app_limit)
            +
            .20*(region/region_limit)
            +
            .10*ratio_term
        )

        return {
            "stable_person_id":tid,
            "appearance_distance":app,
            "region_distance":region,
            "bbox_size_ratio":ratio,
            "edge_pair":edge_pair,
            "recovery_score":score,
            "gap_s":max(
                0.,
                float(
                    self.frame_index*0
                    +
                    0
                )
            )
        }


    def _restore_session_archive(
        self,
        tid,
        det,
        timestamp
    ):
        rec=self.session_archive.pop(tid)

        old=rec["track"]
        mem=rec["memory"]

        old_source=old.source_id

        # After a long disappearance, velocity is no longer reliable.
        mem["velocity"]=np.zeros(2,dtype=float)

        current=center(det.bbox)

        if "centers" in mem:
            mem["centers"].append(current)

        if "sizes" in mem:
            mem["sizes"].append(size(det.bbox))

        home=mem.get("home")

        if home is not None:
            mem["home"]=(
                .95*np.asarray(home,dtype=float)
                +
                .05*current
            )

        self._update_appearance(
            mem,
            getattr(det,"appearance",None)
        )

        changed=(
            det.source_id is not None
            and
            det.source_id != old_source
        )

        self.tracks[tid]=Track(
            tid,
            det.bbox,
            det.keypoints,
            det.confidence,
            timestamp,
            0,
            det.source_id,
            True
        )

        self.memory[tid]=mem

        self.counters[
            "session_archive_recoveries"
        ]+=1

        self.counters[
            "successful_reassociations"
        ]+=1

        if changed:
            self.counters[
                "tracker_id_changes"
            ]+=1

        self._log(
            "session_archive_recovery",
            timestamp,
            stable_person_id=tid,
            old_internal_track_id=old_source,
            new_internal_track_id=det.source_id,
            gap_s=max(
                0.,
                timestamp-old.last_seen
            )
        )


    def _closest_known_appearance(self,det):
        """Appearance distance to any existing public identity."""
        appearance=getattr(det,"appearance",None)

        if appearance is None:
            return None

        distances=[]

        # Active public tracks.
        for mem in self.memory.values():
            d=appearance_distance(
                mem.get("appearance"),
                appearance
            )

            if d is not None:
                distances.append(d)

        # Recently expired public tracks.
        for rec in self.dormant.values():
            d=appearance_distance(
                rec["memory"].get("appearance"),
                appearance
            )

            if d is not None:
                distances.append(d)

        return min(distances) if distances else None


    def _log(self,kind,timestamp,**values):
        self.debug_events.append(dict(kind=kind,timestamp=timestamp,frame_index=self.frame_index,**values))

    def update(self,detections,timestamp,frame_index=None,frame_shape=None):
        if frame_shape is not None:
            self.last_frame_shape=frame_shape
        self.frame_index=self.frame_index+1 if frame_index is None else frame_index
        if frame_shape is not None:self.frame_size=np.array([frame_shape[1],frame_shape[0]],dtype=float)
        self.debug_events=[]; self.reassociations=[]; self.expired=[]

        self._purge_dormant(timestamp)
        self._purge_pending(timestamp)

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

        # Important: count AFTER duplicate suppression, otherwise two
        # boxes on one person would look like two physical people.
        observed_people_count=len(detections)

        expected_people_count=self._expected_people_count(
            timestamp
        )

        if expected_people_count is None:
            expected_people_count=observed_people_count

        self.last_observed_people_count=observed_people_count
        self.last_expected_people_count=expected_people_count

        # Append only AFTER calculating expected_count so the current
        # frame cannot instantly redefine the baseline.
        self.count_history.append(
            (timestamp,observed_people_count)
        )

        ids=list(self.tracks); n=len(ids); m=len(detections)
        self.internal_ids.update(d.source_id for d in detections if d.source_id is not None)
        costs=np.full((n,m+n),10000.); candidates={}
        for row,tid in enumerate(ids):
            costs[row,m+row]=self.max_assignment_cost
            for col,det in enumerate(detections):
                info=self._candidate(tid,det,timestamp); candidates[row,col]=info
                if info['gate_pass']: costs[row,col]=info['cost']
        matches=[]; used=set(); ambiguous=set()
        if n and m:
            rr,cc=linear_sum_assignment(costs)
            optimum=float(costs[rr,cc].sum())
            for row,col in zip(rr,cc):
                if col>=m or costs[row,col]>=self.max_assignment_cost: continue
                info=candidates[row,col]
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

            self._update_appearance(
                mem,
                getattr(det,"appearance",None)
            )

            self.tracks[tid]=Track(
                tid,
                det.bbox,
                det.keypoints,
                det.confidence,
                timestamp,
                0,
                det.source_id,
                reassociated
            )
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

            # ----------------------------------------------------
            # Dormant appearance + geometry recovery
            # ----------------------------------------------------

            dormant_choices=[]

            for dormant_tid in list(self.dormant):
                info=self._dormant_candidate(
                    dormant_tid,
                    det,
                    timestamp
                )

                if info is not None:
                    dormant_choices.append(
                        (
                            info["recovery_score"],
                            dormant_tid,
                            info
                        )
                    )

            dormant_choices.sort(
                key=lambda x:x[0]
            )

            if dormant_choices:
                best_score,best_tid,best_info=dormant_choices[0]

                # If two dormant tracks look almost equally plausible,
                # do NOT guess. A new public ID is safer than merging
                # two different people.
                second_score=(
                    dormant_choices[1][0]
                    if len(dormant_choices)>1
                    else None
                )

                unambiguous=(
                    second_score is None
                    or second_score-best_score >= .12
                )

                if (
                    best_score <= .75
                    and unambiguous
                ):
                    self._restore_dormant(
                        best_tid,
                        det,
                        timestamp
                    )
                    continue

                if not unambiguous:
                    self.counters[
                        "dormant_ambiguous"
                    ]+=1

                    self._log(
                        "deferred",
                        timestamp,
                        detection_index=col,
                        new_internal_track_id=det.source_id,
                        reason="DORMANT_APPEARANCE_AMBIGUOUS"
                    )

                    continue


            # ====================================================
            # ===================================================
            # V6 SESSION ARCHIVE RECOVERY
            # ===================================================

            archive_choices=[]

            for archive_tid in list(
                self.session_archive
            ):
                info=self._session_archive_candidate(
                    archive_tid,
                    det,
                    frame_shape
                )

                if info is not None:
                    archive_choices.append(
                        (
                            info["recovery_score"],
                            archive_tid,
                            info
                        )
                    )

            archive_choices.sort(
                key=lambda x:x[0]
            )

            if archive_choices:

                (
                    best_score,
                    best_tid,
                    best_info
                )=archive_choices[0]

                second_score=(
                    archive_choices[1][0]
                    if len(archive_choices)>1
                    else None
                )

                unambiguous=(
                    second_score is None
                    or
                    second_score-best_score >= .10
                )

                if (
                    best_score <= .88
                    and
                    unambiguous
                ):
                    self._restore_session_archive(
                        best_tid,
                        det,
                        timestamp
                    )

                    continue

                if not unambiguous:
                    self.counters[
                        "session_archive_ambiguous"
                    ]+=1

                    self._log(
                        "deferred",
                        timestamp,
                        detection_index=col,
                        new_internal_track_id=det.source_id,
                        reason="SESSION_ARCHIVE_AMBIGUOUS"
                    )

                    continue


            # V5 PENDING-ID CONFIRMATION
            # ====================================================

            # The first actual person of a session may appear
            # immediately. There is nothing to confuse it with.
            first_public_person=(
                self.next_id == 1
                and not self.tracks
                and not self.dormant
                and not self.session_archive
            )

            if not first_public_person:

                pending_id=self._pending_match(det)

                if pending_id is None:
                    pending_id=self._start_pending(
                        det,
                        timestamp
                    )

                    self._log(
                        "deferred",
                        timestamp,
                        detection_index=col,
                        new_internal_track_id=det.source_id,
                        reason="PENDING_NEW_PERSON_STARTED"
                    )

                    continue

                self._update_pending(
                    pending_id,
                    det,
                    timestamp
                )

                pending=self.pending[pending_id]

                age=max(
                    0.,
                    timestamp-pending["first_seen"]
                )

                hits=pending["hits"]

                closest_known=self._closest_known_appearance(
                    det
                )

                # Did the physical number of detections actually rise
                # above the recent baseline?
                count_increased=(
                    observed_people_count
                    >
                    expected_people_count
                )

                # If appearance is close to an already-known public
                # person, this is probably fragmentation/reassociation,
                # not a genuinely new person.
                looks_like_known=(
                    closest_known is not None
                    and closest_known <= .14
                )

                # Genuine entrance:
                # count rose and detection persisted ~0.35 s.
                confirmed_by_count=(
                    count_increased
                    and age >= .45
                    and hits >= 4
                    and not looks_like_known
                )

                # Replacement case:
                # total count did NOT rise, but this appearance is
                # clearly different from every existing/recent identity.
                confirmed_replacement=(
                    age >= 1.0
                    and hits >= 4
                    and not looks_like_known
                )

                # Absolute safety timeout. We should not make a real
                # person invisible forever if all recovery logic fails.
                hard_timeout=(
                    age >= self.max_gap_s + .75
                    and hits >= 8
                )

                if not (
                    confirmed_by_count
                    or confirmed_replacement
                    or hard_timeout
                ):

                    self.counters[
                        "people_count_new_id_suppressed"
                    ]+=1

                    self._log(
                        "deferred",
                        timestamp,
                        detection_index=col,
                        new_internal_track_id=det.source_id,
                        reason=(
                            "PENDING_LOOKS_LIKE_KNOWN"
                            if looks_like_known
                            else
                            "PENDING_COUNT_NOT_INCREASED"
                        )
                    )

                    continue

                if hard_timeout:
                    self.counters[
                        "pending_hard_timeout_promotions"
                    ]+=1

                elif confirmed_by_count:
                    self.counters[
                        "pending_count_promotions"
                    ]+=1

                else:
                    self.counters[
                        "pending_replacement_promotions"
                    ]+=1

                del self.pending[pending_id]

                self.counters[
                    "pending_promoted"
                ]+=1


            tid=self.next_id; self.next_id+=1; self.counters['stable_ids_created']+=1
            if ids:self.counters['failed_reassociations']+=1
            self._log('new_id',timestamp,new_internal_track_id=det.source_id,new_stable_person_id=tid,
                      bbox=list(det.bbox),detection_index=col,number_of_recent_lost_tracks=sum(self.tracks[t].missed>0 for t in ids),
                      reason='NO_PRIOR_TRACK' if not ids else 'NO_UNAMBIGUOUS_MATCH')
            self.tracks[tid]=Track(tid,det.bbox,det.keypoints,det.confidence,timestamp,0,det.source_id)
            self.memory[tid]=dict(
                home=center(det.bbox),
                velocity=np.zeros(2),
                centers=deque(
                    [center(det.bbox)],
                    maxlen=30
                ),
                sizes=deque(
                    [size(det.bbox)],
                    maxlen=30
                ),
                appearance=None
            )

            self.memory[tid]["home_normalized"]=(
                center(det.bbox)/self.frame_size
            )

            self._update_appearance(
                self.memory[tid],
                getattr(det,"appearance",None)
            )
        for tid in ids:
            if tid in matched_ids:continue
            track=self.tracks[tid]; gap=timestamp-track.last_seen
            if track.missed==0:self.counters['detector_gaps']+=1
            track.missed+=1; self.longest_gap=max(self.longest_gap,gap)
            if gap>self.max_gap_s or (self.max_missed is not None and track.missed>self.max_missed):
                self._log('expired',timestamp,stable_person_id=tid,old_internal_track_id=track.source_id,gap_s=gap,reason='MAX_GAP_EXCEEDED' if gap>self.max_gap_s else 'LEGACY_FRAME_LIMIT')
                self.expired.append(tid)

                self.dormant[tid]={
                    "track":track,
                    "memory":self.memory[tid],
                    "expired_at":timestamp
                }

                del self.tracks[tid]
                del self.memory[tid]
        self.source_to_id={t.source_id:tid for tid,t in self.tracks.items() if t.source_id is not None}
        return [t for t in self.tracks.values() if t.last_seen==timestamp and not t.missed]

    def summary(self):
        return dict(
            self.counters,
            unique_internal_tracker_ids=len(self.internal_ids),
            longest_detector_gap_s=self.longest_gap,
            top_rejection_reasons=dict(self.rejection_reasons),
            observed_people_count=self.last_observed_people_count,
            expected_people_count=self.last_expected_people_count,
            pending_tracks_end=len(self.pending),
            session_archive_size=len(self.session_archive)
        )
