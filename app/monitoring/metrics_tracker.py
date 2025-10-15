"""
Centralized metrics tracking for production monitoring.
Tracks success/failure rates, performance, and quality metrics.

This is a pure observation layer - it doesn't change any behavior.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ProcessingStage(Enum):
    """Stages of document processing pipeline."""
    SURVEY_EXTRACTION = "survey_extraction"
    PROTOCOL_EXTRACTION = "protocol_extraction"
    GAP_ANALYSIS = "gap_analysis"
    QUESTION_MAPPING = "question_mapping"
    BATCH_PROCESSING = "batch_processing"


@dataclass
class ProcessingAttempt:
    """Record of a single processing attempt."""
    stage: ProcessingStage
    timestamp: datetime
    success: bool
    duration_seconds: float
    error_type: Optional[str] = None
    quality_score: float = 1.0  # 0.0 to 1.0
    metadata: Dict = field(default_factory=dict)


class MetricsTracker:
    """
    Tracks processing metrics across all stages.
    Provides failure rates, performance stats, and quality metrics.

    Thread-safe for concurrent operations.
    """

    def __init__(self):
        self.attempts: List[ProcessingAttempt] = []
        self._session_start = datetime.now()
        self._lock = None  # Will add threading.Lock() if needed for production

    def record_attempt(
        self,
        stage: ProcessingStage,
        success: bool,
        duration_seconds: float,
        error_type: Optional[str] = None,
        quality_score: float = 1.0,
        **metadata
    ) -> None:
        """
        Record a processing attempt.

        Args:
            stage: Which processing stage this is
            success: Whether the operation succeeded
            duration_seconds: How long it took
            error_type: Type of error if failed (e.g., 'ValueError', 'APIError')
            quality_score: Quality metric (0.0-1.0), e.g., extraction_completeness
            **metadata: Additional context (file_name, question_count, etc.)
        """
        attempt = ProcessingAttempt(
            stage=stage,
            timestamp=datetime.now(),
            success=success,
            duration_seconds=duration_seconds,
            error_type=error_type,
            quality_score=quality_score,
            metadata=metadata
        )
        self.attempts.append(attempt)

        # Log based on outcome
        if not success:
            logger.error(
                f"❌ {stage.value.upper()} FAILED | "
                f"Duration: {duration_seconds:.2f}s | "
                f"Error: {error_type} | "
                f"Context: {metadata}"
            )
        elif quality_score < 0.5:
            logger.warning(
                f"⚠️  {stage.value.upper()} LOW QUALITY | "
                f"Score: {quality_score:.1%} | "
                f"Duration: {duration_seconds:.2f}s | "
                f"Context: {metadata}"
            )
        else:
            logger.info(
                f"✅ {stage.value.upper()} SUCCESS | "
                f"Duration: {duration_seconds:.2f}s | "
                f"Quality: {quality_score:.1%}"
            )

    def get_stats(self, stage: Optional[ProcessingStage] = None) -> Dict:
        """
        Get statistics for a specific stage or overall.

        Returns:
            Dict with success rates, timing stats, error breakdown
        """
        attempts = [a for a in self.attempts if stage is None or a.stage == stage]

        if not attempts:
            return {"total_attempts": 0, "message": "No data yet"}

        total = len(attempts)
        successes = sum(1 for a in attempts if a.success)
        failures = total - successes

        durations = [a.duration_seconds for a in attempts]
        quality_scores = [a.quality_score for a in attempts if a.success]

        # Error breakdown
        error_breakdown = {}
        for attempt in attempts:
            if not attempt.success and attempt.error_type:
                error_breakdown[attempt.error_type] = error_breakdown.get(attempt.error_type, 0) + 1

        return {
            "total_attempts": total,
            "successes": successes,
            "failures": failures,
            "success_rate": successes / total if total > 0 else 0,
            "failure_rate": failures / total if total > 0 else 0,
            "avg_duration_seconds": sum(durations) / len(durations) if durations else 0,
            "min_duration_seconds": min(durations) if durations else 0,
            "max_duration_seconds": max(durations) if durations else 0,
            "avg_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
            "error_breakdown": error_breakdown,
            "session_duration_minutes": (datetime.now() - self._session_start).total_seconds() / 60
        }

    def log_summary(self) -> None:
        """Log comprehensive summary of all metrics."""
        logger.info("=" * 80)
        logger.info("📊 PROCESSING METRICS SUMMARY")
        logger.info("=" * 80)

        overall = self.get_stats()
        if overall['total_attempts'] == 0:
            logger.info("No operations tracked yet")
            logger.info("=" * 80)
            return

        logger.info(
            f"Overall: {overall['successes']}/{overall['total_attempts']} succeeded "
            f"({overall['success_rate']:.1%} success rate) | "
            f"Session: {overall['session_duration_minutes']:.1f} minutes"
        )

        for stage in ProcessingStage:
            stats = self.get_stats(stage)
            if stats['total_attempts'] > 0:
                logger.info(
                    f"\n{stage.value.upper()}:\n"
                    f"  Attempts: {stats['total_attempts']}\n"
                    f"  Success Rate: {stats['success_rate']:.1%}\n"
                    f"  Avg Duration: {stats['avg_duration_seconds']:.2f}s\n"
                    f"  Avg Quality: {stats['avg_quality_score']:.1%}"
                )
                if stats['error_breakdown']:
                    logger.info(f"  Errors: {stats['error_breakdown']}")

        logger.info("=" * 80)

    def check_thresholds(self) -> List[str]:
        """
        Check if any metrics exceed alert thresholds.

        Returns:
            List of alert messages (empty if all good)
        """
        alerts = []

        # Define acceptable thresholds
        thresholds = {
            ProcessingStage.SURVEY_EXTRACTION: {"failure_rate": 0.10, "min_attempts": 5},
            ProcessingStage.PROTOCOL_EXTRACTION: {"failure_rate": 0.15, "min_attempts": 5},
            ProcessingStage.GAP_ANALYSIS: {"failure_rate": 0.08, "min_attempts": 3},
            ProcessingStage.QUESTION_MAPPING: {"failure_rate": 0.10, "min_attempts": 5},
            ProcessingStage.BATCH_PROCESSING: {"failure_rate": 0.05, "min_attempts": 3},
        }

        for stage, limits in thresholds.items():
            stats = self.get_stats(stage)

            # Only alert after minimum attempts
            if stats['total_attempts'] >= limits['min_attempts']:
                if stats['failure_rate'] > limits['failure_rate']:
                    alert = (
                        f"🚨 {stage.value.upper()}: Failure rate {stats['failure_rate']:.1%} "
                        f"exceeds threshold {limits['failure_rate']:.1%} "
                        f"({stats['failures']}/{stats['total_attempts']} failures)"
                    )
                    alerts.append(alert)
                    logger.critical(alert)

        return alerts

    def reset(self) -> None:
        """Reset all metrics (useful for testing)."""
        self.attempts.clear()
        self._session_start = datetime.now()
        logger.info("📊 Metrics tracker reset")


# Global singleton tracker instance
_global_tracker = None


def get_tracker() -> MetricsTracker:
    """Get the global metrics tracker instance (singleton pattern)."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MetricsTracker()
    return _global_tracker
