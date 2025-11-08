"""
Sync Testing Framework - Comprehensive testing utilities for mobile sync operations

Addresses testing gaps identified in analysis:
- Missing parity tests for REST sync endpoints
- Missing race condition tests for concurrent sync operations
- Missing device simulation and conflict scenarios

Following .claude/rules.md:
- Rule #7: Test utilities <150 lines each
- Rule #11: Specific exception handling
"""

import uuid
import random
import asyncio
import time
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.utils import timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

import logging
logger = logging.getLogger(__name__)


from apps.core.services.sync.sync_operation_interface import SyncRequest, sync_operation_interface

User = get_user_model()


@dataclass
class MockDevice:
    """Mock mobile device for testing sync operations."""
    device_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user: Optional[User] = None
    network_quality: str = 'good'  # excellent, good, fair, poor
    sync_frequency: int = 30  # seconds between syncs
    offline_probability: float = 0.1  # chance of being offline
    conflict_probability: float = 0.05  # chance of creating conflicts
    data_generation_rate: int = 5  # items generated per sync
    client_version: str = '1.0.0'

    def __post_init__(self):
        """Initialize device-specific data."""
        self.local_data_store = {}
        self.pending_syncs = []
        self.sync_history = []
        self.is_online = True


@dataclass
class SyncTestScenario:
    """Test scenario configuration for sync testing."""
    name: str
    description: str
    devices: List[MockDevice]
    duration_seconds: int = 60
    conflict_rate: float = 0.1
    network_issues: bool = False
    concurrent_users: int = 1
    data_types: List[str] = field(default_factory=lambda: ['task', 'ticket'])
    assertions: List[Callable] = field(default_factory=list)


class MockSyncClient:
    """Mock sync client that simulates mobile app behavior."""

    def __init__(self, device: MockDevice, base_url: str = 'http://testserver'):
        """Initialize mock sync client."""
        self.device = device
        self.base_url = base_url
        self.client = Client()
        self.sync_count = 0
        self.conflict_count = 0
        self.error_count = 0

    def generate_sync_data(self, data_type: str, count: int = 5) -> List[Dict[str, Any]]:
        """Generate mock sync data for testing."""
        data = []

        for i in range(count):
            if data_type == 'task':
                item = {
                    'mobile_id': str(uuid.uuid4()),
                    'jobneedname': f'Test Task {i} from {self.device.device_id[:8]}',
                    'priority': random.choice(['HIGH', 'MEDIUM', 'LOW']),
                    'jobstatus': random.choice(['ASSIGNED', 'INPROGRESS', 'COMPLETED']),
                    'version': 1,
                    'created_at': timezone.now().isoformat(),
                }

            elif data_type == 'ticket':
                item = {
                    'mobile_id': str(uuid.uuid4()),
                    'title': f'Test Ticket {i} from {self.device.device_id[:8]}',
                    'priority': random.choice(['HIGH', 'MEDIUM', 'LOW']),
                    'status': random.choice(['NEW', 'OPEN', 'INPROGRESS', 'RESOLVED']),
                    'version': 1,
                    'created_at': timezone.now().isoformat(),
                }

            elif data_type == 'voice':
                item = {
                    'verification_id': str(uuid.uuid4()),
                    'timestamp': timezone.now().isoformat(),
                    'verified': random.choice([True, False]),
                    'confidence_score': round(random.uniform(0.7, 1.0), 2),
                    'quality_score': round(random.uniform(0.8, 1.0), 2),
                    'processing_time_ms': random.randint(100, 500),
                }

            else:
                item = {
                    'mobile_id': str(uuid.uuid4()),
                    'data_type': data_type,
                    'version': 1,
                    'created_at': timezone.now().isoformat(),
                }

            # Introduce conflicts based on device probability
            if random.random() < self.device.conflict_probability:
                item['version'] = random.randint(2, 5)  # Higher version to create conflict

            data.append(item)

        return data

    def sync_rest_endpoint(self, data_type: str, data: List[Dict]) -> Dict[str, Any]:
        """Simulate REST API sync call."""
        try:
            self.client.force_login(self.device.user)

            # Simulate network issues
            if self.device.network_quality == 'poor' and random.random() < 0.3:
                raise ConnectionError("Simulated network error")

            sync_data = {
                'entries': data,
                'device_id': self.device.device_id,
                'client_version': self.device.client_version,
                'last_sync_timestamp': timezone.now().isoformat(),
            }

            # Call appropriate endpoint based on data type
            if data_type == 'task':
                response = self.client.post(
                    '/api/v1/sync/tasks',
                    data=sync_data,
                    content_type='application/json'
                )
            elif data_type == 'ticket':
                response = self.client.post(
                    '/api/v1/sync/tickets',
                    data=sync_data,
                    content_type='application/json'
                )
            else:
                response = self.client.post(
                    '/api/v1/sync/generic',
                    data=sync_data,
                    content_type='application/json'
                )

            self.sync_count += 1
            result = response.json() if hasattr(response, 'json') else {}

            if response.status_code != 200:
                self.error_count += 1

            if result.get('conflicts'):
                self.conflict_count += len(result['conflicts'])

            return result

        except Exception as e:  # OK: Test framework - catch all exceptions for reporting
            self.error_count += 1
            return {'error': str(e), 'synced_items': 0, 'failed_items': len(data)}

    def get_sync_statistics(self) -> Dict[str, Any]:
        """Get sync statistics for this device."""
        return {
            'device_id': self.device.device_id,
            'total_syncs': self.sync_count,
            'conflicts': self.conflict_count,
            'errors': self.error_count,
            'success_rate': (self.sync_count - self.error_count) / max(self.sync_count, 1) * 100,
            'network_quality': self.device.network_quality,
        }


class SyncTestFramework:
    """Comprehensive testing framework for sync operations."""

    def __init__(self):
        """Initialize sync test framework."""
        self.scenarios = {}
        self.results = {}

    def register_scenario(self, scenario: SyncTestScenario) -> None:
        """Register a test scenario."""
        self.scenarios[scenario.name] = scenario

    def create_mock_devices(self, count: int, users: List[User]) -> List[MockDevice]:
        """Create mock devices for testing."""
        devices = []

        for i in range(count):
            device = MockDevice(
                user=users[i % len(users)],
                network_quality=random.choice(['excellent', 'good', 'fair', 'poor']),
                conflict_probability=random.uniform(0.01, 0.1),
                data_generation_rate=random.randint(1, 10),
            )
            devices.append(device)

        return devices

    def run_scenario(self, scenario_name: str, parallel: bool = True) -> Dict[str, Any]:
        """
        Run a test scenario and collect results.

        Args:
            scenario_name: Name of scenario to run
            parallel: Whether to run devices in parallel

        Returns:
            Scenario results with statistics
        """
        if scenario_name not in self.scenarios:
            raise ValueError(f"Unknown scenario: {scenario_name}")

        scenario = self.scenarios[scenario_name]
        start_time = time.time()

        logger.debug(f"Running scenario: {scenario.name}")
        logger.debug(f"Description: {scenario.description}")
        logger.debug(f"Devices: {len(scenario.devices)}")
        logger.debug(f"Duration: {scenario.duration_seconds}s")

        if parallel:
            results = self._run_parallel_sync_test(scenario)
        else:
            results = self._run_sequential_sync_test(scenario)

        duration = time.time() - start_time

        # Compile results
        scenario_results = {
            'scenario_name': scenario_name,
            'duration_seconds': duration,
            'device_results': results,
            'summary': self._calculate_scenario_summary(results),
            'assertions_passed': self._run_scenario_assertions(scenario, results),
        }

        self.results[scenario_name] = scenario_results
        return scenario_results

    def _run_parallel_sync_test(self, scenario: SyncTestScenario) -> List[Dict[str, Any]]:
        """Run sync test with multiple devices in parallel."""
        results = []

        with ThreadPoolExecutor(max_workers=scenario.concurrent_users) as executor:
            # Submit sync tasks for each device
            future_to_device = {}

            for device in scenario.devices:
                future = executor.submit(self._simulate_device_sync, device, scenario)
                future_to_device[future] = device

            # Collect results as they complete
            for future in as_completed(future_to_device):
                device = future_to_device[future]
                try:
                    device_result = future.result()
                    results.append(device_result)
                except Exception as e:  # OK: Test framework - catch all exceptions for reporting
                    results.append({
                        'device_id': device.device_id,
                        'error': str(e),
                        'sync_count': 0,
                    })

        return results

    def _run_sequential_sync_test(self, scenario: SyncTestScenario) -> List[Dict[str, Any]]:
        """Run sync test with devices sequentially."""
        results = []

        for device in scenario.devices:
            try:
                device_result = self._simulate_device_sync(device, scenario)
                results.append(device_result)
            except Exception as e:  # OK: Test framework - catch all exceptions for reporting
                results.append({
                    'device_id': device.device_id,
                    'error': str(e),
                    'sync_count': 0,
                })

        return results

    def _simulate_device_sync(self, device: MockDevice, scenario: SyncTestScenario) -> Dict[str, Any]:
        """Simulate sync operations for a single device."""
        client = MockSyncClient(device)
        end_time = time.time() + scenario.duration_seconds

        sync_operations = []

        while time.time() < end_time:
            # Check if device is online
            if random.random() < device.offline_probability:
                time.sleep(1)  # Simulate offline period
                continue

            # Generate and sync data for each data type
            for data_type in scenario.data_types:
                data = client.generate_sync_data(data_type, device.data_generation_rate)

                result = client.sync_rest_endpoint(data_type, data)
                sync_operations.append({
                    'type': f'{data_type}_rest',
                    'timestamp': timezone.now().isoformat(),
                    'success': result.get('error') is None,
                    'items': len(data),
                    'result': result,
                })

            # Wait before next sync
            time.sleep(device.sync_frequency / 1000)  # Convert to seconds

        # Return device results
        return {
            'device_id': device.device_id,
            'user_id': device.user.id if device.user else None,
            'sync_operations': sync_operations,
            'statistics': client.get_sync_statistics(),
        }

    def _calculate_scenario_summary(self, device_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate summary statistics for scenario."""
        total_syncs = sum(r['statistics']['total_syncs'] for r in device_results if 'statistics' in r)
        total_errors = sum(r['statistics']['errors'] for r in device_results if 'statistics' in r)
        total_conflicts = sum(r['statistics']['conflicts'] for r in device_results if 'statistics' in r)

        return {
            'total_devices': len(device_results),
            'total_sync_operations': total_syncs,
            'total_errors': total_errors,
            'total_conflicts': total_conflicts,
            'overall_success_rate': (total_syncs - total_errors) / max(total_syncs, 1) * 100,
            'conflict_rate': total_conflicts / max(total_syncs, 1) * 100,
        }

    def _run_scenario_assertions(self, scenario: SyncTestScenario, results: List[Dict[str, Any]]) -> bool:
        """Run scenario-specific assertions."""
        try:
            for assertion in scenario.assertions:
                if not assertion(results):
                    return False
            return True
        except Exception as e:  # OK: Test framework - catch all exceptions for reporting
            logger.error(f"Assertion error: {e}")
            return False

    def create_default_scenarios(self, users: List[User]) -> None:
        """Create default test scenarios."""
        # Scenario 1: Basic sync operations
        devices = self.create_mock_devices(5, users)
        basic_scenario = SyncTestScenario(
            name='basic_sync',
            description='Basic sync operations with minimal conflicts',
            devices=devices,
            duration_seconds=30,
            conflict_rate=0.05,
            data_types=['task', 'ticket'],
        )
        self.register_scenario(basic_scenario)

        # Scenario 2: High conflict scenario
        conflict_devices = self.create_mock_devices(3, users)
        for device in conflict_devices:
            device.conflict_probability = 0.3  # High conflict rate

        conflict_scenario = SyncTestScenario(
            name='high_conflict',
            description='High conflict rate scenario',
            devices=conflict_devices,
            duration_seconds=20,
            conflict_rate=0.3,
            data_types=['task'],
        )
        self.register_scenario(conflict_scenario)

        # Scenario 3: Network issues
        network_devices = self.create_mock_devices(4, users)
        for device in network_devices:
            device.network_quality = 'poor'
            device.offline_probability = 0.3

        network_scenario = SyncTestScenario(
            name='network_issues',
            description='Poor network conditions with intermittent connectivity',
            devices=network_devices,
            duration_seconds=25,
            network_issues=True,
            data_types=['voice', 'task'],
        )
        self.register_scenario(network_scenario)


# Global instance
sync_test_framework = SyncTestFramework()
