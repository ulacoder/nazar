"""Offline, every-frame validation through NAZAR's production VisionPipeline.

Example: py -3.14 scripts/validate_video.py --video classroom.mp4 --mode LESSON
"""
import argparse
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
import cv2

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

from app.config import Settings
from app.overlay import draw_overlay
from app.pipeline import VisionPipeline
from app.sessions import SessionManager
from app.storage.database import Store
from app.timelapse import DisabledRecorder
from app.video import media_timestamp,resolve_video_path

def create_writer(path,fps,size):
    for codec in ("avc1","mp4v"):
        writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*codec),fps,size)
        if writer.isOpened(): return writer,codec
        writer.release()
    raise RuntimeError("No MP4 encoder available")

def run(video,output=None,report=None,mode="LESSON",device="auto",max_frames=None):
    source=resolve_video_path(video)
    if not source.is_file(): raise FileNotFoundError(source)
    output=Path(output) if output else ROOT/"data"/"validations"/source.stem/"annotated.mp4"
    report=Path(report) if report else output.with_name("validation_report.json")
    output.parent.mkdir(parents=True,exist_ok=True);report.parent.mkdir(parents=True,exist_ok=True)
    trace=report.with_name("observations.jsonl")
    capture=cv2.VideoCapture(str(source))
    if not capture.isOpened(): raise RuntimeError(f"Cannot open video: {source}")
    fps=capture.get(cv2.CAP_PROP_FPS)
    if fps<=0: fps=25.0
    source_frames=int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    width=int(capture.get(cv2.CAP_PROP_FRAME_WIDTH));height=int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    if width<=0 or height<=0: raise RuntimeError("Video dimensions unavailable")
    settings=Settings.from_env();settings.device=device
    pipeline=VisionPipeline(settings);pipeline.load()
    if pipeline.errors["pose"]: raise RuntimeError(f"Pose model unavailable: {pipeline.errors['pose']}")
    writer,codec=create_writer(output,fps,(width,height))
    store=Store(report.parent/"validation.sqlite3")
    sessions=SessionManager(store,DisabledRecorder(),settings.event_min_duration,settings.event_cooldown)
    session=sessions.start(mode,source_type="VIDEO",source_name=source.name)
    timings=[];observed=Counter();unique_tracks=set();frame_count=0;previous=None
    started=time.perf_counter()
    try:
        with trace.open("w",encoding="utf-8") as observations:
            while True:
                ok,frame=capture.read()
                if not ok or (max_frames is not None and frame_count>=max_frames): break
                timestamp=media_timestamp(capture,frame_count,fps,previous)
                tracks=pipeline.process(frame,timestamp)
                events=sessions.observe(tracks,timestamp,source_offset_s=timestamp)
                writer.write(draw_overlay(frame,tracks,settings.boxes_overlay,settings.skeleton_overlay,settings.attributes_overlay))
                observations.write(json.dumps({"frame":frame_count,"video_time_s":timestamp,"tracks":tracks,"events":events})+"\n")
                for track in tracks:
                    unique_tracks.add(track["track_id"])
                    observed.update(attribute["name"] for attribute in track["attributes"])
                if frame_count>0: timings.append(pipeline.latency.copy())
                frame_count+=1;previous=timestamp
    finally:
        capture.release();writer.release()
        saved=sessions.stop()
    elapsed=time.perf_counter()-started
    metrics={key:round(statistics.mean(sample[key] for sample in timings),2) for key in timings[0]} if timings else {}
    events=store.events(session_id=session["id"],limit=100000)[::-1]
    result={"source":str(source),"source_fps":fps,"source_frames":source_frames,
        "processed_frames":frame_count,"last_video_time_s":previous,"processing_elapsed_s":round(elapsed,2),
        "processing_fps":round(frame_count/max(elapsed,.001),2),"session":saved,
        "unique_track_ids":sorted(unique_tracks),"observed_attribute_frame_counts":dict(observed),
        "events":events,"model_status":pipeline.status()["models"],"model_errors":pipeline.errors,
        "mean_latency_ms_excluding_first_frame":metrics,"pose_calls":pipeline.pose.calls,
        "action_threshold_provenance":"0.39/0.41 from supplied V2 config; V4 checkpoint metadata 0.5; no tuning performed",
        "annotated_video":str(output.resolve()),"annotated_codec":codec,"observations_jsonl":str(trace.resolve())}
    report.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    return result

def main():
    parser=argparse.ArgumentParser(description="Validate a local video through the production NAZAR pipeline")
    parser.add_argument("--video",required=True,help="Local MP4/MOV/AVI input")
    parser.add_argument("--output",help="Annotated MP4 output path")
    parser.add_argument("--report",help="JSON report path")
    parser.add_argument("--mode",choices=("LESSON","EXAM"),default="LESSON")
    parser.add_argument("--device",choices=("auto","cuda","cpu"),default="auto")
    parser.add_argument("--max-frames",type=int,help="Optional development smoke limit")
    args=parser.parse_args()
    result=run(args.video,args.output,args.report,args.mode,args.device,args.max_frames)
    print(json.dumps({"processed_frames":result["processed_frames"],"unique_track_ids":result["unique_track_ids"],
        "event_count":len(result["events"]),"annotated_video":result["annotated_video"],"report":str(Path(args.report).resolve()) if args.report else str(Path(result["annotated_video"]).with_name("validation_report.json"))},indent=2))

if __name__=="__main__": main()
