"""
NOC Load Testing Script.

Tests NOC dashboard under concurrent user load using asyncio and aiohttp.
Run: python -m pytest tests/noc/load_test.py -v
"""

import asyncio
import aiohttp
import time
import statistics
from typing import List, Dict

BASE_URL = "http://localhost:8000"


class NOCLoadTester:
    """Load tester for NOC dashboard."""

    def __init__(self, num_users: int = 100):
        self.num_users = num_users
        self.results: List[Dict] = []

    async def simulate_user(self, session: aiohttp.ClientSession, user_id: int):
        """Simulate single NOC user session."""
        user_results = []

        try:
            start = time.time()
            async with session.get(f'{BASE_URL}/api/noc/overview/') as resp:
                assert resp.status == 200
                duration = time.time() - start
                user_results.append({'endpoint': 'overview', 'duration': duration})

            start = time.time()
            async with session.get(f'{BASE_URL}/api/noc/map-data/') as resp:
                assert resp.status == 200
                duration = time.time() - start
                user_results.append({'endpoint': 'map-data', 'duration': duration})

            start = time.time()
            async with session.get(f'{BASE_URL}/api/noc/alerts/') as resp:
                assert resp.status == 200
                duration = time.time() - start
                user_results.append({'endpoint': 'alerts', 'duration': duration})

        except (aiohttp.ClientError, AssertionError) as e:
            user_results.append({'error': str(e)})

        return user_results

    async def run_load_test(self):
        """Execute load test with concurrent users."""
        async with aiohttp.ClientSession() as session:
            tasks = [
                self.simulate_user(session, i)
                for i in range(self.num_users)
            ]

            start_time = time.time()
            results = await asyncio.gather(*tasks, return_exceptions=True)
            duration = time.time() - start_time

            for result in results:
                if isinstance(result, list):
                    self.results.extend(result)

            return self.generate_report(duration)

    def generate_report(self, total_duration: float) -> Dict:
        """Generate load test report."""
        endpoint_stats = {}

        for result in self.results:
            if 'endpoint' in result:
                endpoint = result['endpoint']
                if endpoint not in endpoint_stats:
                    endpoint_stats[endpoint] = []
                endpoint_stats[endpoint].append(result['duration'])

        report = {
            'total_users': self.num_users,
            'total_duration': total_duration,
            'throughput': self.num_users / total_duration,
            'endpoints': {}
        }

        for endpoint, durations in endpoint_stats.items():
            report['endpoints'][endpoint] = {
                'count': len(durations),
                'mean': statistics.mean(durations),
                'median': statistics.median(durations),
                'p95': self._percentile(durations, 95),
                'p99': self._percentile(durations, 99),
            }

        return report

    @staticmethod
    def _percentile(data: List[float], percentile: int) -> float:
        """Calculate percentile."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]


async def test_noc_load_100_users():
    """Test NOC with 100 concurrent users."""
    tester = NOCLoadTester(num_users=100)
    report = await tester.run_load_test()

    print(f"\nLoad Test Report (100 users):")
    print(f"Total Duration: {report['total_duration']:.2f}s")
    print(f"Throughput: {report['throughput']:.2f} users/second")

    for endpoint, stats in report['endpoints'].items():
        print(f"\n{endpoint}:")
        print(f"  Mean: {stats['mean']*1000:.0f}ms")
        print(f"  P95: {stats['p95']*1000:.0f}ms")
        print(f"  P99: {stats['p99']*1000:.0f}ms")

    assert report['endpoints']['overview']['p95'] < 0.2


if __name__ == '__main__':
    asyncio.run(test_noc_load_100_users())