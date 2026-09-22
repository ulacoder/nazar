"""Exact checkpoint architectures and inference interpretation from the MVP."""
from contextlib import nullcontext
from pathlib import Path
import json
import time
import numpy as np
import torch
from torch import nn
from torchvision.models import mobilenet_v3_small
from ultralytics import YOLO
from .types import Detection
from .appearance import torso_descriptor
from .crops import tensor_from_bgr

def select_device(preference="auto"):
    if preference == "auto": return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    device=torch.device(preference)
    if device.type == "cuda" and not torch.cuda.is_available(): raise RuntimeError("CUDA requested but unavailable")
    return device

def load_mobilenet_2(path, device):
    checkpoint=torch.load(Path(path),map_location="cpu",weights_only=True)
    model=mobilenet_v3_small(weights=None)
    model.classifier[-1]=nn.Linear(model.classifier[-1].in_features,2)
    model.load_state_dict(checkpoint["model_state_dict"],strict=True)
    return model.to(device).eval(), checkpoint

class PoseAdapter:
    def __init__(self, path, conf=.35, device="auto"):
        self.path=Path(path);self.conf=conf;self.device=select_device(device)
        self.model=None;self.latency_ms=0.0;self.error=None;self.calls=0

    def load(self):
        if not self.path.is_file(): raise FileNotFoundError(self.path)
        self.model=YOLO(str(self.path))

    def reset_tracking(self):
        # A new video/session must not inherit ByteTrack's previous identities.
        if self.model is not None: self.model=YOLO(str(self.path))

    def infer(self, frame):
        if self.model is None:
            self.load()

        start=time.perf_counter()

        result=self.model.track(
            frame,
            persist=True,
            tracker="bytetrack.yaml",
            conf=self.conf,
            imgsz=640,
            device=0 if self.device.type=="cuda" else "cpu",
            verbose=False
        )[0]

        self.calls+=1
        self.latency_ms=(time.perf_counter()-start)*1000

        if result.boxes is None or result.keypoints is None:
            return []

        boxes=result.boxes.xyxy.detach().cpu().numpy()
        scores=result.boxes.conf.detach().cpu().numpy()
        points=result.keypoints.data.detach().cpu().numpy()

        ids=(
            result.boxes.id.detach().cpu().numpy().astype(int).tolist()
            if result.boxes.id is not None
            else [None]*len(boxes)
        )

        detections=[]

        for box,kp,score,tid in zip(boxes,points,scores,ids):
            bbox=tuple(map(float,box))
            keypoints=np.asarray(kp)

            appearance=torso_descriptor(
                frame,
                bbox,
                keypoints
            )

            detections.append(
                Detection(
                    bbox,
                    keypoints,
                    float(score),
                    tid,
                    appearance
                )
            )

        return detections


class ActionsAdapter:
    def __init__(self, weights, config, device="auto"):
        self.weights=Path(weights);self.config=Path(config);self.device=select_device(device)
        self.model=None;self.checkpoint=None;self.latency_ms=0.0
        with self.config.open(encoding="utf-8-sig") as f: cfg=json.load(f)
        self.classes=tuple(x.upper() for x in cfg.get("outputs",cfg.get("class_names",())))
        if self.classes != ("READING","WRITING"): raise ValueError(f"Unexpected action order: {self.classes}")
        raw_thresholds=cfg.get("thresholds")
        if raw_thresholds is None and "threshold" in cfg:
            raw_thresholds={name:cfg["threshold"] for name in self.classes}
        if not isinstance(raw_thresholds,dict): raise ValueError("Action config must provide thresholds or threshold")
        self.thresholds={k.upper():float(v) for k,v in raw_thresholds.items()}

    def load(self):
        self.model,self.checkpoint=load_mobilenet_2(self.weights,self.device)
        if tuple(self.checkpoint.get("class_names",())) != self.classes: raise ValueError("Action checkpoint class order differs from config")

    def infer(self, crops):
        if not crops: return np.empty((0,2),dtype=np.float32)
        if self.model is None: self.load()
        start=time.perf_counter()
        batch=torch.stack([tensor_from_bgr(c) for c in crops]).to(self.device,non_blocking=True)
        with torch.inference_mode():
            with (torch.amp.autocast("cuda",dtype=torch.float16) if self.device.type=="cuda" else nullcontext()):
                probabilities=torch.sigmoid(self.model(batch))
        scores=probabilities.float().cpu().numpy()
        self.latency_ms=(time.perf_counter()-start)*1000
        return scores

class HeadAdapter:
    def __init__(self, weights, config, device="auto"):
        self.weights=Path(weights);self.config=Path(config);self.device=select_device(device)
        self.model=None;self.checkpoint=None;self.latency_ms=0.0
        with self.config.open(encoding="utf-8-sig") as f: cfg=json.load(f)
        self.thresholds={k:float(v) for k,v in cfg["prediction_thresholds"].items()}

    def load(self):
        self.model,self.checkpoint=load_mobilenet_2(self.weights,self.device)
        self.pitch_scale=float(self.checkpoint["pitch_scale"])
        self.yaw_scale=float(self.checkpoint["yaw_scale"])

    def infer(self, crops):
        if not crops: return np.empty((0,2),dtype=np.float32)
        if self.model is None: self.load()
        start=time.perf_counter()
        batch=torch.stack([tensor_from_bgr(c) for c in crops]).to(self.device,non_blocking=True)
        with torch.inference_mode():
            with (torch.amp.autocast("cuda",dtype=torch.float16) if self.device.type=="cuda" else nullcontext()):
                output=self.model(batch)
        angles=output.float().cpu().numpy()
        angles[:,0]*=self.pitch_scale;angles[:,1]*=self.yaw_scale
        self.latency_ms=(time.perf_counter()-start)*1000
        return angles

    def classify(self,pitch,yaw):
        t=self.thresholds
        if yaw<=t["yaw_left_deg"]: return "LOOKING_LEFT"
        if yaw>=t["yaw_right_deg"]: return "LOOKING_RIGHT"
        if pitch>=t["pitch_up_deg"]: return "LOOKING_UP"
        if pitch<=t["pitch_down_deg"]: return "LOOKING_DOWN"
        return "LOOKING_FORWARD"
