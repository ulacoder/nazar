"""Safe, streamed video import and metadata validation for the local app."""
from pathlib import Path
import cv2
from werkzeug.utils import secure_filename

SUPPORTED={'.mp4','.mov','.avi','.mkv','.m4v','.webm'}

def inspect_video(path):
    path=Path(path)
    if not path.is_file() or path.stat().st_size<=0:raise ValueError('Video file is empty or unavailable')
    if path.suffix.lower() not in SUPPORTED:raise ValueError('Unsupported video format')
    cap=cv2.VideoCapture(str(path))
    try:
        if not cap.isOpened():raise ValueError('Video container cannot be opened')
        fps=float(cap.get(cv2.CAP_PROP_FPS) or 0);frames=float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0);height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if not width or not height:raise ValueError('Video stream has no resolution')
        if fps<=0 or frames<=0:raise ValueError('Video stream has no duration or frame rate')
        ok,frame=cap.read()
        if not ok or frame is None:raise ValueError('Video frames cannot be decoded')
        duration=frames/fps
        return {'filename':path.name,'path':str(path.resolve()),'size_bytes':path.stat().st_size,'resolution':[width,height],
            'fps':round(fps,3),'duration_s':round(duration,3),'available':True}
    finally:cap.release()

def imported_filename(filename):
    safe=secure_filename(filename or '')
    if not safe or Path(safe).suffix.lower() not in SUPPORTED:raise ValueError('Unsupported video format')
    return safe
