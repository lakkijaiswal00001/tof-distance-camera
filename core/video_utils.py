"""
video_utils.py
==============
Utility functions for video file handling.

Provides:
  - Dummy video generation for testing/headless environments
  - Video file validation
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Optional


def create_dummy_video(
    output_path: str,
    duration_seconds: float = 5.0,
    fps: int = 30,
    width: int = 1280,
    height: int = 720,
    human_readable: bool = True,
) -> bool:
    """
    Create a dummy video file with moving geometric patterns.

    Useful for testing video processing in headless environments
    where no real video files are available.

    Parameters
    ----------
    output_path : str
        Path where the video file will be saved.
    duration_seconds : float
        Duration of the video in seconds (default: 5.0).
    fps : int
        Frames per second (default: 30).
    width : int
        Frame width in pixels (default: 1280).
    height : int
        Frame height in pixels (default: 720).
    human_readable : bool
        If True, adds text to explain it's a dummy video (default: True).

    Returns
    -------
    bool
        True if video was created successfully, False otherwise.
    """
    try:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Define codec and create VideoWriter
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(output_path), fourcc, fps, (width, height))

        if not out.isOpened():
            print(f"[ERROR] Failed to create video writer for {output_path}")
            return False

        frame_count = int(duration_seconds * fps)

        for frame_idx in range(frame_count):
            # Create a frame with animated geometric patterns
            frame = np.zeros((height, width, 3), dtype=np.uint8)

            # Add background gradient
            for i in range(height):
                intensity = int((i / height) * 200)
                frame[i, :] = [intensity, intensity // 2, 50]

            # Draw animated rectangles
            center_x = width // 2
            center_y = height // 2

            # Oscillating rectangle size
            progress = (frame_idx % fps) / fps
            size_factor = int(100 + 50 * np.sin(2 * np.pi * progress))

            x1 = max(0, center_x - size_factor)
            y1 = max(0, center_y - size_factor)
            x2 = min(width, center_x + size_factor)
            y2 = min(height, center_y + size_factor)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 100), 3)

            # Draw moving circle
            circle_offset = int(200 * np.sin(2 * np.pi * progress))
            cx = center_x + circle_offset
            cy = center_y
            cv2.circle(frame, (cx, cy), 50, (255, 0, 100), -1)

            # Add frame counter
            frame_text = f"Frame {frame_idx + 1}/{frame_count}"
            cv2.putText(
                frame, frame_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.0,
                (255, 255, 255),
                2
            )

            # Add human-readable label
            if human_readable:
                cv2.putText(
                    frame,
                    "DUMMY VIDEO - Testing Mode",
                    (20, height - 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.8,
                    (100, 200, 255),
                    2
                )

            out.write(frame)

        out.release()
        file_size_mb = output_path.stat().st_size / (1024 * 1024)
        print(f"[INFO] Created dummy video: {output_path} ({file_size_mb:.1f} MB)")
        return True

    except Exception as e:
        print(f"[ERROR] Failed to create dummy video: {e}")
        return False


def get_or_create_sample_video(
    default_path: str = "data/sample.mp4",
    duration_seconds: float = 5.0,
) -> Optional[str]:
    """
    Get path to sample video, creating a dummy one if it doesn't exist.

    Parameters
    ----------
    default_path : str
        Path where the sample video should be located or created.
    duration_seconds : float
        Duration for the dummy video if created.

    Returns
    -------
    str or None
        Path to the video file if it exists or was created successfully,
        None if creation failed.
    """
    video_path = Path(default_path)

    # If file already exists, return it
    if video_path.exists():
        return str(video_path)

    # Otherwise, create a dummy video
    print(f"[INFO] Sample video not found at {default_path}")
    print(f"[INFO] Creating dummy video for testing...")

    if create_dummy_video(str(video_path), duration_seconds=duration_seconds):
        return str(video_path)
    else:
        return None


def validate_video_file(video_path: str) -> tuple[bool, str]:
    """
    Validate that a video file exists and can be opened.

    Parameters
    ----------
    video_path : str
        Path to the video file.

    Returns
    -------
    tuple
        (is_valid, error_message)
    """
    path = Path(video_path)

    if not path.exists():
        return False, f"Video file not found: {video_path}"

    if not path.is_file():
        return False, f"Path is not a file: {video_path}"

    # Try to open with OpenCV
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        return False, f"Cannot open video file: {video_path}"

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    cap.release()

    if frame_count == 0:
        return False, f"Video file is empty or corrupted: {video_path}"

    return True, f"Valid video: {frame_count} frames @ {fps:.1f} fps"
