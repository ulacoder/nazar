import csv
import json
from pathlib import Path

TIMES=[372.03333333333336,768.4333333333333,2275.9666666666667]

csv_path=Path(r".\tracking_debug_full_v6\tracking_debug.csv")
cache_path=Path(r".\tracking_debug_full_v6\detections.jsonl")

with csv_path.open("r",encoding="utf-8-sig",newline="") as f:
    rows=list(csv.DictReader(f))

cache={}
with cache_path.open("r",encoding="utf-8") as f:
    for line in f:
        r=json.loads(line)
        ts=float(r["timestamp"])
        for target in TIMES:
            if abs(ts-target) <= 1.0:
                cache[round(ts,6)]=r

for target in TIMES:
    print()
    print("="*110)
    print(f"NEW-ID EVENT @ {target:.2f}s")

    print("\nTRACKER EVENTS ±1.5s")

    for r in rows:
        try:
            ts=float(r.get("timestamp",""))
        except:
            continue

        if abs(ts-target)>1.5:
            continue

        if r.get("kind") not in {
            "new_id",
            "deferred",
            "session_archive_recovery",
            "dormant_recovery",
            "candidate"
        }:
            continue

        print(
            f"{ts:9.3f} "
            f"{r.get('kind',''):24} "
            f"det={r.get('detection_index','')} "
            f"public={r.get('stable_person_id','')} "
            f"old={r.get('old_internal_track_id','')} "
            f"new={r.get('new_internal_track_id','')} "
            f"app={r.get('appearance_distance','')} "
            f"cost={r.get('cost','')} "
            f"reason={r.get('reason','')}"
        )

    print("\nRAW DETECTION COUNT around event")

    nearby=sorted(
        (ts,r) for ts,r in cache.items()
        if abs(ts-target)<=1.0
    )

    # print roughly every 0.25 s rather than all 60 frames
    last=None

    for ts,r in nearby:
        if last is not None and ts-last < .24:
            continue

        last=ts

        print(
            f"{ts:9.3f}s -> "
            f"{len(r.get('detections',[]))} raw detections"
        )
