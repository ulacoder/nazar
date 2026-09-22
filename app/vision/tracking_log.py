"""Buffered tracker decision CSV. No model or image work in the writer."""
import csv,json,queue,threading
from pathlib import Path

FIELDS=('kind','timestamp','frame_index','detection_index','new_internal_track_id','new_stable_person_id','stable_person_id','old_internal_track_id','bbox','number_of_recent_lost_tracks','gap_s','iou','normalized_center_distance','bbox_size_ratio','predicted_center_distance','home_center_distance','pose_distance','cost','gate_pass','reason')
class TrackingLog:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.queue=queue.Queue();self.error=None
        self.thread=threading.Thread(target=self._run,name='tracking-log',daemon=True);self.thread.start()
    def record(self,rows):
        if rows:self.queue.put([dict(row) for row in rows])
    def _run(self):
        try:
            with self.path.open('a',newline='',encoding='utf-8') as f:
                writer=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore')
                if f.tell()==0:writer.writeheader()
                while True:
                    rows=self.queue.get()
                    if rows is None:break
                    writer.writerows(rows);f.flush()
        except Exception as exc:self.error=str(exc)
    def close(self):
        self.queue.put(None);self.thread.join()
