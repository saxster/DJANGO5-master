"""
Background job orchestration for AI Mentor long-running operations.

This module provides:
- Job management with progress tracking
- SSE streaming for real-time updates
- Cancellation and resumability
- Error handling and recovery
"""

import uuid
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Generator
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import threading

from django.core.cache import cache


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class JobType(Enum):
    """Types of mentor jobs."""
    PLAN_GENERATION = "plan_generation"
    PATCH_GENERATION = "patch_generation"
    PATCH_APPLICATION = "patch_application"
    TEST_EXECUTION = "test_execution"
    IMPACT_ANALYSIS = "impact_analysis"
    CODE_EXPLANATION = "code_explanation"


@dataclass
class JobProgress:
    """Progress information for a job."""
    current_step: str
    step_number: int
    total_steps: int
    percentage: float
    details: Dict[str, Any] = field(default_factory=dict)
    estimated_remaining_seconds: Optional[int] = None


@dataclass
class JobResult:
    """Result of a completed job."""
    job_id: str
    status: JobStatus
    result_data: Any
    error_message: Optional[str] = None
    progress: Optional[JobProgress] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Job:
    """Job definition and state."""
    job_id: str
    job_type: JobType
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    progress: Optional[JobProgress] = None
    result: Any = None
    error_message: Optional[str] = None
    user_id: Optional[int] = None
    request_data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    can_cancel: bool = True
    can_pause: bool = False


class JobEventStream:
    """Server-Sent Events stream for job progress."""

    def __init__(self, job_id: str):
        self.job_id = job_id
        self.last_event_id = 0

    def get_events(self) -> Generator[str, None, None]:
        """Generate SSE events for job progress."""
        while True:
            job = JobOrchestrator.get_job(self.job_id)
            if not job:
                yield f"data: {json.dumps({'type': 'error', 'message': 'Job not found'})}\n\n"
                break

            # Send progress update
            if job.progress:
                event_data = {
                    'type': 'progress',
                    'job_id': self.job_id,
                    'status': job.status.value,
                    'progress': {
                        'current_step': job.progress.current_step,
                        'step_number': job.progress.step_number,
                        'total_steps': job.progress.total_steps,
                        'percentage': job.progress.percentage,
                        'details': job.progress.details,
                        'estimated_remaining': job.progress.estimated_remaining_seconds
                    },
                    'timestamp': time.time()
                }
                yield f"data: {json.dumps(event_data)}\n\n"

            # Check if job is complete
            if job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED]:
                final_event = {
                    'type': 'complete',
                    'job_id': self.job_id,
                    'status': job.status.value,
                    'result': job.result,
                    'error_message': job.error_message,
                    'timestamp': time.time()
                }
                yield f"data: {json.dumps(final_event)}\n\n"
                break

            # Wait before next update
            time.sleep(1)


class JobOrchestrator:
    """Orchestrates background jobs for AI Mentor operations."""

    _jobs: Dict[str, Job] = {}
    _executor = ThreadPoolExecutor(max_workers=4)
    _lock = threading.Lock()

    @classmethod
    def submit_job(cls, job_type: JobType, job_function: Callable,
                  request_data: Dict[str, Any], user_id: Optional[int] = None,
                  metadata: Dict[str, Any] = None) -> str:
        """Submit a new background job."""
        job_id = str(uuid.uuid4())

        job = Job(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            created_at=datetime.now(),
            user_id=user_id,
            request_data=request_data,
            metadata=metadata or {}
        )

        with cls._lock:
            cls._jobs[job_id] = job

        # Submit to thread pool
        future = cls._executor.submit(cls._execute_job, job_id, job_function)

        # Store future reference for cancellation
        job.metadata['future'] = future

        return job_id

    @classmethod
    def _execute_job(cls, job_id: str, job_function: Callable):
        """Execute a job in the background."""
        job = cls._jobs.get(job_id)
        if not job:
            return

        try:
            # Update job status
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now()

            # Create progress callback
            def progress_callback(step: str, step_num: int, total_steps: int,
                                percentage: float, details: Dict[str, Any] = None):
                job.progress = JobProgress(
                    current_step=step,
                    step_number=step_num,
                    total_steps=total_steps,
                    percentage=percentage,
                    details=details or {}
                )

            # Execute the job function
            result = job_function(job.request_data, progress_callback)

            # Update job with result
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now()
            job.result = result

        except (TypeError, ValueError, json.JSONDecodeError) as e:
            job.status = JobStatus.FAILED
            job.completed_at = datetime.now()
            job.error_message = str(e)
            print(f"Job {job_id} failed: {e}")

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Job]:
        """Get job by ID."""
        return cls._jobs.get(job_id)

    @classmethod
    def get_user_jobs(cls, user_id: int) -> List[Job]:
        """Get all jobs for a specific user."""
        return [job for job in cls._jobs.values() if job.user_id == user_id]

    @classmethod
    def cancel_job(cls, job_id: str) -> bool:
        """Cancel a running job."""
        job = cls._jobs.get(job_id)
        if not job or not job.can_cancel:
            return False

        if job.status == JobStatus.RUNNING:
            # Try to cancel the future
            future = job.metadata.get('future')
            if future and future.cancel():
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now()
                return True

        return False

    @classmethod
    def pause_job(cls, job_id: str) -> bool:
        """Pause a running job (if supported)."""
        job = cls._jobs.get(job_id)
        if not job or not job.can_pause or job.status != JobStatus.RUNNING:
            return False

        job.status = JobStatus.PAUSED
        return True

    @classmethod
    def resume_job(cls, job_id: str) -> bool:
        """Resume a paused job."""
        job = cls._jobs.get(job_id)
        if not job or job.status != JobStatus.PAUSED:
            return False

        job.status = JobStatus.RUNNING
        return True

    @classmethod
    def cleanup_old_jobs(cls, max_age_hours: int = 24):
        """Clean up old completed jobs."""
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)

        with cls._lock:
            job_ids_to_remove = []
            for job_id, job in cls._jobs.items():
                if (job.status in [JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED] and
                    job.completed_at and job.completed_at < cutoff_time):
                    job_ids_to_remove.append(job_id)

            for job_id in job_ids_to_remove:
                del cls._jobs[job_id]

        return len(job_ids_to_remove)

    @classmethod
    def get_job_statistics(cls) -> Dict[str, Any]:
        """Get statistics about job execution."""
        total_jobs = len(cls._jobs)
        if total_jobs == 0:
            return {'total_jobs': 0}

        status_counts = {}
        type_counts = {}
        total_duration = 0
        completed_jobs = 0

        for job in cls._jobs.values():
            # Count by status
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

            # Count by type
            job_type = job.job_type.value
            type_counts[job_type] = type_counts.get(job_type, 0) + 1

            # Calculate duration for completed jobs
            if job.completed_at and job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                total_duration += duration
                completed_jobs += 1

        avg_duration = total_duration / completed_jobs if completed_jobs > 0 else 0

        return {
            'total_jobs': total_jobs,
            'status_counts': status_counts,
            'type_counts': type_counts,
            'average_duration_seconds': round(avg_duration, 2),
            'completed_jobs': completed_jobs,
            'success_rate': status_counts.get('completed', 0) / total_jobs if total_jobs > 0 else 0
        }


# Job function implementations
def plan_generation_job(request_data: Dict[str, Any], progress_callback: Callable):
    """Background job for plan generation."""
    progress_callback("Analyzing request", 1, 5, 0.2)

    # Import here to avoid circular imports
    from apps.mentor.management.commands.mentor_plan import PlanGenerator

    progress_callback("Building impact analysis", 2, 5, 0.4)

    generator = PlanGenerator()

    progress_callback("Generating plan steps", 3, 5, 0.6)

    plan = generator.generate_plan(
        request=request_data['request'],
        scope=request_data.get('scope')
    )

    progress_callback("Validating plan", 4, 5, 0.8)

    # Additional validation could go here

    progress_callback("Plan generation complete", 5, 5, 1.0)

    return plan.to_dict()


def patch_generation_job(request_data: Dict[str, Any], progress_callback: Callable):
    """Background job for patch generation."""
    progress_callback("Initializing patch generation", 1, 6, 0.17)

    from apps.mentor.management.commands.mentor_patch import PatchOrchestrator, PatchRequest

    progress_callback("Analyzing target files", 2, 6, 0.33)

    orchestrator = PatchOrchestrator()

    patch_request = PatchRequest(
        request=request_data['request'],
        scope=request_data.get('scope'),
        patch_type=request_data.get('type', 'improvement'),
        target_files=request_data.get('files'),
        dry_run=request_data.get('dry_run', True)
    )

    progress_callback("Generating patches", 3, 6, 0.5)

    patches = orchestrator.generate_patches(patch_request)

    progress_callback("Running safety validation", 4, 6, 0.67)

    # Enhanced validation with impact analysis
    results = orchestrator.apply_patches(
        patches,
        dry_run=request_data.get('dry_run', True),
        create_branch=request_data.get('create_branch', False)
    )

    progress_callback("Finalizing results", 5, 6, 0.83)

    progress_callback("Patch generation complete", 6, 6, 1.0)

    return {
        'patches': [{
            'type': patch.type.value,
            'priority': patch.priority.value,
            'description': patch.description,
            'file_path': patch.file_path,
            'confidence': patch.confidence
        } for patch in patches],
        'application_results': results
    }


def test_execution_job(request_data: Dict[str, Any], progress_callback: Callable):
    """Background job for test execution."""
    progress_callback("Initializing test execution", 1, 4, 0.25)

    # Import here to avoid circular imports
    from apps.mentor.management.commands.mentor_test import TestSelector, TestRunner

    progress_callback("Selecting tests", 2, 4, 0.5)

    selector = TestSelector()
    runner = TestRunner()

    # Select tests based on criteria
    selected_tests = set()
    if request_data.get('targets'):
        selected_tests.update(selector.select_tests_for_changes(request_data['targets']))

    progress_callback("Running tests", 3, 4, 0.75, {'test_count': len(selected_tests)})

    # Run tests
    session = runner.run_tests(
        selected_tests,
        collect_coverage=request_data.get('coverage', False),
        parallel=request_data.get('parallel', True),
        timeout=request_data.get('timeout', 600)
    )

    progress_callback("Test execution complete", 4, 4, 1.0)

    return {
        'session_id': session.session_id,
        'total_tests': session.total_tests,
        'passed': session.passed,
        'failed': session.failed,
        'duration': session.total_duration,
        'coverage': session.coverage_percentage
    }


# Convenience functions for common job types
def submit_plan_generation(request: str, scope: Optional[List[str]] = None,
                          user_id: Optional[int] = None) -> str:
    """Submit a plan generation job."""
    return JobOrchestrator.submit_job(
        job_type=JobType.PLAN_GENERATION,
        job_function=plan_generation_job,
        request_data={'request': request, 'scope': scope},
        user_id=user_id
    )


def submit_patch_generation(request: str, patch_type: str = 'improvement',
                           scope: Optional[List[str]] = None, dry_run: bool = True,
                           user_id: Optional[int] = None) -> str:
    """Submit a patch generation job."""
    return JobOrchestrator.submit_job(
        job_type=JobType.PATCH_GENERATION,
        job_function=patch_generation_job,
        request_data={
            'request': request,
            'type': patch_type,
            'scope': scope,
            'dry_run': dry_run
        },
        user_id=user_id
    )


def submit_test_execution(targets: List[str], coverage: bool = False,
                         parallel: bool = True, user_id: Optional[int] = None) -> str:
    """Submit a test execution job."""
    return JobOrchestrator.submit_job(
        job_type=JobType.TEST_EXECUTION,
        job_function=test_execution_job,
        request_data={
            'targets': targets,
            'coverage': coverage,
            'parallel': parallel
        },
        user_id=user_id
    )


# Cache-based job persistence (for demo - use database in production)
class JobPersistence:
    """Simple cache-based job persistence."""

    @staticmethod
    def save_job(job: Job):
        """Save job to cache."""
        cache_key = f"mentor_job_{job.job_id}"
        job_data = {
            'job_id': job.job_id,
            'job_type': job.job_type.value,
            'status': job.status.value,
            'created_at': job.created_at.isoformat(),
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'result': job.result,
            'error_message': job.error_message,
            'user_id': job.user_id,
            'request_data': job.request_data,
            'metadata': job.metadata,
            'can_cancel': job.can_cancel,
            'can_pause': job.can_pause
        }

        # Add progress if available
        if job.progress:
            job_data['progress'] = {
                'current_step': job.progress.current_step,
                'step_number': job.progress.step_number,
                'total_steps': job.progress.total_steps,
                'percentage': job.progress.percentage,
                'details': job.progress.details,
                'estimated_remaining_seconds': job.progress.estimated_remaining_seconds
            }

        cache.set(cache_key, job_data, timeout=86400)  # 24 hour timeout

    @staticmethod
    def load_job(job_id: str) -> Optional[Job]:
        """Load job from cache."""
        cache_key = f"mentor_job_{job_id}"
        job_data = cache.get(cache_key)

        if not job_data:
            return None

        # Reconstruct job object
        job = Job(
            job_id=job_data['job_id'],
            job_type=JobType(job_data['job_type']),
            status=JobStatus(job_data['status']),
            created_at=datetime.fromisoformat(job_data['created_at']),
            result=job_data.get('result'),
            error_message=job_data.get('error_message'),
            user_id=job_data.get('user_id'),
            request_data=job_data.get('request_data', {}),
            metadata=job_data.get('metadata', {}),
            can_cancel=job_data.get('can_cancel', True),
            can_pause=job_data.get('can_pause', False)
        )

        if job_data.get('started_at'):
            job.started_at = datetime.fromisoformat(job_data['started_at'])

        if job_data.get('completed_at'):
            job.completed_at = datetime.fromisoformat(job_data['completed_at'])

        # Reconstruct progress if available
        if job_data.get('progress'):
            progress_data = job_data['progress']
            job.progress = JobProgress(
                current_step=progress_data['current_step'],
                step_number=progress_data['step_number'],
                total_steps=progress_data['total_steps'],
                percentage=progress_data['percentage'],
                details=progress_data.get('details', {}),
                estimated_remaining_seconds=progress_data.get('estimated_remaining_seconds')
            )

        return job

    @staticmethod
    def list_user_jobs(user_id: int) -> List[Job]:
        """List all jobs for a user."""
        # This is a simplified implementation
        # In production, you'd query the database more efficiently
        all_job_keys = cache.keys("mentor_job_*")
        user_jobs = []

        for key in all_job_keys:
            job_data = cache.get(key)
            if job_data and job_data.get('user_id') == user_id:
                job = JobPersistence.load_job(job_data['job_id'])
                if job:
                    user_jobs.append(job)

        return sorted(user_jobs, key=lambda j: j.created_at, reverse=True)


# Update JobOrchestrator to use persistence
class PersistentJobOrchestrator(JobOrchestrator):
    """Job orchestrator with persistence."""

    @classmethod
    def get_job(cls, job_id: str) -> Optional[Job]:
        """Get job by ID (with persistence)."""
        # Try memory first
        job = cls._jobs.get(job_id)
        if job:
            return job

        # Fall back to persistence
        job = JobPersistence.load_job(job_id)
        if job:
            cls._jobs[job_id] = job

        return job

    @classmethod
    def _execute_job(cls, job_id: str, job_function: Callable):
        """Execute job with persistence."""
        # Call parent implementation
        super()._execute_job(job_id, job_function)

        # Save to persistence
        job = cls._jobs.get(job_id)
        if job:
            JobPersistence.save_job(job)


# Replace the default orchestrator
JobOrchestrator = PersistentJobOrchestrator