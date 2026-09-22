from pathlib import Path
import csv

p = Path(r".\tracking_debug_5min_v3\tracking_debug.csv")

with p.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

new_ids = [r for r in rows if r.get("kind") == "new_id"]
candidates = [r for r in rows if r.get("kind") == "candidate"]

def num(v):
    try:
        return float(v)
    except:
        return 999999.0

print("="*120)
print("TOP CANDIDATES FOR EVERY NEW PUBLIC ID")
print("="*120)

for event in new_ids:

    ts = event.get("timestamp")
    det = event.get("detection_index")

    same = [
        r for r in candidates
        if r.get("timestamp") == ts
        and r.get("detection_index") == det
    ]

    same.sort(key=lambda r: num(r.get("cost")))

    print()
    print(
        f"NEW public #{event.get('new_stable_person_id')} | "
        f"internal={event.get('new_internal_track_id')} | "
        f"t={float(ts):.2f}s"
    )

    if not same:
        print("  NO ACTIVE CANDIDATES")
        continue

    for r in same[:4]:

        def show(key):
            x=r.get(key,"")
            try:
                return f"{float(x):.3f}"
            except:
                return str(x)

        print(
            f"  candidate public={r.get('stable_person_id','?'):>3} "
            f"oldInt={r.get('old_internal_track_id','?'):>4} | "
            f"gap={show('gap_s'):>6} "
            f"cost={show('cost'):>6} | "
            f"iou={show('iou'):>6} "
            f"center={show('normalized_center_distance'):>6} "
            f"pred={show('predicted_center_distance'):>6} "
            f"home={show('home_center_distance'):>6} "
            f"ratio={show('bbox_size_ratio'):>6} "
            f"pose={show('pose_distance'):>6} | "
            f"gate={r.get('gate_pass')} "
            f"reason={r.get('reason')}"
        )
