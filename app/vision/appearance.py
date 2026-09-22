"""Anonymous torso appearance descriptor. Face region is intentionally excluded."""
import cv2
import numpy as np


def _clip(v, lo, hi):
    return max(lo, min(hi, int(round(v))))


def torso_descriptor(frame, bbox, keypoints=None):
    if frame is None or frame.size == 0:
        return None

    ih, iw = frame.shape[:2]
    x1, y1, x2, y2 = map(float, bbox)

    bw = max(1.0, x2-x1)
    bh = max(1.0, y2-y1)

    # Default: central upper body, deliberately excluding head/face.
    tx1 = x1 + 0.16*bw
    tx2 = x2 - 0.16*bw
    ty1 = y1 + 0.24*bh
    ty2 = y1 + 0.76*bh

    kp = np.asarray(keypoints) if keypoints is not None else None

    # COCO pose: shoulders 5,6 and hips 11,12.
    if kp is not None and kp.ndim == 2 and kp.shape[0] >= 13 and kp.shape[1] >= 3:
        ids = [5, 6, 11, 12]
        good = [i for i in ids if kp[i, 2] >= 0.35]

        if len(good) >= 3:
            xs = [float(kp[i, 0]) for i in good]
            ys = [float(kp[i, 1]) for i in good]

            kx1, kx2 = min(xs), max(xs)
            ky1, ky2 = min(ys), max(ys)

            kw = max(12.0, kx2-kx1)
            kh = max(12.0, ky2-ky1)

            tx1 = kx1 - 0.20*kw
            tx2 = kx2 + 0.20*kw
            ty1 = ky1 - 0.08*kh
            ty2 = ky2 + 0.12*kh

    ax1 = _clip(tx1, 0, iw-1)
    ay1 = _clip(ty1, 0, ih-1)
    ax2 = _clip(tx2, ax1+1, iw)
    ay2 = _clip(ty2, ay1+1, ih)

    crop = frame[ay1:ay2, ax1:ax2]

    if crop.shape[0] < 12 or crop.shape[1] < 12:
        return None

    crop = cv2.resize(crop, (64, 96), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)

    # Two torso zones preserve some white-shirt / dark-vest layout.
    parts = [
        hsv[:48],
        hsv[48:]
    ]

    features = []

    for part in parts:
        hs = cv2.calcHist(
            [part], [0, 1], None,
            [16, 4],
            [0, 180, 0, 256]
        ).reshape(-1)

        v = cv2.calcHist(
            [part], [2], None,
            [8], [0, 256]
        ).reshape(-1)

        hs /= max(float(hs.sum()), 1e-6)
        v /= max(float(v.sum()), 1e-6)

        # Hellinger transform makes histogram distance more stable.
        features.extend(np.sqrt(hs))
        features.extend(np.sqrt(v))

    descriptor = np.asarray(features, dtype=np.float32)

    norm = float(np.linalg.norm(descriptor))
    if norm < 1e-6:
        return None

    return descriptor / norm


def appearance_distance(a, b):
    if a is None or b is None:
        return None

    a = np.asarray(a, dtype=np.float32)
    b = np.asarray(b, dtype=np.float32)

    if a.shape != b.shape or a.size == 0:
        return None

    return float(np.clip(1.0 - np.dot(a, b), 0.0, 2.0))
