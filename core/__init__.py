# core/__init__.py
"""
OA Gait Analysis — Core Package
Exposes the main pipeline components for import convenience.
"""

from .camera import CameraInterface, AlignmentValidator, ValidationStatus
from .pose_estimator import PoseEstimator, PoseLandmarks
from .gait_processor import GaitProcessor, GaitMetrics
from .oa_classifier import OARiskClassifier, RiskAssessment, RiskLevel
from .database import DatabaseManager

__all__ = [
    "CameraInterface",
    "AlignmentValidator",
    "ValidationStatus",
    "PoseEstimator",
    "PoseLandmarks",
    "GaitProcessor",
    "GaitMetrics",
    "OARiskClassifier",
    "RiskAssessment",
    "RiskLevel",
    "DatabaseManager",
]
