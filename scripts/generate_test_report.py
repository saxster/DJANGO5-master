#!/usr/bin/env python
"""
AI Features Test Report Generator
Generates comprehensive HTML and PDF reports from test results
"""

import os
import sys
import json
import argparse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

import jinja2


@dataclass
class TestSuite:
    """Test suite result data"""
    name: str
    tests: int
    failures: int
    errors: int
    skipped: int
    time: float
    test_cases: List[Dict]


@dataclass
class CoverageReport:
    """Code coverage data"""
    lines_total: int
    lines_covered: int
    coverage_percent: float
    modules: Dict[str, Dict]


@dataclass
class SecurityReport:
    """Security scan results"""
    total_issues: int
    high_severity: int
    medium_severity: int
    low_severity: int
    tools_run: List[str]
    detailed_findings: List[Dict]


@dataclass
class PerformanceReport:
    """Performance benchmark results"""
    total_benchmarks: int
    average_duration: float
    slowest_operations: List[Dict]
    resource_usage: Dict


class TestReportGenerator:
    """Generate comprehensive test reports"""
    
    def __init__(self, reports_dir: str = "test_reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        
        # Setup Jinja2 environment
        self.jinja_env = jinja2.Environment(
            loader=jinja2.DictLoader(self._get_templates()),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
    
    def generate_comprehensive_report(
        self,
        junit_xml: Optional[str] = None,
        coverage_xml: Optional[str] = None,
        security_json: Optional[str] = None,
        performance_json: Optional[str] = None,
        output_format: str = 'html'
    ) -> str:
        """
        Generate comprehensive test report from various input files
        
        Args:
            junit_xml: Path to JUnit XML results file
            coverage_xml: Path to coverage XML file
            security_json: Path to security scan JSON file
            performance_json: Path to performance benchmark JSON file
            output_format: Output format ('html', 'pdf', 'json')
            
        Returns:
            Path to generated report file
        """
        print("🔄 Generating comprehensive test report...")
        
        # Parse input files
        test_results = self._parse_junit_xml(junit_xml) if junit_xml else []
        coverage_data = self._parse_coverage_xml(coverage_xml) if coverage_xml else None
        security_data = self._parse_security_json(security_json) if security_json else None
        performance_data = self._parse_performance_json(performance_json) if performance_json else None
        
        # Generate report data
        report_data = {
            'metadata': {
                'generated_at': datetime.now(),
                'generator': 'AI Features Test Report Generator',
                'version': '1.0.0'
            },
            'test_results': test_results,
            'coverage': coverage_data,
            'security': security_data,
            'performance': performance_data,
            'summary': self._generate_summary(test_results, coverage_data, security_data, performance_data)
        }
        
        # Generate output
        if output_format == 'html':
            return self._generate_html_report(report_data)
        elif output_format == 'json':
            return self._generate_json_report(report_data)
        elif output_format == 'pdf':
            return self._generate_pdf_report(report_data)
        else:
            raise ValueError(f"Unsupported output format: {output_format}")
    
    def _parse_junit_xml(self, junit_file: str) -> List[TestSuite]:
        """Parse JUnit XML test results"""
        if not os.path.exists(junit_file):
            print(f"⚠️ JUnit XML file not found: {junit_file}")
            return []
        
        try:
            tree = ET.parse(junit_file)
            root = tree.getroot()
            
            test_suites = []
            
            # Handle both <testsuite> and <testsuites> root elements
            suites = root.findall('.//testsuite')
            if not suites:
                suites = [root] if root.tag == 'testsuite' else []
            
            for suite in suites:
                test_cases = []
                
                for case in suite.findall('testcase'):
                    test_case = {
                        'name': case.get('name', ''),
                        'classname': case.get('classname', ''),
                        'time': float(case.get('time', 0)),
                        'status': 'passed'
                    }
                    
                    # Check for failures, errors, or skips
                    if case.find('failure') is not None:
                        test_case['status'] = 'failed'
                        failure = case.find('failure')
                        test_case['message'] = failure.get('message', '')
                        test_case['details'] = failure.text or ''
                    elif case.find('error') is not None:
                        test_case['status'] = 'error'
                        error = case.find('error')
                        test_case['message'] = error.get('message', '')
                        test_case['details'] = error.text or ''
                    elif case.find('skipped') is not None:
                        test_case['status'] = 'skipped'
                        skipped = case.find('skipped')
                        test_case['message'] = skipped.get('message', '')
                    
                    test_cases.append(test_case)
                
                suite_data = TestSuite(
                    name=suite.get('name', 'Unknown'),
                    tests=int(suite.get('tests', 0)),
                    failures=int(suite.get('failures', 0)),
                    errors=int(suite.get('errors', 0)),
                    skipped=int(suite.get('skipped', 0)),
                    time=float(suite.get('time', 0)),
                    test_cases=test_cases
                )
                
                test_suites.append(suite_data)
            
            print(f"✅ Parsed {len(test_suites)} test suites from JUnit XML")
            return test_suites
            
        except ET.ParseError as e:
            print(f"❌ Error parsing JUnit XML: {e}")
            return []
    
    def _parse_coverage_xml(self, coverage_file: str) -> Optional[CoverageReport]:
        """Parse coverage XML report"""
        if not os.path.exists(coverage_file):
            print(f"⚠️ Coverage XML file not found: {coverage_file}")
            return None
        
        try:
            tree = ET.parse(coverage_file)
            root = tree.getroot()
            
            # Extract overall coverage
            coverage_elem = root.find('.//coverage')
            if coverage_elem is not None:
                lines_total = int(coverage_elem.get('lines-valid', 0))
                lines_covered = int(coverage_elem.get('lines-covered', 0))
                coverage_percent = (lines_covered / lines_total * 100) if lines_total > 0 else 0
            else:
                # Try alternative format
                lines_total = 0
                lines_covered = 0
                for package in root.findall('.//package'):
                    for cls in package.findall('.//class'):
                        for line in cls.findall('.//line'):
                            lines_total += 1
                            if line.get('hits', '0') != '0':
                                lines_covered += 1
                coverage_percent = (lines_covered / lines_total * 100) if lines_total > 0 else 0
            
            # Extract module-level coverage
            modules = {}
            for package in root.findall('.//package'):
                package_name = package.get('name', 'unknown')
                for cls in package.findall('.//class'):
                    class_name = cls.get('name', 'unknown')
                    class_lines = len(cls.findall('.//line'))
                    class_covered = len([l for l in cls.findall('.//line') if l.get('hits', '0') != '0'])
                    
                    modules[f"{package_name}.{class_name}"] = {
                        'lines_total': class_lines,
                        'lines_covered': class_covered,
                        'coverage_percent': (class_covered / class_lines * 100) if class_lines > 0 else 0
                    }
            
            coverage_data = CoverageReport(
                lines_total=lines_total,
                lines_covered=lines_covered,
                coverage_percent=coverage_percent,
                modules=modules
            )
            
            print(f"✅ Parsed coverage data: {coverage_percent:.1f}% coverage")
            return coverage_data
            
        except ET.ParseError as e:
            print(f"❌ Error parsing coverage XML: {e}")
            return None
    
    def _parse_security_json(self, security_file: str) -> Optional[SecurityReport]:
        """Parse security scan JSON results"""
        if not os.path.exists(security_file):
            print(f"⚠️ Security JSON file not found: {security_file}")
            return None
        
        try:
            with open(security_file, 'r') as f:
                data = json.load(f)
            
            # Handle different security report formats
            if 'results' in data:  # Bandit format
                findings = data['results']
                total_issues = len(findings)
                high_severity = len([f for f in findings if f.get('issue_severity') == 'HIGH'])
                medium_severity = len([f for f in findings if f.get('issue_severity') == 'MEDIUM'])
                low_severity = len([f for f in findings if f.get('issue_severity') == 'LOW'])
                tools_run = ['Bandit']
            elif 'vulnerabilities' in data:  # Safety format
                findings = data['vulnerabilities']
                total_issues = len(findings)
                high_severity = len([f for f in findings if f.get('severity', '').lower() == 'high'])
                medium_severity = len([f for f in findings if f.get('severity', '').lower() == 'medium'])
                low_severity = len([f for f in findings if f.get('severity', '').lower() == 'low'])
                tools_run = ['Safety']
            else:  # Combined format
                total_issues = data.get('total_issues', 0)
                high_severity = data.get('high_severity', 0)
                medium_severity = data.get('medium_severity', 0)
                low_severity = data.get('low_severity', 0)
                tools_run = data.get('tools_run', [])
                findings = data.get('detailed_findings', [])
            
            security_data = SecurityReport(
                total_issues=total_issues,
                high_severity=high_severity,
                medium_severity=medium_severity,
                low_severity=low_severity,
                tools_run=tools_run,
                detailed_findings=findings
            )
            
            print(f"✅ Parsed security data: {total_issues} total issues")
            return security_data
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ Error parsing security JSON: {e}")
            return None
    
    def _parse_performance_json(self, performance_file: str) -> Optional[PerformanceReport]:
        """Parse performance benchmark JSON results"""
        if not os.path.exists(performance_file):
            print(f"⚠️ Performance JSON file not found: {performance_file}")
            return None
        
        try:
            with open(performance_file, 'r') as f:
                data = json.load(f)
            
            benchmarks = data.get('benchmarks', [])
            total_benchmarks = len(benchmarks)
            
            if benchmarks:
                total_duration = sum(b.get('stats', {}).get('mean', 0) for b in benchmarks)
                average_duration = total_duration / total_benchmarks
                
                # Sort by mean duration to get slowest operations
                sorted_benchmarks = sorted(
                    benchmarks, 
                    key=lambda x: x.get('stats', {}).get('mean', 0), 
                    reverse=True
                )
                
                slowest_operations = []
                for bench in sorted_benchmarks[:10]:  # Top 10 slowest
                    stats = bench.get('stats', {})
                    slowest_operations.append({
                        'name': bench.get('name', 'Unknown'),
                        'mean_duration': stats.get('mean', 0),
                        'stddev': stats.get('stddev', 0),
                        'min_duration': stats.get('min', 0),
                        'max_duration': stats.get('max', 0)
                    })
            else:
                average_duration = 0
                slowest_operations = []
            
            # Extract resource usage if available
            resource_usage = data.get('resource_usage', {})
            
            performance_data = PerformanceReport(
                total_benchmarks=total_benchmarks,
                average_duration=average_duration,
                slowest_operations=slowest_operations,
                resource_usage=resource_usage
            )
            
            print(f"✅ Parsed performance data: {total_benchmarks} benchmarks")
            return performance_data
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"❌ Error parsing performance JSON: {e}")
            return None
    
    def _generate_summary(
        self, 
        test_results: List[TestSuite],
        coverage_data: Optional[CoverageReport],
        security_data: Optional[SecurityReport],
        performance_data: Optional[PerformanceReport]
    ) -> Dict:
        """Generate overall test summary"""
        summary = {
            'total_tests': 0,
            'passed_tests': 0,
            'failed_tests': 0,
            'error_tests': 0,
            'skipped_tests': 0,
            'total_duration': 0,
            'pass_rate': 0,
            'coverage_percent': 0,
            'security_issues': 0,
            'performance_benchmarks': 0,
            'status': 'unknown'
        }
        
        # Aggregate test results
        for suite in test_results:
            summary['total_tests'] += suite.tests
            summary['failed_tests'] += suite.failures
            summary['error_tests'] += suite.errors  
            summary['skipped_tests'] += suite.skipped
            summary['total_duration'] += suite.time
        
        summary['passed_tests'] = (
            summary['total_tests'] - 
            summary['failed_tests'] - 
            summary['error_tests'] - 
            summary['skipped_tests']
        )
        
        if summary['total_tests'] > 0:
            summary['pass_rate'] = (summary['passed_tests'] / summary['total_tests']) * 100
        
        # Add coverage data
        if coverage_data:
            summary['coverage_percent'] = coverage_data.coverage_percent
        
        # Add security data
        if security_data:
            summary['security_issues'] = security_data.total_issues
        
        # Add performance data
        if performance_data:
            summary['performance_benchmarks'] = performance_data.total_benchmarks
        
        # Determine overall status
        if summary['failed_tests'] > 0 or summary['error_tests'] > 0:
            summary['status'] = 'failed'
        elif security_data and security_data.high_severity > 0:
            summary['status'] = 'warning'
        elif summary['total_tests'] > 0:
            summary['status'] = 'passed'
        else:
            summary['status'] = 'no_tests'
        
        return summary
    
    def _generate_html_report(self, report_data: Dict) -> str:
        """Generate HTML report"""
        template = self.jinja_env.get_template('html_report')
        html_content = template.render(**report_data)
        
        output_file = self.reports_dir / f"ai_features_report_{int(datetime.now().timestamp())}.html"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"✅ HTML report generated: {output_file}")
        return str(output_file)
    
    def _generate_json_report(self, report_data: Dict) -> str:
        """Generate JSON report"""
        # Convert dataclasses to dicts for JSON serialization
        json_data = self._serialize_for_json(report_data)
        
        output_file = self.reports_dir / f"ai_features_report_{int(datetime.now().timestamp())}.json"
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, default=str)
        
        print(f"✅ JSON report generated: {output_file}")
        return str(output_file)
    
    def _generate_pdf_report(self, report_data: Dict) -> str:
        """Generate PDF report (requires additional dependencies)"""
        try:
            import weasyprint
        except ImportError:
            print("⚠️ weasyprint not installed, generating HTML instead of PDF")
            return self._generate_html_report(report_data)
        
        # First generate HTML
        template = self.jinja_env.get_template('html_report')
        html_content = template.render(**report_data)
        
        # Convert to PDF
        output_file = self.reports_dir / f"ai_features_report_{int(datetime.now().timestamp())}.pdf"
        
        html_doc = weasyprint.HTML(string=html_content)
        html_doc.write_pdf(output_file)
        
        print(f"✅ PDF report generated: {output_file}")
        return str(output_file)
    
    def _serialize_for_json(self, obj) -> Any:
        """Convert dataclasses and other objects to JSON-serializable format"""
        if hasattr(obj, '__dataclass_fields__'):
            return {k: self._serialize_for_json(v) for k, v in obj.__dict__.items()}
        elif isinstance(obj, dict):
            return {k: self._serialize_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._serialize_for_json(item) for item in obj]
        elif isinstance(obj, datetime):
            return obj.isoformat()
        else:
            return obj
    
    def _get_templates(self) -> Dict[str, str]:
        """Get Jinja2 templates"""
        return {
            'html_report': """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Features Test Report</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0; padding: 20px; background: #f8f9fa; line-height: 1.6;
        }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 2px solid #e9ecef; }
        .header h1 { color: #2c3e50; margin: 0; font-size: 2.5em; }
        .header .subtitle { color: #6c757d; margin: 10px 0; }
        .status-badge { display: inline-block; padding: 8px 16px; border-radius: 20px; font-weight: bold; text-transform: uppercase; font-size: 0.9em; }
        .status-passed { background: #d4edda; color: #155724; }
        .status-failed { background: #f8d7da; color: #721c24; }
        .status-warning { background: #fff3cd; color: #856404; }
        .summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin: 30px 0; }
        .summary-card { background: #f8f9fa; padding: 20px; border-radius: 8px; text-align: center; border-left: 4px solid #007bff; }
        .summary-card h3 { margin: 0 0 10px 0; color: #495057; font-size: 0.9em; text-transform: uppercase; }
        .summary-card .value { font-size: 2em; font-weight: bold; color: #007bff; }
        .section { margin: 40px 0; }
        .section h2 { color: #2c3e50; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .test-suite { margin: 20px 0; padding: 20px; background: #f8f9fa; border-radius: 8px; }
        .test-suite h3 { margin: 0 0 15px 0; color: #495057; }
        .test-cases { margin: 10px 0; }
        .test-case { padding: 10px; margin: 5px 0; border-radius: 5px; display: flex; justify-content: space-between; align-items: center; }
        .test-passed { background: #d4edda; color: #155724; }
        .test-failed { background: #f8d7da; color: #721c24; }
        .test-skipped { background: #e2e3e5; color: #383d41; }
        .test-error { background: #f5c6cb; color: #721c24; }
        .progress-bar { width: 100%; height: 20px; background: #e9ecef; border-radius: 10px; overflow: hidden; margin: 10px 0; }
        .progress-fill { height: 100%; background: linear-gradient(90deg, #28a745, #20c997); transition: width 0.3s ease; }
        .coverage-module { display: flex; justify-content: space-between; padding: 8px; border-bottom: 1px solid #dee2e6; }
        .security-finding { padding: 15px; margin: 10px 0; border-radius: 5px; border-left: 4px solid #dc3545; }
        .security-high { background: #f8d7da; border-left-color: #dc3545; }
        .security-medium { background: #fff3cd; border-left-color: #ffc107; }
        .security-low { background: #d1ecf1; border-left-color: #17a2b8; }
        .performance-table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        .performance-table th, .performance-table td { padding: 12px; text-align: left; border-bottom: 1px solid #dee2e6; }
        .performance-table th { background: #f8f9fa; font-weight: bold; color: #495057; }
        .footer { text-align: center; margin-top: 40px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #6c757d; }
        @media (max-width: 768px) {
            .container { padding: 20px; }
            .summary-grid { grid-template-columns: 1fr; }
            .test-case { flex-direction: column; align-items: flex-start; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🧠 AI Features Test Report</h1>
            <div class="subtitle">Generated on {{ metadata.generated_at.strftime('%B %d, %Y at %I:%M %p') }}</div>
            <div class="status-badge status-{{ summary.status }}">{{ summary.status.replace('_', ' ').title() }}</div>
        </div>

        <div class="summary-grid">
            <div class="summary-card">
                <h3>Total Tests</h3>
                <div class="value">{{ summary.total_tests }}</div>
            </div>
            <div class="summary-card">
                <h3>Passed</h3>
                <div class="value" style="color: #28a745;">{{ summary.passed_tests }}</div>
            </div>
            <div class="summary-card">
                <h3>Failed</h3>
                <div class="value" style="color: #dc3545;">{{ summary.failed_tests }}</div>
            </div>
            <div class="summary-card">
                <h3>Pass Rate</h3>
                <div class="value" style="color: {% if summary.pass_rate >= 90 %}#28a745{% elif summary.pass_rate >= 70 %}#ffc107{% else %}#dc3545{% endif %};">{{ "%.1f"|format(summary.pass_rate) }}%</div>
            </div>
            {% if coverage %}
            <div class="summary-card">
                <h3>Coverage</h3>
                <div class="value" style="color: {% if coverage.coverage_percent >= 80 %}#28a745{% elif coverage.coverage_percent >= 60 %}#ffc107{% else %}#dc3545{% endif %};">{{ "%.1f"|format(coverage.coverage_percent) }}%</div>
            </div>
            {% endif %}
            {% if security %}
            <div class="summary-card">
                <h3>Security Issues</h3>
                <div class="value" style="color: {% if security.total_issues == 0 %}#28a745{% elif security.high_severity == 0 %}#ffc107{% else %}#dc3545{% endif %};">{{ security.total_issues }}</div>
            </div>
            {% endif %}
        </div>

        {% if coverage %}
        <div class="section">
            <h2>📊 Code Coverage</h2>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {{ coverage.coverage_percent }}%;"></div>
            </div>
            <p><strong>{{ coverage.lines_covered }}</strong> of <strong>{{ coverage.lines_total }}</strong> lines covered ({{ "%.1f"|format(coverage.coverage_percent) }}%)</p>
            
            {% if coverage.modules %}
            <h3>Module Coverage</h3>
            <div style="max-height: 300px; overflow-y: auto; border: 1px solid #dee2e6; border-radius: 5px;">
                {% for module, data in coverage.modules.items() %}
                <div class="coverage-module">
                    <span>{{ module }}</span>
                    <span style="font-weight: bold; color: {% if data.coverage_percent >= 80 %}#28a745{% elif data.coverage_percent >= 60 %}#ffc107{% else %}#dc3545{% endif %};">{{ "%.1f"|format(data.coverage_percent) }}%</span>
                </div>
                {% endfor %}
            </div>
            {% endif %}
        </div>
        {% endif %}

        {% if test_results %}
        <div class="section">
            <h2>🧪 Test Results</h2>
            {% for suite in test_results %}
            <div class="test-suite">
                <h3>{{ suite.name }}</h3>
                <p>
                    <strong>{{ suite.tests }}</strong> tests, 
                    <span style="color: #28a745;"><strong>{{ suite.tests - suite.failures - suite.errors - suite.skipped }}</strong> passed</span>,
                    {% if suite.failures > 0 %}<span style="color: #dc3545;"><strong>{{ suite.failures }}</strong> failed</span>,{% endif %}
                    {% if suite.errors > 0 %}<span style="color: #dc3545;"><strong>{{ suite.errors }}</strong> errors</span>,{% endif %}
                    {% if suite.skipped > 0 %}<span style="color: #6c757d;"><strong>{{ suite.skipped }}</strong> skipped</span>,{% endif %}
                    Duration: <strong>{{ "%.2f"|format(suite.time) }}s</strong>
                </p>
                
                {% if suite.test_cases %}
                <div class="test-cases">
                    {% for case in suite.test_cases %}
                    <div class="test-case test-{{ case.status }}">
                        <div>
                            <strong>{{ case.name }}</strong>
                            {% if case.classname %}<br><small>{{ case.classname }}</small>{% endif %}
                            {% if case.message %}<br><small style="opacity: 0.8;">{{ case.message }}</small>{% endif %}
                        </div>
                        <div>{{ "%.3f"|format(case.time) }}s</div>
                    </div>
                    {% endfor %}
                </div>
                {% endif %}
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if security and security.total_issues > 0 %}
        <div class="section">
            <h2>🔒 Security Findings</h2>
            <p>Security scan completed using: {{ security.tools_run|join(', ') }}</p>
            
            <div class="summary-grid" style="margin: 20px 0;">
                <div class="summary-card">
                    <h3>High Severity</h3>
                    <div class="value" style="color: #dc3545;">{{ security.high_severity }}</div>
                </div>
                <div class="summary-card">
                    <h3>Medium Severity</h3>
                    <div class="value" style="color: #ffc107;">{{ security.medium_severity }}</div>
                </div>
                <div class="summary-card">
                    <h3>Low Severity</h3>
                    <div class="value" style="color: #17a2b8;">{{ security.low_severity }}</div>
                </div>
            </div>
            
            {% if security.detailed_findings %}
            {% for finding in security.detailed_findings[:10] %}
            <div class="security-finding security-{{ finding.get('severity', 'low').lower() }}">
                <h4>{{ finding.get('test_name', finding.get('issue_text', 'Security Finding')) }}</h4>
                {% if finding.get('filename') %}<p><strong>File:</strong> {{ finding.filename }}{% if finding.get('line_number') %}:{{ finding.line_number }}{% endif %}</p>{% endif %}
                {% if finding.get('issue_text') %}<p>{{ finding.issue_text }}</p>{% endif %}
            </div>
            {% endfor %}
            {% endif %}
        </div>
        {% endif %}

        {% if performance and performance.total_benchmarks > 0 %}
        <div class="section">
            <h2>⚡ Performance Benchmarks</h2>
            <p><strong>{{ performance.total_benchmarks }}</strong> benchmarks executed, average duration: <strong>{{ "%.3f"|format(performance.average_duration * 1000) }}ms</strong></p>
            
            {% if performance.slowest_operations %}
            <h3>Slowest Operations</h3>
            <table class="performance-table">
                <thead>
                    <tr>
                        <th>Operation</th>
                        <th>Mean Duration</th>
                        <th>Std Deviation</th>
                        <th>Min Duration</th>
                        <th>Max Duration</th>
                    </tr>
                </thead>
                <tbody>
                    {% for op in performance.slowest_operations %}
                    <tr>
                        <td>{{ op.name }}</td>
                        <td>{{ "%.3f"|format(op.mean_duration * 1000) }}ms</td>
                        <td>{{ "%.3f"|format(op.stddev * 1000) }}ms</td>
                        <td>{{ "%.3f"|format(op.min_duration * 1000) }}ms</td>
                        <td>{{ "%.3f"|format(op.max_duration * 1000) }}ms</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
            {% endif %}
        </div>
        {% endif %}

        <div class="footer">
            <p>Report generated by {{ metadata.generator }} v{{ metadata.version }}</p>
            <p>For detailed logs and artifacts, check the CI/CD pipeline outputs</p>
        </div>
    </div>
</body>
</html>
            """
        }


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description='Generate comprehensive test reports for AI features'
    )
    
    parser.add_argument(
        '--junit-xml', 
        help='Path to JUnit XML test results file'
    )
    parser.add_argument(
        '--coverage-xml', 
        help='Path to coverage XML report file'
    )
    parser.add_argument(
        '--security-json', 
        help='Path to security scan JSON results file'
    )
    parser.add_argument(
        '--performance-json', 
        help='Path to performance benchmark JSON file'
    )
    parser.add_argument(
        '--output-format', 
        choices=['html', 'pdf', 'json'], 
        default='html',
        help='Output format (default: html)'
    )
    parser.add_argument(
        '--output-dir', 
        default='test_reports',
        help='Output directory for reports (default: test_reports)'
    )
    parser.add_argument(
        '--auto-discover', 
        action='store_true',
        help='Automatically discover report files in current directory'
    )
    
    args = parser.parse_args()
    
    # Auto-discover report files if requested
    if args.auto_discover:
        current_dir = Path('.')
        
        if not args.junit_xml:
            junit_files = list(current_dir.glob('**/test-results*.xml'))
            if junit_files:
                args.junit_xml = str(junit_files[0])
                print(f"🔍 Auto-discovered JUnit XML: {args.junit_xml}")
        
        if not args.coverage_xml:
            coverage_files = list(current_dir.glob('**/coverage*.xml'))
            if coverage_files:
                args.coverage_xml = str(coverage_files[0])
                print(f"🔍 Auto-discovered coverage XML: {args.coverage_xml}")
        
        if not args.security_json:
            security_files = list(current_dir.glob('**/security-summary.json'))
            if not security_files:
                security_files = list(current_dir.glob('**/bandit-report.json'))
            if security_files:
                args.security_json = str(security_files[0])
                print(f"🔍 Auto-discovered security JSON: {args.security_json}")
        
        if not args.performance_json:
            perf_files = list(current_dir.glob('**/benchmark-results.json'))
            if perf_files:
                args.performance_json = str(perf_files[0])
                print(f"🔍 Auto-discovered performance JSON: {args.performance_json}")
    
    # Generate report
    generator = TestReportGenerator(args.output_dir)
    
    try:
        report_file = generator.generate_comprehensive_report(
            junit_xml=args.junit_xml,
            coverage_xml=args.coverage_xml,
            security_json=args.security_json,
            performance_json=args.performance_json,
            output_format=args.output_format
        )
        
        print(f"\n🎉 Report generation completed successfully!")
        print(f"📄 Report saved to: {report_file}")
        
        if args.output_format == 'html':
            print(f"🌐 Open in browser: file://{os.path.abspath(report_file)}")
        
    except Exception as e:
        print(f"❌ Error generating report: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()