"""
core/oa_classifier.py
=====================
OA Risk Classification Logic.

Takes a GaitMetrics object (from GaitProcessor) and applies a weighted,
rule-based scoring algorithm grounded in published clinical gait norms to
produce a RiskAssessment with:
  - Numeric risk score
  - Risk level: LOW / MODERATE / HIGH
  - Per-marker flags and human-readable explanations

Clinical Reference Ranges
--------------------------
Source: Winter DA (2009) Biomechanics and Motor Control of Human Movement;
        Kadaba et al. (1990) J Orthop Res; Mündermann et al. (2005) OA & Cartilage.

  Knee ROM during walking:       55°–75°
  L/R knee angle asymmetry:      < 8°
  Hip sway asymmetry:            < 15% of hip width
  Stride duration CV:            < 3%
  Stance phase ratio (each side): 60%–65% of gait cycle

Offline-first: pure Python, no external dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List

import numpy as np

from .gait_processor import GaitMetrics


# ──────────────────────────────────────────────────────────────────────────────
# Enums & Constants
# ──────────────────────────────────────────────────────────────────────────────

class RiskLevel(Enum):
    LOW      = "Low Risk"
    MODERATE = "Moderate — Monitor Closely"
    HIGH     = "High Risk / Potential OA Indicator"

    @property
    def color_bgr(self):
        """OpenCV BGR colour for HUD rendering."""
        return {
            RiskLevel.LOW:      (0,   200, 80),
            RiskLevel.MODERATE: (0,   180, 255),
            RiskLevel.HIGH:     (0,   50,  230),
        }[self]


# Thresholds derived from published normal ranges
_NORMAL = {
    "knee_rom_low_warn":    55.0,   # below this → 1 pt
    "knee_rom_low_severe":  50.0,   # below this → 2 pts
    "knee_asym_warn":        8.0,
    "knee_asym_severe":     12.0,
    "hip_sway_warn":        15.0,   # percentage
    "hip_sway_severe":      22.0,
    "stride_cv_warn":        3.0,   # percentage
    "stride_cv_severe":      6.0,
    "stance_low_warn":       0.55,  # ratio
    "stance_high_warn":      0.68,
}

# Risk score thresholds
_SCORE_MODERATE = 3
_SCORE_HIGH     = 6


# ──────────────────────────────────────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class MarkerFlag:
    """One individual OA risk marker evaluation."""
    name:        str
    value:       float
    unit:        str
    normal_range: str
    points:      int        # penalty points contributed
    flagged:     bool
    explanation: str


@dataclass
class RiskAssessment:
    """
    Complete OA risk classification result for one screening session.

    Attributes
    ----------
    score : int
        Total accumulated penalty points.
    level : RiskLevel
        Categorical risk classification.
    markers : list of MarkerFlag
        Per-marker evaluation with values and explanations.
    summary : str
        Human-readable overall summary paragraph.
    data_sufficient : bool
        False if the gait window was too short for reliable assessment.
    """
    score:            int
    level:            RiskLevel
    markers:          List[MarkerFlag]
    summary:          str
    data_sufficient:  bool = True

    @property
    def flagged_markers(self) -> List[MarkerFlag]:
        return [m for m in self.markers if m.flagged]


# ──────────────────────────────────────────────────────────────────────────────
# OARiskClassifier
# ──────────────────────────────────────────────────────────────────────────────

class OARiskClassifier:
    """
    Rule-based weighted scoring classifier for OA gait risk.

    All thresholds are sourced from peer-reviewed biomechanics literature
    and are tuneable via the `thresholds` parameter.

    Parameters
    ----------
    thresholds : dict | None
        Optional override dict to replace any of the default threshold values.
        Keys must match those defined in _NORMAL above.

    Example
    -------
    ::

        clf = OARiskClassifier()
        assessment = clf.classify(metrics)
        print(assessment.level.value)
        for m in assessment.flagged_markers:
            print(f"  ⚠ {m.name}: {m.value:.1f}{m.unit}  ({m.explanation})")
    """

    def __init__(self, thresholds: Dict | None = None) -> None:
        self._t = dict(_NORMAL)
        if thresholds:
            self._t.update(thresholds)

    # ── Public API ────────────────────────────────────────────────────────────

    def classify(self, metrics: GaitMetrics) -> RiskAssessment:
        """
        Classify the supplied GaitMetrics and return a RiskAssessment.

        Parameters
        ----------
        metrics : GaitMetrics
            Aggregated kinematic metrics from GaitProcessor.compute_metrics().

        Returns
        -------
        RiskAssessment
        """
        if not metrics.is_valid():
            return RiskAssessment(
                score=0,
                level=RiskLevel.LOW,
                markers=[],
                summary=(
                    "Insufficient gait data collected. "
                    "Please record at least 3–4 complete walking steps."
                ),
                data_sufficient=False,
            )

        marker_flags: List[MarkerFlag] = []
        total_score = 0

        # ── 1. Knee ROM — Left ────────────────────────────────────────────────
        pts, expl = self._score_knee_rom(metrics.left_knee_rom)
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Left Knee ROM",
            value=metrics.left_knee_rom,
            unit="°",
            normal_range="55°–75°",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 2. Knee ROM — Right ───────────────────────────────────────────────
        pts, expl = self._score_knee_rom(metrics.right_knee_rom)
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Right Knee ROM",
            value=metrics.right_knee_rom,
            unit="°",
            normal_range="55°–75°",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 3. Knee Angle Asymmetry ───────────────────────────────────────────
        pts, expl = self._score_knee_asymmetry(metrics.knee_angle_asymmetry)
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Knee Angle Asymmetry",
            value=metrics.knee_angle_asymmetry,
            unit="°",
            normal_range="< 8°",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 4. Hip Sway Asymmetry ─────────────────────────────────────────────
        pts, expl = self._score_hip_sway(metrics.hip_sway_asymmetry_pct)
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Hip Sway Asymmetry",
            value=metrics.hip_sway_asymmetry_pct,
            unit="%",
            normal_range="< 15%",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 5. Stride Duration Variability ────────────────────────────────────
        pts, expl = self._score_stride_cv(metrics.stride_duration_cv)
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Stride Timing Variability (CV)",
            value=metrics.stride_duration_cv,
            unit="%",
            normal_range="< 3%",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 6. Left Stance Phase Ratio ────────────────────────────────────────
        pts, expl = self._score_stance(metrics.left_stance_ratio, "Left")
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Left Stance Phase Ratio",
            value=metrics.left_stance_ratio * 100,
            unit="%",
            normal_range="60–65%",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── 7. Right Stance Phase Ratio ───────────────────────────────────────
        pts, expl = self._score_stance(metrics.right_stance_ratio, "Right")
        total_score += pts
        marker_flags.append(MarkerFlag(
            name="Right Stance Phase Ratio",
            value=metrics.right_stance_ratio * 100,
            unit="%",
            normal_range="60–65%",
            points=pts,
            flagged=pts > 0,
            explanation=expl,
        ))

        # ── Determine Risk Level ──────────────────────────────────────────────
        if total_score >= _SCORE_HIGH:
            level = RiskLevel.HIGH
        elif total_score >= _SCORE_MODERATE:
            level = RiskLevel.MODERATE
        else:
            level = RiskLevel.LOW

        summary = self._build_summary(total_score, level, marker_flags, metrics)

        return RiskAssessment(
            score=total_score,
            level=level,
            markers=marker_flags,
            summary=summary,
            data_sufficient=True,
        )

    # ── Scoring sub-rules ─────────────────────────────────────────────────────

    def _score_knee_rom(self, rom: float) -> tuple[int, str]:
        rom = float(rom or 0.0)
        if np.isnan(rom) or rom < 0:
            return 0, "Insufficient data for knee ROM assessment."

        t = self._t
        if rom < t["knee_rom_low_severe"]:
            return 2, (
                f"Severely restricted knee ROM ({rom:.1f}°). "
                "Values below 50° suggest significant joint stiffness — "
                "a key early-OA indicator."
            )
        if rom < t["knee_rom_low_warn"]:
            return 1, (
                f"Mildly restricted knee ROM ({rom:.1f}°). "
                "Normal walking requires 55°–75° of knee flexion."
            )
        if rom > 80.0:
            return 1, (
                f"Elevated knee ROM ({rom:.1f}°). "
                "Hyperflexion compensation may indicate instability."
            )
        return 0, f"Knee ROM within normal range ({rom:.1f}°)."

    def _score_knee_asymmetry(self, asym: float) -> tuple[int, str]:
        t = self._t
        if asym > t["knee_asym_severe"]:
            return 2, (
                f"Significant left/right knee angle asymmetry ({asym:.1f}°). "
                "Suggests compensatory offloading of a painful joint."
            )
        if asym > t["knee_asym_warn"]:
            return 1, (
                f"Mild knee angle asymmetry ({asym:.1f}°). "
                "Monitor for progressive unilateral compensation."
            )
        return 0, f"Knee angle symmetry within normal range ({asym:.1f}°)."

    def _score_hip_sway(self, sway_pct: float) -> tuple[int, str]:
        t = self._t
        if sway_pct > t["hip_sway_severe"]:
            return 2, (
                f"Excessive hip sway asymmetry ({sway_pct:.1f}%). "
                "May reflect abductor weakness or valgus collapse — OA risk factor."
            )
        if sway_pct > t["hip_sway_warn"]:
            return 1, (
                f"Elevated hip sway asymmetry ({sway_pct:.1f}%). "
                "Minor lateral imbalance detected."
            )
        return 0, f"Hip sway symmetry within normal range ({sway_pct:.1f}%)."

    def _score_stride_cv(self, cv: float) -> tuple[int, str]:
        t = self._t
        if cv > t["stride_cv_severe"]:
            return 2, (
                f"Highly irregular stride timing (CV={cv:.1f}%). "
                "Inconsistent rhythm may indicate pain-avoidance gait."
            )
        if cv > t["stride_cv_warn"]:
            return 1, (
                f"Moderately irregular stride timing (CV={cv:.1f}%). "
                "Slight variability above normal."
            )
        return 0, f"Stride timing regularity within normal range (CV={cv:.1f}%)."

    def _score_stance(self, ratio: float, side: str) -> tuple[int, str]:
        t = self._t
        pct = ratio * 100
        if ratio < t["stance_low_warn"] or ratio > t["stance_high_warn"]:
            return 1, (
                f"{side} stance phase ratio abnormal ({pct:.1f}%). "
                f"Normal range is 60–65%. "
                "Altered weight-bearing timing may indicate antalgic gait."
            )
        return 0, f"{side} stance phase ratio within normal range ({pct:.1f}%)."

    # ── Summary builder ───────────────────────────────────────────────────────

    @staticmethod
    def _build_summary(
        score: int,
        level: RiskLevel,
        markers: List[MarkerFlag],
        metrics: GaitMetrics,
    ) -> str:
        flagged = [m.name for m in markers if m.flagged]
        cadence_info = (
            f"Cadence: {metrics.cadence_spm:.0f} steps/min. "
            if metrics.cadence_spm > 0 else ""
        )

        if level == RiskLevel.LOW:
            return (
                f"Gait analysis complete. Risk Score: {score}. "
                f"{cadence_info}"
                "No significant OA risk markers detected. "
                "Gait parameters fall within published normal ranges. "
                "Continue routine monitoring."
            )

        flagged_str = ", ".join(flagged) if flagged else "none"
        base = (
            f"Gait analysis complete. Risk Score: {score}. "
            f"{cadence_info}"
            f"Flagged markers: {flagged_str}. "
        )

        if level == RiskLevel.MODERATE:
            return base + (
                "Moderate deviation from normal gait patterns detected. "
                "Recommend follow-up clinical assessment and physiotherapy evaluation."
            )

        return base + (
            "Multiple OA risk markers identified. "
            "STRONGLY recommend clinical evaluation by an orthopaedic specialist. "
            "This screening result is indicative only and not a clinical diagnosis."
        )
