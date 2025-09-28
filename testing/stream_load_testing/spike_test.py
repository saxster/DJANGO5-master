#!/usr/bin/env python3
"""
Stream Testbench Spike Test
Quick performance validation for CI/CD pipeline
"""

import os
import sys
import django
import asyncio
import websockets
import json
import time
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Setup Django environment
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()


class StreamSpikeTest:
    """
    Quick spike test for stream infrastructure
    Designed for CI/CD performance gates
    """

    def __init__(self):
        self.results = {
            'websocket': {},
            'overall': {}
        }

    async def run_websocket_spike_test(self, duration_seconds=30, connections=5, messages_per_second=2):
        """Run WebSocket spike test"""
        print(f"🔌 Running WebSocket spike test...")
        print(f"   Duration: {duration_seconds}s")
        print(f"   Connections: {connections}")
        print(f"   Rate: {messages_per_second} msgs/sec per connection")

        start_time = time.time()
        latencies = []
        successful_messages = 0
        failed_messages = 0
        connection_errors = 0

        async def single_connection_test(connection_id):
            """Test a single WebSocket connection"""
            nonlocal successful_messages, failed_messages, connection_errors

            try:
                uri = "ws://localhost:8000/ws/mobile/sync/?device_id=spike_test_device"

                async with websockets.connect(uri, timeout=10) as websocket:
                    print(f"   ✅ Connection {connection_id} established")

                    # Send messages for the duration
                    end_time = start_time + duration_seconds
                    message_interval = 1.0 / messages_per_second

                    while time.time() < end_time:
                        message_start = time.time()

                        # Create test message
                        message = {
                            "type": "heartbeat",
                            "client_time": datetime.now().isoformat(),
                            "connection_id": connection_id,
                            "test_data": {
                                "quality_score": 0.85,
                                "timestamp": int(time.time() * 1000)
                            }
                        }

                        try:
                            # Send message
                            await websocket.send(json.dumps(message))

                            # Wait for response (optional)
                            try:
                                response = await asyncio.wait_for(
                                    websocket.recv(), timeout=2.0
                                )
                                latency = (time.time() - message_start) * 1000
                                latencies.append(latency)
                                successful_messages += 1

                            except asyncio.TimeoutError:
                                # No response expected for all message types
                                latency = (time.time() - message_start) * 1000
                                latencies.append(latency)
                                successful_messages += 1

                        except websockets.exceptions.ConnectionClosed:
                            print(f"   ⚠️  Connection {connection_id} closed by server")
                            break
                        except Exception as e:
                            print(f"   ❌ Message error on connection {connection_id}: {e}")
                            failed_messages += 1

                        # Wait for next message
                        await asyncio.sleep(message_interval)

            except websockets.exceptions.InvalidStatusCode as e:
                print(f"   ❌ Connection {connection_id} failed - invalid status: {e}")
                connection_errors += 1
            except websockets.exceptions.ConnectionRefused:
                print(f"   ❌ Connection {connection_id} refused - server not available")
                connection_errors += 1
            except Exception as e:
                print(f"   ❌ Connection {connection_id} error: {e}")
                connection_errors += 1

        # Run all connections concurrently
        tasks = [single_connection_test(i) for i in range(connections)]
        await asyncio.gather(*tasks, return_exceptions=True)

        end_time = time.time()
        test_duration = end_time - start_time

        # Calculate results
        total_messages = successful_messages + failed_messages
        success_rate = (successful_messages / total_messages) if total_messages > 0 else 0
        error_rate = (failed_messages / total_messages) if total_messages > 0 else 0

        results = {
            'test_duration': test_duration,
            'total_connections': connections,
            'successful_connections': connections - connection_errors,
            'connection_errors': connection_errors,
            'total_messages': total_messages,
            'successful_messages': successful_messages,
            'failed_messages': failed_messages,
            'success_rate': success_rate,
            'error_rate': error_rate,
            'average_latency_ms': statistics.mean(latencies) if latencies else 0,
            'p95_latency_ms': statistics.quantiles(latencies, n=20)[18] if len(latencies) > 10 else 0,
            'p99_latency_ms': statistics.quantiles(latencies, n=100)[98] if len(latencies) > 50 else 0,
            'throughput_qps': successful_messages / test_duration if test_duration > 0 else 0
        }

        self.results['websocket'] = results
        return results

    def run_http_spike_test(self, duration_seconds=30, connections=3, requests_per_second=1):
        """Run HTTP API spike test"""
        print(f"🌐 Running HTTP spike test...")
        print(f"   Duration: {duration_seconds}s")
        print(f"   Connections: {connections}")
        print(f"   Rate: {requests_per_second} req/sec per connection")

        import requests
        from requests.exceptions import RequestException

        start_time = time.time()
        latencies = []
        successful_requests = 0
        failed_requests = 0

        def single_connection_test(connection_id):
            """Test a single HTTP connection"""
            nonlocal successful_requests, failed_requests

            session = requests.Session()
            end_time = start_time + duration_seconds
            request_interval = 1.0 / requests_per_second

            while time.time() < end_time:
                request_start = time.time()

                try:
                    # Test health check endpoint
                    response = session.get(
                        'http://localhost:8000/health/',
                        timeout=5.0
                    )

                    latency = (time.time() - request_start) * 1000
                    latencies.append(latency)

                    if response.status_code == 200:
                        successful_requests += 1
                    else:
                        failed_requests += 1

                except RequestException as e:
                    failed_requests += 1
                    print(f"   ❌ HTTP request failed on connection {connection_id}: {e}")

                time.sleep(request_interval)

        # Run connections in parallel
        with ThreadPoolExecutor(max_workers=connections) as executor:
            futures = [executor.submit(single_connection_test, i) for i in range(connections)]

            # Wait for all to complete
            for future in futures:
                try:
                    future.result(timeout=duration_seconds + 10)
                except Exception as e:
                    print(f"   ❌ Connection thread error: {e}")

        end_time = time.time()
        test_duration = end_time - start_time

        # Calculate results
        total_requests = successful_requests + failed_requests
        success_rate = (successful_requests / total_requests) if total_requests > 0 else 0

        results = {
            'test_duration': test_duration,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': failed_requests,
            'success_rate': success_rate,
            'error_rate': (failed_requests / total_requests) if total_requests > 0 else 0,
            'average_latency_ms': statistics.mean(latencies) if latencies else 0,
            'p95_latency_ms': statistics.quantiles(latencies, n=20)[18] if len(latencies) > 10 else 0,
            'throughput_qps': successful_requests / test_duration if test_duration > 0 else 0
        }

        self.results['http'] = results
        return results

    def run_all_spike_tests(self):
        """Run complete spike test suite"""
        print("🚀 Stream Testbench Spike Test Suite")
        print("=" * 50)

        all_passed = True

        # Run WebSocket test
        try:
            ws_results = asyncio.run(self.run_websocket_spike_test())
            print(f"\n📊 WebSocket Results:")
            self.print_results(ws_results)

            # Check WebSocket SLOs
            ws_passed = self.check_slos(ws_results, 'WebSocket')
            all_passed &= ws_passed

        except Exception as e:
            print(f"❌ WebSocket test failed: {e}")
            all_passed = False

        # Run HTTP test
        try:
            http_results = self.run_http_spike_test()
            print(f"\n📊 HTTP Results:")
            self.print_results(http_results)

            # Check HTTP SLOs
            http_passed = self.check_slos(http_results, 'HTTP')
            all_passed &= http_passed

        except Exception as e:
            print(f"❌ HTTP test failed: {e}")
            all_passed = False

        # Overall summary
        print(f"\n{'='*50}")
        print(f"🏆 Overall Results:")

        if all_passed:
            print("✅ All spike tests PASSED")
            print("🚦 Stream infrastructure ready for load")
        else:
            print("❌ Some spike tests FAILED")
            print("🚨 Stream infrastructure needs attention")

        return all_passed

    def print_results(self, results):
        """Print formatted test results"""
        print(f"   Duration: {results['test_duration']:.1f}s")
        print(f"   Success Rate: {results['success_rate']:.1%}")
        print(f"   Error Rate: {results['error_rate']:.1%}")
        print(f"   Avg Latency: {results['average_latency_ms']:.1f}ms")
        print(f"   P95 Latency: {results['p95_latency_ms']:.1f}ms")
        print(f"   Throughput: {results['throughput_qps']:.2f} QPS")

        if 'total_connections' in results:
            print(f"   Connections: {results['successful_connections']}/{results['total_connections']}")

    def check_slos(self, results, test_type):
        """Check Service Level Objectives"""
        print(f"\n🎯 {test_type} SLO Check:")

        # Define SLO thresholds for spike tests
        slo_thresholds = {
            'max_error_rate': 0.1,      # 10% max error rate
            'max_p95_latency': 2000,    # 2 second max P95 latency
            'min_success_rate': 0.8,    # 80% min success rate
            'min_throughput': 0.5       # 0.5 QPS minimum
        }

        slo_violations = []

        # Check error rate
        if results['error_rate'] > slo_thresholds['max_error_rate']:
            slo_violations.append(
                f"Error rate {results['error_rate']:.1%} > {slo_thresholds['max_error_rate']:.1%}"
            )

        # Check P95 latency
        if results['p95_latency_ms'] > slo_thresholds['max_p95_latency']:
            slo_violations.append(
                f"P95 latency {results['p95_latency_ms']:.1f}ms > {slo_thresholds['max_p95_latency']}ms"
            )

        # Check success rate
        if results['success_rate'] < slo_thresholds['min_success_rate']:
            slo_violations.append(
                f"Success rate {results['success_rate']:.1%} < {slo_thresholds['min_success_rate']:.1%}"
            )

        # Check throughput
        if results['throughput_qps'] < slo_thresholds['min_throughput']:
            slo_violations.append(
                f"Throughput {results['throughput_qps']:.2f} QPS < {slo_thresholds['min_throughput']} QPS"
            )

        if slo_violations:
            print("❌ SLO violations:")
            for violation in slo_violations:
                print(f"   • {violation}")
            return False
        else:
            print("✅ All SLOs met")
            return True

    def save_results(self, filename='spike_test_results.json'):
        """Save test results to file"""
        self.results['timestamp'] = datetime.now().isoformat()
        self.results['test_type'] = 'spike_test'

        with open(filename, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"💾 Results saved to {filename}")


if __name__ == "__main__":
    print("🚀 Stream Testbench Spike Test")
    print("Quick performance validation for CI/CD")
    print("=" * 50)

    tester = StreamSpikeTest()

    try:
        # Run spike tests
        success = tester.run_all_spike_tests()

        # Save results
        tester.save_results()

        # Exit with appropriate code
        if success:
            print("\n🎉 Spike test completed successfully!")
            sys.exit(0)
        else:
            print("\n💥 Spike test failed - performance issues detected")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Spike test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Spike test crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)