"""
core/camera.py
==============
Camera interface and pre-recording alignment validator.

Responsibilities:
  - Open and release webcam or video file via OpenCV.
  - Before recording begins, analyse each frame to determine if the
    subject is correctly positioned (full body visible, within the
    optimal distance zone, horizontally centred).
  - Emit a ValidationStatus so the caller / UI can show guidance.

Offline-first: no network calls; relies solely on OpenCV + landmark
geometry provided by the pose estimator.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Tuple

import cv2
import numpy as np

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# Custom exception
# ──────────────────────────────────────────────────────────────────────────────

class CameraError(RuntimeError):
    """
    Raised when a camera/video source cannot be opened after exhausting
    all retry attempts.  The message includes a user-friendly diagnosis
    and suggested fix so it is safe to display directly to end users.
    """


# ──────────────────────────────────────────────────────────────────────────────
# Enums & Data Classes
# ──────────────────────────────────────────────────────────────────────────────

class ValidationStatus(Enum):
    """Possible outcomes of a pre-recording alignment check."""
    NO_PERSON    = auto()   # No pose detected in frame
    TOO_CLOSE    = auto()   # Subject too close to camera
    TOO_FAR      = auto()   # Subject too far from camera
    OFF_CENTER   = auto()   # Subject not horizontally centred
    PARTIAL_BODY = auto()   # Ankles or head not fully visible
    READY        = auto()   # Good position — safe to start recording


@dataclass
class AlignmentFeedback:
    """Rich result returned by AlignmentValidator.check()."""
    status: ValidationStatus
    message: str
    # Normalised [0,1] bounding box of detected person (or None)
    bbox: Optional[Tuple[float, float, float, float]] = None
    # Estimated distance tier: "close" | "ok" | "far" | None
    distance_tier: Optional[str] = None


# ──────────────────────────────────────────────────────────────────────────────
# AlignmentValidator
# ──────────────────────────────────────────────────────────────────────────────

class AlignmentValidator:
    """
    Analyses pose landmarks to determine whether the subject is
    correctly framed before recording begins.

    Parameters
    ----------
    centre_tolerance : float
        Maximum allowed horizontal offset of body mid-point from frame
        centre, expressed as a fraction of frame width (default 0.15).
    min_body_fraction : float
        Minimum fraction of frame height the detected body should span
        (default 0.55).  Bodies spanning less are considered TOO_FAR.
    max_body_fraction : float
        Maximum fraction of frame height the body may span before being
        classified as TOO_CLOSE (default 0.92).
    required_stable_frames : int
        Number of consecutive READY frames needed before emitting READY
        (debouncing jitter — default 10).
    """

    # Landmark indices used for bounding-box estimation
    _HEAD_IDX   = 0   # nose
    _L_ANKLE    = 27
    _R_ANKLE    = 28
    _L_HIP      = 23
    _R_HIP      = 24
    _L_SHOULDER = 11
    _R_SHOULDER = 12

    def __init__(
        self,
        centre_tolerance: float = 0.18,
        min_body_fraction: float = 0.55,
        max_body_fraction: float = 0.92,
        required_stable_frames: int = 10,
    ) -> None:
        self.centre_tolerance = centre_tolerance
        self.min_body_fraction = min_body_fraction
        self.max_body_fraction = max_body_fraction
        self.required_stable_frames = required_stable_frames
        self._stable_count = 0

    def check(self, landmarks) -> AlignmentFeedback:
        """
        Evaluate pose landmarks and return an AlignmentFeedback.

        Parameters
        ----------
        landmarks :
            mediapipe NormalizedLandmarkList or None (when no pose detected).

        Returns
        -------
        AlignmentFeedback
        """
        if landmarks is None:
            self._stable_count = 0
            return AlignmentFeedback(
                status=ValidationStatus.NO_PERSON,
                message="No person detected. Please step into the frame.",
            )

        lm = landmarks.landmark

        # ── Extract key points (normalised 0-1 coords) ──────────────────────
        nose      = lm[self._HEAD_IDX]
        l_ankle   = lm[self._L_ANKLE]
        r_ankle   = lm[self._R_ANKLE]
        l_hip     = lm[self._L_HIP]
        r_hip     = lm[self._R_HIP]
        l_sho     = lm[self._L_SHOULDER]
        r_sho     = lm[self._R_SHOULDER]

        # Visibility gate: key landmarks must be sufficiently visible
        critical = [nose, l_ankle, r_ankle, l_hip, r_hip]
        if any(pt.visibility < 0.4 for pt in critical):
            self._stable_count = 0
            return AlignmentFeedback(
                status=ValidationStatus.PARTIAL_BODY,
                message="Ensure your full body (head to feet) is visible.",
            )

        # ── Bounding box in normalised coords ────────────────────────────────
        xs = [p.x for p in lm]
        ys = [p.y for p in lm]
        x_min, x_max = min(xs), max(xs)
        y_min, y_max = min(ys), max(ys)
        bbox = (x_min, y_min, x_max - x_min, y_max - y_min)

        body_height_frac = y_max - y_min
        body_centre_x    = (x_min + x_max) / 2.0

        # ── Distance check (via body-height fraction) ────────────────────────
        if body_height_frac > self.max_body_fraction:
            self._stable_count = 0
            return AlignmentFeedback(
                status=ValidationStatus.TOO_CLOSE,
                message="Too close! Please step back from the camera.",
                bbox=bbox,
                distance_tier="close",
            )

        if body_height_frac < self.min_body_fraction:
            self._stable_count = 0
            return AlignmentFeedback(
                status=ValidationStatus.TOO_FAR,
                message="Too far! Please step closer to the camera.",
                bbox=bbox,
                distance_tier="far",
            )

        # ── Horizontal centring check ────────────────────────────────────────
        offset = abs(body_centre_x - 0.5)
        if offset > self.centre_tolerance:
            direction = "left" if body_centre_x < 0.5 else "right"
            self._stable_count = 0
            return AlignmentFeedback(
                status=ValidationStatus.OFF_CENTER,
                message=f"Move slightly to the {direction} to centre yourself.",
                bbox=bbox,
                distance_tier="ok",
            )

        # ── All checks passed — require N consecutive frames ─────────────────
        self._stable_count += 1
        if self._stable_count >= self.required_stable_frames:
            return AlignmentFeedback(
                status=ValidationStatus.READY,
                message="Great position! Recording will start now.",
                bbox=bbox,
                distance_tier="ok",
            )

        remaining = self.required_stable_frames - self._stable_count
        return AlignmentFeedback(
            status=ValidationStatus.OFF_CENTER,   # re-use as "almost ready"
            message=f"Hold still… ({remaining} frames to stabilise)",
            bbox=bbox,
            distance_tier="ok",
        )

    def reset(self) -> None:
        """Reset the stable-frame debounce counter."""
        self._stable_count = 0


# ──────────────────────────────────────────────────────────────────────────────
# CameraInterface
# ──────────────────────────────────────────────────────────────────────────────

class CameraInterface:
    """
    Hardened wrapper around cv2.VideoCapture supporting live webcams
    and pre-recorded video files.

    Key improvements over a bare VideoCapture call:
    - Retries on transient device failures (e.g. briefly busy USB bus).
    - Falls back to a lower resolution if the requested one is refused.
    - Provides open_safe() which returns (bool, error_msg) instead of raising.
    - read() guards against sudden device disconnection during a session.
    - All failures emit clear, actionable user-facing messages.

    Usage
    -----
    ::

        # Preferred — context manager auto-releases on exit:
        with CameraInterface(source=0) as cam:
            while cam.is_open():
                ok, frame = cam.read()
                if not ok:
                    break

        # Without context manager:
        cam = CameraInterface(source=0)
        success, err = cam.open_safe()
        if not success:
            print(err)
        else:
            ok, frame = cam.read()
            cam.release()

    Parameters
    ----------
    source : int | str
        Webcam device index (int) or path to a video file (str).
    width, height : int
        Requested capture resolution.  Actual resolution may differ if
        the camera does not support it; a fallback resolution is tried.
    fps : int
        Requested capture frame rate (ignored for video files).
    open_retries : int
        Number of additional open attempts after the first failure.
        Each retry waits 0.5 s before retrying (default 2 extra attempts).
    """

    # Fallback resolution tried if the requested one is refused
    _FALLBACK_W = 640
    _FALLBACK_H = 480

    def __init__(
        self,
        source: int | str = 0,
        width:  int = 1280,
        height: int = 720,
        fps:    int = 30,
        open_retries: int = 2,
    ) -> None:
        self.source       = source
        self._width       = width
        self._height      = height
        self._fps         = fps
        self._open_retries = max(0, open_retries)
        self._cap: Optional[cv2.VideoCapture] = None

    # ── Context-manager support ───────────────────────────────────────────────

    def __enter__(self) -> "CameraInterface":
        self.open()   # raises CameraError on failure
        return self

    def __exit__(self, *_) -> None:
        self.release()

    # ── Public API ────────────────────────────────────────────────────────────

    def open(self) -> None:
        """
        Open the capture device or video file.

        Raises
        ------
        CameraError
            If the device/file cannot be opened after all retry attempts.
        """
        success, error_msg = self.open_safe()
        if not success:
            raise CameraError(error_msg)

    def open_safe(self) -> Tuple[bool, str]:
        """
        Try to open the capture source without raising an exception.

        Returns
        -------
        (True, "")         on success.
        (False, error_msg) on failure — *error_msg* is human-readable.
        """
        is_file = isinstance(self.source, str)

        for attempt in range(1 + self._open_retries):
            try:
                cap = cv2.VideoCapture(self.source)
            except Exception as exc:
                log.warning("VideoCapture() raised on attempt %d: %s", attempt + 1, exc)
                cap = None

            if cap is not None and cap.isOpened():
                if not is_file:
                    self._apply_camera_props(cap)
                self._cap = cap
                log.info(
                    "Camera opened: source=%r  %dx%d @ %.0ffps",
                    self.source,
                    self.actual_width,
                    self.actual_height,
                    self.actual_fps,
                )
                return True, ""

            # Clean up a half-opened capture before retrying
            if cap is not None:
                cap.release()

            if attempt < self._open_retries:
                log.warning(
                    "Camera source %r not ready (attempt %d/%d) — retrying in 0.5 s …",
                    self.source, attempt + 1, 1 + self._open_retries,
                )
                time.sleep(0.5)

        # ── All attempts exhausted — build informative message ─────────────────
        if is_file:
            from pathlib import Path
            p = Path(str(self.source))
            if not p.exists():
                msg = (
                    f"Video file not found: {self.source!r}\n"
                    "       Check the path and try again."
                )
            else:
                msg = (
                    f"Cannot open video file: {self.source!r}\n"
                    "       The file may be corrupt or an unsupported codec.\n"
                    "       Try: pip install opencv-python (includes most codecs)."
                )
        else:
            msg = (
                f"Cannot open webcam (index {self.source}).\n"
                "  Possible causes:\n"
                "    • The camera index is wrong — try --camera 0 or --camera 1\n"
                "    • Another app (Teams, Zoom, OBS…) is using the camera\n"
                "    • The webcam driver is not installed\n"
                "    • USB connection is loose or the camera is unplugged"
            )

        log.error("CameraInterface.open_safe: %s", msg)
        print(f"\n[CAMERA ERROR] {msg}\n")
        return False, msg

    def release(self) -> None:
        """Release the capture device and free resources."""
        if self._cap is not None:
            try:
                if self._cap.isOpened():
                    self._cap.release()
            except Exception as exc:
                log.debug("release() error (ignored): %s", exc)
            finally:
                self._cap = None

    def is_open(self) -> bool:
        """Return True if the capture device is open and readable."""
        return self._cap is not None and self._cap.isOpened()

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read the next frame.

        Returns
        -------
        (success, frame) — frame is a BGR numpy array, or None on failure.
        Handles sudden camera disconnection gracefully (returns False, None).
        """
        if not self.is_open():
            return False, None
        try:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                log.debug("Camera read returned no frame (device disconnected?).")
                return False, None
            return True, frame
        except Exception as exc:
            log.warning("Camera read error: %s", exc)
            return False, None

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def actual_width(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))  if self._cap else 0

    @property
    def actual_height(self) -> int:
        return int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) if self._cap else 0

    @property
    def actual_fps(self) -> float:
        fps = self._cap.get(cv2.CAP_PROP_FPS) if self._cap else 0.0
        # Some cameras report 0 or unrealistic values — clamp sensibly
        return fps if 1.0 <= fps <= 300.0 else 30.0

    @property
    def total_frames(self) -> int:
        """Total frame count (meaningful for video files; 0 for webcams)."""
        if self._cap:
            return int(self._cap.get(cv2.CAP_PROP_FRAME_COUNT))
        return 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _apply_camera_props(self, cap: cv2.VideoCapture) -> None:
        """
        Apply resolution and FPS hints to a live webcam VideoCapture.
        Falls back to a lower resolution if the requested one is refused.
        """
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        cap.set(cv2.CAP_PROP_FPS,          self._fps)

        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        # If the camera silently rejected our resolution, try the fallback
        if (actual_w != self._width or actual_h != self._height) and (
            self._width > self._FALLBACK_W
        ):
            log.info(
                "Requested %dx%d refused by camera (got %dx%d). "
                "Retrying at fallback %dx%d.",
                self._width, self._height,
                actual_w, actual_h,
                self._FALLBACK_W, self._FALLBACK_H,
            )
            print(
                f"[INFO] Camera does not support {self._width}x{self._height}. "
                f"Falling back to {self._FALLBACK_W}x{self._FALLBACK_H}."
            )
            cap.set(cv2.CAP_PROP_FRAME_WIDTH,  self._FALLBACK_W)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._FALLBACK_H)
