import json
from pathlib import Path

import cv2
import numpy as np

from app.vision.appearance import torso_descriptor, appearance_distance


VIDEO = Path(r"C:\Users\Abik\Videos\Captures\датасет — копия.mp4")
CACHE = Path(r".\tracking_debug_5min\detections.jsonl")

SAMPLE_EVERY = 10


def iou(a, b):
    ax1, ay1, ax2, ay2 = map(float, a)
    bx1, by1, bx2, by2 = map(float, b)

    x1, y1 = max(ax1,bx1), max(ay1,by1)
    x2, y2 = min(ax2,bx2), min(ay2,by2)

    inter = max(0.0,x2-x1)*max(0.0,y2-y1)

    aa = max(0.0,ax2-ax1)*max(0.0,ay2-ay1)
    bb = max(0.0,bx2-bx1)*max(0.0,by2-by1)

    return inter/max(aa+bb-inter,1e-6)


def stats(name, values):
    values = np.asarray(values, dtype=np.float32)

    print()
    print(name)
    print("count =", len(values))

    if not len(values):
        return

    for p in [5,10,25,50,75,90,95,99]:
        print(f"p{p:02d} = {np.percentile(values,p):.4f}")

    print("mean =", round(float(values.mean()),4))


cap = cv2.VideoCapture(str(VIDEO))

if not cap.isOpened():
    raise SystemExit("Cannot open video")

same_source = []
different_people = []

last = {}

with CACHE.open("r", encoding="utf-8") as f:

    for row_index, line in enumerate(f):

        record = json.loads(line)
        frame_index = int(record["frame_index"])

        ok, frame = cap.read()

        if not ok:
            break

        if row_index % SAMPLE_EVERY:
            continue

        current = []

        for d in record["detections"]:

            desc = torso_descriptor(
                frame,
                d["bbox"],
                np.asarray(d["keypoints"], dtype=np.float32)
            )

            if desc is None:
                continue

            source = d.get("source_id")

            current.append((
                source,
                d["bbox"],
                desc
            ))

            if source is not None and source in last:
                old_frame, old_desc = last[source]

                # Only compare nearby observations of the same ByteTrack source.
                if frame_index-old_frame <= SAMPLE_EVERY*3:
                    dist = appearance_distance(old_desc, desc)

                    if dist is not None:
                        same_source.append(dist)

            if source is not None:
                last[source] = (frame_index, desc)


        # Simultaneous detections that clearly occupy different places.
        for i in range(len(current)):
            for j in range(i+1, len(current)):

                sa, ba, da = current[i]
                sb, bb, db = current[j]

                if sa is not None and sb is not None and sa == sb:
                    continue

                # Avoid counting duplicate boxes as two different people.
                if iou(ba, bb) >= 0.20:
                    continue

                dist = appearance_distance(da, db)

                if dist is not None:
                    different_people.append(dist)


cap.release()

print("="*72)
print("ANONYMOUS TORSO APPEARANCE CALIBRATION")
print("="*72)

stats("SAME SOURCE / NEARBY FRAMES", same_source)
stats("DIFFERENT SIMULTANEOUS DETECTIONS", different_people)

if same_source and different_people:

    same95 = float(np.percentile(same_source,95))
    diff10 = float(np.percentile(different_people,10))

    print()
    print("="*72)
    print("SEPARATION")
    print("="*72)
    print("same-source p95 :", round(same95,4))
    print("different p10   :", round(diff10,4))
    print("margin          :", round(diff10-same95,4))

    if diff10 > same95:
        print("RESULT: useful separation")
    else:
        print("RESULT: distributions overlap; use appearance only as supporting evidence")
