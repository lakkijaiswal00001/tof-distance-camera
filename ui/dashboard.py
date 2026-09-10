"""
ui/dashboard.py
===============
OpenCV-based real-time HUD and session history viewer.

Components
----------
- Live skeleton overlay (drawn by PoseEstimator)
- Floating metric panel: current knee angles, hip sway, step count
- Alignment guide: colour-coded bounding box + status message
- Recording countdown timer
- End-of-session risk summary screen (full-frame overlay)
- Session history table viewer (terminal + OpenCV window)

Design principles:
  - All rendering is pure OpenCV — no GUI framework required.
  - Colours follow a consistent medical-grade palette.
  - All text uses cv2.FONT_HERSHEY_DUPLEX for legibility.
"""

from __future__ import annotations

import textwrap
from typing import List, Optional

import cv2
import numpy as np

from core.camera       import AlignmentFeedback, ValidationStatus
from core.gait_processor import GaitMetrics
from core.oa_classifier  import RiskAssessment, RiskLevel
from core.database       import SessionRecord


# ──────────────────────────────────────────────────────────────────────────────
# Colour Palette (BGR)
# ──────────────────────────────────────────────────────────────────────────────

_CLR_BG         = (20, 20, 30)       # dark navy panel background
_CLR_ACCENT     = (0, 220, 180)      # teal accent
_CLR_TEXT       = (230, 230, 235)    # near-white text
_CLR_DIM        = (120, 120, 130)    # muted label text
_CLR_READY      = (0, 210, 80)       # green — valid alignment
_CLR_WARN       = (0, 180, 240)      # amber (as BGR)
_CLR_DANGER     = (30, 40, 220)      # red — high risk / bad alignment
_CLR_MODERATE   = (0, 165, 255)      # orange
_CLR_RECORDING  = (0, 40, 200)       # red dot indicator

_FONT       = cv2.FONT_HERSHEY_DUPLEX
_FONT_SMALL = cv2.FONT_HERSHEY_SIMPLEX


def _risk_color(level: RiskLevel):
    return {
        RiskLevel.LOW:      _CLR_READY,
        RiskLevel.MODERATE: _CLR_MODERATE,
        RiskLevel.HIGH:     _CLR_DANGER,
    }[level]


# ──────────────────────────────────────────────────────────────────────────────
# GaitDashboard
# ──────────────────────────────────────────────────────────────────────────────

class GaitDashboard:
    """
    Manages all OpenCV HUD rendering for the gait screening pipeline.

    Parameters
    ----------
    window_name : str
        OpenCV named window title.
    panel_width : int
        Width of the right-side metric panel in pixels.
    """

    WINDOW = "OA Gait Analysis — Early Detection System"

    def __init__(self, window_name: str = WINDOW, panel_width: int = 320) -> None:
        self._win   = window_name
        self._pw    = panel_width
        cv2.namedWindow(self._win, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(self._win, 1280, 720)

    # ── Alignment phase ───────────────────────────────────────────────────────

    def render_alignment(
        self,
        frame: np.ndarray,
        feedback: AlignmentFeedback,
        countdown: Optional[int] = None,
    ) -> np.ndarray:
        """
        Draw alignment guidance overlay on *frame* and return the composite.

        Parameters
        ----------
        frame : BGR frame from camera.
        feedback : AlignmentFeedback from AlignmentValidator.
        countdown : Seconds remaining in pre-recording countdown (or None).
        """
        out = frame.copy()
        h, w = out.shape[:2]

        # ── Status colour ────────────────────────────────────────────────────
        st = feedback.status
        if st == ValidationStatus.READY:
            border_color = _CLR_READY
        elif st == ValidationStatus.NO_PERSON:
            border_color = _CLR_DIM
        else:
            border_color = _CLR_WARN

        # ── Guide bounding box ───────────────────────────────────────────────
        # Draw a target zone rectangle (centre 60% of width, 85% of height)
        gx1 = int(w * 0.20); gy1 = int(h * 0.05)
        gx2 = int(w * 0.80); gy2 = int(h * 0.95)
        cv2.rectangle(out, (gx1, gy1), (gx2, gy2), border_color, 2)

        # Corner accent lines
        corner_len = 30
        for cx, cy, dx, dy in [
            (gx1, gy1, +1, +1), (gx2, gy1, -1, +1),
            (gx1, gy2, +1, -1), (gx2, gy2, -1, -1),
        ]:
            cv2.line(out, (cx, cy), (cx + dx * corner_len, cy), border_color, 3)
            cv2.line(out, (cx, cy), (cx, cy + dy * corner_len), border_color, 3)

        # ── Subject bounding box (if detected) ───────────────────────────────
        if feedback.bbox:
            bx, by, bw, bh = feedback.bbox
            px1 = int(bx * w); py1 = int(by * h)
            px2 = int((bx + bw) * w); py2 = int((by + bh) * h)
            cv2.rectangle(out, (px1, py1), (px2, py2), _CLR_ACCENT, 1)

        # ── Semi-transparent header bar ───────────────────────────────────────
        overlay = out.copy()
        cv2.rectangle(overlay, (0, 0), (w, 60), _CLR_BG, -1)
        cv2.addWeighted(overlay, 0.75, out, 0.25, 0, out)

        cv2.putText(out, "OA GAIT SCREENING", (16, 38),
                    _FONT, 0.85, _CLR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(out, "ALIGNMENT CHECK", (w - 260, 38),
                    _FONT, 0.7, _CLR_DIM, 1, cv2.LINE_AA)

        # ── Status message bar ────────────────────────────────────────────────
        overlay2 = out.copy()
        cv2.rectangle(overlay2, (0, h - 70), (w, h), _CLR_BG, -1)
        cv2.addWeighted(overlay2, 0.80, out, 0.20, 0, out)

        cv2.putText(out, feedback.message, (20, h - 35),
                    _FONT, 0.72, border_color, 2, cv2.LINE_AA)

        # ── Countdown overlay ────────────────────────────────────────────────
        if countdown is not None and st == ValidationStatus.READY:
            text = str(countdown)
            ts   = cv2.getTextSize(text, _FONT, 4.5, 6)[0]
            tx   = (w - ts[0]) // 2
            ty   = (h + ts[1]) // 2
            cv2.putText(out, text, (tx + 2, ty + 2),
                        _FONT, 4.5, (0, 0, 0), 10, cv2.LINE_AA)
            cv2.putText(out, text, (tx, ty),
                        _FONT, 4.5, _CLR_READY, 6, cv2.LINE_AA)

        return out

    # ── Live recording HUD ────────────────────────────────────────────────────

    def render_live(
        self,
        frame: np.ndarray,
        left_knee:  float,
        right_knee: float,
        hip_sway:   float,
        step_count: int,
        elapsed:    float,
        cadence:    float = 0.0,
    ) -> np.ndarray:
        """
        Draw the live metric panel alongside the camera feed.

        Returns a horizontally concatenated frame (cam | panel).
        """
        h, w = frame.shape[:2]

        # ── Right-side metric panel ───────────────────────────────────────────
        panel = np.full((h, self._pw, 3), _CLR_BG, dtype=np.uint8)

        def _label(text: str, y: int, color=_CLR_DIM, scale=0.55) -> None:
            cv2.putText(panel, text, (14, y), _FONT_SMALL, scale, color,
                        1, cv2.LINE_AA)

        def _value(text: str, y: int, color=_CLR_TEXT, scale=0.9) -> None:
            cv2.putText(panel, text, (14, y), _FONT, scale, color,
                        2, cv2.LINE_AA)

        def _divider(y: int) -> None:
            cv2.line(panel, (10, y), (self._pw - 10, y), (50, 50, 60), 1)

        # Title
        cv2.putText(panel, "LIVE METRICS", (14, 38), _FONT, 0.72,
                    _CLR_ACCENT, 2, cv2.LINE_AA)
        _divider(50)

        # Recording indicator
        rec_y = 80
        cv2.circle(panel, (self._pw - 28, rec_y - 7), 8, _CLR_RECORDING, -1)
        cv2.putText(panel, "REC", (self._pw - 70, rec_y),
                    _FONT_SMALL, 0.55, _CLR_RECORDING, 1, cv2.LINE_AA)
        _label(f"  {int(elapsed // 60):02d}:{int(elapsed % 60):02d}", rec_y,
               _CLR_TEXT, 0.65)

        _divider(95)

        # Knee angles
        _label("KNEE FLEXION", 125)

        lk_col = _CLR_READY if 50 < left_knee < 170 else _CLR_WARN
        rk_col = _CLR_READY if 50 < right_knee < 170 else _CLR_WARN

        _label("Left", 155, _CLR_DIM, 0.50)
        _value(f"{left_knee:5.1f} deg", 155, lk_col, 0.80)

        _label("Right", 190, _CLR_DIM, 0.50)
        _value(f"{right_knee:5.1f} deg", 190, rk_col, 0.80)

        asym = abs(left_knee - right_knee)
        asym_col = _CLR_READY if asym < 8 else _CLR_WARN
        _label("Asymmetry", 225, _CLR_DIM, 0.50)
        _value(f"{asym:5.1f} deg", 225, asym_col, 0.80)

        _divider(245)

        # Hip sway
        _label("HIP SWAY", 275)
        hs_col = _CLR_READY if hip_sway < 15 else _CLR_WARN
        _value(f"{hip_sway:5.1f} %", 305, hs_col, 0.80)

        _divider(325)

        # Cadence / steps
        _label("CADENCE", 355)
        _value(f"{cadence:5.0f} spm", 385, _CLR_TEXT, 0.80)

        _label("STEPS", 420)
        _value(str(step_count), 450, _CLR_ACCENT, 1.1)

        _divider(470)

        # Control hint
        _label("Press [Q] to end session", h - 20, _CLR_DIM, 0.48)

        # Vertical separator on frame
        cv2.line(frame, (w - 2, 0), (w - 2, h), _CLR_ACCENT, 2)

        return np.hstack([frame, panel])

    # ── End-of-session summary ────────────────────────────────────────────────

    def render_summary(
        self,
        frame: np.ndarray,
        metrics: GaitMetrics,
        assessment: RiskAssessment,
        session_id: int,
    ) -> np.ndarray:
        """
        Render a full-frame end-of-session risk summary overlay.

        The caller should display this frame and wait for a keypress.
        """
        h, w = frame.shape[:2]
        overlay = np.full((h, w + self._pw, 3), _CLR_BG, dtype=np.uint8)

        risk_col = _risk_color(assessment.level)

        # ── Header ────────────────────────────────────────────────────────────
        cv2.putText(overlay, "SCREENING COMPLETE", (40, 60),
                    _FONT, 1.1, _CLR_ACCENT, 2, cv2.LINE_AA)
        cv2.putText(overlay, f"Session #{session_id}", (40, 95),
                    _FONT_SMALL, 0.60, _CLR_DIM, 1, cv2.LINE_AA)
        cv2.line(overlay, (40, 108), (w + self._pw - 40, 108), (50, 55, 70), 1)

        # ── Risk badge ────────────────────────────────────────────────────────
        badge_x, badge_y = 40, 130
        badge_w = w + self._pw - 80
        cv2.rectangle(overlay, (badge_x, badge_y),
                      (badge_x + badge_w, badge_y + 70), risk_col, -1)
        cv2.rectangle(overlay, (badge_x, badge_y),
                      (badge_x + badge_w, badge_y + 70), (255, 255, 255), 1)

        badge_text = assessment.level.value.upper()
        ts = cv2.getTextSize(badge_text, _FONT, 1.0, 2)[0]
        bx = badge_x + (badge_w - ts[0]) // 2
        cv2.putText(overlay, badge_text, (bx, badge_y + 47),
                    _FONT, 1.0, _CLR_BG, 2, cv2.LINE_AA)

        # Score
        score_text = f"Risk Score: {assessment.score}"
        cv2.putText(overlay, score_text, (badge_x + badge_w // 2 - 60, badge_y + 95),
                    _FONT_SMALL, 0.65, risk_col, 2, cv2.LINE_AA)

        # ── Metrics table ─────────────────────────────────────────────────────
        col_w = (w + self._pw - 80) // 2
        rows = [
            ("Left Knee ROM",      f"{metrics.left_knee_rom:.1f}°",  55, 75),
            ("Right Knee ROM",     f"{metrics.right_knee_rom:.1f}°", 55, 75),
            ("Knee Asymmetry",     f"{metrics.knee_angle_asymmetry:.1f}°",  0, 8),
            ("Hip Sway Asym.",     f"{metrics.hip_sway_asymmetry_pct:.1f}%", 0, 15),
            ("Stride Timing CV",   f"{metrics.stride_duration_cv:.1f}%",    0, 3),
            ("L Stance Ratio",     f"{metrics.left_stance_ratio*100:.1f}%", 60, 65),
            ("R Stance Ratio",     f"{metrics.right_stance_ratio*100:.1f}%",60, 65),
            ("Cadence",            f"{metrics.cadence_spm:.0f} spm", 90, 130),
        ]

        table_y = 230
        for i, (label, val, lo, hi) in enumerate(rows):
            col = i % 2
            row = i // 2
            rx = 40 + col * col_w
            ry = table_y + row * 52

            # Determine if flagged
            try:
                num = float(val.split()[0].rstrip("°%"))
                flagged = not (lo <= num <= hi) if lo < hi else False
            except Exception:
                flagged = False

            val_col = _CLR_DANGER if flagged else _CLR_READY
            cv2.putText(overlay, label, (rx, ry),
                        _FONT_SMALL, 0.55, _CLR_DIM, 1, cv2.LINE_AA)
            cv2.putText(overlay, val, (rx, ry + 28),
                        _FONT, 0.82, val_col, 2, cv2.LINE_AA)

        # ── Flagged markers ───────────────────────────────────────────────────
        flag_y = table_y + (len(rows) // 2) * 52 + 30
        cv2.line(overlay, (40, flag_y), (w + self._pw - 40, flag_y), (50, 55, 70), 1)
        flag_y += 24

        if assessment.flagged_markers:
            cv2.putText(overlay, "FLAGGED OA MARKERS:", (40, flag_y),
                        _FONT_SMALL, 0.60, _CLR_WARN, 1, cv2.LINE_AA)
            flag_y += 24
            for m in assessment.flagged_markers[:4]:   # max 4 lines
                cv2.putText(overlay, f"  • {m.name}: {m.value:.1f}{m.unit}",
                            (40, flag_y), _FONT_SMALL, 0.52, _CLR_WARN,
                            1, cv2.LINE_AA)
                flag_y += 22
        else:
            cv2.putText(overlay, "No OA risk markers flagged.",
                        (40, flag_y), _FONT_SMALL, 0.60, _CLR_READY,
                        1, cv2.LINE_AA)
            flag_y += 24

        # ── Summary text ──────────────────────────────────────────────────────
        flag_y += 10
        cv2.line(overlay, (40, flag_y), (w + self._pw - 40, flag_y), (50, 55, 70), 1)
        flag_y += 20
        wrapped = textwrap.wrap(assessment.summary, width=90)
        for line in wrapped[:3]:
            cv2.putText(overlay, line, (40, flag_y),
                        _FONT_SMALL, 0.50, _CLR_TEXT, 1, cv2.LINE_AA)
            flag_y += 20

        # ── Footer ────────────────────────────────────────────────────────────
        cv2.putText(overlay, "For informational use only. Not a clinical diagnosis.",
                    (40, h - 40), _FONT_SMALL, 0.48, _CLR_DIM, 1, cv2.LINE_AA)
        cv2.putText(overlay, "Press any key to continue...",
                    (40, h - 18), _FONT_SMALL, 0.52, _CLR_ACCENT, 1, cv2.LINE_AA)

        return overlay

    # ── History viewer ────────────────────────────────────────────────────────

    def render_history(self, records: List[SessionRecord]) -> None:
        """
        Display a tabular session history in both terminal and OpenCV window.
        Press Q or ESC to exit history view.
        """
        if not records:
            print("\n  No sessions recorded yet.\n")
            return

        # Terminal table
        print("\n" + "─" * 100)
        print(f"  {'ID':>4}  {'Timestamp':26}  {'Risk Level':35}  "
              f"{'Score':>5}  {'Steps':>5}  {'Cadence':>9}")
        print("─" * 100)
        for r in records:
            ts = r.timestamp[:19].replace("T", " ")
            cad = f"{r.cadence_spm:.0f} spm" if r.cadence_spm else "  N/A"
            print(f"  {r.id:>4}  {ts:26}  {r.risk_level:35}  "
                  f"{r.risk_score:>5}  {r.step_count:>5}  {cad:>9}")
        print("─" * 100 + "\n")

        # OpenCV window table
        row_h = 36
        total_h = max(720, 80 + row_h * (len(records) + 1))
        canvas = np.full((total_h, 1280, 3), _CLR_BG, dtype=np.uint8)

        cv2.putText(canvas, "SESSION HISTORY", (20, 45),
                    _FONT, 1.0, _CLR_ACCENT, 2, cv2.LINE_AA)
        cv2.line(canvas, (20, 58), (1260, 58), (50, 55, 70), 1)

        headers = ["ID", "Timestamp", "Risk Level", "Score", "Steps", "Cadence (spm)"]
        col_xs  = [20, 80, 280, 570, 660, 740]

        for col, (hdr, cx) in enumerate(zip(headers, col_xs)):
            cv2.putText(canvas, hdr, (cx, 88), _FONT_SMALL, 0.60,
                        _CLR_DIM, 1, cv2.LINE_AA)

        for i, r in enumerate(records):
            y = 88 + row_h * (i + 1)
            bg_color = (28, 28, 38) if i % 2 == 0 else (35, 35, 48)
            cv2.rectangle(canvas, (20, y - 22), (1260, y + 8), bg_color, -1)

            risk_col = (
                _CLR_READY    if "Low"  in r.risk_level else
                _CLR_MODERATE if "Mod"  in r.risk_level else
                _CLR_DANGER
            )
            ts = r.timestamp[:19].replace("T", " ")
            cad = f"{r.cadence_spm:.0f}" if r.cadence_spm else "N/A"

            values = [str(r.id), ts, r.risk_level, str(r.risk_score),
                      str(r.step_count), cad]
            colors = [_CLR_TEXT, _CLR_TEXT, risk_col, risk_col, _CLR_TEXT, _CLR_TEXT]

            for val, cx, col in zip(values, col_xs, colors):
                cv2.putText(canvas, val, (cx, y), _FONT_SMALL, 0.58,
                            col, 1, cv2.LINE_AA)

        cv2.putText(canvas, "Press Q or ESC to exit",
                    (20, total_h - 14), _FONT_SMALL, 0.52, _CLR_DIM, 1, cv2.LINE_AA)

        cv2.imshow(self._win, canvas)
        while True:
            k = cv2.waitKey(50) & 0xFF
            if k in (ord("q"), ord("Q"), 27):
                break

    # ── Window helpers ────────────────────────────────────────────────────────

    def show(self, frame: np.ndarray) -> None:
        """Display *frame* in the managed window."""
        cv2.imshow(self._win, frame)

    def wait_key(self, ms: int = 1) -> int:
        """cv2.waitKey wrapper — returns the key code."""
        return cv2.waitKey(ms) & 0xFF

    def close(self) -> None:
        """Destroy the OpenCV window."""
        cv2.destroyWindow(self._win)
