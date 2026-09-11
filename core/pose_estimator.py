"""
core/pose_estimator.py
======================
Lightweight, offline MediaPipe Pose wrapper.

Python 3.9 – 3.13 compatible. All MediaPipe TFLite model files are
bundled inside the ``mediapipe`` pip package — no internet connection
is required at runtime.

If the MediaPipe binaries are unavailable on the current Python build
(e.g. Python 3.13 before official support lands), the estimator
gracefully degrades to **mock mode**:
  - ``process()`` always returns None (no pose data)
  - ``draw_landmarks()`` is a safe no-op
  - A clear, human-readable warning is printed — no silent crash.
"""

from __future__ import annotations

import importlib
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import numpy as np

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Module-level dependency verification  (runs once at import time)
# ──────────────────────────────────────────────────────────────────────────────

def _verify_dependencies() -> dict:
    """
    Probe all required packages and print actionable warnings for any
    that are missing or broken — so the user never sees a cryptic
    AttributeError or ImportError with no guidance.

    Returns
    -------
    dict  {package_name: bool}  — True = importable and functional.
    """
    _checks = {
        "cv2":       ("cv2",       "pip install opencv-python>=4.8.0"),
        "numpy":     ("numpy",     "pip install numpy>=1.24.0"),
        "mediapipe": ("mediapipe", "pip install mediapipe>=0.10.0"),
        "sqlite3":   ("sqlite3",   "(stdlib — reinstall Python if missing)"),
    }
    status: dict = {}
    for key, (module, hint) in _checks.items():
        try:
            mod = importlib.import_module(module)
            # Touch a stable attribute to confirm the binary loaded correctly
            _ = (
                getattr(mod, "__version__", None)
                or getattr(mod, "sqlite_version", None)
                or True
            )
            status[key] = True
        except Exception as exc:
            msg = (
                f"[DEPENDENCY] {module} unavailable: {exc}\n"
                f"             Fix: {hint}"
            )
            log.warning(msg)
            print(f"\n[WARN] {msg}\n")
            status[key] = False
    return status


#: Populated at import time; importers may inspect this dict.
DEPENDENCY_STATUS: dict = _verify_dependencies()


# ──────────────────────────────────────────────────────────────────────────────
# OpenCV import (guarded — so the rest of the module still loads if absent)
# ──────────────────────────────────────────────────────────────────────────────

if DEPENDENCY_STATUS.get("cv2"):
    import cv2
else:
    cv2 = None  # type: ignore[assignment]


# ──────────────────────────────────────────────────────────────────────────────
# Mock fallbacks for missing MediaPipe sub-modules
# ──────────────────────────────────────────────────────────────────────────────

class _MockPoseSolutions:
    """
    Minimal no-op stand-in for ``mp.solutions.pose``.
    Returned when binaries are unavailable so the rest of the pipeline
    can import and partially run without raising AttributeError.
    """
    POSE_CONNECTIONS = frozenset()

    class Pose:
        def __init__(self, **_kwargs) -> None:
            pass

        def process(self, _frame):
            class _EmptyResult:
                pose_landmarks = None
            return _EmptyResult()

        def close(self) -> None:
            pass


class _MockDrawingUtils:
    """No-op stand-in for ``mp.solutions.drawing_utils``."""

    class DrawingSpec:
        def __init__(self, **_kw) -> None:
            pass

    @staticmethod
    def draw_landmarks(*_args, **_kwargs) -> None:
        pass


class _MockDrawingStyles:
    """No-op stand-in for ``mp.solutions.drawing_styles``."""
    pass


# ──────────────────────────────────────────────────────────────────────────────
# MediaPipe solutions resolver  (Python 3.9 – 3.13 compatible)
# ──────────────────────────────────────────────────────────────────────────────

def _resolve_mp_solutions() -> tuple:
    """
    Robustly resolve ``mp.solutions.pose``, ``drawing_utils``, and
    ``drawing_styles`` across MediaPipe 0.8 – 0.10+ and Python 3.9 – 3.13.

    Resolution order for every sub-module:
      1. ``mediapipe.solutions.<name>``         (standard public API)
      2. ``mediapipe.python.solutions.<name>``  (internal path, some builds)
      3. Mock fallback                          (never raises, logs warning)

    Returns
    -------
    tuple : (mp_pose, mp_drawing, mp_styles)
    """

    def _try(attr: str, internal_mod: str):
        """Try standard path, then internal path; return None on total failure."""
        # 1 — standard path via mediapipe.solutions
        try:
            import mediapipe as _mp
            if hasattr(_mp, "solutions"):
                obj = getattr(_mp.solutions, attr, None)
                if obj is not None:
                    return obj
        except Exception:
            pass
        # 2 — internal path (some MediaPipe builds on Python 3.12/3.13)
        try:
            return importlib.import_module(internal_mod)
        except Exception:
            pass
        return None

    # ── Pose solutions ────────────────────────────────────────────────────────
    mp_pose = _try("pose", "mediapipe.python.solutions.pose")
    if mp_pose is None or not hasattr(mp_pose, "Pose"):
        print(
            "\n[WARN] mediapipe.solutions.pose unavailable on this Python build.\n"
            "       Pose estimation will run in MOCK mode — no skeleton / angles.\n"
            "       Upgrade:  pip install --upgrade 'mediapipe>=0.10.0'\n"
        )
        mp_pose = _MockPoseSolutions()

    # ── Drawing utils ─────────────────────────────────────────────────────────
    mp_drawing = _try(
        "drawing_utils", "mediapipe.python.solutions.drawing_utils"
    )
    # Try additional fallback paths
    if mp_drawing is None:
        try:
            from mediapipe.solutions import drawing_utils as mp_drawing
        except Exception:
            pass

    if mp_drawing is None or not hasattr(mp_drawing, "draw_landmarks"):
        log.warning("mediapipe.drawing_utils unavailable — skeleton overlay disabled.")
        mp_drawing = _MockDrawingUtils()

    # ── Drawing styles ────────────────────────────────────────────────────────
    mp_styles = _try(
        "drawing_styles", "mediapipe.python.solutions.drawing_styles"
    )
    if mp_styles is None:
        mp_styles = _MockDrawingStyles()

    return mp_pose, mp_drawing, mp_styles


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class Point3D:
    """A single normalised landmark point with visibility confidence."""
    x: float           # 0.0 – 1.0 (normalised to frame width)
    y: float           # 0.0 – 1.0 (normalised to frame height)
    z: float           # Relative depth (negative = closer to camera)
    visibility: float  # 0.0 – 1.0


@dataclass
class PoseLandmarks:
    """
    Structured pose result for a single frame.

    Landmark indices follow the MediaPipe Pose convention:
      https://developers.google.com/mediapipe/solutions/vision/pose_landmarker

    Key indices used downstream:
      0  = nose
      11 = left shoulder,   12 = right shoulder
      23 = left hip,        24 = right hip
      25 = left knee,       26 = right knee
      27 = left ankle,      28 = right ankle
      29 = left heel,       30 = right heel
      31 = left foot index, 32 = right foot index
    """
    landmarks: List[Point3D]                          # 33 points
    raw: object = field(repr=False, default=None)     # raw MP result (for draw)

    def __len__(self) -> int:
        return len(self.landmarks)

    def __getitem__(self, idx: int) -> Point3D:
        return self.landmarks[idx]

    # ── Named accessors ───────────────────────────────────────────────────────

    @property
    def left_hip(self)       -> Point3D: return self.landmarks[23]
    @property
    def right_hip(self)      -> Point3D: return self.landmarks[24]
    @property
    def left_knee(self)      -> Point3D: return self.landmarks[25]
    @property
    def right_knee(self)     -> Point3D: return self.landmarks[26]
    @property
    def left_ankle(self)     -> Point3D: return self.landmarks[27]
    @property
    def right_ankle(self)    -> Point3D: return self.landmarks[28]
    @property
    def left_shoulder(self)  -> Point3D: return self.landmarks[11]
    @property
    def right_shoulder(self) -> Point3D: return self.landmarks[12]
    @property
    def nose(self)           -> Point3D: return self.landmarks[0]


# ──────────────────────────────────────────────────────────────────────────────
# PoseEstimator
# ──────────────────────────────────────────────────────────────────────────────

class PoseEstimator:
    """
    Wraps mediapipe.solutions.pose.Pose for frame-by-frame inference.

    Fully safe on Python 3.9 – 3.13.  If MediaPipe binaries are
    unavailable, the estimator silently falls back to mock mode:
    ``process()`` returns None on every frame, ``draw_landmarks()`` is
    a no-op.  A clear warning is printed at construction time.

    Parameters
    ----------
    model_complexity : int
        0 = Lite  (fastest, good for low-spec machines)
        1 = Full  (balanced — recommended default)
        2 = Heavy (most accurate, slowest)
    min_detection_confidence : float
        Minimum confidence for initial person detection (0.0 – 1.0).
    min_tracking_confidence : float
        Minimum confidence to keep tracking without re-detecting (0.0 – 1.0).
    smooth_landmarks : bool
        Apply temporal smoothing to reduce jitter (recommended True).
    """

    def __init__(
        self,
        model_complexity: int = 1,
        min_detection_confidence: float = 0.50,
        min_tracking_confidence: float = 0.40,
        smooth_landmarks: bool = True,
    ) -> None:
        # ── Resolve MediaPipe sub-modules — never raises ───────────────────────
        self._mp_pose, self._mp_drawing, self._mp_styles = _resolve_mp_solutions()

        # ── Detect mock mode ──────────────────────────────────────────────────
        self._is_mock: bool = isinstance(self._mp_pose, _MockPoseSolutions)

        # ── Initialise the Pose estimator ─────────────────────────────────────
        try:
            self._pose = self._mp_pose.Pose(
                static_image_mode=False,
                model_complexity=model_complexity,
                smooth_landmarks=smooth_landmarks,
                enable_segmentation=False,
                min_detection_confidence=min_detection_confidence,
                min_tracking_confidence=min_tracking_confidence,
            )
            if not self._is_mock:
                log.info(
                    "PoseEstimator ready  (complexity=%d, det=%.2f, track=%.2f)",
                    model_complexity,
                    min_detection_confidence,
                    min_tracking_confidence,
                )
        except Exception as exc:
            log.error("MediaPipe Pose.__init__ failed: %s", exc)
            print(
                f"\n[ERROR] MediaPipe Pose initialisation failed: {exc}\n"
                "        Falling back to mock mode — no real pose estimation.\n"
                "        Fix:  pip install --upgrade 'mediapipe>=0.10.0'\n"
            )
            self._pose = _MockPoseSolutions.Pose()
            self._is_mock = True

    # ── Context-manager support ───────────────────────────────────────────────

    def __enter__(self) -> "PoseEstimator":
        return self

    def __exit__(self, *_) -> None:
        self.close()

    def close(self) -> None:
        """Release MediaPipe resources (safe to call in any state)."""
        try:
            self._pose.close()
        except Exception:
            pass

    @property
    def is_mock(self) -> bool:
        """True if running in degraded mock mode (no real pose data)."""
        return self._is_mock

    # ── Core inference ────────────────────────────────────────────────────────

    def process(self, frame_bgr: np.ndarray) -> Optional[PoseLandmarks]:
        """
        Run pose estimation on a single BGR frame.

        Returns None if:
        - No pose is detected in the frame.
        - Running in mock/degraded mode.
        - An inference error occurred (warning is printed; never raises).
        """
        if self._is_mock or cv2 is None:
            return None

        try:
            frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            frame_rgb.flags.writeable = False   # perf: avoid unnecessary copy
            result = self._pose.process(frame_rgb)
            frame_rgb.flags.writeable = True
        except Exception as exc:
            log.warning("Pose inference error (frame skipped): %s", exc)
            return None

        if not result.pose_landmarks:
            return None

        lm_list: List[Point3D] = [
            Point3D(
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=lm.visibility,
            )
            for lm in result.pose_landmarks.landmark
        ]

        return PoseLandmarks(landmarks=lm_list, raw=result)

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def draw_landmarks(
        self,
        frame_bgr: np.ndarray,
        pose_landmarks: Optional[PoseLandmarks],
        draw_connections: bool = True,
    ) -> np.ndarray:
        """
        Draw the full body skeleton on *frame_bgr* (in-place).

        Silently skips if in mock mode, landmarks are None, or a
        rendering error occurs — never raises.
        Returns the frame (modified in-place, or unchanged on failure).
        """
        if (
            self._is_mock
            or cv2 is None
            or pose_landmarks is None
            or pose_landmarks.raw is None
        ):
            return frame_bgr

        try:
            connections = (
                self._mp_pose.POSE_CONNECTIONS if draw_connections else None
            )
            self._mp_drawing.draw_landmarks(
                frame_bgr,
                pose_landmarks.raw.pose_landmarks,
                connections,
                landmark_drawing_spec=self._mp_drawing.DrawingSpec(
                    color=(0, 255, 120), thickness=2, circle_radius=4
                ),
                connection_drawing_spec=self._mp_drawing.DrawingSpec(
                    color=(255, 255, 255), thickness=2
                ),
            )
        except Exception as exc:
            log.debug("Skeleton draw failed (non-critical): %s", exc)

        return frame_bgr

    def draw_joint_angle(
        self,
        frame: np.ndarray,
        angle: float,
        point: Point3D,
        label: str,
        frame_w: int,
        frame_h: int,
        color: Tuple[int, int, int] = (0, 255, 200),
    ) -> None:
        """Render a labelled angle badge near a joint landmark. Never raises."""
        if cv2 is None:
            return
        try:
            px = int(point.x * frame_w)
            py = int(point.y * frame_h)
            cv2.putText(
                frame,
                f"{label}: {angle:.1f}\u00b0",
                (px + 10, py),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                color,
                2,
                cv2.LINE_AA,
            )
        except Exception:
            pass   # Non-critical — skip silently


# ──────────────────────────────────────────────────────────────────────────────
# Geometry helpers (pure NumPy — used by GaitProcessor)
# ──────────────────────────────────────────────────────────────────────────────

def angle_between_three_points(
    a: Point3D,
    b: Point3D,
    c: Point3D,
) -> float:
    """
    Compute the interior angle at point *b* formed by vectors b→a and b→c.

    Uses only the (x, y) plane (2-D projection) — appropriate for both
    frontal and sagittal camera views.

    Returns
    -------
    float : angle in degrees (0 – 180).  Returns 0.0 on degenerate input.
    """
    vec_ba = np.array([a.x - b.x, a.y - b.y], dtype=np.float64)
    vec_bc = np.array([c.x - b.x, c.y - b.y], dtype=np.float64)

    norm_ba = np.linalg.norm(vec_ba)
    norm_bc = np.linalg.norm(vec_bc)

    if norm_ba < 1e-9 or norm_bc < 1e-9:
        return 0.0

    cos_theta = np.dot(vec_ba, vec_bc) / (norm_ba * norm_bc)
    cos_theta = float(np.clip(cos_theta, -1.0, 1.0))   # numerical safety
    return float(np.degrees(np.arccos(cos_theta)))
