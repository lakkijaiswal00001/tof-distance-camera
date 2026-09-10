"""
core/gait_processor.py
======================
Kinematic metric extraction engine.

For each frame the processor receives pose landmarks and accumulates
data into a rolling buffer.  Once a complete walking cycle is detected
(two consecutive heel-strikes on the same side), it computes a full
set of GaitMetrics.

Extracted Metrics
-----------------
- Left / Right knee flexion angle (per frame → mean, min, max, ROM)
- Hip sway asymmetry  (lateral deviation from body midline)
- Stride duration     (time between heel-strikes on the same side)
- Stance phase ratio  (fraction of gait cycle where foot is near ground)
- Cadence             (steps per minute)

Offline-first: pure NumPy, no external dependencies.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import numpy as np

from .pose_estimator import PoseLandmarks, angle_between_three_points


# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

# Landmark indices
_L_HIP    = 23
_R_HIP    = 24
_L_KNEE   = 25
_R_KNEE   = 26
_L_ANKLE  = 27
_R_ANKLE  = 28
_L_HEEL   = 29
_R_HEEL   = 30
_L_FOOT   = 31
_R_FOOT   = 32
_L_SHLDR  = 11
_R_SHLDR  = 12

# Heel-strike detection: ankle Y must be within this threshold of the
# maximum Y seen (closest to ground in image coords where Y increases downward)
_HEEL_STRIKE_Y_THRESH = 0.04   # normalised units

# Minimum velocity sign-change gap (frames) to avoid double-counting
_MIN_STEP_FRAMES = 10

# Rolling buffer length (frames kept for metric computation)
_BUFFER_SIZE = 300   # ~10 s at 30 fps


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class FrameSnapshot:
    """Per-frame kinematic snapshot stored in the rolling buffer."""
    timestamp: float           # time.monotonic()
    left_knee_angle: float     # degrees
    right_knee_angle: float    # degrees
    left_ankle_y: float        # normalised Y (0-1)
    right_ankle_y: float       # normalised Y
    hip_midpoint_x: float      # normalised X of hip centre
    left_hip_x: float
    right_hip_x: float
    left_on_ground: bool       # estimated stance flag
    right_on_ground: bool


@dataclass
class StepEvent:
    """Records one heel-strike event."""
    side: str          # "left" | "right"
    frame_index: int
    timestamp: float


@dataclass
class GaitMetrics:
    """
    Aggregated kinematic metrics over one complete analysis window.

    All angles are in degrees.  Durations are in seconds.
    Asymmetry values are expressed as a percentage of the relevant span.
    """
    # ── Knee angles ──────────────────────────────────────────────────────────
    left_knee_mean:  float = 0.0
    left_knee_min:   float = 0.0
    left_knee_max:   float = 0.0
    left_knee_rom:   float = 0.0    # Range of Motion = max - min

    right_knee_mean: float = 0.0
    right_knee_min:  float = 0.0
    right_knee_max:  float = 0.0
    right_knee_rom:  float = 0.0

    knee_angle_asymmetry: float = 0.0   # |left_mean - right_mean|

    # ── Hip sway ─────────────────────────────────────────────────────────────
    hip_sway_asymmetry_pct: float = 0.0  # % of hip width span

    # ── Stride / cadence ────────────────────────────────────────────────────
    stride_duration_mean: float = 0.0    # seconds
    stride_duration_cv:   float = 0.0    # coefficient of variation (%)
    cadence_spm:          float = 0.0    # steps per minute

    # ── Stance phase ─────────────────────────────────────────────────────────
    left_stance_ratio:  float = 0.0      # fraction 0-1
    right_stance_ratio: float = 0.0

    # ── Upper-body fallback (when ankles/knees not visible) ─────────────
    uses_upper_body_fallback: bool = False
    shoulder_rom_mean: float = 0.0       # shoulder angle ROM when fallback active
    hip_twist_angle_mean: float = 0.0    # torso twist angle when fallback active

    # ── Sample count ─────────────────────────────────────────────────────────
    frame_count: int = 0
    step_count:  int = 0

    def is_valid(self) -> bool:
        """Return True if enough data was collected for a reliable assessment."""
        return self.frame_count >= 30 and self.step_count >= 2


# ──────────────────────────────────────────────────────────────────────────────
# GaitProcessor
# ──────────────────────────────────────────────────────────────────────────────

class GaitProcessor:
    """
    Stateful per-frame accumulator that computes GaitMetrics.

    Typical usage
    -------------
    ::

        processor = GaitProcessor()
        for frame in frames:
            pose = estimator.process(frame)
            if pose:
                processor.update(pose)

        metrics = processor.compute_metrics()
        processor.reset()

    Parameters
    ----------
    fps : float
        Camera / video FPS used to convert frame counts to durations.
    buffer_size : int
        Maximum number of frame snapshots retained (older ones are dropped).
    """

    def __init__(self, fps: float = 30.0, buffer_size: int = _BUFFER_SIZE) -> None:
        self.fps = max(fps, 1.0)
        self._buffer: Deque[FrameSnapshot] = deque(maxlen=buffer_size)
        self._step_events: List[StepEvent] = []
        self._frame_index = 0

        # Heel-strike detection state
        self._left_ankle_y_history:  Deque[float] = deque(maxlen=5)
        self._right_ankle_y_history: Deque[float] = deque(maxlen=5)
        self._last_left_strike_frame  = -_MIN_STEP_FRAMES
        self._last_right_strike_frame = -_MIN_STEP_FRAMES

        # For running real-time display
        self.latest_left_knee_angle:  float = 0.0
        self.latest_right_knee_angle: float = 0.0

    # ── Public API ────────────────────────────────────────────────────────────

    def update(self, pose: PoseLandmarks) -> None:
        """
        Ingest one frame's pose landmarks, update internal state.

        Call this once per frame during recording.
        """
        lm = pose.landmarks

        # ── Compute knee angles ───────────────────────────────────────────────
        left_knee_angle = angle_between_three_points(
            lm[_L_HIP], lm[_L_KNEE], lm[_L_ANKLE]
        )
        right_knee_angle = angle_between_three_points(
            lm[_R_HIP], lm[_R_KNEE], lm[_R_ANKLE]
        )

        self.latest_left_knee_angle  = left_knee_angle
        self.latest_right_knee_angle = right_knee_angle

        # ── Hip positions ─────────────────────────────────────────────────────
        l_hip_x = lm[_L_HIP].x
        r_hip_x = lm[_R_HIP].x
        hip_mid_x = (l_hip_x + r_hip_x) / 2.0

        # ── Ankle Y coords (ground proximity) ────────────────────────────────
        l_ankle_y = lm[_L_ANKLE].y
        r_ankle_y = lm[_R_ANKLE].y

        # ── Stance estimation (foot near ground → high Y in image) ───────────
        # We compute a running max for each ankle to find "ground level"
        self._left_ankle_y_history.append(l_ankle_y)
        self._right_ankle_y_history.append(r_ankle_y)

        ground_y_left  = max(self._left_ankle_y_history)
        ground_y_right = max(self._right_ankle_y_history)

        left_on_ground  = (ground_y_left  - l_ankle_y) < _HEEL_STRIKE_Y_THRESH
        right_on_ground = (ground_y_right - r_ankle_y) < _HEEL_STRIKE_Y_THRESH

        # ── Heel-strike detection (local Y minimum → velocity sign change) ────
        self._detect_heel_strike("left",  l_ankle_y, self._frame_index)
        self._detect_heel_strike("right", r_ankle_y, self._frame_index)

        # ── Store snapshot ────────────────────────────────────────────────────
        snapshot = FrameSnapshot(
            timestamp=time.monotonic(),
            left_knee_angle=left_knee_angle,
            right_knee_angle=right_knee_angle,
            left_ankle_y=l_ankle_y,
            right_ankle_y=r_ankle_y,
            hip_midpoint_x=hip_mid_x,
            left_hip_x=l_hip_x,
            right_hip_x=r_hip_x,
            left_on_ground=left_on_ground,
            right_on_ground=right_on_ground,
        )
        self._buffer.append(snapshot)
        self._frame_index += 1

    def compute_metrics(self) -> GaitMetrics:
        """
        Compute aggregated GaitMetrics from the accumulated buffer.

        Call this after recording completes (or at any point for live stats).
        """
        metrics = GaitMetrics()

        if len(self._buffer) < 10:
            return metrics

        buf = list(self._buffer)
        metrics.frame_count = len(buf)
        metrics.step_count  = len(self._step_events)

        # ── Knee angles ───────────────────────────────────────────────────────
        lka = np.array([s.left_knee_angle  for s in buf])
        rka = np.array([s.right_knee_angle for s in buf])

        metrics.left_knee_mean  = float(np.mean(lka))
        metrics.left_knee_min   = float(np.min(lka))
        metrics.left_knee_max   = float(np.max(lka))
        metrics.left_knee_rom   = metrics.left_knee_max - metrics.left_knee_min

        metrics.right_knee_mean  = float(np.mean(rka))
        metrics.right_knee_min   = float(np.min(rka))
        metrics.right_knee_max   = float(np.max(rka))
        metrics.right_knee_rom   = metrics.right_knee_max - metrics.right_knee_min

        metrics.knee_angle_asymmetry = abs(
            metrics.left_knee_mean - metrics.right_knee_mean
        )

        # ── Hip sway asymmetry ────────────────────────────────────────────────
        # Measure lateral deviation of each hip from body midline
        mid_xs = np.array([s.hip_midpoint_x for s in buf])
        l_hip_xs = np.array([s.left_hip_x  for s in buf])
        r_hip_xs = np.array([s.right_hip_x for s in buf])

        # Hip width span (normalised)
        hip_width = float(np.mean(np.abs(l_hip_xs - r_hip_xs)))
        if hip_width > 1e-6:
            left_dev  = float(np.std(l_hip_xs - mid_xs)) or 0.0
            right_dev = float(np.std(r_hip_xs - mid_xs)) or 0.0
            metrics.hip_sway_asymmetry_pct = float(
                abs(left_dev - right_dev) / hip_width * 100.0
            )
            # Guard against NaN
            if np.isnan(metrics.hip_sway_asymmetry_pct) or metrics.hip_sway_asymmetry_pct < 0:
                metrics.hip_sway_asymmetry_pct = 0.0
        else:
            metrics.hip_sway_asymmetry_pct = 0.0

        # ── Stance phase ratios ───────────────────────────────────────────────
        left_stance_frames  = sum(1 for s in buf if s.left_on_ground)
        right_stance_frames = sum(1 for s in buf if s.right_on_ground)
        metrics.left_stance_ratio  = left_stance_frames  / metrics.frame_count
        metrics.right_stance_ratio = right_stance_frames / metrics.frame_count

        # ── Stride duration (from heel-strike timestamps) ─────────────────────
        # Fixed: compute cadence from ALL heel strikes (both sides), not just one side
        all_strikes = sorted(
            [(e.timestamp, e.side) for e in self._step_events],
            key=lambda x: x[0]
        )

        step_intervals: List[float] = []
        for i in range(1, len(all_strikes)):
            step_intervals.append(all_strikes[i][0] - all_strikes[i - 1][0])

        if step_intervals:
            si = np.array(step_intervals)
            mean_step_interval = float(np.mean(si))
            metrics.cadence_spm = 60.0 / mean_step_interval if mean_step_interval > 0 else 0.0
            # Stride = 2 steps (left + right)
            metrics.stride_duration_mean = mean_step_interval * 2.0
            metrics.stride_duration_cv = (
                float(np.std(si) / mean_step_interval * 100.0)
                if mean_step_interval > 0 else 0.0
            )

        return metrics

    def reset(self) -> None:
        """Clear all accumulated data — call between sessions."""
        self._buffer.clear()
        self._step_events.clear()
        self._frame_index = 0
        self._left_ankle_y_history.clear()
        self._right_ankle_y_history.clear()
        self._last_left_strike_frame  = -_MIN_STEP_FRAMES
        self._last_right_strike_frame = -_MIN_STEP_FRAMES
        self.latest_left_knee_angle   = 0.0
        self.latest_right_knee_angle  = 0.0

    @property
    def frame_count(self) -> int:
        """Number of frames accumulated so far."""
        return self._frame_index

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _detect_heel_strike(
        self,
        side: str,
        ankle_y: float,
        frame_idx: int,
    ) -> None:
        """
        Detect a heel-strike (local maximum in ankle Y = foot closest to ground).

        We maintain a 3-frame window; a peak is detected when the middle
        value exceeds both neighbours — i.e. the foot was as close to ground
        as it gets before lifting off again.

        Fixed: use strict inequality to avoid triggering on flat plateaus
        (stationary subjects where ankle_y doesn't change).
        """
        history = (
            self._left_ankle_y_history
            if side == "left"
            else self._right_ankle_y_history
        )
        last_frame = (
            self._last_left_strike_frame
            if side == "left"
            else self._last_right_strike_frame
        )

        if len(history) < 3:
            return

        h = list(history)
        # Local maximum in Y (foot at lowest point / ground contact peak)
        # FIXED: use > on first check to avoid flat-plateau false positives
        if h[-2] > h[-3] and h[-2] >= h[-1]:
            if frame_idx - last_frame >= _MIN_STEP_FRAMES:
                event = StepEvent(
                    side=side,
                    frame_index=frame_idx,
                    timestamp=time.monotonic(),
                )
                self._step_events.append(event)
                if side == "left":
                    self._last_left_strike_frame = frame_idx
                else:
                    self._last_right_strike_frame = frame_idx

        # ── Prune old events to keep buffer windows aligned ─────────────────
        # Only keep events from the last 300 frames
        cutoff_frame = max(0, frame_idx - 300)
        self._step_events = [e for e in self._step_events if e.frame_index >= cutoff_frame]
