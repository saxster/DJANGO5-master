"""
Stream Event Capture Service
Captures and stores stream events with PII protection
"""

import uuid
import hashlib
import time
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from asgiref.sync import sync_to_async

from ..models import TestRun, StreamEvent
from .pii_redactor import pii_redactor

logger = logging.getLogger('streamlab.capture')


class StreamEventCapture:
    """
    Captures stream events with PII protection and anomaly detection
    """

    def __init__(self):
        self.active_runs = {}  # Cache active test runs
        self.event_buffer = []  # Buffer for batch processing
        self.buffer_size = 100
        self.last_flush = time.time()

    async def capture_event(self,
                           correlation_id: str,
                           endpoint: str,
                           payload: Dict[str, Any],
                           direction: str = 'inbound',
                           latency_ms: float = 0.0,
                           outcome: str = 'success',
                           error_details: Dict[str, Any] = None,
                           message_correlation_id: str = None,
                           channel_topic: str = '') -> Optional[str]:
        """
        Capture a stream event with PII protection

        Args:
            correlation_id: WebSocket/connection correlation ID
            endpoint: Endpoint or topic
            payload: Event payload (will be sanitized)
            direction: 'inbound' or 'outbound'
            latency_ms: Processing latency in milliseconds
            outcome: 'success', 'error', 'timeout', 'anomaly'
            error_details: Error information if outcome is error
            message_correlation_id: Individual message correlation ID
            channel_topic: MQTT topic or WebSocket channel

        Returns:
            Event ID if successfully captured
        """
        try:
            # Find active test run for this correlation ID
            test_run = await self._get_active_run(correlation_id)
            if not test_run:
                # Not part of a test scenario - don't capture
                return None

            # Redact PII from payload
            sanitized_payload = pii_redactor.redact(payload, endpoint)

            # Calculate schema hash for anomaly detection
            schema_hash = pii_redactor.calculate_schema_hash(payload)

            # Generate stack trace hash if error
            stack_trace_hash = ''
            if outcome == 'error' and error_details:
                stack_trace_hash = self._generate_stack_trace_hash(error_details)

            # Determine message size
            message_size = len(str(payload)) if payload else 0

            # Create event record
            event = StreamEvent(
                run=test_run,
                correlation_id=correlation_id,
                message_correlation_id=message_correlation_id or str(uuid.uuid4()),
                direction=direction,
                endpoint=endpoint,
                channel_topic=channel_topic,
                latency_ms=latency_ms,
                message_size_bytes=message_size,
                outcome=outcome,
                payload_sanitized=sanitized_payload,
                payload_schema_hash=schema_hash,
                stack_trace_hash=stack_trace_hash
            )

            # Add error details if present
            if error_details:
                event.error_code = error_details.get('error_code', '')
                event.error_message = error_details.get('error_message', '')[:500]  # Truncate
                event.http_status_code = error_details.get('http_status', None)

            # Save event
            await sync_to_async(event.save)()

            # Update run statistics
            await self._update_run_stats(test_run, event)

            # Log capture
            logger.info(
                "Stream event captured",
                extra={
                    'event_id': str(event.id),
                    'correlation_id': correlation_id,
                    'endpoint': endpoint,
                    'outcome': outcome,
                    'latency_ms': latency_ms,
                    'run_id': str(test_run.id)
                }
            )

            return str(event.id)

        except (ConnectionError, TimeoutError, asyncio.CancelledError) as e:
            logger.error(
                f"Failed to capture stream event: {e}",
                extra={
                    'correlation_id': correlation_id,
                    'endpoint': endpoint,
                    'outcome': outcome
                },
                exc_info=True
            )
            return None

    @sync_to_async
    def _get_active_run(self, correlation_id: str) -> Optional[TestRun]:
        """Get active test run for correlation ID"""
        try:
            # Check cache first
            if correlation_id in self.active_runs:
                run = self.active_runs[correlation_id]
                if run.status == 'running':
                    return run

            # Query database
            run = TestRun.objects.filter(
                status='running'
            ).select_related('scenario').first()

            if run:
                self.active_runs[correlation_id] = run

            return run

        except TestRun.DoesNotExist:
            return None

    @sync_to_async
    def _update_run_stats(self, test_run: TestRun, event: StreamEvent):
        """Update test run statistics"""
        try:
            # Increment counters
            test_run.total_events += 1

            if event.outcome == 'success':
                test_run.successful_events += 1
            else:
                test_run.failed_events += 1

            if event.outcome == 'anomaly':
                test_run.anomalies_detected += 1

            # Update error rate
            if test_run.total_events > 0:
                test_run.error_rate = test_run.failed_events / test_run.total_events

            test_run.save()

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Failed to update run stats: {e}")

    def _generate_stack_trace_hash(self, error_details: Dict[str, Any]) -> str:
        """Generate hash of stack trace for error correlation"""
        try:
            # Extract relevant parts of stack trace
            stack_trace = error_details.get('traceback', '')
            exception_type = error_details.get('exception_type', '')
            exception_message = error_details.get('exception_message', '')

            # Create signature from exception type and key stack frames
            signature_parts = [exception_type]

            if stack_trace:
                # Extract function names and file names from stack trace
                lines = stack_trace.split('\n')
                for line in lines:
                    if 'File "' in line and 'line' in line:
                        # Extract file and function info
                        parts = line.strip().split(',')
                        if len(parts) >= 2:
                            file_part = parts[0].replace('File "', '').replace('"', '')
                            func_part = parts[1].strip() if len(parts) > 1 else ''
                            # Use just filename, not full path
                            filename = file_part.split('/')[-1] if '/' in file_part else file_part
                            signature_parts.append(f"{filename}:{func_part}")

            # Combine signature parts
            signature = '|'.join(signature_parts[:5])  # Limit to first 5 stack frames

            # Generate hash
            return hashlib.sha256(signature.encode()).hexdigest()[:16]

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError):
            return hashlib.sha256(str(error_details).encode()).hexdigest()[:16]

    async def start_test_run_capture(self, test_run_id: str):
        """Start capturing events for a test run"""
        try:
            test_run = await sync_to_async(TestRun.objects.get)(id=test_run_id)
            test_run.status = 'running'
            await sync_to_async(test_run.save)()

            logger.info(f"Started event capture for run {test_run_id}")

        except TestRun.DoesNotExist:
            logger.error(f"Test run {test_run_id} not found")

    async def stop_test_run_capture(self, test_run_id: str):
        """Stop capturing events for a test run and calculate final metrics"""
        try:
            test_run = await sync_to_async(TestRun.objects.select_related('scenario').get)(id=test_run_id)

            # Calculate final performance metrics
            await self._calculate_final_metrics(test_run)

            # Mark as completed
            test_run.mark_completed()

            # Clear from cache
            self.active_runs = {k: v for k, v in self.active_runs.items() if v.id != test_run.id}

            logger.info(f"Stopped event capture for run {test_run_id}")

        except TestRun.DoesNotExist:
            logger.error(f"Test run {test_run_id} not found")

    @sync_to_async
    def _calculate_final_metrics(self, test_run: TestRun):
        """Calculate final performance metrics for a test run"""
        try:
            events = test_run.events.all()
            latencies = [e.latency_ms for e in events if e.latency_ms is not None]

            if latencies:
                latencies.sort()
                count = len(latencies)

                # Calculate percentiles
                test_run.p50_latency_ms = latencies[int(count * 0.5)] if count > 0 else 0
                test_run.p95_latency_ms = latencies[int(count * 0.95)] if count > 0 else 0
                test_run.p99_latency_ms = latencies[int(count * 0.99)] if count > 0 else 0

            # Calculate throughput
            duration = test_run.duration_seconds
            if duration and duration > 0:
                test_run.throughput_qps = test_run.successful_events / duration

            # Store additional metrics
            metrics = test_run.metrics or {}
            metrics.update({
                'total_latencies_calculated': len(latencies),
                'calculation_timestamp': timezone.now().isoformat(),
                'slo_met': test_run.is_within_slo
            })
            test_run.metrics = metrics

            test_run.save()

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Failed to calculate final metrics: {e}")

    def get_anomaly_threshold(self, endpoint: str) -> float:
        """Get anomaly detection threshold for endpoint"""
        # Default thresholds by endpoint type
        thresholds = {
            'websocket': 100.0,  # 100ms
            'mqtt': 50.0,        # 50ms
            'http': 200.0        # 200ms
        }

        endpoint_lower = endpoint.lower()
        for key, threshold in thresholds.items():
            if key in endpoint_lower:
                return threshold

        return 100.0  # Default

    async def detect_anomaly(self, event: StreamEvent) -> bool:
        """Detect if event represents an anomaly"""
        try:
            threshold = self.get_anomaly_threshold(event.endpoint)

            # Check latency anomaly
            if event.latency_ms > threshold:
                return True

            # Check error conditions
            if event.outcome in ['error', 'timeout']:
                return True

            # Check for schema changes
            if await self._is_schema_anomaly(event):
                return True

            return False

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError) as e:
            logger.error(f"Anomaly detection failed: {e}")
            return False

    @sync_to_async
    def _is_schema_anomaly(self, event: StreamEvent) -> bool:
        """Check if event schema is anomalous compared to recent events"""
        try:
            # Get recent events for same endpoint
            recent_events = StreamEvent.objects.filter(
                endpoint=event.endpoint,
                timestamp__gte=timezone.now() - timezone.timedelta(minutes=30)
            ).exclude(id=event.id)[:100]

            if not recent_events:
                return False

            # Count schema hash occurrences
            schema_counts = {}
            for e in recent_events:
                hash_val = e.payload_schema_hash
                schema_counts[hash_val] = schema_counts.get(hash_val, 0) + 1

            # If this schema is rare (< 5% of recent events), it's anomalous
            total_events = len(recent_events)
            current_count = schema_counts.get(event.payload_schema_hash, 0)

            if total_events > 10 and current_count / total_events < 0.05:
                return True

            return False

        except (ConnectionError, DatabaseError, IntegrityError, ObjectDoesNotExist, TimeoutError, asyncio.CancelledError):
            return False


# Singleton instance
stream_event_capture = StreamEventCapture()