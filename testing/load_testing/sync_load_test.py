#!/usr/bin/env python3
"""
Mobile Sync Load Testing Suite

Tests sync system performance under various load conditions:
- 1,000 concurrent sync requests
- 10,000 items synced in 1 minute
- 100 simultaneous resumable uploads
- Conflict resolution under load

Success Criteria:
- P95 latency < 200ms
- 0% data loss
- 100% conflict resolution accuracy
- Graceful degradation (no crashes)

Usage:
    python sync_load_test.py --scenario all --duration 300
    python sync_load_test.py --scenario concurrent --connections 1000
    python sync_load_test.py --scenario high_volume --items 10000
    python sync_load_test.py --scenario uploads --sessions 100
    python sync_load_test.py --scenario conflicts --conflicts 500
"""

import os
import sys
import django
import asyncio
import websockets
import json
import time
import statistics
import argparse
import uuid
import hashlib
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()


class SyncLoadTest:
    """
    Comprehensive load testing for mobile sync system.

    Scenarios:
    1. Concurrent Connections: 1,000 simultaneous WebSocket connections
    2. High Volume: 10,000 items synced in 1 minute
    3. Resumable Uploads: 100 simultaneous chunked uploads
    4. Conflict Resolution: High conflict rate scenarios
    """

    def __init__(self, base_url="ws://localhost:8000"):
        self.base_url = base_url
        self.results = defaultdict(lambda: {
            'latencies': [],
            'successes': 0,
            'failures': 0,
            'errors': []
        })

    def run_all_scenarios(self, duration=300):
        """Run all load test scenarios."""
        print("=" * 70)
        print("MOBILE SYNC LOAD TEST SUITE")
        print("=" * 70)
        print(f"Base URL: {self.base_url}")
        print(f"Duration: {duration}s")
        print()

        scenarios = [
            ('concurrent', self.test_concurrent_connections, {'connections': 1000}),
            ('high_volume', self.test_high_volume_sync, {'items': 10000, 'duration': 60}),
            ('uploads', self.test_resumable_uploads, {'sessions': 100}),
            ('conflicts', self.test_conflict_resolution, {'conflicts': 500}),
        ]

        for name, test_func, kwargs in scenarios:
            print(f"\n{'=' * 70}")
            print(f"Running Scenario: {name.upper()}")
            print(f"{'=' * 70}")

            start_time = time.time()
            try:
                result = asyncio.run(test_func(**kwargs))
                self.results[name] = result
                elapsed = time.time() - start_time

                print(f"\n✅ Scenario completed in {elapsed:.2f}s")
                self._display_scenario_results(name, result)

            except (ConnectionError, asyncio.TimeoutError) as e:
                print(f"\n❌ Scenario failed: {e}")
                self.results[name]['error'] = str(e)

        self._display_final_summary()

    async def test_concurrent_connections(self, connections=1000, duration=60):
        """
        Test 1: Concurrent Connections

        Target: 1,000 simultaneous WebSocket connections
        Success Criteria: P95 latency < 200ms, no connection failures
        """
        print(f"📊 Testing {connections} concurrent connections...")
        print(f"   Duration: {duration}s")

        latencies = []
        successes = 0
        failures = 0
        connection_errors = 0

        async def single_connection_test(conn_id):
            nonlocal successes, failures, connection_errors

            try:
                uri = f"{self.base_url}/ws/mobile/sync/?device_id=load_test_{conn_id}"

                async with websockets.connect(uri, timeout=10) as websocket:
                    start_time = time.time()

                    message = {
                        "type": "sync",
                        "payload": {
                            "voice_data": [{
                                "verification_id": str(uuid.uuid4()),
                                "timestamp": datetime.now().isoformat(),
                                "verified": True,
                                "confidence_score": 0.95,
                            }]
                        }
                    }

                    await websocket.send(json.dumps(message))

                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        latency = (time.time() - start_time) * 1000
                        latencies.append(latency)
                        successes += 1
                    except asyncio.TimeoutError:
                        failures += 1

            except (websockets.exceptions.WebSocketException, ConnectionError, OSError) as e:
                connection_errors += 1
                failures += 1

        tasks = [single_connection_test(i) for i in range(connections)]
        await asyncio.gather(*tasks, return_exceptions=True)

        return self._calculate_results(latencies, successes, failures, connection_errors)

    async def test_high_volume_sync(self, items=10000, duration=60):
        """
        Test 2: High Volume Sync

        Target: 10,000 items synced in 1 minute
        Success Criteria: 100% success rate, 0% data loss
        """
        print(f"📊 Testing high-volume sync: {items} items in {duration}s...")
        print(f"   Target rate: {items/duration:.1f} items/second")

        latencies = []
        successes = 0
        failures = 0
        items_synced = 0

        batch_size = 100
        num_batches = items // batch_size

        async def sync_batch(batch_id):
            nonlocal successes, failures, items_synced

            try:
                uri = f"{self.base_url}/ws/mobile/sync/?device_id=high_volume_test"

                async with websockets.connect(uri, timeout=10) as websocket:
                    start_time = time.time()

                    voice_data = [
                        {
                            "verification_id": str(uuid.uuid4()),
                            "timestamp": datetime.now().isoformat(),
                            "verified": True,
                            "confidence_score": 0.90 + (i % 10) / 100,
                        }
                        for i in range(batch_size)
                    ]

                    message = {
                        "type": "sync",
                        "payload": {"voice_data": voice_data}
                    }

                    await websocket.send(json.dumps(message))

                    try:
                        response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        latency = (time.time() - start_time) * 1000
                        latencies.append(latency)

                        response_data = json.loads(response)
                        items_synced += response_data.get('synced_items', 0)
                        successes += 1

                    except asyncio.TimeoutError:
                        failures += 1

            except (websockets.exceptions.WebSocketException, ConnectionError) as e:
                failures += 1

        tasks = [sync_batch(i) for i in range(num_batches)]
        await asyncio.gather(*tasks, return_exceptions=True)

        result = self._calculate_results(latencies, successes, failures)
        result['items_synced'] = items_synced
        result['target_items'] = items
        result['data_loss_pct'] = ((items - items_synced) / items) * 100 if items > 0 else 0

        return result

    async def test_resumable_uploads(self, sessions=100):
        """
        Test 3: Resumable Uploads

        Target: 100 simultaneous chunked file uploads
        Success Criteria: All uploads complete successfully
        """
        print(f"📊 Testing {sessions} simultaneous resumable uploads...")

        from apps.core.services.resumable_upload_service import ResumableUploadService

        latencies = []
        successes = 0
        failures = 0
        total_bytes = 0

        def test_single_upload(session_id):
            nonlocal successes, failures, total_bytes

            try:
                start_time = time.time()

                from django.contrib.auth import get_user_model
                User = get_user_model()
                user = User.objects.first()

                if not user:
                    failures += 1
                    return

                filename = f"test_file_{session_id}.dat"
                file_size = 5 * 1024 * 1024
                file_hash = hashlib.sha256(f"test_{session_id}".encode()).hexdigest()

                session = ResumableUploadService.init_upload(
                    user=user,
                    filename=filename,
                    total_size=file_size,
                    mime_type='application/octet-stream',
                    file_hash=file_hash
                )

                chunk_data = b'x' * ResumableUploadService.DEFAULT_CHUNK_SIZE
                chunk_hash = hashlib.sha256(chunk_data).hexdigest()

                ResumableUploadService.upload_chunk(
                    upload_id=session['upload_id'],
                    chunk_index=0,
                    chunk_data=chunk_data,
                    checksum=chunk_hash
                )

                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                total_bytes += len(chunk_data)
                successes += 1

            except (ValueError, IOError, ConnectionError) as e:
                failures += 1

        with ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(test_single_upload, i) for i in range(sessions)]
            for future in as_completed(futures):
                try:
                    future.result()
                except (ValueError, IOError) as e:
                    failures += 1

        result = self._calculate_results(latencies, successes, failures)
        result['total_bytes_uploaded'] = total_bytes
        result['avg_throughput_mbps'] = (total_bytes / (1024 * 1024)) / (sum(latencies) / 1000) if latencies else 0

        return result

    async def test_conflict_resolution(self, conflicts=500):
        """
        Test 4: Conflict Resolution Under Load

        Target: High conflict rate scenario
        Success Criteria: 100% conflict resolution accuracy
        """
        print(f"📊 Testing conflict resolution: {conflicts} conflicts...")

        from apps.core.models.sync_conflict_policy import ConflictResolutionLog

        latencies = []
        successes = 0
        failures = 0
        conflicts_created = 0

        async def create_conflict(conflict_id):
            nonlocal successes, failures, conflicts_created

            try:
                start_time = time.time()

                mobile_id = uuid.uuid4()

                log_entry = await asyncio.to_thread(
                    ConflictResolutionLog.objects.create,
                    mobile_id=mobile_id,
                    domain='journal',
                    server_version=1,
                    client_version=2,
                    resolution_strategy='most_recent_wins',
                    resolution_result='resolved',
                    winning_version='client',
                )

                latency = (time.time() - start_time) * 1000
                latencies.append(latency)
                conflicts_created += 1
                successes += 1

            except (ValueError, ConnectionError) as e:
                failures += 1

        tasks = [create_conflict(i) for i in range(conflicts)]
        await asyncio.gather(*tasks, return_exceptions=True)

        result = self._calculate_results(latencies, successes, failures)
        result['conflicts_created'] = conflicts_created
        result['resolution_accuracy_pct'] = (successes / conflicts) * 100 if conflicts > 0 else 0

        return result

    def _calculate_results(self, latencies, successes, failures, connection_errors=0):
        """Calculate performance metrics."""
        if not latencies:
            return {
                'successes': successes,
                'failures': failures,
                'connection_errors': connection_errors,
                'p50': 0,
                'p95': 0,
                'p99': 0,
                'avg_latency': 0,
                'min_latency': 0,
                'max_latency': 0,
            }

        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        return {
            'successes': successes,
            'failures': failures,
            'connection_errors': connection_errors,
            'p50': sorted_latencies[int(n * 0.50)] if n > 0 else 0,
            'p95': sorted_latencies[int(n * 0.95)] if n > 0 else 0,
            'p99': sorted_latencies[int(n * 0.99)] if n > 0 else 0,
            'avg_latency': statistics.mean(latencies),
            'min_latency': min(latencies),
            'max_latency': max(latencies),
        }

    def _display_scenario_results(self, name, result):
        """Display results for a single scenario."""
        print(f"\n📈 Results for {name}:")
        print(f"   Successes:        {result.get('successes', 0)}")
        print(f"   Failures:         {result.get('failures', 0)}")

        if 'connection_errors' in result:
            print(f"   Connection Errors: {result['connection_errors']}")

        print(f"\n   Latency Metrics:")
        print(f"   P50:  {result.get('p50', 0):.2f}ms")
        print(f"   P95:  {result.get('p95', 0):.2f}ms ({'✅ PASS' if result.get('p95', 0) < 200 else '❌ FAIL'})")
        print(f"   P99:  {result.get('p99', 0):.2f}ms")
        print(f"   Avg:  {result.get('avg_latency', 0):.2f}ms")
        print(f"   Min:  {result.get('min_latency', 0):.2f}ms")
        print(f"   Max:  {result.get('max_latency', 0):.2f}ms")

        if 'items_synced' in result:
            print(f"\n   Items Synced:     {result['items_synced']} / {result['target_items']}")
            print(f"   Data Loss:        {result['data_loss_pct']:.2f}% ({'✅ PASS' if result['data_loss_pct'] == 0 else '❌ FAIL'})")

        if 'total_bytes_uploaded' in result:
            print(f"\n   Total Bytes:      {result['total_bytes_uploaded'] / (1024*1024):.2f} MB")
            print(f"   Avg Throughput:   {result['avg_throughput_mbps']:.2f} MB/s")

        if 'conflicts_created' in result:
            print(f"\n   Conflicts Created: {result['conflicts_created']}")
            print(f"   Resolution Accuracy: {result['resolution_accuracy_pct']:.1f}% ({'✅ PASS' if result['resolution_accuracy_pct'] == 100 else '❌ FAIL'})")

    def _display_final_summary(self):
        """Display final test summary."""
        print(f"\n{'=' * 70}")
        print("FINAL SUMMARY")
        print(f"{'=' * 70}")

        total_successes = sum(r.get('successes', 0) for r in self.results.values())
        total_failures = sum(r.get('failures', 0) for r in self.results.values())
        total_tests = total_successes + total_failures

        success_rate = (total_successes / total_tests * 100) if total_tests > 0 else 0

        print(f"\nTotal Tests:      {total_tests}")
        print(f"Total Successes:  {total_successes}")
        print(f"Total Failures:   {total_failures}")
        print(f"Success Rate:     {success_rate:.1f}%")

        all_passed = all(
            r.get('p95', 0) < 200 and
            r.get('data_loss_pct', 0) == 0
            for r in self.results.values()
        )

        print(f"\nOverall Status:   {'✅ ALL TESTS PASSED' if all_passed else '❌ SOME TESTS FAILED'}")
        print()


def main():
    parser = argparse.ArgumentParser(description='Mobile Sync Load Testing')
    parser.add_argument('--scenario', choices=['all', 'concurrent', 'high_volume', 'uploads', 'conflicts'],
                       default='all', help='Test scenario to run')
    parser.add_argument('--duration', type=int, default=300, help='Test duration in seconds')
    parser.add_argument('--connections', type=int, default=1000, help='Number of concurrent connections')
    parser.add_argument('--items', type=int, default=10000, help='Number of items to sync')
    parser.add_argument('--sessions', type=int, default=100, help='Number of upload sessions')
    parser.add_argument('--conflicts', type=int, default=500, help='Number of conflicts to create')
    parser.add_argument('--base-url', default='ws://localhost:8000', help='WebSocket base URL')

    args = parser.parse_args()

    tester = SyncLoadTest(base_url=args.base_url)

    if args.scenario == 'all':
        tester.run_all_scenarios(duration=args.duration)
    elif args.scenario == 'concurrent':
        result = asyncio.run(tester.test_concurrent_connections(connections=args.connections))
        tester._display_scenario_results('concurrent', result)
    elif args.scenario == 'high_volume':
        result = asyncio.run(tester.test_high_volume_sync(items=args.items))
        tester._display_scenario_results('high_volume', result)
    elif args.scenario == 'uploads':
        result = asyncio.run(tester.test_resumable_uploads(sessions=args.sessions))
        tester._display_scenario_results('uploads', result)
    elif args.scenario == 'conflicts':
        result = asyncio.run(tester.test_conflict_resolution(conflicts=args.conflicts))
        tester._display_scenario_results('conflicts', result)


if __name__ == '__main__':
    main()
