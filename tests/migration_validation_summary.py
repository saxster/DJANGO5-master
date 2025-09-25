#!/usr/bin/env python
"""
Migration validation summary - runs all validation checks and provides a comprehensive report.
"""

import os
import sys
import django
from pathlib import Path
from datetime import datetime
import json
import subprocess
from typing import Dict, List, Tuple
from colorama import init, Fore, Style

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'youtility.settings')
django.setup()

# Initialize colorama
init(autoreset=True)


class MigrationValidationSummary:
    """Run all validation checks and generate comprehensive report"""
    
    def __init__(self):
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'phases': {},
            'overall_status': 'unknown',
            'recommendations': []
        }
        
        self.validation_scripts = [
            {
                'name': 'Quick Check',
                'script': 'check_orm_migration.py',
                'phase': 'basic',
                'critical': True
            },
            {
                'name': 'Schema Validation',
                'script': 'tests/validate_schema.py',
                'phase': 'schema',
                'critical': True
            },
            {
                'name': 'Model Inspection',
                'script': 'tests/inspect_models.py',
                'phase': 'schema',
                'critical': False
            },
            {
                'name': 'Database Consistency',
                'script': 'tests/check_db_consistency.py',
                'phase': 'consistency',
                'critical': True
            },
            {
                'name': 'Data Integrity',
                'script': 'tests/validate_data_integrity.py',
                'phase': 'integrity',
                'critical': True
            },
            {
                'name': 'Integration Tests',
                'script': 'tests/run_integration_tests.py',
                'phase': 'testing',
                'critical': True
            }
        ]
    
    def print_header(self, text, level=1):
        """Print formatted header"""
        if level == 1:
            print(f"\n{Fore.BLUE}{'=' * 80}")
            print(f"{Fore.BLUE}{text.center(80)}")
            print(f"{Fore.BLUE}{'=' * 80}{Style.RESET_ALL}\n")
        else:
            print(f"\n{Fore.CYAN}{text}")
            print(f"{Fore.CYAN}{'-' * len(text)}{Style.RESET_ALL}")
    
    def run_validation_script(self, script_info: Dict) -> Tuple[bool, str]:
        """Run a validation script and capture results"""
        script_path = project_root / script_info['script']
        
        print(f"\nRunning {script_info['name']}...", end='', flush=True)
        
        try:
            result = subprocess.run(
                [sys.executable, str(script_path)],
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            success = result.returncode == 0
            
            if success:
                print(f" {Fore.GREEN}✓ PASSED{Style.RESET_ALL}")
            else:
                print(f" {Fore.RED}✗ FAILED{Style.RESET_ALL}")
            
            # Save output
            output_file = project_root / 'tests' / f"{script_info['name'].replace(' ', '_').lower()}_output.txt"
            with open(output_file, 'w') as f:
                f.write(f"=== {script_info['name']} Output ===\n")
                f.write(f"Exit Code: {result.returncode}\n\n")
                f.write("STDOUT:\n")
                f.write(result.stdout)
                f.write("\n\nSTDERR:\n")
                f.write(result.stderr)
            
            return success, result.stdout
            
        except subprocess.TimeoutExpired:
            print(f" {Fore.YELLOW}⚠ TIMEOUT{Style.RESET_ALL}")
            return False, "Script timed out after 5 minutes"
        except Exception as e:
            print(f" {Fore.RED}✗ ERROR: {str(e)}{Style.RESET_ALL}")
            return False, str(e)
    
    def analyze_results(self):
        """Analyze validation results and determine overall status"""
        critical_failures = 0
        total_critical = 0
        
        for phase, phase_results in self.results['phases'].items():
            for test in phase_results['tests']:
                if test['critical']:
                    total_critical += 1
                    if not test['success']:
                        critical_failures += 1
        
        if critical_failures == 0:
            self.results['overall_status'] = 'success'
        elif critical_failures < total_critical / 2:
            self.results['overall_status'] = 'partial_success'
        else:
            self.results['overall_status'] = 'failure'
        
        # Generate recommendations
        if critical_failures > 0:
            self.results['recommendations'].append(
                "Critical validation failures detected. Review failed tests before proceeding."
            )
        
        # Check specific issues
        for phase, phase_results in self.results['phases'].items():
            if phase == 'integrity':
                integrity_test = next((t for t in phase_results['tests'] if t['name'] == 'Data Integrity'), None)
                if integrity_test and not integrity_test['success']:
                    self.results['recommendations'].append(
                        "Data integrity issues found. ORM queries may not return identical results to raw SQL."
                    )
            
            elif phase == 'schema':
                schema_test = next((t for t in phase_results['tests'] if t['name'] == 'Schema Validation'), None)
                if schema_test and not schema_test['success']:
                    self.results['recommendations'].append(
                        "Schema validation failed. Check model definitions and database structure."
                    )
    
    def generate_html_report(self):
        """Generate HTML summary report"""
        html_path = project_root / 'tests' / 'migration_validation_report.html'
        
        html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Django ORM Migration Validation Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; box-shadow: 0 0 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #555; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
        .status-success {{ color: #28a745; font-weight: bold; }}
        .status-failure {{ color: #dc3545; font-weight: bold; }}
        .status-partial {{ color: #ffc107; font-weight: bold; }}
        .phase {{ margin: 20px 0; padding: 15px; background-color: #f8f9fa; border-radius: 5px; }}
        .test-result {{ margin: 10px 0; padding: 10px; background-color: white; border-left: 4px solid #ddd; }}
        .test-success {{ border-left-color: #28a745; }}
        .test-failure {{ border-left-color: #dc3545; }}
        .recommendations {{ background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; margin: 20px 0; border-radius: 5px; }}
        .summary-box {{ display: flex; justify-content: space-around; margin: 20px 0; }}
        .summary-item {{ text-align: center; padding: 20px; background-color: #f8f9fa; border-radius: 5px; flex: 1; margin: 0 10px; }}
        .summary-number {{ font-size: 36px; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #f8f9fa; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Django ORM Migration Validation Report</h1>
        <p style="text-align: center; color: #666;">Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        
        <h2>Overall Status: <span class="status-{self.results['overall_status']}">{self.results['overall_status'].upper()}</span></h2>
        
        <div class="summary-box">
            <div class="summary-item">
                <div class="summary-number">{sum(len(p['tests']) for p in self.results['phases'].values())}</div>
                <div>Total Tests</div>
            </div>
            <div class="summary-item">
                <div class="summary-number" style="color: #28a745;">
                    {sum(1 for p in self.results['phases'].values() for t in p['tests'] if t['success'])}
                </div>
                <div>Passed</div>
            </div>
            <div class="summary-item">
                <div class="summary-number" style="color: #dc3545;">
                    {sum(1 for p in self.results['phases'].values() for t in p['tests'] if not t['success'])}
                </div>
                <div>Failed</div>
            </div>
        </div>
"""
        
        # Add recommendations if any
        if self.results['recommendations']:
            html_content += """
        <div class="recommendations">
            <h3>Recommendations</h3>
            <ul>
"""
            for rec in self.results['recommendations']:
                html_content += f"                <li>{rec}</li>\n"
            html_content += """
            </ul>
        </div>
"""
        
        # Add phase results
        for phase_name, phase_data in self.results['phases'].items():
            html_content += f"""
        <div class="phase">
            <h2>{phase_name.replace('_', ' ').title()}</h2>
"""
            for test in phase_data['tests']:
                status_class = 'test-success' if test['success'] else 'test-failure'
                status_icon = '✓' if test['success'] else '✗'
                critical_badge = '<span style="color: #dc3545; font-size: 12px;">[CRITICAL]</span>' if test['critical'] else ''
                
                html_content += f"""
            <div class="test-result {status_class}">
                <strong>{status_icon} {test['name']}</strong> {critical_badge}
                <div style="color: #666; font-size: 14px; margin-top: 5px;">
                    Duration: {test.get('duration', 'N/A')}
                </div>
            </div>
"""
            html_content += """
        </div>
"""
        
        # Add detailed results table
        html_content += """
        <h2>Detailed Test Results</h2>
        <table>
            <tr>
                <th>Phase</th>
                <th>Test</th>
                <th>Status</th>
                <th>Critical</th>
                <th>Output File</th>
            </tr>
"""
        
        for phase_name, phase_data in self.results['phases'].items():
            for test in phase_data['tests']:
                status_style = 'color: #28a745;' if test['success'] else 'color: #dc3545;'
                status_text = 'PASSED' if test['success'] else 'FAILED'
                critical_text = 'Yes' if test['critical'] else 'No'
                output_file = f"{test['name'].replace(' ', '_').lower()}_output.txt"
                
                html_content += f"""
            <tr>
                <td>{phase_name.replace('_', ' ').title()}</td>
                <td>{test['name']}</td>
                <td style="{status_style}">{status_text}</td>
                <td>{critical_text}</td>
                <td><a href="{output_file}">{output_file}</a></td>
            </tr>
"""
        
        html_content += """
        </table>
        
        <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; color: #666;">
            <p>Django ORM Migration Validation Suite</p>
            <p>For detailed logs, check the individual output files in the tests directory.</p>
        </div>
    </div>
</body>
</html>
"""
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        print(f"\nHTML report generated: {html_path}")
    
    def run_all_validations(self):
        """Run all validation checks"""
        self.print_header("DJANGO ORM MIGRATION VALIDATION SUITE", 1)
        
        print(f"Running comprehensive validation checks...")
        print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        
        # Group tests by phase
        phases = {}
        for script in self.validation_scripts:
            phase = script['phase']
            if phase not in phases:
                phases[phase] = []
            phases[phase].append(script)
        
        # Run tests by phase
        for phase_name, phase_scripts in phases.items():
            self.print_header(f"Phase: {phase_name.upper()}", 2)
            
            phase_results = {
                'name': phase_name,
                'tests': [],
                'start_time': datetime.now()
            }
            
            for script in phase_scripts:
                start_time = datetime.now()
                success, output = self.run_validation_script(script)
                duration = (datetime.now() - start_time).total_seconds()
                
                phase_results['tests'].append({
                    'name': script['name'],
                    'success': success,
                    'critical': script['critical'],
                    'duration': f"{duration:.2f}s"
                })
            
            phase_results['end_time'] = datetime.now()
            phase_results['total_duration'] = (
                phase_results['end_time'] - phase_results['start_time']
            ).total_seconds()
            
            self.results['phases'][phase_name] = phase_results
        
        # Analyze results
        self.analyze_results()
        
        # Generate reports
        self.print_header("VALIDATION SUMMARY", 1)
        
        # Print summary
        total_tests = sum(len(p['tests']) for p in self.results['phases'].values())
        passed_tests = sum(1 for p in self.results['phases'].values() for t in p['tests'] if t['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests Run: {total_tests}")
        print(f"Passed: {Fore.GREEN}{passed_tests}{Style.RESET_ALL}")
        print(f"Failed: {Fore.RED}{failed_tests}{Style.RESET_ALL}")
        
        # Overall status
        if self.results['overall_status'] == 'success':
            print(f"\nOverall Status: {Fore.GREEN}SUCCESS - All critical tests passed!{Style.RESET_ALL}")
        elif self.results['overall_status'] == 'partial_success':
            print(f"\nOverall Status: {Fore.YELLOW}PARTIAL SUCCESS - Some critical tests failed{Style.RESET_ALL}")
        else:
            print(f"\nOverall Status: {Fore.RED}FAILURE - Multiple critical tests failed{Style.RESET_ALL}")
        
        # Recommendations
        if self.results['recommendations']:
            print(f"\n{Fore.YELLOW}Recommendations:{Style.RESET_ALL}")
            for i, rec in enumerate(self.results['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        # Save JSON report
        json_path = project_root / 'tests' / 'migration_validation_summary.json'
        with open(json_path, 'w') as f:
            json.dump(self.results, f, indent=2, default=str)
        
        print(f"\nJSON report saved: {json_path}")
        
        # Generate HTML report
        self.generate_html_report()
        
        return self.results['overall_status'] == 'success'


def main():
    """Main entry point"""
    validator = MigrationValidationSummary()
    success = validator.run_all_validations()
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())