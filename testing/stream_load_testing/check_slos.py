#!/usr/bin/env python3
"""
SLO (Service Level Objective) Validation Script
Validates test results against defined performance SLOs
"""

import json
import sys
import argparse
from pathlib import Path
from typing import Dict, Any, List


class SLOChecker:
    """
    Validates test results against Service Level Objectives
    """

    def __init__(self):
        self.default_slos = {
            'websocket': {
                'max_error_rate': 0.01,        # 1% max error rate
                'max_p95_latency_ms': 100,     # 100ms max P95 latency
                'max_p99_latency_ms': 200,     # 200ms max P99 latency
                'min_success_rate': 0.99,      # 99% min success rate
                'min_throughput_qps': 10,      # 10 QPS minimum
                'max_connection_errors': 0.05   # 5% max connection error rate
            },
            'mqtt': {
                'max_error_rate': 0.02,        # 2% max error rate
                'max_p95_latency_ms': 200,     # 200ms max P95 latency
                'max_p99_latency_ms': 500,     # 500ms max P99 latency
                'min_success_rate': 0.98,      # 98% min success rate
                'min_throughput_qps': 5,       # 5 QPS minimum
                'max_connection_errors': 0.1   # 10% max connection error rate
            },
            'http': {
                'max_error_rate': 0.005,       # 0.5% max error rate
                'max_p95_latency_ms': 300,     # 300ms max P95 latency
                'max_p99_latency_ms': 1000,    # 1000ms max P99 latency
                'min_success_rate': 0.995,     # 99.5% min success rate
                'min_throughput_qps': 20,      # 20 QPS minimum
            },
            'overall': {
                'max_total_anomalies': 5,      # Max 5 anomalies per test
                'max_critical_anomalies': 0,   # No critical anomalies allowed
                'min_test_duration': 10,       # Minimum test duration
                'max_memory_usage_mb': 1000    # Max memory usage during test
            }
        }

    def load_results(self, results_file: Path) -> List[Dict[str, Any]]:
        """Load test results from JSON file"""
        try:
            with open(results_file, 'r') as f:
                data = json.load(f)

            # Handle both single result and list of results
            if isinstance(data, dict):
                if 'scenarioName' in data:
                    # Single test result
                    return [data]
                else:
                    # Results wrapper
                    return data.get('results', [data])
            elif isinstance(data, list):
                return data
            else:
                raise ValueError(f"Invalid results format in {results_file}")

        except FileNotFoundError:
            print(f"❌ Results file not found: {results_file}")
            return []
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in results file: {e}")
            return []
        except Exception as e:
            print(f"❌ Error loading results: {e}")
            return []

    def determine_protocol(self, result: Dict[str, Any]) -> str:
        """Determine protocol from test result"""
        scenario_name = result.get('scenarioName', '').lower()

        if 'websocket' in scenario_name or 'ws' in scenario_name:
            return 'websocket'
        elif 'mqtt' in scenario_name:
            return 'mqtt'
        elif 'http' in scenario_name or 'rest' in scenario_name:
            return 'http'
        else:
            # Default to websocket for unknown
            return 'websocket'

    def validate_result(self, result: Dict[str, Any], custom_slos: Dict[str, Any] = None) -> Dict[str, Any]:
        """Validate a single test result against SLOs"""
        protocol = self.determine_protocol(result)
        slos = custom_slos or self.default_slos.get(protocol, self.default_slos['websocket'])

        violations = []
        warnings = []

        # Extract metrics from result
        error_rate = result.get('errorRate', 0)
        p95_latency = result.get('p95LatencyMs', 0)
        p99_latency = result.get('p99LatencyMs', 0)
        success_rate = 1 - error_rate  # Calculate from error rate
        throughput = result.get('throughputQps', 0)
        total_messages = result.get('totalMessages', 0)
        anomalies = result.get('anomaliesDetected', 0)

        # Check error rate
        if error_rate > slos.get('max_error_rate', 1.0):
            violations.append(
                f"Error rate {error_rate:.1%} exceeds SLO {slos['max_error_rate']:.1%}"
            )

        # Check P95 latency
        if p95_latency > slos.get('max_p95_latency_ms', float('inf')):
            violations.append(
                f"P95 latency {p95_latency:.1f}ms exceeds SLO {slos['max_p95_latency_ms']}ms"
            )

        # Check P99 latency
        if p99_latency > slos.get('max_p99_latency_ms', float('inf')):
            violations.append(
                f"P99 latency {p99_latency:.1f}ms exceeds SLO {slos['max_p99_latency_ms']}ms"
            )

        # Check success rate
        if success_rate < slos.get('min_success_rate', 0):
            violations.append(
                f"Success rate {success_rate:.1%} below SLO {slos['min_success_rate']:.1%}"
            )

        # Check throughput
        if throughput < slos.get('min_throughput_qps', 0):
            violations.append(
                f"Throughput {throughput:.2f} QPS below SLO {slos['min_throughput_qps']} QPS"
            )

        # Check anomalies
        max_anomalies = slos.get('max_total_anomalies', float('inf'))
        if anomalies > max_anomalies:
            violations.append(
                f"Anomalies {anomalies} exceeds SLO {max_anomalies}"
            )

        # Warnings for borderline performance
        if error_rate > slos.get('max_error_rate', 1.0) * 0.5:
            warnings.append(f"Error rate {error_rate:.1%} approaching SLO threshold")

        if p95_latency > slos.get('max_p95_latency_ms', float('inf')) * 0.8:
            warnings.append(f"P95 latency {p95_latency:.1f}ms approaching SLO threshold")

        return {
            'protocol': protocol,
            'slo_violations': violations,
            'warnings': warnings,
            'passed': len(violations) == 0,
            'metrics': {
                'error_rate': error_rate,
                'p95_latency_ms': p95_latency,
                'p99_latency_ms': p99_latency,
                'success_rate': success_rate,
                'throughput_qps': throughput,
                'total_messages': total_messages,
                'anomalies_detected': anomalies
            }
        }

    def validate_all_results(self, results: List[Dict[str, Any]],
                           custom_slos: Dict[str, Any] = None) -> bool:
        """Validate all test results"""
        print("🎯 Validating SLOs...")
        print("=" * 30)

        all_passed = True
        total_violations = 0

        for i, result in enumerate(results):
            scenario_name = result.get('scenarioName', f'Test {i+1}')
            print(f"\n📊 {scenario_name}:")

            validation = self.validate_result(result, custom_slos)

            # Print metrics
            metrics = validation['metrics']
            print(f"   Protocol: {validation['protocol']}")
            print(f"   Messages: {metrics['total_messages']:,}")
            print(f"   Success Rate: {metrics['success_rate']:.1%}")
            print(f"   Error Rate: {metrics['error_rate']:.1%}")
            print(f"   P95 Latency: {metrics['p95_latency_ms']:.1f}ms")
            print(f"   Throughput: {metrics['throughput_qps']:.2f} QPS")

            # Print violations
            if validation['slo_violations']:
                print(f"   ❌ SLO Violations:")
                for violation in validation['slo_violations']:
                    print(f"      • {violation}")
                all_passed = False
                total_violations += len(validation['slo_violations'])
            else:
                print(f"   ✅ All SLOs met")

            # Print warnings
            if validation['warnings']:
                print(f"   ⚠️  Warnings:")
                for warning in validation['warnings']:
                    print(f"      • {warning}")

        # Overall summary
        print(f"\n{'='*50}")
        print(f"🏆 SLO Validation Summary:")
        print(f"   Tests: {len(results)}")
        print(f"   Passed: {sum(1 for r in results if self.validate_result(r)['passed'])}")
        print(f"   Failed: {sum(1 for r in results if not self.validate_result(r)['passed'])}")
        print(f"   Total Violations: {total_violations}")

        if all_passed:
            print("✅ ALL SLOs MET - Performance is acceptable")
        else:
            print("❌ SLO VIOLATIONS DETECTED - Performance needs improvement")

        return all_passed


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(description='Validate Stream Testbench SLOs')

    parser.add_argument(
        'results_file',
        type=Path,
        help='JSON file containing test results'
    )

    parser.add_argument(
        '--max-error-rate',
        type=float,
        help='Maximum allowed error rate (0.0 to 1.0)'
    )

    parser.add_argument(
        '--max-p95-latency',
        type=float,
        help='Maximum allowed P95 latency in milliseconds'
    )

    parser.add_argument(
        '--min-throughput',
        type=float,
        help='Minimum required throughput in QPS'
    )

    parser.add_argument(
        '--protocol',
        choices=['websocket', 'mqtt', 'http'],
        help='Override protocol detection'
    )

    parser.add_argument(
        '--fail-on-warnings',
        action='store_true',
        help='Treat warnings as failures'
    )

    args = parser.parse_args()

    # Create SLO checker
    checker = SLOChecker()

    # Load results
    results = checker.load_results(args.results_file)
    if not results:
        print("❌ No valid results found")
        sys.exit(1)

    # Build custom SLOs from command line arguments
    custom_slos = {}
    if args.max_error_rate is not None:
        custom_slos['max_error_rate'] = args.max_error_rate
    if args.max_p95_latency is not None:
        custom_slos['max_p95_latency_ms'] = args.max_p95_latency
    if args.min_throughput is not None:
        custom_slos['min_throughput_qps'] = args.min_throughput

    # Validate results
    all_passed = checker.validate_all_results(results, custom_slos if custom_slos else None)

    # Check warnings if requested
    if args.fail_on_warnings:
        has_warnings = any(
            checker.validate_result(result)['warnings']
            for result in results
        )
        if has_warnings:
            print("\n⚠️  Treating warnings as failures")
            all_passed = False

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()