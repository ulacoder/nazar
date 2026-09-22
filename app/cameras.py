"""Portable camera discovery with optional Windows friendly-name support."""
from dataclasses import asdict,dataclass
import platform
import cv2

@dataclass
class CameraDevice:
    device_id:str
    name:str
    index:int
    backend:str
    resolution:tuple|None=None
    fps:float|None=None
    available:bool=False
    error:str|None=None

    def as_dict(self):
        value=asdict(self);value['resolution']=list(self.resolution) if self.resolution else None
        value['fps']=round(self.fps,1) if self.fps is not None else None
        return value

class CameraManager:
    def __init__(self,max_indices=8,enumerator=None,capture_factory=None):
        self.max_indices=max_indices;self.enumerator=enumerator;self.capture_factory=capture_factory or cv2.VideoCapture
        self.devices=[]

    def _windows_devices(self):
        if self.enumerator:return list(self.enumerator())
        try:
            from cv2_enumerate_cameras import enumerate_cameras
            return list(enumerate_cameras())
        except (ImportError,RuntimeError,TypeError):return []

    def discover(self):
        hints=self._windows_devices() if platform.system()=='Windows' else []
        by_index={int(getattr(item,'index',getattr(item,'index',-1))):item for item in hints if getattr(item,'index',None) is not None}
        devices=[]
        for index in range(self.max_indices):
            hint=by_index.get(index); name=str(getattr(hint,'name','')) if hint else ''
            backend=str(getattr(hint,'backend','DSHOW' if platform.system()=='Windows' else 'ANY'))
            cap=None
            try:
                cap=self.capture_factory(index,cv2.CAP_DSHOW if platform.system()=='Windows' else cv2.CAP_ANY)
                if not cap.isOpened():continue
                width=int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0);height=int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
                fps=float(cap.get(cv2.CAP_PROP_FPS) or 0)
                stable=str(getattr(hint,'path','') or getattr(hint,'guid','') or '')
                if not stable:
                    stable=f"index:{index}:{name or 'camera'}"
                devices.append(CameraDevice(stable,name or f"Camera {index}",index,backend,(width,height) if width and height else None,fps or None,True))
            except Exception as exc:
                if hint:devices.append(CameraDevice(f"index:{index}",name or f"Camera {index}",index,backend,error=str(exc)))
            finally:
                if cap is not None:cap.release()
        self.devices=devices
        return [device.as_dict() for device in devices]

    def get(self,device_id):
        return next((item for item in self.devices if item.device_id==device_id),None)

    def select(self,device_id):
        if not self.devices:self.discover()
        device=self.get(device_id)
        if device is None:raise ValueError('Unknown camera device')
        return device
