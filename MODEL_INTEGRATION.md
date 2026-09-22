# Model integration contracts

The supplied `NAZAR_Actions_MVP.zip` was inspected before implementation; see [MODEL_INSPECTION_REPORT.md](MODEL_INSPECTION_REPORT.md) for archive inventory, checkpoint metadata, and the reference runner. No checkpoint was retrained or replaced.

## Pose and tracking

`models/yolo11n-pose.pt` is called **once per AI frame** using Ultralytics `.track(persist=True, tracker="bytetrack.yaml", conf=0.35, imgsz=640)`. It returns one box and 17 COCO `(x,y,confidence)` keypoints per person. `0.35` is the visible-keypoint confidence cutoff. The application uses ByteTrack's source ID when present, plus a separate stable application track ID, and does not treat detection order as identity. Application track histories expire after 15 missed processed frames (the reference runner used 90). Video replay resets ByteTrack and application histories.

## Actions V4

`models/actions_v4_epoch_1.pt` loads strictly into `torchvision.models.mobilenet_v3_small(weights=None)` with its final classifier changed to `Linear(1024,2)`. Outputs are independent sigmoid probabilities in this exact order: `READING`, `WRITING`; both may coexist. Person crops are box-centered squares with side `max(width,height,16)`, replicated-border padding, OpenCV resize to `256×256` (`INTER_AREA`), BGR→RGB PIL, torchvision `Resize(256)`, `CenterCrop(224)`, `ToTensor`, and ImageNet normalization. Crops are batched and mapped back by track ID.

The implemented configurable thresholds **READING=0.39** and **WRITING=0.41** are the supplied V2 config's values used by the supplied reference runner with V4 weights. They are **not validated V4 thresholds** and were not tuned here. The V4 checkpoint independently stores metadata `threshold=0.5`; this is documented, not silently substituted for the two reference-runner defaults. EMA alpha is `0.25`, followed by 5 positive votes in 7 frames for each action independently.

## Head Direction V2

`models/headpose_v2_best.pt` uses the same MobileNetV3-Small two-output architecture and strict checkpoint loading. Raw outputs are `[pitch,yaw]`; multiply by checkpoint scales `[60,90]` to get degrees. Head crops use visible facial keypoints and the reference face/person-size rules, with replicated-border padding and the same `256→224` RGB/ImageNet transform. Yaw is classified before pitch: ≤−23° `LOOKING_LEFT`, ≥23° `LOOKING_RIGHT`; otherwise pitch ≥12° `LOOKING_UP`, ≤−14° `LOOKING_DOWN`; otherwise `LOOKING_FORWARD`. These are the supplied **prediction** thresholds, not its ground-truth label boundaries.

Head angles use EMA alpha `0.25` and a five-direction majority window. The production adapter exposes `UNKNOWN_HEAD` until at least three valid head samples. It does not issue a direction when fewer than two face keypoints are visible. Missing/invalid head evidence, disappeared tracks, and confirmed TURNED_BACK clear both direction votes and the angle EMA so stale directions cannot reappear.

## Geometry and observable states

Complete hip–knee–ankle legs with knee angle ≥155° provide STANDING pose candidates; 55–140° provides SITTING. The reference uses a 15-valid-frame shoulder baseline, seven-frame history, and four motion votes, but assumes initial sitting. NAZAR intentionally requires repeated visible geometry to confirm the initial state, including initial STANDING, rather than guessing sitting. If the necessary joints are not visible, posture can remain unknown. Hand raised means either visible wrist is more than 4% of person height above its shoulder, confirmed by the seven-frame vote history. TURNED_BACK uses weak face/eyes and strong shoulders, confirmed by five of seven frames, and suppresses head direction.

Public attributes are `SITTING`, `STANDING`, `HAND_RAISED`, `READING`, `WRITING`, `LOOKING_LEFT`, `LOOKING_RIGHT`, `LOOKING_UP`, `LOOKING_DOWN`, `LOOKING_FORWARD`, and `TURNED_BACK`. `UNKNOWN_HEAD` and unknown posture are exposed in track details but are not positive events. These are model/geometry observations, not verified intent or classroom performance.

## Devices and degradation

`NAZAR_DEVICE=auto` selects CUDA when PyTorch reports it available and CPU otherwise. CUDA inference uses float16 autocast for the two classifiers; CPU uses full precision. The RTX 5060 Laptop GPU was exercised with the supplied three checkpoints, and an explicit CPU path was exercised. A missing Actions or Head checkpoint leaves pose/tracking and the other model available and reports the error. A missing pose checkpoint reports an error and produces no person observations; no substitute AI model is used.
