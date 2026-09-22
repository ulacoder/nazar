import json
from pathlib import Path
import numpy as np

p=Path(r".\tracking_debug_5min\detections.jsonl")

target=204.9

for line in p.open("r",encoding="utf-8"):
    r=json.loads(line)

    if abs(float(r["timestamp"])-target) > 1e-4:
        continue

    print("timestamp:",r["timestamp"])

    for i,d in enumerate(r["detections"]):
        print()
        print("DET",i)
        print("source_id:",d["source_id"])
        print("confidence:",round(float(d["confidence"]),4))
        print("bbox:",[round(float(x),2) for x in d["bbox"]])

    break
