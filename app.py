#!/usr/bin/env python3
"""
app.py — Render Web Service for CareSetu v1.0

Provides:
  - Health check endpoint (GET /)
  - Video upload & analysis endpoint (POST /api/analyze)
  - Session history endpoint (GET /api/sessions)

Runs on Render as a headless web server (no webcam).
"""

from flask import Flask, request, jsonify
import os
import sys
from pathlib import Path
import logging

# Add repo to path
repo_root = Path(__file__).parent
sys.path.insert(0, str(repo_root))

from core.database import DatabaseManager

# Setup logging
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize database
db = DatabaseManager()

@app.route('/', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        'status': 'ok',
        'service': 'CareSetu v1.0 Gait Screening',
        'mode': 'headless-file',
        'version': '1.0.0',
        'environment': 'Render (headless server)',
    }), 200


@app.route('/api/sessions', methods=['GET'])
def get_sessions():
    """Get all past screening sessions."""
    try:
        limit = request.args.get('limit', default=50, type=int)
        sessions = db.get_all_sessions(limit=limit)
        count = db.get_session_count()

        result = {
            'total_sessions': count,
            'returned': len(sessions),
            'sessions': [
                {
                    'id': s[0],
                    'timestamp': s[1],
                    'mode': s[2],
                    'duration_seconds': s[3],
                    'risk_level': s[4],
                    'risk_score': s[5],
                    'summary': s[6],
                }
                for s in sessions
            ]
        }
        return jsonify(result), 200
    except Exception as e:
        log.error(f"Error fetching sessions: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/api/analyze', methods=['POST'])
def analyze_video():
    """
    Analyze a gait video file.

    Expects:
      - video_file: uploaded MP4/AVI file
      - OR video_path: path to existing video on server

    Returns:
      - session_id, risk_level, risk_score, metrics
    """
    try:
        # Import OAScreeningPipeline lazily to avoid import-time side effects
        from main import OAScreeningPipeline

        # Option 1: Accept uploaded file
        if 'video_file' in request.files:
            video_file = request.files['video_file']
            if video_file.filename == '':
                return jsonify({'error': 'No file selected'}), 400

            # Save uploaded file
            upload_dir = Path('/tmp/caresetu_uploads')
            upload_dir.mkdir(exist_ok=True)
            video_path = upload_dir / video_file.filename
            video_file.save(str(video_path))
            log.info(f"Uploaded video: {video_path}")

        # Option 2: Use existing file path
        elif 'video_path' in request.json:
            video_path = request.json['video_path']
            if not Path(video_path).exists():
                return jsonify({'error': f'Video file not found: {video_path}'}), 404
        else:
            return jsonify({'error': 'Provide video_file or video_path'}), 400

        # Analyze the video
        log.info(f"Analyzing video: {video_path}")
        pipeline = OAScreeningPipeline()
        metrics, duration = pipeline.run_file(str(video_path))

        # Classify risk
        assessment = pipeline.classifier.classify(metrics)

        # Save to database
        session_id = pipeline.db.save_session(
            metrics, assessment,
            mode='api',
            duration_seconds=duration,
        )

        result = {
            'session_id': session_id,
            'duration_seconds': duration,
            'risk_level': assessment.level.value,
            'risk_score': assessment.score,
            'summary': assessment.summary,
            'metrics': {
                'cadence_spm': metrics.cadence_spm,
                'knee_rom_l': metrics.knee_rom_l_mean,
                'knee_rom_r': metrics.knee_rom_r_mean,
                'knee_asymmetry': metrics.knee_angle_asymmetry_deg,
                'hip_sway': metrics.hip_sway_asymmetry_pct,
                'stride_cv': metrics.stride_duration_cv_pct,
            }
        }

        log.info(f"Analysis complete: session {session_id}, risk {assessment.level.value}")
        return jsonify(result), 200

    except Exception as e:
        log.error(f"Analysis error: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@app.route('/api/status', methods=['GET'])
def status():
    """Get service status and statistics."""
    try:
        session_count = db.get_session_count()
        return jsonify({
            'status': 'running',
            'total_sessions_analyzed': session_count,
            'environment': 'Render (headless)',
            'python_version': f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        }), 200
    except Exception as e:
        log.error(f"Status error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 10000))
    log.info(f"Starting Flask app on 0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
