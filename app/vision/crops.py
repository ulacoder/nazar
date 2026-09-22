"""Pixel preparation copied in behavior from the supplied MVP reference runner."""
import cv2
import numpy as np
from PIL import Image
from torchvision import transforms

NORMALIZE = transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
TRANSFORM = transforms.Compose([transforms.Resize(256), transforms.CenterCrop(224), transforms.ToTensor(), NORMALIZE])

def crop_square_center(frame, cx, cy, side):
    side = max(float(side), 16.0)
    x1, y1, x2, y2 = (int(round(cx-side/2)), int(round(cy-side/2)), int(round(cx+side/2)), int(round(cy+side/2)))
    h, w = frame.shape[:2]
    left, top, right, bottom = max(0,-x1), max(0,-y1), max(0,x2-w), max(0,y2-h)
    if any((left, top, right, bottom)):
        frame = cv2.copyMakeBorder(frame, top, bottom, left, right, cv2.BORDER_REPLICATE)
        x1 += left; x2 += left; y1 += top; y2 += top
    crop = frame[y1:y2, x1:x2]
    return crop if crop.size else None

def make_person_crop(frame, box):
    x1,y1,x2,y2 = map(float,box)
    width,height = max(x2-x1,2),max(y2-y1,2)
    crop = crop_square_center(frame,(x1+x2)/2,(y1+y2)/2,max(width,height))
    return None if crop is None else cv2.resize(crop,(256,256),interpolation=cv2.INTER_AREA)

def make_head_crop(frame, box, keypoints, keypoint_conf=.35):
    x1,y1,x2,y2=map(float,box)
    person_w,person_h=max(x2-x1,2),max(y2-y1,2)
    face=np.asarray(keypoints[:5])
    points=face[face[:,2]>=keypoint_conf]
    if len(points)>=2:
        xs,ys=points[:,0],points[:,1]
        face_w=max(float(xs.max()-xs.min()),person_w*.18)
        face_h=max(float(ys.max()-ys.min()),person_h*.08)
        side=min(max(face_w*2.25,face_h*3.0,person_w*.40,person_h*.20),person_h*.42)
        cx=float(np.median(xs));cy=float(np.mean(ys))-side*.04
    else:
        side=min(max(person_w*.58,person_h*.28),person_h*.42)
        cx=(x1+x2)/2;cy=y1+person_h*.16
    crop=crop_square_center(frame,cx,cy,side)
    return None if crop is None else cv2.resize(crop,(256,256),interpolation=cv2.INTER_AREA)

def tensor_from_bgr(crop):
    rgb=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)
    return TRANSFORM(Image.fromarray(rgb))
