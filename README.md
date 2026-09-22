# NAZAR

NAZAR is a local, anonymous classroom-observation application. It runs the supplied pose, Actions, and Head Direction checkpoints on a webcam or prerecorded video; it tracks temporary people, stabilizes observable states, saves Lesson/Exam events to SQLite, and records a session timelapse. The dashboard runs at `http://127.0.0.1:8000/`. It does not identify people or assign behavioral scores.

## Windows PowerShell installation

The verified development machine uses Python 3.14, PyTorch 2.11.0+cu128, and an RTX 5060 Laptop GPU. From this project directory:

```powershell
Set-Location 'C:\Users\Abik\Documents\ChatGPT\NAZAR'
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install torch==2.11.0 torchvision==0.26.0 --index-url https://download.pytorch.org/whl/cu128
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
```

The CUDA wheel command is for this tested machine. For another GPU/driver, choose a compatible wheel using the [PyTorch installer](https://pytorch.org/get-started/locally/). For CPU-only operation, install `torch==2.11.0 torchvision==0.26.0` from `https://download.pytorch.org/whl/cpu` instead and set `NAZAR_DEVICE=cpu`. Checkpoint files must remain under `models/` or be supplied using the `NAZAR_*_WEIGHTS` variables in `.env.example`.

## Launch

Camera (default):

```powershell
Set-Location 'C:\Users\Abik\Documents\ChatGPT\NAZAR'
$env:NAZAR_INPUT_SOURCE='CAMERA'
.\.venv\Scripts\python.exe serve.py
```

Prerecorded video, no webcam interaction:

```powershell
Set-Location 'C:\Users\Abik\Documents\ChatGPT\NAZAR'
$env:NAZAR_INPUT_SOURCE='VIDEO'
$env:NAZAR_VIDEO_PATH='C:\path\to\classroom.mp4'
.\.venv\Scripts\python.exe serve.py
```

Open `http://127.0.0.1:8000/`. In Video mode, pressing Start Lesson or Start Exam replays the file from the beginning. The live UI uses a latest-frame worker and may skip source frames if inference is slower than playback. The development command below processes **every frame**. Source-file timestamps, not wall-clock capture times, drive video event confirmation and are stored as `source_offset_s`; `occurred_at` remains the local run's UTC audit timestamp. Stop the session after playback to persist its summary and timelapse. The webcam remains available whenever `CAMERA` is selected. Explicit environment variables take precedence over settings saved in SQLite; other settings can be changed in the dashboard.

Start Session now asks for a Lesson or Exam type and optional teacher/proctor, class/group, subject/exam, and notes, followed by explicit confirmation. It stores only session context, never student names. Recent teacher/class/subject values are offered locally in this browser. Existing sessions without metadata remain readable. Open Sessions → Open to view that session's Overview, Events, Analytics, and Timelapse; the main navigation has no global Analytics page. The session-specific API is `GET /api/sessions/<id>/analytics`, with observations and events strictly restricted to `<id>`. Chart numbers are confirmed event occurrences, not time spent in a state. Historic event end times were not persisted, so no durations are inferred; old sessions have no people-over-time samples. Event-to-timelapse seeking is approximate when timing metadata exists.

## Hosted dashboard (Vercel)

The dashboard can be hosted on Vercel while the models keep running locally. Vercel serves only the static UI (`vercel.json` runs `node scripts/build_static.mjs` into `dist/`; no Python is deployed). The page calls the local backend at `http://127.0.0.1:8000`, so start `serve.py` as above, then open the Vercel URL in Chrome, Edge or Firefox on the same machine (Chrome may ask to allow access to local network devices). Safari blocks HTTPS pages from calling `http://127.0.0.1`.

- Another backend address: open `https://<vercel-url>/?api=http://host:port` once (remembered in the browser); `?api=` resets it.
- The local backend only answers cross-origin requests from `https://nazar.vercel.app`, `https://nazar-ulagats-projects.vercel.app` and this project's preview URLs. For a custom domain set `NAZAR_ALLOWED_ORIGINS` (comma-separated, `*` wildcard allowed) before launching `serve.py`.

## Every-frame video validation

```powershell
Set-Location 'C:\Users\Abik\Documents\ChatGPT\NAZAR'
.\.venv\Scripts\python.exe scripts\validate_video.py --video 'C:\path\to\classroom.mp4' --mode LESSON --device auto
```

Use `--mode EXAM` for Exam event rules, `--device cpu` to force CPU, and optionally `--output`, `--report`, or `--max-frames`. Defaults are `data\validations\<video-stem>\annotated.mp4`, `validation_report.json`, `observations.jsonl`, and `validation.sqlite3`. This command calls the **same `VisionPipeline.process` and `SessionManager.observe`** as the live application. The annotated video is written at the source FPS; the JSONL contains each frame's video time, tracked observations, and generated events. The report contains model status/errors, latency, IDs, observed-attribute counts, and events. It does not assert ground-truth accuracy: review the annotated output against the supplied clip.

## Tests and diagnostics

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m compileall -q app scripts serve.py
node --check app\static\js\dashboard.js
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8000/api/status
```

`node` is needed only for the optional JavaScript syntax check. `/api/status` shows model loading/error/device, source connection or EOF, actual source and AI FPS, last model latencies, process/system CPU/RAM, and GPU/VRAM where available. If a model is missing, its error is exposed without substituting another classifier; pose is required for person observations. If a camera disconnects, capture retries. A failed timelapse is reported in the session instead of discarding event data. OpenCV may print an OpenH264 warning and fall back to another working MP4 encoder; verify playback on the target browser.

See [ARCHITECTURE.md](ARCHITECTURE.md), [MODEL_INTEGRATION.md](MODEL_INTEGRATION.md), and [MODEL_INSPECTION_REPORT.md](MODEL_INSPECTION_REPORT.md). The complete classroom/full-body behavioral validation awaits the user-provided prerecorded video; the included smoke clip is not a ground-truth classroom test.
