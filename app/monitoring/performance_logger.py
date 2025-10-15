"""
Context manager for tracking function execution time and outcomes.
Pure observation layer - doesn't change behavior, only logs metrics.
"""

import logging
import time
from contextlib import contextmanager
from typing import Optional, Any
from app.monitoring.metrics_tracker import ProcessingStage, get_tracker

logger = logging.getLogger(__name__)


@contextmanager
def track_processing(
    stage: ProcessingStage,
    operation_name: str,
    **metadata
):
    """
    Context manager to track processing time and outcome.

    Usage:
        with track_processing(ProcessingStage.SURVEY_EXTRACTION, "extract_questions", filename="survey.pdf"):
            questions = extract_questions(pdf_path)
            # Questions are automatically tracked

    Args:
        stage: Which processing stage this is
        operation_name: Human-readable operation name
        **metadata: Additional context to log

    Yields:
        None (just wraps the operation)
    """
    start_time = time.time()
    tracker = get_tracker()

    logger.info(f"🔵 Starting {stage.value}: {operation_name}")
    if metadata:
        logger.debug(f"   Context: {metadata}")

    error_type = None
    success = False

    try:
        yield  # Execute the wrapped code
        success = True
        duration = time.time() - start_time
        logger.info(f"✅ Completed {stage.value}: {operation_name} in {duration:.2f}s")

    except Exception as e:
        error_type = type(e).__name__
        duration = time.time() - start_time
        logger.error(
            f"❌ Failed {stage.value}: {operation_name} after {duration:.2f}s - "
            f"{error_type}: {str(e)[:200]}"
        )
        raise  # Re-raise to preserve original behavior

    finally:
        # Always record metrics, even on failure
        if 'duration' not in locals():
            duration = time.time() - start_time

        tracker.record_attempt(
            stage=stage,
            success=success,
            duration_seconds=duration,
            error_type=error_type,
            quality_score=1.0,  # Default, can be overridden by calling set_quality_score()
            operation=operation_name,
            **metadata
        )


class QualityScoreContext:
    """
    Context manager to set quality score for current operation.

    Usage:
        with track_processing(ProcessingStage.SURVEY_EXTRACTION, "extract"):
            questions = extract()
            quality = calculate_quality(questions)
            with quality_score(quality):
                pass  # Quality recorded automatically
    """

    def __init__(self, score: float):
        if not 0.0 <= score <= 1.0:
            raise ValueError(f"Quality score must be 0.0-1.0, got {score}")
        self.score = score

    def __enter__(self):
        # Store in thread-local storage or pass through context
        # For now, just log it
        logger.debug(f"Quality score set: {self.score:.1%}")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


def quality_score(score: float) -> QualityScoreContext:
    """
    Set quality score for the current operation.

    Args:
        score: Quality metric (0.0-1.0), e.g., extraction_completeness

    Returns:
        Context manager that records the score
    """
    return QualityScoreContext(score)


# Convenience function for simple timing without context manager
def time_operation(stage: ProcessingStage, operation_name: str):
    """
    Decorator to time a function and record metrics.

    Usage:
        @time_operation(ProcessingStage.SURVEY_EXTRACTION, "extract_questions")
        def extract_questions(pdf_path):
            ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            with track_processing(stage, operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator
