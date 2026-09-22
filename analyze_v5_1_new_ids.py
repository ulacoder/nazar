import json
from pathlib import Path

p = Path(r".\tracking_debug_5min_v5_1\tracking_summary.json")
data = json.loads(p.read_text(encoding="utf-8"))

W, H = 1762, 1030

for e in data.get("new_id_explanations", []):

    bbox = e.get("bbox") or [0,0,0,0]

    try:
        x1,y1,x2,y2 = map(float,bbox)

        edge = (
            x1 <= W*0.03 or
            x2 >= W*0.97 or
            y1 <= H*0.03 or
            y2 >= H*0.97
        )
    except:
        edge = False

    print()
    print("="*105)

    print(
        f"NEW #{e.get('new_stable_person_id')} "
        f"t={float(e.get('timestamp',0)):.2f}s "
        f"internal={e.get('new_internal_track_id')} "
        f"EDGE={edge}"
    )

    print("bbox:", bbox)

    candidates = e.get("candidates", [])

    if not candidates:
        print("NO ACTIVE CANDIDATES")
        continue

    candidates = sorted(
        candidates,
        key=lambda c: float(c.get("cost",9999))
    )

    for c in candidates[:5]:

        def f(key):
            v=c.get(key)
            if v is None:
                return "-"
            try:
                return f"{float(v):.3f}"
            except:
                return str(v)

        print(
            f"  public={c.get('stable_person_id')} "
            f"oldInt={c.get('old_internal_track_id')} | "
            f"app={f('appearance_distance')} "
            f"cost={f('cost')} "
            f"center={f('normalized_center_distance')} "
            f"home={f('home_center_distance')} "
            f"ratio={f('bbox_size_ratio')} "
            f"iou={f('iou')} "
            f"gap={f('gap_s')} | "
            f"{c.get('reason')}"
        )
