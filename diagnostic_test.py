#!/usr/bin/env python3
"""
diagnostic_test.py - Test pose detection and data saving
"""
import sys
from pathlib import Path

repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from core.database import DatabaseManager
from core.pose_estimator import PoseEstimator
from core.gait_processor import GaitProcessor
from core.oa_classifier import OARiskClassifier
from core.camera import CameraInterface
import logging

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

print("\n" + "="*60)
print("DIAGNOSTIC TEST: Pose Detection & Data Saving")
print("="*60 + "\n")

# Test 1: Database initialization
print("[1] Testing database initialization...")
try:
    db = DatabaseManager()
    count = db.get_session_count()
    print(f"[OK] Database OK - {count} existing sessions")
except Exception as e:
    print(f"[FAIL] Database failed: {e}")
    sys.exit(1)

# Test 2: Pose estimator
print("\n[2] Testing pose estimator...")
try:
    estimator = PoseEstimator(model_complexity=1)
    print(f"[OK] Pose estimator loaded")
except Exception as e:
    print(f"[FAIL] Pose estimator failed: {e}")
    sys.exit(1)

# Test 3: Video file detection
print("\n[3] Testing video file access...")
video_path = Path("sample.mp4")
if video_path.exists():
    print(f"[OK] Video file found: {video_path} ({video_path.stat().st_size} bytes)")
else:
    print(f"[FAIL] Video file not found: {video_path}")
    sys.exit(1)

# Test 4: Camera/video capture
print("\n[4] Testing video capture...")
try:
    camera = CameraInterface(source=str(video_path))
    success, msg = camera.open_safe()
    if success:
        print(f"[OK] Video opened successfully")
        ok, frame = camera.read()
        if ok and frame is not None:
            print(f"[OK] Frame read OK: {frame.shape}")

            # Test pose detection on first frame
            print("\n[5] Testing pose detection on first frame...")
            pose = estimator.process(frame)
            if pose and pose.raw and pose.raw.pose_landmarks:
                print(f"[OK] Pose detected: {len(pose.raw.pose_landmarks.landmark)} landmarks")

                # Check for key landmarks
                lm = pose.raw.pose_landmarks.landmark
                print(f"  - Nose (0): {lm[0].x:.3f}, {lm[0].y:.3f}")
                print(f"  - L Knee (25): {lm[25].x:.3f}, {lm[25].y:.3f}")
                print(f"  - R Knee (26): {lm[26].x:.3f}, {lm[26].y:.3f}")
            else:
                print(f"[FAIL] No pose detected in first frame")
        else:
            print(f"[FAIL] Failed to read frame")
        camera.release()
    else:
        print(f"[FAIL] Video open failed: {msg}")
        sys.exit(1)
except Exception as e:
    print(f"[FAIL] Camera test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Gait metrics computation
print("\n[6] Testing gait metrics computation...")
try:
    processor = GaitProcessor(fps=30.0)
    classifier = OARiskClassifier()

    # Process all frames
    camera = CameraInterface(source=str(video_path))
    camera.open_safe()

    frame_count = 0
    while True:
        ok, frame = camera.read()
        if not ok:
            break
        frame_count += 1
        pose = estimator.process(frame)
        if pose:
            processor.update(pose)

    camera.release()

    metrics = processor.compute_metrics()
    assessment = classifier.classify(metrics)

    print(f"[OK] Processed {frame_count} frames")
    print(f"  - Cadence: {metrics.cadence_spm:.1f} steps/min")
    print(f"  - L Knee ROM: {metrics.left_knee_rom:.1f} degrees")
    print(f"  - R Knee ROM: {metrics.right_knee_rom:.1f} degrees")
    print(f"  - Risk Level: {assessment.level.value}")
    print(f"  - Risk Score: {assessment.score}")

    # Test 6: Database save
    print("\n[7] Testing database save...")
    session_id = db.save_session(
        metrics, assessment,
        mode='diagnostic',
        duration_seconds=frame_count / 30.0
    )

    if session_id > 0:
        print(f"[OK] Session saved: ID #{session_id}")

        # Verify save
        record = db.get_session_by_id(session_id)
        if record:
            print(f"[OK] Session retrieved from DB")
            print(f"  - Risk Level: {record.risk_level}")
            print(f"  - Cadence: {record.cadence_spm}")
            print(f"  - Duration: {record.duration_seconds:.1f}s")
        else:
            print(f"[FAIL] Session not found in DB")
    else:
        print(f"[FAIL] Failed to save session")

except Exception as e:
    print(f"[FAIL] Metrics/Save test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("ALL TESTS PASSED")
print("="*60 + "\n")
