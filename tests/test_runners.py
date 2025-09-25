"""
Custom test runners and utilities for AI features testing
Provides parallel execution, performance monitoring, and report generation
"""

import os
import sys
import time
import json
import pytest
import multiprocessing
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta

import psutil
from django.test.runner import DiscoverRunner
from django.conf import settings
from django.db import connection
from django.core.management.color import no_style


@dataclass
class TestResult:
    """Data class for test execution results"""
    test_name: str
    status: str  # passed, failed, skipped, error
    duration: float
    memory_usage: float
    cpu_usage: float
    error_message: Optional[str] = None
    coverage_data: Optional[Dict] = None
    performance_metrics: Optional[Dict] = None


@dataclass
class TestSession:
    """Data class for complete test session"""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    environment: str
    configuration: Dict
    results: List[TestResult]
    summary: Optional[Dict] = None


class AIFeaturesTestRunner(DiscoverRunner):
    """Enhanced test runner for AI features with monitoring and reporting"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.start_time = None
        self.session = None
        self.performance_data = []
        self.resource_monitor = None
        
    def setup_test_environment(self, **kwargs):
        """Setup test environment with AI-specific configurations"""
        super().setup_test_environment(**kwargs)
        
        # Initialize test session
        self.session = TestSession(
            session_id=f"ai_tests_{int(time.time())}",
            start_time=datetime.now(),
            end_time=None,
            environment=os.getenv('TEST_ENVIRONMENT', 'local'),
            configuration=self._get_test_configuration(),
            results=[]
        )
        
        # Setup resource monitoring
        self.resource_monitor = ResourceMonitor()
        self.resource_monitor.start()
        
        # Configure AI testing environment
        self._configure_ai_environment()
        
        print(f"🧠 AI Features Test Session: {self.session.session_id}")
        print(f"📅 Started: {self.session.start_time}")
        print(f"🌍 Environment: {self.session.environment}")
    
    def teardown_test_environment(self, old_config, **kwargs):
        """Cleanup test environment and generate reports"""
        # Stop resource monitoring
        if self.resource_monitor:
            self.resource_monitor.stop()
        
        # Complete test session
        if self.session:
            self.session.end_time = datetime.now()
            self.session.summary = self._generate_session_summary()
        
        # Generate reports
        self._generate_test_reports()
        
        super().teardown_test_environment(old_config, **kwargs)
        
        print(f"✅ Test session completed: {self.session.session_id}")
        print(f"⏱️ Duration: {self.session.end_time - self.session.start_time}")
    
    def run_tests(self, test_labels, **kwargs):
        """Run tests with enhanced monitoring"""
        self.start_time = time.time()
        
        try:
            # Run the actual tests
            result = super().run_tests(test_labels, **kwargs)
            
            # Collect performance metrics
            if hasattr(result, 'testsRun'):
                self._record_test_metrics(result)
            
            return result
            
        except Exception as e:
            print(f"❌ Test execution failed: {e}")
            raise
    
    def _get_test_configuration(self) -> Dict:
        """Get current test configuration"""
        from tests.test_settings import get_test_config
        return get_test_config()
    
    def _configure_ai_environment(self):
        """Configure AI-specific test environment"""
        # Set up mock ML models
        if os.getenv('MOCK_ML_MODELS', 'true').lower() == 'true':
            self._setup_mock_models()
        
        # Configure test databases
        self._setup_test_database()
        
        # Setup temporary directories
        temp_dirs = ['/tmp/test_models', '/tmp/test_images', '/tmp/test_logs']
        for directory in temp_dirs:
            os.makedirs(directory, exist_ok=True)
    
    def _setup_mock_models(self):
        """Setup mock ML models for testing"""
        import numpy as np
        import pickle
        from tests.utils import MockMLModels
        
        # Create mock models
        models = {
            'isolation_forest': MockMLModels.MockIsolationForest(),
            'face_detector': MockMLModels.MockFaceDetector(),
            'fraud_classifier': MockMLModels.MockFraudClassifier()
        }
        
        # Save mock models to temporary directory
        model_dir = Path('/tmp/test_models')
        for name, model in models.items():
            model_path = model_dir / f"{name}.pkl"
            with open(model_path, 'wb') as f:
                pickle.dump(model, f)
    
    def _setup_test_database(self):
        """Setup test database with optimizations"""
        if connection.vendor == 'postgresql':
            # Optimize PostgreSQL for testing
            with connection.cursor() as cursor:
                cursor.execute("SET synchronous_commit TO OFF;")
                cursor.execute("SET wal_buffers TO '16MB';")
                cursor.execute("SET checkpoint_completion_target TO 0.9;")
        
        elif connection.vendor == 'sqlite':
            # Optimize SQLite for testing
            with connection.cursor() as cursor:
                cursor.execute("PRAGMA synchronous = OFF;")
                cursor.execute("PRAGMA journal_mode = MEMORY;")
                cursor.execute("PRAGMA temp_store = MEMORY;")
    
    def _record_test_metrics(self, result):
        """Record test execution metrics"""
        duration = time.time() - self.start_time
        
        metrics = {
            'total_tests': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped) if hasattr(result, 'skipped') else 0,
            'duration': duration,
            'tests_per_second': result.testsRun / duration if duration > 0 else 0
        }
        
        # Add resource usage
        if self.resource_monitor:
            metrics.update(self.resource_monitor.get_summary())
        
        self.performance_data.append(metrics)
    
    def _generate_session_summary(self) -> Dict:
        """Generate summary of test session"""
        total_tests = len(self.session.results)
        passed = sum(1 for r in self.session.results if r.status == 'passed')
        failed = sum(1 for r in self.session.results if r.status == 'failed')
        skipped = sum(1 for r in self.session.results if r.status == 'skipped')
        
        duration = (self.session.end_time - self.session.start_time).total_seconds()
        
        return {
            'total_tests': total_tests,
            'passed': passed,
            'failed': failed,
            'skipped': skipped,
            'pass_rate': (passed / total_tests * 100) if total_tests > 0 else 0,
            'duration_seconds': duration,
            'tests_per_second': total_tests / duration if duration > 0 else 0,
            'performance_data': self.performance_data,
            'environment_info': {
                'python_version': sys.version,
                'django_version': getattr(settings, 'DJANGO_VERSION', 'unknown'),
                'database': connection.vendor,
                'cpu_count': multiprocessing.cpu_count(),
                'memory_total_gb': psutil.virtual_memory().total / (1024**3)
            }
        }
    
    def _generate_test_reports(self):
        """Generate comprehensive test reports"""
        if not self.session:
            return
        
        reports_dir = Path('test_reports')
        reports_dir.mkdir(exist_ok=True)
        
        # Generate JSON report
        json_report = reports_dir / f"{self.session.session_id}.json"
        with open(json_report, 'w') as f:
            json.dump(asdict(self.session), f, indent=2, default=str)
        
        # Generate HTML report
        html_report = reports_dir / f"{self.session.session_id}.html"
        self._generate_html_report(html_report)
        
        # Generate performance report
        perf_report = reports_dir / f"{self.session.session_id}_performance.json"
        with open(perf_report, 'w') as f:
            json.dump({
                'session_id': self.session.session_id,
                'performance_data': self.performance_data,
                'resource_usage': self.resource_monitor.get_detailed_stats() if self.resource_monitor else {}
            }, f, indent=2)
        
        print(f"📊 Reports generated in: {reports_dir}")
    
    def _generate_html_report(self, output_path: Path):
        """Generate HTML test report"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>AI Features Test Report - {session_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background: #f8f9fa; padding: 20px; border-radius: 5px; }}
                .summary {{ display: flex; gap: 20px; margin: 20px 0; }}
                .metric {{ background: #e9ecef; padding: 15px; border-radius: 5px; flex: 1; }}
                .passed {{ color: #28a745; }}
                .failed {{ color: #dc3545; }}
                .skipped {{ color: #ffc107; }}
                .test-list {{ margin: 20px 0; }}
                .test-item {{ padding: 10px; border-bottom: 1px solid #dee2e6; }}
                .performance {{ background: #f8f9fa; padding: 15px; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🧠 AI Features Test Report</h1>
                <p><strong>Session:</strong> {session_id}</p>
                <p><strong>Environment:</strong> {environment}</p>
                <p><strong>Duration:</strong> {duration}</p>
                <p><strong>Timestamp:</strong> {timestamp}</p>
            </div>
            
            <div class="summary">
                <div class="metric">
                    <h3>Total Tests</h3>
                    <h2>{total_tests}</h2>
                </div>
                <div class="metric">
                    <h3 class="passed">Passed</h3>
                    <h2>{passed}</h2>
                </div>
                <div class="metric">
                    <h3 class="failed">Failed</h3>
                    <h2>{failed}</h2>
                </div>
                <div class="metric">
                    <h3 class="skipped">Skipped</h3>
                    <h2>{skipped}</h2>
                </div>
                <div class="metric">
                    <h3>Pass Rate</h3>
                    <h2>{pass_rate:.1f}%</h2>
                </div>
            </div>
            
            <div class="performance">
                <h3>Performance Metrics</h3>
                <p><strong>Tests per Second:</strong> {tests_per_second:.2f}</p>
                <p><strong>Average Memory Usage:</strong> {avg_memory:.1f} MB</p>
                <p><strong>Peak CPU Usage:</strong> {peak_cpu:.1f}%</p>
            </div>
            
            <div class="test-list">
                <h3>Test Results</h3>
                {test_results}
            </div>
            
            <div>
                <h3>Environment Information</h3>
                <pre>{env_info}</pre>
            </div>
        </body>
        </html>
        """
        
        # Prepare data for template
        summary = self.session.summary or {}
        
        # Generate test results HTML
        test_results_html = ""
        for result in self.session.results:
            status_class = result.status
            test_results_html += f"""
            <div class="test-item">
                <span class="{status_class}">● {result.status.upper()}</span>
                <strong>{result.test_name}</strong>
                <span style="float: right;">{result.duration:.3f}s</span>
                {f'<br><small style="color: red;">{result.error_message}</small>' if result.error_message else ''}
            </div>
            """
        
        # Fill template
        html_content = html_template.format(
            session_id=self.session.session_id,
            environment=self.session.environment,
            duration=str(self.session.end_time - self.session.start_time),
            timestamp=self.session.start_time.strftime('%Y-%m-%d %H:%M:%S'),
            total_tests=summary.get('total_tests', 0),
            passed=summary.get('passed', 0),
            failed=summary.get('failed', 0),
            skipped=summary.get('skipped', 0),
            pass_rate=summary.get('pass_rate', 0),
            tests_per_second=summary.get('tests_per_second', 0),
            avg_memory=summary.get('avg_memory_mb', 0),
            peak_cpu=summary.get('peak_cpu_percent', 0),
            test_results=test_results_html,
            env_info=json.dumps(summary.get('environment_info', {}), indent=2)
        )
        
        with open(output_path, 'w') as f:
            f.write(html_content)


class ResourceMonitor:
    """Monitor system resources during test execution"""
    
    def __init__(self):
        self.process = psutil.Process()
        self.monitoring = False
        self.data = []
        self.start_stats = None
    
    def start(self):
        """Start resource monitoring"""
        self.monitoring = True
        self.start_stats = {
            'memory': self.process.memory_info().rss / (1024 * 1024),  # MB
            'cpu': self.process.cpu_percent(),
            'timestamp': time.time()
        }
        
        # Start background monitoring
        import threading
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def stop(self):
        """Stop resource monitoring"""
        self.monitoring = False
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self.monitoring:
            try:
                memory_mb = self.process.memory_info().rss / (1024 * 1024)
                cpu_percent = self.process.cpu_percent()
                
                self.data.append({
                    'timestamp': time.time(),
                    'memory_mb': memory_mb,
                    'cpu_percent': cpu_percent
                })
                
                time.sleep(1)  # Sample every second
                
            except psutil.NoSuchProcess:
                break
            except Exception as e:
                print(f"⚠️ Resource monitoring error: {e}")
                break
    
    def get_summary(self) -> Dict:
        """Get summary of resource usage"""
        if not self.data:
            return {}
        
        memory_values = [d['memory_mb'] for d in self.data]
        cpu_values = [d['cpu_percent'] for d in self.data]
        
        return {
            'avg_memory_mb': sum(memory_values) / len(memory_values),
            'peak_memory_mb': max(memory_values),
            'avg_cpu_percent': sum(cpu_values) / len(cpu_values),
            'peak_cpu_percent': max(cpu_values),
            'samples_collected': len(self.data)
        }
    
    def get_detailed_stats(self) -> Dict:
        """Get detailed resource statistics"""
        return {
            'start_stats': self.start_stats,
            'summary': self.get_summary(),
            'timeline': self.data[-100:]  # Last 100 samples
        }


class ParallelTestRunner:
    """Parallel test execution for AI features"""
    
    def __init__(self, max_workers: int = None):
        self.max_workers = max_workers or max(1, multiprocessing.cpu_count() - 1)
        self.results = []
    
    def run_test_suite(self, test_modules: List[str], config: Dict = None) -> Dict:
        """
        Run test suite in parallel
        
        Args:
            test_modules: List of test modules to run
            config: Test configuration
            
        Returns:
            Test execution results
        """
        start_time = time.time()
        
        # Prepare test batches
        batches = self._create_test_batches(test_modules)
        
        # Run batches in parallel
        with multiprocessing.Pool(self.max_workers) as pool:
            batch_results = pool.map(self._run_test_batch, batches)
        
        # Combine results
        combined_results = self._combine_results(batch_results)
        combined_results['execution_time'] = time.time() - start_time
        combined_results['parallel_workers'] = self.max_workers
        
        return combined_results
    
    def _create_test_batches(self, test_modules: List[str]) -> List[List[str]]:
        """Create balanced test batches for parallel execution"""
        batch_size = max(1, len(test_modules) // self.max_workers)
        batches = []
        
        for i in range(0, len(test_modules), batch_size):
            batch = test_modules[i:i + batch_size]
            batches.append(batch)
        
        return batches
    
    def _run_test_batch(self, batch: List[str]) -> Dict:
        """Run a batch of tests"""
        batch_start = time.time()
        
        # Execute tests in batch
        results = []
        for test_module in batch:
            try:
                result = self._run_single_test_module(test_module)
                results.append(result)
            except Exception as e:
                results.append({
                    'module': test_module,
                    'status': 'error',
                    'error': str(e)
                })
        
        return {
            'batch_id': id(batch),
            'results': results,
            'execution_time': time.time() - batch_start,
            'worker_pid': os.getpid()
        }
    
    def _run_single_test_module(self, test_module: str) -> Dict:
        """Run a single test module"""
        # Use pytest to run the module
        import subprocess
        
        cmd = [
            sys.executable, '-m', 'pytest',
            test_module,
            '--json-report',
            '--json-report-file=/tmp/pytest_report.json',
            '-q'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            return {
                'module': test_module,
                'status': 'passed' if result.returncode == 0 else 'failed',
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
            
        except subprocess.TimeoutExpired:
            return {
                'module': test_module,
                'status': 'timeout',
                'error': 'Test execution timed out'
            }
    
    def _combine_results(self, batch_results: List[Dict]) -> Dict:
        """Combine results from all batches"""
        total_tests = 0
        passed_tests = 0
        failed_tests = 0
        error_tests = 0
        
        all_results = []
        
        for batch in batch_results:
            for result in batch['results']:
                all_results.append(result)
                total_tests += 1
                
                if result['status'] == 'passed':
                    passed_tests += 1
                elif result['status'] == 'failed':
                    failed_tests += 1
                else:
                    error_tests += 1
        
        return {
            'total_tests': total_tests,
            'passed': passed_tests,
            'failed': failed_tests,
            'errors': error_tests,
            'pass_rate': (passed_tests / total_tests * 100) if total_tests > 0 else 0,
            'detailed_results': all_results,
            'batch_count': len(batch_results)
        }