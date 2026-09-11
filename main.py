"""
main.py
=======
OA Gait Analysis & Video Screening Module — Entry Point

Orchestrates the full pipeline:
  Camera → AlignmentValidator → PoseEstimator → GaitProcessor
  → OARiskClassifier → DatabaseManager → GaitDashboard

Modes
-----
  screen   Live webcam screening session (default)
  file     Analyse a pre-recorded video file
  history  Browse past screening sessions

Usage
-----
  # Live webcam (default camera):
  python main.py

  # Specify a webcam index:
  python main.py --mode screen --camera 1

  # Analyse a video file:
  python main.py --mode file --input walk.mp4

  # Browse history:
  python main.py --mode history

  # Low-spec machines (MediaPipe Lite model):
  python main.py --model-complexity 0

Offline-first: no internet connection required after pip install.
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

# ── Package imports ───────────────────────────────────────────────────────────
from core.camera         import CameraInterface, CameraError, AlignmentValidator, ValidationStatus
from core.pose_estimator import PoseEstimator
from core.gait_processor import GaitProcessor
from core.oa_classifier  import OARiskClassifier
from core.database       import DatabaseManager
from ui.dashboard        import GaitDashboard
from core.video_utils    import get_or_create_sample_video, validate_video_file

# Enable structured logging to console so all [WARN]/[ERROR] messages surface
logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s  [%(name)s]  %(message)s",
)



# ──────────────────────────────────────────────────────────────────────────────
# Configuration defaults
# ──────────────────────────────────────────────────────────────────────────────

_DEFAULT_CAMERA          = 0
_DEFAULT_WIDTH           = 1280
_DEFAULT_HEIGHT          = 720
_DEFAULT_FPS             = 30
_DEFAULT_MODEL_COMPLEXITY = 1         # 0=Lite, 1=Full, 2=Heavy
_COUNTDOWN_SECONDS       = 3          # seconds before recording starts
_MIN_RECORD_SECONDS      = 5          # minimum to consider a valid session
_MAX_RECORD_SECONDS      = 60         # safety auto-stop


# ──────────────────────────────────────────────────────────────────────────────
# Pipeline orchestrator
# ──────────────────────────────────────────────────────────────────────────────

class OAScreeningPipeline:
    """
    Manages a complete end-to-end gait screening session.

    Parameters
    ----------
    camera_source : int | str
        Webcam index or path to a video file.
    model_complexity : int
        MediaPipe model complexity (0, 1, or 2).
    db_path : Path | None
        Override path for the SQLite database.
    """

    def __init__(
        self,
        camera_source: int | str = _DEFAULT_CAMERA,
        model_complexity: int    = _DEFAULT_MODEL_COMPLEXITY,
        db_path: Optional[Path]  = None,
    ) -> None:
        self.source           = camera_source
        self.model_complexity = model_complexity

        # Instantiate all components
        # Note: Camera is initialized lazily (on-demand) to avoid errors on headless systems
        self.camera     = None  # Will be created in run_screen() or run_file()
        self.estimator  = PoseEstimator(model_complexity=model_complexity)
        self.processor  = GaitProcessor(fps=float(_DEFAULT_FPS))
        self.validator  = AlignmentValidator()
        self.classifier = OARiskClassifier()
        self.db         = DatabaseManager(db_path=db_path)
        self.dashboard  = GaitDashboard()

    # ── Main entry points ─────────────────────────────────────────────────────

    def run_screen(self) -> None:
        """Run a live webcam screening session."""
        # Initialize camera on demand
        self.camera = CameraInterface(
            source=self.source,
            width=_DEFAULT_WIDTH,
            height=_DEFAULT_HEIGHT,
            fps=_DEFAULT_FPS,
        )
        self._run_session(mode="webcam")

    def run_file(self, path: str) -> tuple:
        """
        Run analysis on a pre-recorded video file.

        If the file doesn't exist, attempts to create a dummy video for testing.

        Returns
        -------
        tuple
            (GaitMetrics, duration_seconds)
        """
        video_path = Path(path)

        # If file doesn't exist, try to create a dummy video
        if not video_path.exists():
            print(f"[WARN] Video file not found: {path}")
            print("[INFO] Attempting to create a dummy video for testing...")

            dummy_path = get_or_create_sample_video(str(path))
            if dummy_path is None:
                print(f"[ERROR] Failed to create dummy video at {path}")
                print("[ERROR] Cannot proceed without a video file.")
                return self.processor.compute_metrics(), 0.0

            path = dummy_path

        # Validate the video file
        is_valid, validation_msg = validate_video_file(path)
        if not is_valid:
            print(f"[ERROR] {validation_msg}")
            return self.processor.compute_metrics(), 0.0

        self.camera = CameraInterface(source=path)
        return self._run_session(mode="file", skip_alignment=True)

    def run_history(self) -> None:
        """Display the session history browser."""
        records = self.db.get_all_sessions(limit=50)
        count   = self.db.get_session_count()
        print(f"\n  Total sessions in database: {count}")
        self.dashboard.render_history(records)
        self.dashboard.close()

    # ── Session state machine ─────────────────────────────────────────────────

    def _run_session(self, mode: str, skip_alignment: bool = False) -> tuple:
        """
        Internal session loop.

        Phase 1 (Alignment): show guidance until READY (skipped for file mode).
        Phase 2 (Countdown): 3-second countdown before recording.
        Phase 3 (Recording): collect landmarks, update HUD.
        Phase 4 (Analysis):  compute metrics, classify, save, show summary.

        Returns
        -------
        tuple
            (GaitMetrics, duration_seconds)
        """
        print(f"\n  [OA Gait Analysis]  Mode: {mode.upper()}")
        print("  Controls: [Q] quit session  [S] skip alignment")
        print("  ─" * 28)

        # ── Open camera with graceful failure handling ─────────────────────────
        success, error_msg = self.camera.open_safe()
        if not success:
            print(f"\n  {error_msg}")
            print("  Cannot start session.")
            self.dashboard.close()
            # Return empty metrics and 0 duration on error
            return self.processor.compute_metrics(), 0.0

        try:
            print(f"  Camera opened: {self.camera.actual_width}×"
                  f"{self.camera.actual_height} @ {self.camera.actual_fps:.0f}fps\n")

            # ── Phase 1: Alignment ─────────────────────────────────────────────
            if not skip_alignment:
                aligned = self._alignment_phase()
                if not aligned:
                    print("  Session cancelled during alignment.")
                    return self.processor.compute_metrics(), 0.0

            # ── Phase 2: Countdown ────────────────────────────────────────────
            if not skip_alignment:
                cancelled = self._countdown_phase()
                if cancelled:
                    print("  Session cancelled during countdown.")
                    return self.processor.compute_metrics(), 0.0

            # ── Phase 3: Recording ────────────────────────────────────────────
            metrics, duration = self._recording_phase(mode)

            if duration < _MIN_RECORD_SECONDS and mode == "webcam":
                print(
                    f"  [WARN] Recording too short ({duration:.1f}s). "
                    "Walk for at least 5 seconds for a valid assessment."
                )

            # ── Phase 4: Analysis & Summary ───────────────────────────────────
            assessment = self.classifier.classify(metrics)
            session_id = self.db.save_session(
                metrics, assessment,
                mode=mode,
                duration_seconds=duration,
            )

            if session_id == -1:
                print("  [WARN] Session could not be saved to the database.")
            else:
                print(f"\n  Session #{session_id} saved.")

            print(f"  Risk Level : {assessment.level.value}")
            print(f"  Risk Score : {assessment.score}")
            print(f"  Summary    : {assessment.summary}\n")

            # Display summary (skip graphical display in headless mode)
            if self.dashboard._headless:
                print("[INFO] Running in headless mode. Skipping graphical summary display.")
            else:
                try:
                    # Build a blank canvas for summary (camera is still open but not used)
                    _, frame = self.camera.read()
                    if frame is None:
                        frame_h = _DEFAULT_HEIGHT
                        frame_w = _DEFAULT_WIDTH
                        frame = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)

                    summary_frame = self.dashboard.render_summary(
                        frame, metrics, assessment, session_id if session_id != -1 else 0
                    )
                    self.dashboard.show(summary_frame)
                    print("  Displaying summary — press any key to exit.")
                    cv2.waitKey(0)
                except Exception as e:
                    print(f"[WARN] Failed to display summary: {e}")

        finally:
            self.camera.release()
            self.dashboard.close()
            self.estimator.close()

        # Return metrics and duration on success
        return metrics, duration

    # ── Phase helpers ─────────────────────────────────────────────────────────

    def _alignment_phase(self) -> bool:
        """
        Show alignment guidance until READY or user quits/skips.
        Returns True if aligned, False if cancelled.
        """
        self.validator.reset()
        print("  [Phase 1/3] Alignment check — step into frame…")

        while True:
            ok, frame = self.camera.read()
            if not ok:
                return False

            pose = self.estimator.process(frame)
            self.estimator.draw_landmarks(frame, pose) if pose else None

            feedback = self.validator.check(
                pose.raw.pose_landmarks if pose else None
            )

            out = self.dashboard.render_alignment(frame, feedback)
            self.dashboard.show(out)

            key = self.dashboard.wait_key(1)
            if key in (ord("q"), ord("Q"), 27):
                return False
            if key in (ord("s"), ord("S")):
                print("  Alignment skipped by user.")
                return True
            if feedback.status == ValidationStatus.READY:
                print("  Alignment confirmed. Starting countdown…")
                return True

    def _countdown_phase(self) -> bool:
        """
        3-second countdown with live preview.
        Returns True if cancelled.
        """
        print(f"  [Phase 2/3] Countdown ({_COUNTDOWN_SECONDS}s)…")
        start = time.monotonic()

        while True:
            ok, frame = self.camera.read()
            if not ok:
                return True

            pose = self.estimator.process(frame)
            self.estimator.draw_landmarks(frame, pose) if pose else None

            feedback = self.validator.check(
                pose.raw.pose_landmarks if pose else None
            )
            elapsed  = time.monotonic() - start
            remaining = max(0, _COUNTDOWN_SECONDS - int(elapsed))

            out = self.dashboard.render_alignment(
                frame, feedback, countdown=remaining
            )
            self.dashboard.show(out)

            key = self.dashboard.wait_key(1)
            if key in (ord("q"), ord("Q"), 27):
                return True

            if elapsed >= _COUNTDOWN_SECONDS:
                print("  Recording started. Walk naturally across the frame.")
                return False

    def _recording_phase(self, mode: str) -> tuple:
        """
        Record and process frames until Q is pressed or timeout.
        Returns (GaitMetrics, duration_seconds).
        """
        print(f"  [Phase 3/3] Recording… (press Q to stop, max {_MAX_RECORD_SECONDS}s)")
        self.processor.reset()

        actual_fps = self.camera.actual_fps or float(_DEFAULT_FPS)
        self.processor.fps = actual_fps

        start_time = time.monotonic()
        poses_detected = 0
        frames_processed = 0

        while True:
            ok, frame = self.camera.read()
            if not ok:
                break

            frames_processed += 1
            elapsed = time.monotonic() - start_time

            # Auto-stop
            if elapsed >= _MAX_RECORD_SECONDS:
                print(f"  Auto-stopped after {_MAX_RECORD_SECONDS}s.")
                break

            pose = self.estimator.process(frame)
            if pose:
                poses_detected += 1
                self.processor.update(pose)
                self.estimator.draw_landmarks(frame, pose)

            # Compute real live metrics (not fabricated)
            live_metrics = self.processor.compute_metrics()

            # Live HUD
            live = self.dashboard.render_live(
                frame=frame,
                left_knee=self.processor.latest_left_knee_angle,
                right_knee=self.processor.latest_right_knee_angle,
                hip_sway=live_metrics.hip_sway_asymmetry_pct,
                step_count=len(self.processor._step_events),  # real step count
                elapsed=elapsed,
                cadence=live_metrics.cadence_spm,
            )
            self.dashboard.show(live)

            key = self.dashboard.wait_key(1)
            if key in (ord("q"), ord("Q"), 27):
                print(f"  Recording stopped at {elapsed:.1f}s.")
                break

        duration = time.monotonic() - start_time
        metrics  = self.processor.compute_metrics()

        # Log detection statistics
        detection_rate = (poses_detected / frames_processed * 100) if frames_processed > 0 else 0
        print(f"\n  Detection Stats:")
        print(f"    - Frames processed: {frames_processed}")
        print(f"    - Poses detected: {poses_detected}")
        print(f"    - Detection rate: {detection_rate:.1f}%")
        print(f"    - Cadence: {metrics.cadence_spm:.1f} steps/min")
        print(f"    - L Knee ROM: {metrics.left_knee_rom:.1f}°")
        print(f"    - R Knee ROM: {metrics.right_knee_rom:.1f}°\n")

        if poses_detected == 0:
            print("  [WARN] No poses detected during recording!")
            print("  [WARN] Check camera/video quality and lighting.")

        return metrics, duration


# ──────────────────────────────────────────────────────────────────────────────
# CLI
# ──────────────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oa_gait",
        description=(
            "OA Gait Analysis — Offline Early Osteoarthritis Screening System\n"
            "─────────────────────────────────────────────────────────────────\n"
            "Runs entirely offline. Results are saved to a local SQLite database.\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--mode", "-m",
        choices=["screen", "file", "history"],
        default="file",
        help=(
            "file    = analyse a video file (default)\n"
            "screen  = live webcam session\n"
            "history = browse past sessions"
        ),
    )
    parser.add_argument(
        "--camera", "-c",
        type=int,
        default=_DEFAULT_CAMERA,
        metavar="INDEX",
        help="Webcam device index (default: 0).",
    )
    parser.add_argument(
        "--input", "-i",
        type=str,
        default=None,
        metavar="FILE",
        help="Path to input video file (required for --mode file).",
    )
    parser.add_argument(
        "--model-complexity",
        type=int,
        choices=[0, 1, 2],
        default=_DEFAULT_MODEL_COMPLEXITY,
        metavar="N",
        help=(
            "MediaPipe Pose model complexity:\n"
            "  0 = Lite  (fastest, use on low-spec machines)\n"
            "  1 = Full  (recommended, default)\n"
            "  2 = Heavy (most accurate, slowest)"
        ),
    )
    parser.add_argument(
        "--db",
        type=str,
        default=None,
        metavar="PATH",
        help="Custom path for the SQLite database file.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    db_path = Path(args.db) if args.db else None

    pipeline = OAScreeningPipeline(
        camera_source=args.camera,
        model_complexity=args.model_complexity,
        db_path=db_path,
    )

    print("\n  ╔══════════════════════════════════════════════════════════╗")
    print("  ║      OA GAIT ANALYSIS — EARLY DETECTION SYSTEM          ║")
    print("  ║      Offline-first  •  MediaPipe  •  SQLite             ║")
    print("  ╚══════════════════════════════════════════════════════════╝\n")

    if args.mode == "screen":
        pipeline.run_screen()

    elif args.mode == "file":
        # Default to sample.mp4 if no input file specified
        input_file = args.input if args.input else "sample.mp4"
        pipeline.run_file(input_file)

    elif args.mode == "history":
        pipeline.run_history()


if __name__ == "__main__":
    main()
