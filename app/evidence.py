"""Timestamp evidence and serialized post-session encoding from existing recordings."""
import csv,json,logging,subprocess,threading,bisect
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from functools import lru_cache
import cv2

log=logging.getLogger(__name__)
WORKER=ThreadPoolExecutor(max_workers=1,thread_name_prefix='evidence')

def evidence_window(offset,duration,pre=3.,post=3.):
    return round(max(0.,float(offset)-float(duration or 0)-pre),3),round(float(offset)+post,3)

@lru_cache(maxsize=64)
def _duration(path,mtime):
    cap=cv2.VideoCapture(path)
    try:
        fps=cap.get(cv2.CAP_PROP_FPS)
        return cap.get(cv2.CAP_PROP_FRAME_COUNT)/fps if cap.isOpened() and fps>0 else 0.
    finally:cap.release()

def recording(session):
    original=session.get('source_video_path')
    if original and Path(original).is_file():
        path=Path(original);return path,'source',[],_duration(str(path),path.stat().st_mtime_ns)
    path=Path(session.get('timelapse_path') or '')
    if not session.get('timelapse_available') or not path.is_file():return None,'unavailable',[],0
    timing=path.with_suffix('.timestamps.csv')
    if not timing.is_file():return None,'missing_timestamp_map',[],0
    with timing.open(encoding='utf-8') as f:rows=[(float(r['session_offset_s']),float(r['recording_offset_s'])) for r in csv.DictReader(f)]
    return path,'timelapse',rows,_duration(str(path),path.stat().st_mtime_ns)

def map_window(start,end,kind,rows,duration):
    if kind=='source':return (max(0,start),min(end,duration)) if start<duration else None
    if kind!='timelapse' or not rows:return None
    # Include only frames actually sampled during the requested window.
    offsets=[r[0] for r in rows];lo=bisect.bisect_left(offsets,start);hi=bisect.bisect_right(offsets,end)-1
    if lo>hi or lo>=len(rows):return None
    frame_step=rows[1][1]-rows[0][1] if len(rows)>1 else duration
    return rows[lo][1],min(duration,rows[hi][1]+frame_step)

def evidence_items(session,events,output_dir,roles=None):
    path,kind,timing,duration=recording(session)
    manifest_path=Path(output_dir)/'manifest.json';manifest={}
    if manifest_path.exists():
        try:manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
        except (ValueError,OSError):pass
    items=[]
    if session.get('mode')!='EXAM':return items
    for event in events:
        if event.get('review_priority') not in {'REVIEW','HIGH_REVIEW'}:continue
        item=dict(event);start=event.get('evidence_start_s');end=event.get('evidence_end_s')
        item['role']=(roles or {}).get(event.get('track_id'),'UNKNOWN')
        mapped=map_window(start,end,kind,timing,duration) if start is not None and end is not None else None
        item.update(available=bool(mapped),recording_kind=kind,recording_start_s=mapped[0] if mapped else None,recording_end_s=mapped[1] if mapped else None,
                    event_start_s=event.get('session_offset_s'),event_end_s=round((event.get('session_offset_s') or 0)+(event.get('duration_s') or 0),3),
                    unavailable_reason=None if mapped else 'No recording samples with reliable timestamps in this window',person_highlight_available=False)
        clip=manifest.get(str(event['id']),{})
        item['clip_available']=clip.get('status')=='ready' and (Path(output_dir)/clip.get('filename','')).is_file()
        item['clip_status']=clip.get('status','not_generated');item['clip_error']=clip.get('error')
        item['status']='READY' if item['clip_available'] or item['available'] else ('FAILED' if item['clip_status']=='failed' else 'UNAVAILABLE')
        if item['clip_status']=='encoding':item['status']='PROCESSING'
        if item['clip_available']:item['clip_url']=f"/api/sessions/{session['id']}/evidence/{event['id']}/clip"
        if mapped:item['recording_url']=f"/api/sessions/{session['id']}/evidence/recording"
        items.append(item)
    return items

def merged_windows(items):
    groups=[]
    for e in sorted((e for e in items if e['available']),key=lambda e:e['recording_start_s']):
        a,b=e['recording_start_s'],e['recording_end_s']
        if groups and a<=groups[-1]['end']:
            groups[-1]['end']=max(groups[-1]['end'],b);groups[-1]['events'].append(e)
        else:groups.append(dict(start=a,end=b,events=[e]))
    return groups

def generate_review_clips(session,events,output_dir):
    # One worker for all sessions; no encoder/model work on inference thread.
    return WORKER.submit(_generate,dict(session),list(events),Path(output_dir))

def _generate(session,events,output_dir):
    items=evidence_items(session,events,output_dir);groups=merged_windows(items)
    if not groups:return
    path,_,_,_=recording(session);output_dir.mkdir(parents=True,exist_ok=True);manifest={}
    def save():
        temp=output_dir/'manifest.tmp';temp.write_text(json.dumps(manifest,indent=2),encoding='utf-8');temp.replace(output_dir/'manifest.json')
    try:
        import imageio_ffmpeg
        executable=imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        executable=None
    for group in groups:
        first=group['events'][0];filename=f"{first['id']}_{first['event_type']}.mp4";target=output_dir/filename
        state=dict(filename=filename,status='encoding',recording_start_s=group['start'],recording_end_s=group['end'])
        for e in group['events']:manifest[str(e['id'])]=state
        save()
        try:
            if not executable:raise RuntimeError('imageio-ffmpeg is required for optional H.264 clips')
            result=subprocess.run([executable,'-hide_banner','-loglevel','error','-y','-ss',str(group['start']),'-i',str(path),'-t',str(group['end']-group['start']),'-an','-c:v','libx264','-preset','veryfast','-threads','1','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],capture_output=True,text=True,timeout=180,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            if result.returncode or not target.is_file() or not target.stat().st_size:raise RuntimeError(result.stderr[-2000:] or 'Encoder produced no clip')
            state['status']='ready'
        except Exception as exc:state.update(status='failed',error=str(exc));log.exception('Evidence generation failed')
        save()
