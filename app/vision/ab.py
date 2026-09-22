"""Experimental V1/V2 action shadow inference and asynchronous audit logging."""
from __future__ import annotations

import csv
import logging
import queue
import re
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import cv2

from .models import ActionsAdapter

log = logging.getLogger(__name__)
CLASSES = ("READING", "WRITING")
_FIELDS = [
    "timestamp", "session_offset_s", "session_id", "track_id", "body_state", "head_direction",
    "v1_reading_probability", "v1_writing_probability", "v2_reading_probability", "v2_writing_probability",
    "reading_probability_delta", "writing_probability_delta", "v1_reading_prediction", "v1_writing_prediction",
    "v2_reading_prediction", "v2_writing_prediction", "v1_ms", "v2_ms", "actions_ab_ms",
    "total_ai_pipeline_ms",
]


def _safe(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value)).strip("_.") or "session"


class AsyncABLogger:
    """Writes one row per person asynchronously and stores sparse disagreement crops."""
    def __init__(self, output_dir: Path, enabled: bool = True):
        self.output_dir = Path(output_dir)
        self.enabled = bool(enabled)
        self._queue = queue.Queue(maxsize=512)
        self._stop = object()
        self._thread = threading.Thread(target=self._writer, name="nazar-actions-ab", daemon=True)
        self._lock = threading.Lock()
        self._session = "standalone"
        self._base_timestamp = None
        self._last_disagreement = {}
        self._counters = Counter()
        self._tracks = set()
        self._last_summary = {}
        if self.enabled:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self._thread.start()

    def set_session(self, session_id: str | None):
        with self._lock:
            if self._counters:
                self._last_summary = self._summary_locked()
            self._session = _safe(session_id or "standalone")
            self._base_timestamp = None
            self._last_disagreement.clear()
            self._counters = Counter()
            self._tracks = set()

    def record(self, timestamp, track_id, crop, v1, v2, thresholds, body_state="UNKNOWN", head_direction="UNKNOWN",
               v1_ms=0.0, v2_ms=0.0, total_ms=0.0):
        if not self.enabled:
            return
        now = float(timestamp)
        with self._lock:
            if self._base_timestamp is None:
                self._base_timestamp = now
            session = self._session
            offset = now - self._base_timestamp
        v1 = [float(x) for x in v1]; v2 = [float(x) for x in v2]
        p1 = [v1[i] >= float(thresholds[CLASSES[i]]) for i in range(2)]
        p2 = [v2[i] >= float(thresholds[CLASSES[i]]) for i in range(2)]
        disagree = []
        for i, name in enumerate(CLASSES):
            if p1[i] != p2[i]:
                key = (int(track_id), name, p1[i], p2[i])
                with self._lock:
                    last = self._last_disagreement.get(key, -1e9)
                    if offset - last >= 2.0:
                        self._last_disagreement[key] = offset
                        disagree.append((name, crop.copy() if crop is not None else None, v1[i], v2[i]))
        row = {
            "timestamp": datetime.now(timezone.utc).isoformat(), "session_offset_s": round(offset, 3),
            "session_id": session, "track_id": int(track_id), "body_state": body_state,
            "head_direction": head_direction, "v1_reading_probability": round(v1[0], 6),
            "v1_writing_probability": round(v1[1], 6), "v2_reading_probability": round(v2[0], 6),
            "v2_writing_probability": round(v2[1], 6), "reading_probability_delta": round(v2[0] - v1[0], 6),
            "writing_probability_delta": round(v2[1] - v1[1], 6), "v1_reading_prediction": int(p1[0]),
            "v1_writing_prediction": int(p1[1]), "v2_reading_prediction": int(p2[0]),
            "v2_writing_prediction": int(p2[1]), "v1_ms": round(float(v1_ms), 3),
            "v2_ms": round(float(v2_ms), 3), "actions_ab_ms": round(float(v1_ms + v2_ms), 3),
            "total_ai_pipeline_ms": round(float(total_ms), 3),
        }
        with self._lock:
            self._counters["rows"] += 1; self._tracks.add((session, int(track_id)))
            self._counters["agreement"] += int(p1 == p2)
            self._counters["disagreement"] += int(p1 != p2)
            for i, name in enumerate(CLASSES):
                self._counters[f"{name}_v1_prob_sum"] += v1[i]
                self._counters[f"{name}_v2_prob_sum"] += v2[i]
                self._counters[f"{name}_v1_yes"] += int(p1[i])
                self._counters[f"{name}_v2_yes"] += int(p2[i])
                self._counters[f"{name}_agreement"] += int(p1[i] == p2[i])
                self._counters[f"{name}_disagreement"] += int(p1[i] != p2[i])
                self._counters[f"v1_{name}_{int(p1[i])}"] += 1
                self._counters[f"v2_{name}_{int(p2[i])}"] += 1
        try:
            self._queue.put_nowait((session, row, disagree))
        except queue.Full:
            with self._lock: self._counters["dropped"] += 1

    def _writer(self):
        handles = {}
        writers = {}
        try:
            while True:
                item = self._queue.get()
                if item is self._stop:
                    break
                session, row, disagreements = item
                if session not in writers:
                    path = self.output_dir / f"{session}_actions_ab.csv"
                    fh = path.open("a", newline="", encoding="utf-8")
                    writer = csv.DictWriter(fh, fieldnames=_FIELDS)
                    if fh.tell() == 0: writer.writeheader()
                    handles[session] = fh; writers[session] = writer
                writers[session].writerow(row); handles[session].flush()
                if disagreements:
                    folder = self.output_dir / session / "disagreements"
                    folder.mkdir(parents=True, exist_ok=True)
                    meta_path = folder / "disagreements.csv"
                    meta_exists = meta_path.exists()
                    with meta_path.open("a", newline="", encoding="utf-8") as meta_fh:
                        meta_fields = ["timestamp", "session_offset_s", "session_id", "track_id", "class", "v1_probability", "v2_probability", "crop_path"]
                        meta_writer = csv.DictWriter(meta_fh, fieldnames=meta_fields)
                        if not meta_exists: meta_writer.writeheader()
                        
                        for name, crop, a, b in disagreements:
                            if crop is None: continue
                            stamp = f"{float(row['session_offset_s']):09.3f}".replace('.', '_')
                            filename = f"{stamp}_track{row['track_id']}_{name}_v1-{a:.3f}_v2-{b:.3f}.jpg"
                            target = folder / filename
                            cv2.imwrite(str(target), crop)
                            meta_writer.writerow({"timestamp":row["timestamp"],"session_offset_s":row["session_offset_s"],"session_id":session,"track_id":row["track_id"],"class":name,"v1_probability":round(a,6),"v2_probability":round(b,6),"crop_path":str(target)})
                    continue
        finally:
            for fh in handles.values(): fh.close()

    def summary(self):
        with self._lock:
            if not self._counters and self._last_summary:
                return dict(self._last_summary)
            return self._summary_locked()

    def _summary_locked(self):
            result = dict(self._counters)
            result["unique_tracks"] = len(self._tracks)
            result["session_id"] = self._session
            result["enabled"] = self.enabled
            result["queue_size"] = self._queue.qsize()
            rows=max(1,result.get("rows",0))
            result["classes"]={name:{"v1_yes":result.get(f"{name}_v1_yes",0),"v2_yes":result.get(f"{name}_v2_yes",0),"agreement":result.get(f"{name}_agreement",0),"disagreement":result.get(f"{name}_disagreement",0),"agreement_pct":round(100*result.get(f"{name}_agreement",0)/rows,2),"v1_average_probability":round(result.get(f"{name}_v1_prob_sum",0)/rows,6),"v2_average_probability":round(result.get(f"{name}_v2_prob_sum",0)/rows,6)} for name in CLASSES}
            return result

    def close(self):
        if self.enabled and self._thread.is_alive():
            self._queue.put(self._stop)
            self._thread.join(timeout=5)


class ShadowActions:
    def __init__(self, settings, logger=None):
        self.enabled = bool(settings.actions_ab_enabled)
        self.adapter = ActionsAdapter(settings.actions_ab_weights, settings.actions_ab_config, settings.device) if self.enabled else None
        self.logger = logger or AsyncABLogger(settings.actions_ab_output_dir, self.enabled)
        self.error = None
        self.latency_ms = 0.0

    @property
    def loaded(self):
        return bool(self.adapter is not None and self.adapter.model is not None)

    @property
    def thresholds(self):
        return self.adapter.thresholds if self.adapter is not None else {name: .5 for name in CLASSES}

    def load(self):
        if self.adapter is None: return
        self.adapter.load(); self.error = None

    def infer(self, crops):
        if self.adapter is None: return []
        result = self.adapter.infer(crops); self.latency_ms = self.adapter.latency_ms
        return result

    def set_session(self, session_id):
        self.logger.set_session(session_id)

    def close(self):
        self.logger.close()
