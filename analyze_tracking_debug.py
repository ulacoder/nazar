from pathlib import Path
import csv
from collections import Counter

p = Path(r".\tracking_debug_5min\tracking_debug.csv")

with p.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

print("="*95)
print("TRACKING DEBUG ANALYSIS")
print("="*95)
print("Rows:", len(rows))
print("Columns:")
print(rows[0].keys() if rows else "EMPTY")

kind_counts = Counter(r.get("kind","") for r in rows)
print()
print("EVENT TYPES")
for k,v in kind_counts.most_common():
    print(f"{k:25} {v}")

new_ids = [
    r for r in rows
    if r.get("kind") == "new_id"
]

print()
print("="*95)
print("NEW PUBLIC IDs")
print("="*95)
print("Count:", len(new_ids))

reason_counts = Counter(
    r.get("reason","")
    for r in new_ids
)

print()
print("Reasons:")
for k,v in reason_counts.most_common():
    print(f"{k:35} {v}")

def fnum(x):
    try:
        return float(x)
    except:
        return None

print()
print("NEW-ID TIMELINE")

for i,r in enumerate(new_ids,1):

    ts = fnum(r.get("timestamp"))
    sid = r.get("new_stable_person_id","")
    internal = r.get("new_internal_track_id","")
    recent = r.get("number_of_recent_lost_tracks","")
    reason = r.get("reason","")

    if ts is None:
        tstr = "?"
    else:
        m = int(ts//60)
        s = ts - m*60
        tstr = f"{m:02d}:{s:05.2f}"

    print(
        f"{i:02d} | {tstr} | "
        f"public={sid:>3} | "
        f"internal={internal:>4} | "
        f"lost_nearby={recent:>3} | "
        f"{reason}"
    )


# ------------------------------------------------------------
# For every new ID, show recent expired/deferred/reassociation
# ------------------------------------------------------------

interesting = {
    "expired",
    "deferred",
    "reassociation",
    "new_id"
}

events = [
    r for r in rows
    if r.get("kind") in interesting
]

print()
print("="*95)
print("CONTEXT AROUND EACH NEW ID (previous 3 seconds)")
print("="*95)

for i,new in enumerate(new_ids,1):

    ts = fnum(new.get("timestamp"))

    if ts is None:
        continue

    context = []

    for r in events:
        rt = fnum(r.get("timestamp"))

        if rt is None:
            continue

        if ts-3.0 <= rt <= ts:
            context.append(r)

    print()
    print(
        f"--- NEW #{new.get('new_stable_person_id')} "
        f"at {ts:.2f}s ---"
    )

    for r in context[-15:]:

        print(
            f"{float(r['timestamp']):8.2f} | "
            f"{r.get('kind',''):13} | "
            f"stable={r.get('stable_person_id', r.get('new_stable_person_id','')):>3} | "
            f"oldInt={r.get('old_internal_track_id',''):>4} | "
            f"newInt={r.get('new_internal_track_id',''):>4} | "
            f"gap={r.get('gap_s',''):>7} | "
            f"reason={r.get('reason','')}"
        )
