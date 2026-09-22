"""Readable Unicode overlay; backend canonical states are never translated."""
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

SKELETON=((5,6),(5,7),(7,9),(6,8),(8,10),(5,11),(6,12),(11,12),(11,13),(13,15),(12,14),(14,16))
NAMES=('PERSON','STUDENT','TEACHER','UNKNOWN_PERSON','SITTING','STANDING','WRITING','READING','HAND_RAISED','TURNED_BACK','HEAD','LOOKING_FORWARD','LOOKING_LEFT','LOOKING_RIGHT','LOOKING_UP','LOOKING_DOWN')
TEXT={
'en':dict(zip(NAMES,('PERSON','STUDENT','TEACHER','PERSON','SITTING','STANDING','WRITING','READING','HAND RAISED','TURNED BACK','HEAD','FORWARD','LEFT','RIGHT','UP','DOWN'))),
'ru':dict(zip(NAMES,('УЧЕНИК','УЧЕНИК','УЧИТЕЛЬ','ЧЕЛОВЕК','СИДИТ','СТОИТ','ПИШЕТ','ЧИТАЕТ','РУКА ПОДНЯТА','ПОВЕРНУТ НАЗАД','ГОЛОВА','ВПЕРЕД','ВЛЕВО','ВПРАВО','ВВЕРХ','ВНИЗ'))),
'kk':dict(zip(NAMES,('ОҚУШЫ','ОҚУШЫ','МҰҒАЛІМ','АДАМ','ОТЫР','ТҰР','ЖАЗЫП ОТЫР','ОҚЫП ОТЫР','ҚОЛ КӨТЕРДІ','АРТҚА БҰРЫЛДЫ','БАСЫ','АЛҒА','СОЛҒА','ОҢҒА','ЖОҒАРЫ','ТӨМЕН')))}

@lru_cache(maxsize=32)
def font(size,bold=False):
    for path in (Path('C:/Windows/Fonts')/('arialbd.ttf' if bold else 'arial.ttf'),Path('/usr/share/fonts/truetype/dejavu')/('DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf')):
        if path.exists():return ImageFont.truetype(str(path),size)
    return ImageFont.load_default(size=size)

def overlay_lines(track,attributes=True,debug=False,language='en'):
    t=TEXT.get(language,TEXT['en']); role=track.get('role','UNKNOWN'); label=t.get({'STUDENT':'STUDENT','TEACHER':'TEACHER'}.get(role,'UNKNOWN_PERSON'),'PERSON');lines=[(f"{label} #{track['track_id']}",True)]
    names={a['name'] for a in track.get('attributes',[])}
    if attributes:
        main=[t[n] for n in ('SITTING','STANDING','WRITING','READING','HAND_RAISED') if n in names]
        if main:lines.append((' • '.join(main),False))
        if 'TURNED_BACK' in names:lines.append((t['TURNED_BACK'],False))
        else:
            head=track.get('head',{}).get('label')
            if head in t:lines.append((f"{t['HEAD']}: {t[head]}",False))
    if debug:
        h=track.get('head',{});parts=[]
        if h.get('pitch') is not None:parts.append(f"P {h['pitch']:.1f}")
        if h.get('yaw') is not None:parts.append(f"Y {h['yaw']:.1f}")
        if parts:lines.append((' '.join(parts),False))
        if track.get('internal_track_id') is not None:lines.append((f"internal {track['internal_track_id']}",False))
        for model in ('v1','v2'):
            raw=track.get('actions_ab',{}).get(model)
            if raw:lines.append((f"{model} R {raw['READING']:.3f} W {raw['WRITING']:.3f}",False))
        fusion=track.get('actions_temporal',{})
        if fusion:lines.append((f"motion {fusion.get('writing_motion_score',0):.3f} temporal {fusion.get('writing_temporal_score',0):.3f}",False))
    return lines

def panel_layout(track,shape,lines):
    height,width=shape[:2]; pad=8;max_width=max(1,width-2);base=max(12,min(22,int(height/32)))
    wrapped=[]
    for text,bold in lines:
        f=font(base+2 if bold else base,bold);buf=''
        for char in text:
            if buf and f.getlength(buf+char)>max_width-2*pad:
                wrapped.append((buf,bold,f));buf=''
            buf+=char
        if buf:wrapped.append((buf,bold,f))
    line_h=base+7;max_lines=max(1,(height-2*pad)//line_h);wrapped=wrapped[:max_lines]
    pw=min(max_width,int(max((f.getlength(text) for text,_,f in wrapped),default=0))+2*pad)
    ph=min(height,len(wrapped)*line_h+2*pad)
    x1,y1,x2,y2=map(int,track['bbox'])
    x=max(0,min(x1,width-pw));y=y1-ph-4
    if y<0:
        # Prefer beside the box when there is space; otherwise its lower edge.
        if x2+pw+4<=width:x=x2+4;y=y1
        elif x1-pw-4>=0:x=x1-pw-4;y=y1
        else:y=y2-ph
    y=max(0,min(y,height-ph))
    return (x,y,pw,ph),wrapped,line_h

def draw_overlay(frame,tracks,boxes=True,skeleton=False,attributes=True,debug=False,language='en'):
    result=frame.copy()
    for track in tracks:
        x1,y1,x2,y2=map(int,track['bbox'])
        if boxes:cv2.rectangle(result,(x1,y1),(x2,y2),(191,155,34),2)
        if skeleton:
            kp=track['keypoints']
            for a,b in SKELETON:
                if kp[a][2]>=.35 and kp[b][2]>=.35:cv2.line(result,tuple(map(int,kp[a][:2])),tuple(map(int,kp[b][:2])),(205,215,80),2)
        (x,y,w,h),lines,line_h=panel_layout(track,result.shape,overlay_lines(track,attributes,debug,language))
        if not w or not h:continue
        roi=result[y:y+h,x:x+w];background=np.full_like(roi,(20,24,30));roi=cv2.addWeighted(roi,.16,background,.84,0)
        image=Image.fromarray(cv2.cvtColor(roi,cv2.COLOR_BGR2RGB));draw=ImageDraw.Draw(image)
        for i,(text,bold,f) in enumerate(lines):draw.text((8,6+i*line_h),text,font=f,fill=(255,255,255) if bold else (225,231,237))
        result[y:y+h,x:x+w]=cv2.cvtColor(np.asarray(image),cv2.COLOR_RGB2BGR)
    return result
