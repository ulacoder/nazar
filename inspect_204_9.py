import csv
from pathlib import Path

p=Path(r".\tracking_debug_5min_v5_1\tracking_debug.csv")

with p.open("r",encoding="utf-8-sig",newline="") as f:
    rows=list(csv.DictReader(f))

target=204.9

def num(x):
    try:
        return float(x)
    except:
        return None

for r in rows:
    ts=num(r.get("timestamp"))

    if ts is None or abs(ts-target)>0.0001:
        continue

    if r.get("kind") not in {
        "candidate",
        "reassociation",
        "new_id",
        "deferred"
    }:
        continue

    print(
        f"{r.get('kind'):14} "
        f"det={r.get('detection_index',''):>2} "
        f"public={r.get('stable_person_id',''):>3} "
        f"oldInt={r.get('old_internal_track_id',''):>3} "
        f"newInt={r.get('new_internal_track_id',''):>3} "
        f"app={r.get('appearance_distance',''):>8} "
        f"cost={r.get('cost',''):>8} "
        f"center={r.get('normalized_center_distance',''):>8} "
        f"iou={r.get('iou',''):>8} "
        f"reason={r.get('reason','')}"
    )
