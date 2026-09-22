"""Local HTTP API and server-sent live state."""
from pathlib import Path
from flask import Flask,Response,jsonify,render_template,request,send_file,send_from_directory
from .config import Settings
from .runtime import Runtime
from .evidence import evidence_items,recording
from .videos import imported_filename,inspect_video
import json,os,re
import cv2
import csv,io,zipfile,shutil

# Hosted UI (Vercel) calling this local backend. Override with a comma-separated NAZAR_ALLOWED_ORIGINS;
# entries may use * as a wildcard, e.g. https://nazar-*-ulagats-projects.vercel.app
DEFAULT_ALLOWED_ORIGINS="https://nazar.vercel.app,https://nazar-ulagats-projects.vercel.app,https://nazar-*-ulagats-projects.vercel.app"

def _origin_matcher(value):
    patterns=[re.escape(o.strip().rstrip('/')).replace(r'\*','[a-z0-9-]*') for o in value.split(',') if o.strip()]
    return re.compile('^(?:'+'|'.join(patterns)+')$') if patterns else None

def create_app(settings=None,runtime=None,start_runtime=False):
    settings=settings or Settings.from_env()
    runtime=runtime or Runtime(settings)
    app=Flask(__name__)
    app.config["NAZAR_RUNTIME"]=runtime
    if start_runtime: runtime.start()
    allowed_origins=_origin_matcher(os.getenv("NAZAR_ALLOWED_ORIGINS",DEFAULT_ALLOWED_ORIGINS))

    @app.after_request
    def cors(response):
        origin=request.headers.get("Origin")
        if origin and allowed_origins and allowed_origins.match(origin):
            response.headers["Access-Control-Allow-Origin"]=origin
            response.headers["Access-Control-Allow-Methods"]="GET, POST, PATCH, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"]=request.headers.get("Access-Control-Request-Headers","Content-Type")
            response.headers["Access-Control-Allow-Private-Network"]="true"
            response.headers["Access-Control-Max-Age"]="600"
            response.vary.add("Origin")
        return response

    @app.get("/")
    def home(): return render_template("index.html")

    @app.get("/api/health")
    def health():
        pipeline=runtime.pipeline.status()
        source=runtime.camera.status()
        return jsonify({"ok":True,"input_source":source["source"],"source_connected":source["connected"],
            "source_ended":source.get("ended",False),"source_error":source.get("error"),
            "camera":source["connected"] if source["source"]=="CAMERA" else None,
            "models":pipeline["models"],"ai_error":runtime.last_error})

    @app.get("/api/state")
    def state(): return jsonify(runtime.state())

    @app.get("/api/status")
    def status(): return jsonify(runtime.status())

    @app.get('/api/cameras')
    def cameras(): return jsonify(runtime.cameras())

    @app.post('/api/cameras/rescan')
    def cameras_rescan(): return jsonify(runtime.cameras(rescan=True))

    @app.get('/api/camera/status')
    def camera_status(): return jsonify(runtime.camera.status())

    @app.get('/api/camera/preview')
    def camera_preview():
        device_id=request.args.get('device_id')
        try:
            device=runtime.camera_manager.select(device_id)
            cap=cv2.VideoCapture(device.index,cv2.CAP_DSHOW if device.backend.upper()=='DSHOW' else cv2.CAP_ANY)
            try:
                if not cap.isOpened(): return jsonify(error='Camera unavailable'),409
                ok,frame=cap.read()
            finally: cap.release()
            if not ok:return jsonify(error='Camera frame unavailable'),409
            ok,encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,82])
            if not ok:return jsonify(error='Camera preview encoding failed'),500
            return Response(encoded.tobytes(),mimetype='image/jpeg',headers={'Cache-Control':'no-store'})
        except ValueError as exc:return jsonify(error=str(exc)),400

    @app.post('/api/camera/select')
    def camera_select():
        try:return jsonify(runtime.select_camera(request.get_json(silent=True)))
        except ValueError as exc:return jsonify(error=str(exc)),400
        except RuntimeError as exc:return jsonify(error=str(exc)),409

    @app.post('/api/videos/import')
    def video_import():
        upload=request.files.get('video')
        if upload is None or not upload.filename:return jsonify(error='Choose a video file'),400
        try:
            filename=imported_filename(upload.filename);folder=Path(settings.video_import_dir).resolve();folder.mkdir(parents=True,exist_ok=True)
            target=folder/filename
            upload.save(target)
            metadata=inspect_video(target);metadata['url']=f'/api/videos/{filename}'
            result=runtime.import_video(target);result.update(url=metadata['url'])
            return jsonify(result),201
        except (ValueError,OSError) as exc:
            try:
                if 'target' in locals() and target.exists():target.unlink()
            except OSError:pass
            return jsonify(error=str(exc)),400
        except RuntimeError as exc:return jsonify(error=str(exc)),409

    @app.get('/api/videos/<path:filename>')
    def imported_video(filename):
        folder=Path(settings.video_import_dir).resolve();path=(folder/filename).resolve()
        if not path.is_relative_to(folder) or not path.is_file():return jsonify(error='Video not found'),404
        return send_file(path,mimetype='video/mp4',conditional=True)

    @app.get("/api/actions-ab")
    def actions_ab(): return jsonify(runtime.pipeline.actions_ab_summary())

    @app.get("/api/live")
    def live_events(): return Response(runtime.events_stream(),mimetype="text/event-stream",headers={"Cache-Control":"no-cache","X-Accel-Buffering":"no"})

    @app.get("/stream")
    def stream(): return Response(runtime.video_stream(request.args.get('lang','en')),mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.post("/api/session/start")
    def start_session():
        payload=request.get_json(silent=True)
        if payload is None: payload={}
        if not isinstance(payload,dict): return jsonify(error="Request body must be an object"),400
        try: return jsonify(runtime.start_session(payload.get("mode","LESSON"),payload)),201
        except ValueError as exc: return jsonify(error=str(exc)),400
        except RuntimeError as exc: return jsonify(error=str(exc)),409

    @app.post("/api/session/stop")
    def stop_session():
        try: return jsonify(runtime.stop_session())
        except RuntimeError as exc: return jsonify(error=str(exc)),409

    @app.patch('/api/session/people/<int:person_id>/role')
    def set_person_role(person_id):
        payload=request.get_json(silent=True) or {}
        try: return jsonify(runtime.set_person_role(person_id,payload.get('role')))
        except ValueError as exc: return jsonify(error=str(exc)),400
        except RuntimeError as exc: return jsonify(error=str(exc)),409

    @app.get("/api/sessions")
    def sessions(): return jsonify(runtime.store.sessions())

    @app.get("/api/sessions/<int:session_id>")
    def session(session_id):
        item=runtime.store.session(session_id)
        if not item: return jsonify(error="Session not found"),404
        source_path=Path(item.get('source_video_path') or '') if item.get('source_video_path') else None
        if source_path and source_path.is_file():
            try: item['source_metadata']=inspect_video(source_path)
            except (OSError,ValueError): item['source_metadata']=None
        else: item['source_metadata']=None
        item["events"]=runtime.store.events(session_id=session_id)
        return jsonify(item)

    @app.get("/api/sessions/<int:session_id>/events")
    def session_events(session_id):
        if not runtime.store.session(session_id): return jsonify(error="Session not found"),404
        if request.args.get('page')=='1':
            return jsonify(runtime.store.event_page(session_id,
                track_id=request.args.get('track',type=int),event_type=request.args.get('type') or None,
                offset=max(0,request.args.get('offset',0,type=int)),limit=min(100,max(1,request.args.get('limit',100,type=int)))))
        return jsonify(runtime.store.events(session_id=session_id,limit=None))

    @app.get('/api/sessions/<int:session_id>/people/<int:track_id>')
    def person_detail(session_id,track_id):
        if not runtime.store.session(session_id):return jsonify(error='Session not found'),404
        result=runtime.store.person_detail(session_id,track_id)
        if result is None:return jsonify(error='Track not found in this session'),404
        return jsonify(result)

    @app.get("/api/sessions/<int:session_id>/analytics")
    def session_analytics(session_id):
        result=runtime.store.session_analytics(session_id)
        if result is None: return jsonify(error="Session not found"),404
        return jsonify(result)

    @app.get("/api/events")
    def events():
        try:
            session_id=request.args.get("session",type=int)
            limit=min(max(request.args.get("limit",500,type=int),1),2000)
            return jsonify(runtime.store.events(session_id=session_id,mode=request.args.get("mode") or None,
                event_type=request.args.get("type") or None,date=request.args.get("date") or None,limit=limit))
        except (ValueError,TypeError) as exc: return jsonify(error=str(exc)),400

    @app.get("/api/settings")
    def settings_get():
        return jsonify({"values":runtime.settings_view(),"action_thresholds":runtime.pipeline.actions.thresholds,
            "action_threshold_source":"Supplied actions_v2_hardneg/config.json, used by MVP runner with V4 checkpoint; not validated V4 thresholds",
            "action_v4_checkpoint_threshold":0.5})

    @app.post("/api/settings")
    def settings_post():
        try: return jsonify({"values":runtime.update_settings(request.get_json(silent=True))})
        except ValueError as exc: return jsonify(error=str(exc)),400
        except RuntimeError as exc: return jsonify(error=str(exc)),409

    @app.get("/api/timelapse/<int:session_id>")
    def timelapse(session_id):
        item=runtime.store.session(session_id)
        if not item or not item["timelapse_available"]: return jsonify(error="Timelapse unavailable"),404
        path=Path(item["timelapse_path"]).resolve()
        if not path.is_relative_to(settings.sessions_dir.resolve()) or not path.is_file(): return jsonify(error="Timelapse unavailable"),404
        return send_file(path,mimetype="video/mp4",conditional=True)

    @app.get('/api/sessions/<int:session_id>/evidence')
    def evidence_list(session_id):
        session=runtime.store.session(session_id)
        if not session:return jsonify(error='Session not found'),404
        items=evidence_items(session,runtime.store.events(session_id,limit=None),settings.evidence_dir/str(session_id),runtime.store.person_roles(session_id))
        for key,param in [('track_id','person'),('role','role'),('event_type','type'),('review_priority','priority')]:
            value=request.args.get(param)
            if value:items=[e for e in items if str(e.get(key))==value]
        offset=max(0,request.args.get('offset',0,type=int));limit=min(100,max(1,request.args.get('limit',50,type=int)))
        return jsonify(items=items[offset:offset+limit],total=len(items),offset=offset,limit=limit)

    @app.get('/api/sessions/<int:session_id>/people')
    def session_people(session_id):
        result=runtime.store.session_analytics(session_id)
        if result is None:return jsonify(error='Session not found'),404
        return jsonify(items=result['people'],total=len(result['people']))

    @app.get('/api/sessions/<int:session_id>/timeline/<int:track_id>')
    def person_timeline(session_id,track_id):
        if not runtime.store.session(session_id):return jsonify(error='Session not found'),404
        page=runtime.store.event_page(session_id,track_id,event_type=request.args.get('type') or None,
            offset=max(0,request.args.get('offset',0,type=int)),limit=min(100,max(1,request.args.get('limit',100,type=int))))
        priority=request.args.get('priority')
        if priority:page['items']=[e for e in page['items'] if e.get('review_priority')==priority]
        return jsonify(page)

    @app.delete('/api/sessions/<int:session_id>')
    def delete_session(session_id):
        if request.args.get('confirm') not in ('1','true','yes'):
            return jsonify(error='Confirmation required',requires_confirmation=True),409
        item=runtime.store.delete_session(session_id)
        if not item:return jsonify(error='Session not found'),404
        root=settings.evidence_dir.resolve();folder=(root/str(session_id)).resolve()
        if folder.is_relative_to(root) and folder != root and folder.is_dir():shutil.rmtree(folder)
        for raw in (item.get('timelapse_path'),):
            if raw:
                path=Path(raw).resolve();base=settings.sessions_dir.resolve()
                if path.is_relative_to(base) and path.is_file():path.unlink()
        return jsonify(deleted=session_id)

    @app.get('/api/sessions/<int:session_id>/export')
    def export_session(session_id):
        session=runtime.store.session(session_id)
        if not session:return jsonify(error='Session not found'),404
        analytics=runtime.store.session_analytics(session_id)
        events=runtime.store.events(session_id,limit=None)
        mem=io.BytesIO()
        with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
            z.writestr('session.json',json.dumps(session,ensure_ascii=False,indent=2,default=str))
            z.writestr('analytics.json',json.dumps(analytics,ensure_ascii=False,indent=2,default=str))
            z.writestr('people-roles.json',json.dumps(runtime.store.person_roles(session_id),ensure_ascii=False,indent=2,default=str))
            out=io.StringIO();writer=csv.DictWriter(out,fieldnames=sorted({k for e in events for k in e}) or ['id']);writer.writeheader();writer.writerows(events)
            z.writestr('events.csv',out.getvalue())
        mem.seek(0);return send_file(mem,as_attachment=True,download_name=f'nazar-session-{session_id}.zip',mimetype='application/zip')

    @app.get('/api/sessions/<int:session_id>/evidence/recording')
    def evidence_recording(session_id):
        session=runtime.store.session(session_id)
        if not session or session['mode']!='EXAM':return jsonify(error='Recording unavailable'),404
        path,_,_,_=recording(session)
        if path is None:return jsonify(error='Recording unavailable'),404
        return send_file(path.resolve(),mimetype='video/mp4',conditional=True)

    @app.get('/api/sessions/<int:session_id>/evidence/<int:event_id>/clip')
    def evidence_clip(session_id,event_id):
        folder=(settings.evidence_dir/str(session_id)).resolve();manifest=folder/'manifest.json'
        if not manifest.is_file():return jsonify(error='Clip unavailable'),404
        item=json.loads(manifest.read_text(encoding='utf-8')).get(str(event_id),{})
        path=(folder/item.get('filename','')).resolve()
        if item.get('status')!='ready' or not path.is_relative_to(folder) or not path.is_file():return jsonify(error='Clip unavailable'),404
        return send_file(path,mimetype='video/mp4',conditional=True)

    return app
