import json
import cv2
import numpy as np
from pathlib import Path

from app.vision.appearance import torso_descriptor, appearance_distance

VIDEO = r"C:\Users\Abik\Videos\Captures\датасет — копия.mp4"
CACHE = Path(r".\tracking_debug_5min\detections.jsonl")

TIMES = [
    14.0,
    35.36666666666667,
    75.26666666666667,
    156.36666666666667,
    229.03333333333333,
]

records = {}

for line in CACHE.open("r", encoding="utf-8"):
    r=json.loads(line)
    ts=float(r["timestamp"])

    for target in TIMES:
        if abs(ts-target) < 1e-4:
            records[target]=r

cap=cv2.VideoCapture(VIDEO)
fps=cap.get(cv2.CAP_PROP_FPS) or 30

descs=[]

for ts in TIMES:

    r=records[ts]

    # Edge person = right/bottom detection.
    candidates=[
        d for d in r["detections"]
        if float(d["bbox"][0]) > 1250
        and float(d["bbox"][1]) > 700
    ]

    if not candidates:
        print("NO EDGE DETECTION:",ts)
        descs.append(None)
        continue

    d=max(
        candidates,
        key=lambda x: float(x["confidence"])
    )

    cap.set(
        cv2.CAP_PROP_POS_FRAMES,
        int(round(ts*fps))
    )

    ok,frame=cap.read()

    if not ok:
        print("FRAME ERROR:",ts)
        descs.append(None)
        continue

    desc=torso_descriptor(
        frame,
        d["bbox"],
        np.asarray(d["keypoints"],dtype=np.float32)
    )

    descs.append(desc)

    print(
        f"{ts:7.2f}s | "
        f"source={d['source_id']} | "
        f"conf={float(d['confidence']):.3f} | "
        f"bbox={[round(float(x),1) for x in d['bbox']]}"
    )

cap.release()

print()
print("PAIRWISE APPEARANCE DISTANCE")
print("      " + " ".join(f"{t:7.1f}" for t in TIMES))

for i,ts in enumerate(TIMES):
    row=[]

    for j in range(len(TIMES)):
        if descs[i] is None or descs[j] is None:
            row.append("   --- ")
        else:
            row.append(
                f"{appearance_distance(descs[i],descs[j]):7.3f}"
            )

    print(f"{ts:5.1f} " + " ".join(row))
