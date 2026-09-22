# Architecture

## Production data path

`CameraSource` or `VideoFileSource` → one `VisionPipeline.process(frame, timestamp)` call → YOLO11n pose/ByteTrack once → stable application track IDs → per-ID geometry and batched person/head crops → Actions and Head models → per-ID temporal multi-label state → `EventEngine` → `SessionManager` → SQLite. `scripts/validate_video.py` decodes every file frame and calls this same pipeline and session manager; it has no alternate model implementation. Its annotation uses the same `draw_overlay` helper as the live stream.

The live source worker captures or decodes independently of the AI worker. The AI worker consumes the latest frame, so it cannot block capture but can skip frames when inference is slower than playback. Video timestamps come from OpenCV's media position, with frame-index/FPS fallback when the container omits or repeats time. Starting a video session closes and restarts its source at frame zero and clears the pose tracker and per-ID temporal histories. End-of-file clears visible tracks; the final source frame remains available for a still preview. `CAMERA` does not replay.

`TrackManager` retains application IDs across detection reordering, using the model's tracker IDs when present and spatial matching otherwise. Crops and predictions are assembled with parallel track-ID arrays and attached by ID, never by raw detection-list position. Each track owns its body/hand/turned-back/action/head history. Missing or invalid face evidence, a missed track, expiration, or TURNED_BACK clears stale head state. A new standing person requires repeated full-leg pose evidence rather than being initialized as sitting.

`EventEngine` requires continuous confirmation for `event_min_duration` and applies per-track/type cooldown. It processes independently coexisting attributes—e.g., WRITING plus LOOKING_DOWN—without forcing one label. Events are recorded only within an active LESSON or EXAM session. Sessions, events, settings, optional teacher/class/subject/notes metadata, visibility samples, anonymous session-local track IDs, and timelapse metadata use `Store` (`data/nazar.sqlite3`, schema version 4). Events carry an exact video `source_offset_s` plus a session-relative `session_offset_s` and a separate run audit `occurred_at`. Visibility samples are stored about once per source-second while a session is active; old sessions have no such history. Timelapse sampling is an independent worker and performs no AI inference. A recording failure leaves events and session persistence intact.

## Project map

| Location | Responsibility |
|---|---|
| `models/` | Supplied checkpoints and configs; no retraining. |
| `app/vision/models.py` | Strict checkpoint adapters, preprocessing entry points, device selection. |
| `app/vision/crops.py`, `geometry.py`, `temporal.py`, `tracker.py` | Crop fidelity, keypoint rules, temporal state, stable identity. |
| `app/pipeline.py` | Single pose pass and per-ID model association. |
| `app/camera.py`, `video.py` | Interchangeable latest-frame input sources. |
| `app/runtime.py` | AI/source threads, source switching, live state and streams. |
| `app/events.py`, `sessions.py`, `storage/database.py` | Event confirmation, session lifecycle, SQLite. |
| `app/timelapse.py`, `overlay.py` | Independent MP4 recording and shared annotation. |
| `app/server.py`, `templates/`, `static/`, `serve.py` | Local HTTP API and functional dashboard. |
| `scripts/validate_video.py` | Every-frame offline validation with annotated MP4 and JSON/SQLite evidence. |
| `tests/` | Contracts, reordering, failure, video source/replay, session/API tests. |

## HTTP API

`GET /api/health`, `/api/state`, `/api/status`, `/api/live` (server-sent events), `/stream` (MJPEG), `/api/settings`, `/api/sessions`, `/api/sessions/<id>`, `/api/sessions/<id>/events`, `/api/sessions/<id>/analytics`, `/api/events`, `/api/timelapse/<id>`; `POST /api/session/start`, `/api/session/stop`, `/api/settings`. The optional session-start JSON fields `teacher`, `class_name`, `subject`, `notes` are validated and stored only on the session. Global `/api/analytics` was removed: the analytics endpoint queries observations with the requested session ID only. Its counts represent confirmed event occurrences; it explicitly returns null for durations because event end times were not persisted. The dashboard uses only these local routes. `/api/health` distinguishes a normal video EOF (`source_ended`) from camera availability; model errors and worker errors are separately visible. `/api/timelapse/<id>` serves only saved files within the configured sessions directory.

The dashboard's global Events view remains a filterable log, while Sessions → a selected session provides Overview, Events, Analytics, and Timelapse tabs. Metadata labels are localized in English, Kazakh, and Russian; entered values are not translated. Recent teacher/class/subject suggestions live in that browser's localStorage. Approximate event-to-timelapse seeking uses the capture interval and output FPS recorded at session start; dropped captures or old sessions without timing metadata cannot be aligned exactly. Neither opening the page nor viewing historical analytics reruns inference.

The application binds to `127.0.0.1:8000` using Flask's development server; it has no authentication or remote deployment configuration. The current design stores temporary track IDs, observations/events, and video/timelapse paths, not identities. The input video and generated output remain local. This is an observational prototype, not a grading, discipline, identity-recognition, or medical system.

