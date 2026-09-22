from pathlib import Path
import csv
import cv2
import math
import numpy as np

ROOT = Path(r".\tracking_debug_5min_v4")

CSV = ROOT / "tracking_debug.csv"
VIDEO = ROOT / "annotated_tracking.mp4"
OUT = ROOT / "new_id_review"

OUT.mkdir(exist_ok=True)

with CSV.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

events = [
    r for r in rows
    if r.get("kind") == "new_id"
]

cap = cv2.VideoCapture(str(VIDEO))

if not cap.isOpened():
    raise SystemExit(f"Cannot open {VIDEO}")

fps = cap.get(cv2.CAP_PROP_FPS) or 30
w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

TILE_W = 480
TILE_H = int(h * TILE_W / w)

COLS = 3
EVENTS_PER_SHEET = 6


def get_frame(sec):

    sec = max(0, sec)

    cap.set(
        cv2.CAP_PROP_POS_MSEC,
        sec * 1000
    )

    ok, frame = cap.read()

    if not ok:
        return np.zeros(
            (TILE_H,TILE_W,3),
            dtype=np.uint8
        )

    return cv2.resize(
        frame,
        (TILE_W,TILE_H)
    )


def stamp(img, text):

    out = img.copy()

    cv2.rectangle(
        out,
        (0,0),
        (out.shape[1],38),
        (0,0,0),
        -1
    )

    cv2.putText(
        out,
        text,
        (8,26),
        cv2.FONT_HERSHEY_SIMPLEX,
        .58,
        (255,255,255),
        2,
        cv2.LINE_AA
    )

    return out


sheets = []

for idx,event in enumerate(events,1):

    ts = float(event["timestamp"])

    public_id = (
        event.get("new_stable_person_id")
        or "?"
    )

    internal = (
        event.get("new_internal_track_id")
        or "?"
    )

    before = stamp(
        get_frame(ts-1.0),
        f"#{idx:02d} BEFORE  t={ts-1:.2f}s"
    )

    current = stamp(
        get_frame(ts),
        f"NEW PUBLIC #{public_id}  int={internal}  t={ts:.2f}s"
    )

    after = stamp(
        get_frame(ts+1.0),
        f"#{idx:02d} AFTER   t={ts+1:.2f}s"
    )

    row = np.hstack([
        before,
        current,
        after
    ])

    sheets.append(row)


for part,start in enumerate(
    range(0,len(sheets),EVENTS_PER_SHEET),
    1
):

    chunk = sheets[
        start:start+EVENTS_PER_SHEET
    ]

    canvas = np.vstack(chunk)

    path = (
        OUT
        /
        f"new_ids_part_{part:02d}.jpg"
    )

    cv2.imwrite(
        str(path),
        canvas
    )

    print("Saved:",path)

cap.release()

print()
print("NEW-ID events:",len(events))
print("Review folder:",OUT)

