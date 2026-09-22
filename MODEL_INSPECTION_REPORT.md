# NAZAR Actions MVP — Model Inspection Report

Inspected 20 September 2026. Source: `C:\Users\Abik\Desktop\NAZAR_Actions_MVP.zip` (SHA-256 `8BFFAFBF8BAE09EB2580F0D151DF1BB813C231D83084EE3FB58831D13E5D047E`). This report describes the supplied files and the behavior of `run_nazar_actions_mvp.py`. The application was implemented after this inspection; see `ARCHITECTURE.md` and `MODEL_INTEGRATION.md` for actual production behavior and deliberate safety differences.

## Complete package inventory

| File | Role |
|---|---|
| `run_nazar_actions_mvp.py` | Authoritative offline video reference, 2,100+ lines. |
| `yolo11n-pose.pt` | Ultralytics YOLO11n pose checkpoint; COCO 17-keypoint output. |
| `runs/actions_v4_multiperson/epoch_1.pt` | Trained Actions V4 checkpoint, epoch 1. |
| `runs/actions_v2_hardneg/config.json` | Action output names and thresholds used by the runner; named for V2. |
| `runs/headpose_v2_balanced/best.pt` | Trained Head Direction V2 checkpoint, epoch 4. |
| `runs/headpose_v2_balanced/head_direction_config.json` | Head direction categories, thresholds, test metrics. |
| `requirements.txt` | Unpinned `torch`, `torchvision`, `ultralytics`, `opencv-python`, `numpy`, `pillow`. |

The archive has no training scripts, sample video, model-specific V4 Actions config, event engine, web application, or tests.

## Exact model contract

**Pose.** The runner calls `YOLO(yolo11n-pose.pt).track(frame, persist=True, tracker="bytetrack.yaml", conf=0.35, imgsz=640, device=0, verbose=False)` once per frame. It reuses `result.boxes.xyxy`, `result.boxes.id`, and `result.keypoints.data` downstream. Keypoint confidence cutoff is `0.35`. The inference result has 17 keypoints with `(x, y, confidence)` per person. If ByteTrack supplies no IDs, the runner falls back to detection-order IDs `1..N`; these fallback IDs are not stable.

**Actions.** `torchvision.models.mobilenet_v3_small(weights=None)` with the final classifier layer replaced by `Linear(1024, 2)`. The V4 checkpoint's `model_state_dict` loads strictly into this architecture. Output order is `READING`, `WRITING`, confirmed by both config and checkpoint `class_names`. Apply independent sigmoid to both logits: this is multi-label, so both may be true. The runner uses `READING >= 0.39`, `WRITING >= 0.41` from the V2 config. Its V4 checkpoint separately records `threshold: 0.5`, with no per-class V4 thresholds. This pairing is an unresolved provenance/calibration issue; the V2 config's F1 values cannot be attributed to the V4 checkpoint. The checkpoint records `macro_f1=0.6894006130`; the V2 config claims `macro_f1=0.7048` and separate class metrics.

**Head Direction.** The same MobileNetV3-Small architecture with `Linear(1024, 2)` loads the head checkpoint strictly. Outputs are raw `[pitch, yaw]`; there is no sigmoid or tanh in the runner. Multiply pitch by checkpoint `pitch_scale=60.0`, yaw by `yaw_scale=90.0` to obtain degrees. Classification checks yaw first: `yaw <= -23` → `HEAD_LEFT`, `yaw >= 23` → `HEAD_RIGHT`; otherwise `pitch >= 12` → `HEAD_UP`, `pitch <= -14` → `HEAD_DOWN`; otherwise `HEAD_FORWARD`. The config distinguishes these prediction thresholds from ground-truth category boundaries (`yaw ±25`, pitch up `15`, down `-15`). It claims test accuracy `0.9568`, macro F1 `0.8723`; these metrics were not reproduced during inspection.

## Image preparation and crops

Both classifiers receive BGR camera crops converted to RGB PIL images, then `Resize(256)`, `CenterCrop(224)`, `ToTensor()` and ImageNet normalization (mean `[0.485, 0.456, 0.406]`, standard deviation `[0.229, 0.224, 0.225]`). Their crops are first resized by OpenCV to `256×256` with `INTER_AREA`; the transform center-crops this square to `224×224`.

The person crop is a square centered on the bounding box, side `max(box width, box height, 16)`. The head crop uses visible face keypoints 0–4 (confidence `>=0.35`) if at least two exist. Its side is `max(2.25×face width, 3×face height, 0.40×person width, 0.20×person height)`, capped at `0.42×person height`; face width has a `0.18×person width` floor and face height a `0.08×person height` floor. Center X is median face X; center Y is mean face Y shifted upward by `0.04×side`. With fewer than two face points, it uses side `max(0.58×person width, 0.28×person height)`, also capped at `0.42×person height`, centered at person midpoint X and `box top + 0.16×person height`. Both square crops use replicated border pixels when outside the frame.

The runner batches person crops and head crops separately, keeps parallel track-ID arrays, and attaches each batch output back to its track ID. It uses `torch.no_grad()` and CUDA float16 autocast.

## Geometry and temporal logic

**Body:** For either complete hip–knee–ankle leg (keypoint confidence `>=0.35`), median knee angle `>=155°` is a pose `STANDING` candidate; `55–140°` is `SITTING`. Final body state uses a per-track fixed-camera shoulder-height baseline over 15 valid frames. The initial state is assumed `SITTING` after this internal baseline; no visible user calibration is requested. A `STANDING` candidate needs shoulder rise `>=0.12×baseline person height`, person-height ratio `>=1.06`, visible hip and knee, and a pose `STANDING` candidate. A return to `SITTING` needs absolute rise `<=0.07` and height ratio `0.85–1.15`. Final motion history is 7 samples with 4 votes. Confirmed sitting slowly adapts baseline by 2%. This initial-sitting assumption can mislabel a person who enters standing.

**Hand raised:** Each visible shoulder/wrist pair is raised if wrist Y is above shoulder Y by more than `0.04×person height`. Either side gives a single `HAND_RAISED` boolean. History length is 7; mean `>=0.5` confirms. The supplied code does not output left/right/both-hand states.

**Turned back:** Mean confidence of face keypoints 0–4 `<0.30`, eyes 1–2 `<0.30`, and shoulders 5–6 `>0.80`. Confirmed at 5 true votes in 7 frames. It suppresses head direction and clears direction history, but the runner does not reset its head-angle EMA.

**Actions:** Independent per-track EMA of `[READING, WRITING]` probabilities with alpha `0.25`; independent thresholding followed by 5 positive votes within 7 samples. Thus both actions can be active at once.

**Head:** Per-track EMA of angle pair with alpha `0.25`; classify yaw before pitch; majority vote over the last 5 directions. Before 3 samples, the runner returns the latest raw direction rather than `UNKNOWN`. A new track starts with `HEAD_UNKNOWN` until it has a model result.

**Tracking expiry:** Per-track histories are removed after 90 processed frames without a matching track. `POSE_HISTORY=7` mode produces final body label. The reference writes one CSV row per visible track per frame and an annotated video; it does not create session events.

## Phase 1 runtime verification

On this machine: Python 3.14, PyTorch `2.11.0+cu128`, torchvision `0.26.0+cu128`, Ultralytics `8.4.150`, OpenCV `5.0.0`; CUDA is available on the NVIDIA GeForce RTX 5060 Laptop GPU. Both classifier checkpoints loaded with `strict=True`, produced finite `(1,2)` CUDA outputs on a synthetic tensor, and YOLO loaded and ran on a blank `640×480` frame, returning an empty `(0,17,3)` keypoint tensor. The blank-frame YOLO first-pass took about 358 ms, including initialization; this is not steady-state performance or behavioral validation.

## Integration decisions before the main build

1. Preserve the exact architecture, crop, normalization, scaling, output order, and reference temporal behavior in isolated, testable model adapters. Keep the V2-config/V4-checkpoint threshold provenance visible in configuration and diagnostics; do not present V2 validation scores as V4 results.
2. Use a stable tracker ID from ByteTrack. If the tracker returns no ID, do not use detection-order numbers as persistent identities.
3. Use `UNKNOWN_HEAD` when face evidence is insufficient or turned back, and clear stale head EMA on that transition. Test the behavior against the runner and document intentional safety fixes.
4. Provide CPU fallback and conditional CUDA autocast; the offline runner explicitly aborts without CUDA, while the intended application must run on CPU.
5. Keep the 15-frame body baseline, but do not copy the initial-sitting assumption: require repeated visible sitting or standing geometry. Classroom-video validation is still needed before relying on body events.
6. Map reference outputs to public observable names (`LOOKING_*`, `HAND_RAISED`, etc.) without introducing unsupported learned classes or judgments.

## Implementation plan after Phase 1

1. Build model adapters and parity tests for crop pixels, transforms, checkpoint loading, batching, output scaling, and track-ID association. Add short video smoke tests and measure steady-state GPU/CPU latency.
2. Build independent latest-frame camera capture and AI workers. Run pose once per AI frame, then apply tracking, geometry, Actions, Head Direction, and per-track temporal state.
3. Add a separate event engine with duration/confidence/cooldown rules, then Lesson/Exam sessions, SQLite persistence, and an independent timelapse worker.
4. Add local APIs, real-time state updates, real diagnostics, and the requested screenshot-inspired UI for Live, Sessions, Events, Analytics, System, and Settings.
5. Verify multi-person detection reordering, track expiry, no-camera/model degradation, session lifecycle, recording, CUDA inference, CPU fallback, and real webcam behavior. Document measured outcomes and remaining limitations.
