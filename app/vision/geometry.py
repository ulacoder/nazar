"""COCO keypoint geometry from the supplied Actions MVP runner."""
import numpy as np

KEYPOINT_CONF=.35

def joint_angle(a,b,c):
    ba=np.asarray(a,dtype=np.float32)-np.asarray(b,dtype=np.float32)
    bc=np.asarray(c,dtype=np.float32)-np.asarray(b,dtype=np.float32)
    denominator=np.linalg.norm(ba)*np.linalg.norm(bc)
    if denominator<1e-6: return None
    return float(np.degrees(np.arccos(np.clip(np.dot(ba,bc)/denominator,-1,1))))

def pose_body_state(keypoints):
    angles=[]
    for hip,knee,ankle in ((11,13,15),(12,14,16)):
        if min(keypoints[hip,2],keypoints[knee,2],keypoints[ankle,2])<KEYPOINT_CONF: continue
        angle=joint_angle(keypoints[hip,:2],keypoints[knee,:2],keypoints[ankle,:2])
        if angle is not None: angles.append(angle)
    if not angles: return None
    median=float(np.median(angles))
    if median>=155: return "STANDING"
    if 55<=median<=140: return "SITTING"
    return None

def hand_raised_state(keypoints,person_height):
    checks=[];margin=person_height*.04
    for shoulder,wrist in ((5,9),(6,10)):
        if min(keypoints[shoulder,2],keypoints[wrist,2])<KEYPOINT_CONF: continue
        checks.append(bool(keypoints[wrist,1]<keypoints[shoulder,1]-margin))
    return any(checks) if checks else None

def turned_back_candidate(keypoints):
    face=float(np.mean(keypoints[0:5,2]))
    eyes=float(np.mean(keypoints[1:3,2]))
    shoulders=float(np.mean(keypoints[5:7,2]))
    return bool(face<.30 and eyes<.30 and shoulders>.80)

def shoulder_anchor_y(keypoints):
    ys=[float(keypoints[i,1]) for i in (5,6) if keypoints[i,2]>=KEYPOINT_CONF]
    return float(np.median(ys)) if ys else None

def face_visible(keypoints):
    return sum(bool(keypoints[i,2]>=KEYPOINT_CONF) for i in range(5))>=2
