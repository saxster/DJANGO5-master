#!/usr/bin/env python
"""
Performance Optimization Dependencies Validation Script

This script validates that all required dependencies and components are properly
installed and configured for the performance optimization system.

Usage:
    python scripts/validate_performance_dependencies.py
    python scripts/validate_performance_dependencies.py --verbose
"""

import os
import sys
import importlib
import subprocess
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
import argparse

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')

import django
django.setup()

from django.conf import settings
from django.db import connection
from django.core.cache import cache


@dataclass
class DependencyCheck:
    """Represents a dependency validation result"""
    name: str
    required: bool
    available: bool
    version: Optional[str] = None
    error: Optional[str] = None
    recommendation: Optional[str] = None


class PerformanceDependencyValidator:
    """Validates all dependencies for performance optimizations"""
    
    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.results: List[DependencyCheck] = []
        
        print("🔍 Performance Optimization Dependencies Validation")
        print("=" * 55)
    
    def validate_all_dependencies(self):
        """Validate all required and optional dependencies"""
        
        # Core Python dependencies
        self._check_python_version()
        
        # Django framework
        self._check_django_requirements()
        
        # Database requirements
        self._check_database_requirements()
        
        # Cache requirements
        self._check_cache_requirements()
        
        # Image processing dependencies
        self._check_image_processing_deps()
        
        # Compression dependencies
        self._check_compression_deps()
        
        # Monitoring dependencies
        self._check_monitoring_deps()
        
        # Optional performance dependencies
        self._check_optional_deps()
        
        # Custom modules
        self._check_custom_modules()
        
        self._print_validation_results()
    
    def _check_python_version(self):
        """Check Python version compatibility"""
        import sys
        
        python_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        min_required = (3, 8)
        current = (sys.version_info.major, sys.version_info.minor)
        
        is_compatible = current >= min_required
        
        self.results.append(DependencyCheck(
            name="Python Version",
            required=True,
            available=is_compatible,
            version=python_version,
            error=f"Python {min_required[0]}.{min_required[1]}+ required" if not is_compatible else None,
            recommendation="Upgrade Python to 3.8 or higher" if not is_compatible else None
        ))
        
        if self.verbose:
            print(f"  ✓ Python {python_version} {'✅' if is_compatible else '❌'}")
    
    def _check_django_requirements(self):
        """Check Django and related requirements"""
        try:
            import django
            django_version = django.get_version()
            
            # Check Django version
            version_parts = [int(x) for x in django_version.split('.')]
            min_required = [4, 2]  # Django 4.2+
            is_compatible = version_parts[:2] >= min_required
            
            self.results.append(DependencyCheck(
                name="Django Framework",
                required=True,
                available=True,
                version=django_version,
                error=f"Django {min_required[0]}.{min_required[1]}+ required" if not is_compatible else None
            ))
            
            if self.verbose:
                print(f"  ✓ Django {django_version} {'✅' if is_compatible else '❌'}")
            
        except ImportError as e:
            self.results.append(DependencyCheck(
                name="Django Framework",
                required=True,
                available=False,
                error=str(e)
            ))
    
    def _check_database_requirements(self):
        """Check database configuration and requirements"""
        try:
            # Check database connection
            with connection.cursor() as cursor:
                cursor.execute("SELECT version()")
                db_version = cursor.fetchone()[0]
            
            self.results.append(DependencyCheck(
                name="Database Connection",
                required=True,
                available=True,
                version=db_version.split()[0] if db_version else "Unknown"
            ))
            
            # Check for PostgreSQL (recommended)
            is_postgres = 'postgresql' in settings.DATABASES['default']['ENGINE']
            
            self.results.append(DependencyCheck(
                name="PostgreSQL Database",
                required=False,
                available=is_postgres,
                recommendation="PostgreSQL recommended for optimal performance" if not is_postgres else None
            ))
            
            # Check for postgis (for spatial features)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT PostGIS_full_version()")
                    postgis_available = True
                    postgis_version = cursor.fetchone()[0].split()[1] if cursor.fetchone() else "Unknown"
            except Exception:
                postgis_available = False
                postgis_version = None
            
            self.results.append(DependencyCheck(
                name="PostGIS Extension",
                required=False,
                available=postgis_available,
                version=postgis_version,
                recommendation="PostGIS recommended for spatial asset optimization" if not postgis_available else None
            ))
            
            if self.verbose:
                print(f"  ✓ Database: {'✅' if is_postgres else '⚠️'}")
                print(f"  ✓ PostGIS: {'✅' if postgis_available else '⚠️'}")
                
        except Exception as e:
            self.results.append(DependencyCheck(
                name="Database Connection",
                required=True,
                available=False,
                error=str(e)
            ))
    
    def _check_cache_requirements(self):
        """Check cache backend configuration"""
        try:
            # Test basic cache functionality
            cache.set('dependency_test', 'test_value', 30)
            cache_working = cache.get('dependency_test') == 'test_value'
            cache.delete('dependency_test')
            
            cache_backend = cache.__class__.__name__
            
            self.results.append(DependencyCheck(
                name="Cache Backend",
                required=True,
                available=cache_working,
                version=cache_backend
            ))
            
            # Check for Redis (recommended)
            is_redis = 'redis' in cache_backend.lower() or 'Redis' in cache_backend
            
            self.results.append(DependencyCheck(
                name="Redis Cache",
                required=False,
                available=is_redis,
                recommendation="Redis recommended for optimal cache performance" if not is_redis else None
            ))
            
            if self.verbose:
                print(f"  ✓ Cache Backend: {cache_backend} {'✅' if cache_working else '❌'}")
                print(f"  ✓ Redis: {'✅' if is_redis else '⚠️'}")
                
        except Exception as e:
            self.results.append(DependencyCheck(
                name="Cache Backend",
                required=True,
                available=False,
                error=str(e)
            ))
    
    def _check_image_processing_deps(self):
        """Check image processing dependencies"""
        # PIL/Pillow
        try:
            from PIL import Image
            import PIL
            
            self.results.append(DependencyCheck(
                name="Pillow (PIL)",
                required=False,
                available=True,
                version=PIL.__version__,
                recommendation="Pillow enables WebP image conversion for better performance"
            ))
            
            # Check WebP support in PIL
            try:
                from PIL import ImageFormat
                webp_supported = 'WEBP' in Image.EXTENSION
            except:
                try:
                    # Alternative check
                    img = Image.new('RGB', (1, 1))
                    import io
                    buf = io.BytesIO()
                    img.save(buf, format='WEBP')
                    webp_supported = True
                except:
                    webp_supported = False
            
            self.results.append(DependencyCheck(
                name="WebP Support",
                required=False,
                available=webp_supported,
                recommendation="WebP support enables advanced image compression" if not webp_supported else None
            ))
            
            if self.verbose:
                print(f"  ✓ Pillow: ✅ (v{PIL.__version__})")
                print(f"  ✓ WebP: {'✅' if webp_supported else '⚠️'}")
                
        except ImportError:
            self.results.append(DependencyCheck(
                name="Pillow (PIL)",
                required=False,
                available=False,
                recommendation="Install Pillow for image optimization: pip install Pillow"
            ))
    
    def _check_compression_deps(self):
        """Check compression dependencies"""
        # Brotli
        try:
            import brotli
            
            self.results.append(DependencyCheck(
                name="Brotli Compression",
                required=False,
                available=True,
                recommendation="Brotli provides better compression than gzip"
            ))
            
            if self.verbose:
                print(f"  ✓ Brotli: ✅")
                
        except ImportError:
            self.results.append(DependencyCheck(
                name="Brotli Compression",
                required=False,
                available=False,
                recommendation="Install Brotli for better compression: pip install brotli"
            ))
        
        # gzip (built-in)
        try:
            import gzip
            
            self.results.append(DependencyCheck(
                name="Gzip Compression",
                required=True,
                available=True,
                version="Built-in"
            ))
            
        except ImportError:
            self.results.append(DependencyCheck(
                name="Gzip Compression",
                required=True,
                available=False,
                error="gzip module missing (should be built-in)"
            ))
    
    def _check_monitoring_deps(self):
        """Check monitoring and metrics dependencies"""
        # psutil for system monitoring
        try:
            import psutil
            
            self.results.append(DependencyCheck(
                name="psutil (System Monitoring)",
                required=False,
                available=True,
                version=psutil.__version__,
                recommendation="psutil enables system resource monitoring"
            ))
            
            if self.verbose:
                print(f"  ✓ psutil: ✅ (v{psutil.__version__})")
                
        except ImportError:
            self.results.append(DependencyCheck(
                name="psutil (System Monitoring)",
                required=False,
                available=False,
                recommendation="Install psutil for system monitoring: pip install psutil"
            ))
    
    def _check_optional_deps(self):
        """Check optional performance dependencies"""
        # ujson for faster JSON processing
        try:
            import ujson
            
            self.results.append(DependencyCheck(
                name="ujson (Fast JSON)",
                required=False,
                available=True,
                recommendation="ujson provides faster JSON processing"
            ))
            
        except ImportError:
            self.results.append(DependencyCheck(
                name="ujson (Fast JSON)",
                required=False,
                available=False,
                recommendation="Install ujson for faster JSON: pip install ujson"
            ))
        
        # orjson as alternative
        try:
            import orjson
            
            self.results.append(DependencyCheck(
                name="orjson (Fast JSON)",
                required=False,
                available=True,
                recommendation="orjson provides fastest JSON processing"
            ))
            
        except ImportError:
            self.results.append(DependencyCheck(
                name="orjson (Fast JSON)",
                required=False,
                available=False,
                recommendation="Install orjson for fastest JSON: pip install orjson"
            ))
    
    def _check_custom_modules(self):
        """Check custom performance optimization modules"""
        modules_to_check = [
            ('apps.core.cache_strategies', 'Cache Strategies Module'),
            ('apps.core.cache_manager', 'Cache Manager Module'),
            ('apps.activity.managers.job_manager_orm_optimized', 'Optimized Job Manager'),
            ('apps.activity.managers.asset_manager_orm_optimized', 'Optimized Asset Manager'),
            ('apps.core.utils_new.query_optimizer', 'Query Optimizer'),
        ]
        
        for module_path, display_name in modules_to_check:
            try:
                importlib.import_module(module_path)
                
                self.results.append(DependencyCheck(
                    name=display_name,
                    required=True,
                    available=True
                ))
                
                if self.verbose:
                    print(f"  ✓ {display_name}: ✅")
                    
            except ImportError as e:
                self.results.append(DependencyCheck(
                    name=display_name,
                    required=True,
                    available=False,
                    error=str(e)
                ))
        
        # Check monitoring modules (optional)
        optional_modules = [
            ('monitoring.performance_monitor_enhanced', 'Enhanced Performance Monitor'),
            ('monitoring.real_time_alerts', 'Real-time Alerts System'),
        ]
        
        for module_path, display_name in optional_modules:
            try:
                importlib.import_module(module_path)
                
                self.results.append(DependencyCheck(
                    name=display_name,
                    required=False,
                    available=True
                ))
                
            except ImportError:
                self.results.append(DependencyCheck(
                    name=display_name,
                    required=False,
                    available=False,
                    recommendation=f"Module {module_path} not found - monitoring features may be limited"
                ))
    
    def _print_validation_results(self):
        """Print comprehensive validation results"""
        print("\n" + "=" * 60)
        print("🎯 DEPENDENCY VALIDATION RESULTS")
        print("=" * 60)
        
        # Summary statistics
        total = len(self.results)
        required_available = len([r for r in self.results if r.required and r.available])
        required_total = len([r for r in self.results if r.required])
        optional_available = len([r for r in self.results if not r.required and r.available])
        optional_total = len([r for r in self.results if not r.required])
        
        print(f"\n📊 Summary:")
        print(f"  Required Dependencies: {required_available}/{required_total} ✅")
        print(f"  Optional Dependencies: {optional_available}/{optional_total} ✅")
        print(f"  Total: {required_available + optional_available}/{total}")
        
        # Categorize results
        critical_missing = [r for r in self.results if r.required and not r.available]
        optional_missing = [r for r in self.results if not r.required and not r.available]
        available = [r for r in self.results if r.available]
        
        # Show available dependencies
        if available:
            print(f"\n✅ Available Dependencies:")
            for result in available:
                status = "REQUIRED" if result.required else "OPTIONAL"
                version_info = f" (v{result.version})" if result.version else ""
                print(f"  ✓ {result.name}{version_info} - {status}")
        
        # Show missing required dependencies
        if critical_missing:
            print(f"\n❌ Missing Required Dependencies:")
            for result in critical_missing:
                print(f"  ✗ {result.name}")
                if result.error:
                    print(f"    Error: {result.error}")
                if result.recommendation:
                    print(f"    💡 {result.recommendation}")
        
        # Show missing optional dependencies
        if optional_missing:
            print(f"\n⚠️  Missing Optional Dependencies:")
            for result in optional_missing:
                print(f"  ⚠ {result.name}")
                if result.recommendation:
                    print(f"    💡 {result.recommendation}")
        
        # Overall status and recommendations
        print(f"\n🎯 Overall Status:")
        if critical_missing:
            print("  ❌ CRITICAL ISSUES: Some required dependencies are missing!")
            print("  🚨 Performance optimizations may not work properly.")
            print("  📋 Action Required: Install missing required dependencies.")
        elif optional_missing:
            print("  ⚠️  GOOD WITH IMPROVEMENTS: All required dependencies available.")
            print("  📈 Consider installing optional dependencies for better performance.")
        else:
            print("  ✅ EXCELLENT: All dependencies are available!")
            print("  🚀 Your system is ready for optimal performance!")
        
        # Installation commands
        if optional_missing:
            print(f"\n📦 Recommended Installation Commands:")
            install_commands = []
            
            for result in optional_missing:
                if "Pillow" in result.name:
                    install_commands.append("pip install Pillow")
                elif "brotli" in result.name.lower():
                    install_commands.append("pip install brotli")
                elif "psutil" in result.name:
                    install_commands.append("pip install psutil")
                elif "ujson" in result.name:
                    install_commands.append("pip install ujson")
                elif "orjson" in result.name:
                    install_commands.append("pip install orjson")
            
            for cmd in set(install_commands):  # Remove duplicates
                print(f"  {cmd}")
        
        # Save results
        self._save_validation_results()
        print(f"\n📄 Detailed validation results saved to: dependency_validation.json")
        print("=" * 60)
    
    def _save_validation_results(self):
        """Save validation results to JSON file"""
        import json
        from datetime import datetime
        
        results_data = {
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'total_dependencies': len(self.results),
                'required_available': len([r for r in self.results if r.required and r.available]),
                'required_total': len([r for r in self.results if r.required]),
                'optional_available': len([r for r in self.results if not r.required and r.available]),
                'optional_total': len([r for r in self.results if not r.required])
            },
            'dependencies': []
        }
        
        for result in self.results:
            results_data['dependencies'].append({
                'name': result.name,
                'required': result.required,
                'available': result.available,
                'version': result.version,
                'error': result.error,
                'recommendation': result.recommendation
            })
        
        with open('dependency_validation.json', 'w') as f:
            json.dump(results_data, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description='Validate performance optimization dependencies')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    validator = PerformanceDependencyValidator(verbose=args.verbose)
    validator.validate_all_dependencies()


if __name__ == '__main__':
    main()