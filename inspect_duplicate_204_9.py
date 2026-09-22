import json
import cv2
import numpy as np

from app.vision.appearance import torso_descriptor, appearance_distance
from app.vision.tracker import _iou, _overlap_min, _distance, _bbox_ratio

VIDEO=r"C:\Users\Abik\Videos\Captures\датасет — копия.mp4"
CACHE=r".\tracking_debug_5min\detections.jsonl"
TARGET=204.9

record=None

for line in open(CACHE,"r",encoding="utf-8"):
    r=json.loads(line)
    if abs(float(r["timestamp"])-TARGET)<1e-4:
        record=r
        break

if record is None:
    raise SystemExit("frame not found")

cap=cv2.VideoCapture(VIDEO)
fps=cap.get(cv2.CAP_PROP_FPS) or 30
cap.set(cv2.CAP_PROP_POS_FRAMES,int(round(TARGET*fps)))
ok,frame=cap.read()
cap.release()

if not ok:
    raise SystemExit("cannot read frame")

a,b=record["detections"][:2]

ba=np.asarray(a["bbox"],dtype=float)
bb=np.asarray(b["bbox"],dtype=float)

ka=np.asarray(a["keypoints"],dtype=np.float32)
kb=np.asarray(b["keypoints"],dtype=np.float32)

da=torso_descriptor(frame,ba,ka)
db=torso_descriptor(frame,bb,kb)

print("IoU        =",round(_iou(ba,bb),4))
print("OverlapMin =",round(_overlap_min(ba,bb),4))
print("Distance   =",round(_distance(ba,bb),4))
print("BBox ratio =",round(_bbox_ratio(ba,bb),4))
print("Appearance =",round(appearance_distance(da,db),4))

valid=(ka[:,2]>=.40)&(kb[:,2]>=.40)

if valid.sum()>=4:
    scale=max(*(bb[2:]-bb[:2]),*(ba[2:]-ba[:2]))
    pose=np.median(
        np.linalg.norm(
            ka[valid,:2]-kb[valid,:2],
            axis=1
        )
    )/scale
    print("Pose dist  =",round(float(pose),4))
else:
    print("Pose dist  = insufficient keypoints")
