"""Isolated production PoseAdapter + stable tracker, with incremental decision logs."""
import argparse,csv,json,sys,time,importlib.util
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2
import numpy as np
from app.config import Settings
from app.vision.models import PoseAdapter
from app.vision.tracker import TrackManager
from app.vision.tracking_log import TrackingLog
from app.vision.types import Detection

def main():
    p=argparse.ArgumentParser();p.add_argument('--video',required=True);p.add_argument('--output-dir',default='data/tracking_debug/run');p.add_argument('--stride',type=int,default=1);p.add_argument('--max-frames',type=int,default=0);p.add_argument('--start-s',type=float,default=0);p.add_argument('--replay-cache');args=p.parse_args()
    if args.stride<1:p.error('stride must be positive')
    s=Settings.from_env();cap=cv2.VideoCapture(args.video)
    if not cap.isOpened():raise SystemExit('Cannot open video')
    fps=cap.get(5) or 30.;count=cap.get(7);w=int(cap.get(3));h=int(cap.get(4))
    out=Path(args.output_dir);out.mkdir(parents=True,exist_ok=True)
    logger=TrackingLog(out/'tracking_debug.csv');pose=None
    replay=Path(args.replay_cache).open(encoding='utf-8') if args.replay_cache else None
    if not replay:pose=PoseAdapter(s.pose_weights,s.pose_conf,s.device);pose.load()
    tracker=TrackManager(max_gap_s=s.track_max_gap_s,stationary_prior=s.track_stationary_prior,home_alpha=s.track_home_alpha,ambiguity_margin=s.track_ambiguity_margin)
    baseline=None;old_path=Path('data/tracking_debug/audit/tracker_before.py')
    if old_path.exists():
        spec=importlib.util.spec_from_file_location('app.vision.audit_baseline',old_path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);baseline=mod.TrackManager(max_gap_s=s.track_max_gap_s)
    writer=cv2.VideoWriter(str(out/'annotated_tracking.mp4'),cv2.VideoWriter_fourcc(*'mp4v'),fps/args.stride,(w,h))
    if not writer.isOpened():raise SystemExit('Video writer unavailable')
    pose_ms=[];tracking_ms=[];old_ms=[];new_ids=[];old_ids=[];frames=0;index=int(args.start_s*fps);cap.set(cv2.CAP_PROP_POS_FRAMES,index)
    started=time.perf_counter()
    try:
        with (out/'detections.jsonl').open('w',encoding='utf-8') as cache:
            while True:
                ok,frame=cap.read()
                if not ok:break
                ts=index/fps
                if replay:
                    line=replay.readline()
                    if not line:break
                    record=json.loads(line);ts=record['timestamp']
                    dets=[Detection(tuple(d['bbox']),np.asarray(d['keypoints']),d['confidence'],d['source_id']) for d in record['detections']]
                else:
                    dets=pose.infer(frame);pose_ms.append(pose.latency_ms)
                cache.write(json.dumps(dict(timestamp=ts,frame_index=index,detections=[dict(bbox=d.bbox,source_id=d.source_id,confidence=d.confidence,keypoints=d.keypoints.tolist()) for d in dets]))+'\n')
                start=time.perf_counter();tracks=tracker.update(dets,ts,frame_index=index,frame_shape=frame.shape);tracking_ms.append((time.perf_counter()-start)*1000)
                logger.record(tracker.debug_events)
                for event in tracker.debug_events:
                    if event['kind']=='new_id':new_ids.append(dict(event,candidates=[x for x in tracker.debug_events if x['kind']=='candidate' and x['detection_index']==event['detection_index']]))
                if baseline:
                    start=time.perf_counter();baseline.update(dets,ts);old_ms.append((time.perf_counter()-start)*1000)
                    old_ids.extend(dict(e) for e in baseline.debug_events if e['kind']=='new_id');baseline.reassociations.clear()
                for t in tracker.tracks.values():
                    a,b,c,d=map(int,t.bbox);color=(100,150,150) if t.missed else (40,210,240)
                    cv2.rectangle(frame,(a,b),(c,d),color,2)
                    label=f'Person #{t.track_id} internal {t.source_id} '+('LOST' if t.missed else 'REASSOCIATED' if t.reassociated else '')
                    cv2.putText(frame,label,(max(4,a),max(22,b-8)),0,.5,(255,255,255),2)
                writer.write(frame);frames+=1
                if frames%100==0:print(f'processed={frames} media={ts:.1f}s stable_ids={tracker.next_id-1}',flush=True)
                if args.max_frames and frames>=args.max_frames:break
                for _ in range(args.stride-1):
                    if not cap.grab():break
                index+=args.stride
    finally:cap.release();writer.release();logger.close()
    summary=dict(tracker.summary(),video=str(Path(args.video).resolve()),video_duration_s=count/fps,frames_processed=frames,stride=args.stride,pose_calls=pose.calls if pose else 0,used_cached_pose=bool(replay),unique_stable_person_ids=tracker.next_id-1,device=str(pose.device) if pose else 'cached',elapsed_s=time.perf_counter()-started,
                 pose_ms_mean=float(np.mean(pose_ms)) if pose_ms else None,tracking_ms_mean=float(np.mean(tracking_ms)),baseline_tracking_ms_mean=float(np.mean(old_ms)) if old_ms else None,baseline_stable_ids=baseline.next_id-1 if baseline else None,new_id_explanations=new_ids,baseline_new_ids=old_ids)
    (out/'tracking_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'new_id_explanations','baseline_new_ids'}},indent=2))
if __name__=='__main__':main()
