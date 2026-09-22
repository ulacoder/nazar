from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class Detection:
    bbox: tuple[float, float, float, float]
    keypoints: np.ndarray
    confidence: float
    source_id: Optional[int] = None
    appearance: Optional[np.ndarray] = None

@dataclass
class Track:
    track_id: int
    bbox: tuple[float, float, float, float]
    keypoints: np.ndarray
    confidence: float
    last_seen: float
    missed: int = 0
    source_id: Optional[int] = None
    reassociated: bool = False
