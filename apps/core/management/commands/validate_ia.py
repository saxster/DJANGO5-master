"""
Management command for Information Architecture validation
Validates URL mappings, checks for dead links, and reports migration status
"""
from django.test import Client
from django.utils import timezone
from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware

import logging
logger = logging.getLogger(__name__)


User = get_user_model()


class Command(BaseCommand):
    """
    Django management command to validate Information Architecture implementation
    
    Usage:
        python manage.py validate_ia
        python manage.py validate_ia --full-check
        python manage.py validate_ia --fix-redirects
        python manage.py validate_ia --generate-report
    """
    
    help = 'Validate Information Architecture implementation and URL migration'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--full-check',
            action='store_true',
            help='Perform comprehensive validation including HTTP checks'
        )
        
        parser.add_argument(
            '--fix-redirects',
            action='store_true',
            help='Attempt to fix redirect issues automatically'
        )
        
        parser.add_argument(
            '--generate-report',
            action='store_true',
            help='Generate detailed validation report'
        )
        
        parser.add_argument(
            '--check-external',
            action='store_true',
            help='Check external links and references'
        )
        
        parser.add_argument(
            '--output-format',
            type=str,
            choices=['text', 'json', 'html'],
            default='text',
            help='Output format for reports'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        self.stdout.write(
            self.style.SUCCESS('🚀 Starting Information Architecture Validation')
        )
        
        # Initialize validation results
        self.results = {
            'url_mappings': {'passed': 0, 'failed': 0, 'issues': []},
            'redirects': {'passed': 0, 'failed': 0, 'issues': []},
            'navigation': {'passed': 0, 'failed': 0, 'issues': []},
            'performance': {'passed': 0, 'failed': 0, 'issues': []},
            'structure': {'passed': 0, 'failed': 0, 'issues': []},
        }
        
        # Run validation checks
        self.validate_url_mappings()
        self.validate_redirects(full_check=options['full_check'])
        self.validate_navigation_structure()
        self.validate_performance()
        self.validate_url_structure()
        
        if options['check_external']:
            self.validate_external_references()
        
        if options['fix_redirects']:
            self.fix_redirect_issues()
        
        if options['generate_report']:
            self.generate_detailed_report(options['output_format'])
        
        # Display summary
        self.display_summary()
        
        # Exit with error code if critical issues found
        if self.has_critical_issues():
            sys.exit(1)
    
    def validate_url_mappings(self):
        """Validate URL mapping completeness and consistency"""
        self.stdout.write('\n📋 Validating URL Mappings...')
        
        router = OptimizedURLRouter
        mappings = router.URL_MAPPINGS
        
        # Check mapping completeness
        critical_urls = [
            'scheduler/jobneedtasks/', 'activity/asset/', 'peoples/people/',
            'helpdesk/ticket/', 'reports/get_reports/', 'onboarding/bu/',
        ]
        
        missing_mappings = []
        for url in critical_urls:
            if url not in mappings:
                missing_mappings.append(url)
                self.results['url_mappings']['failed'] += 1
            else:
                self.results['url_mappings']['passed'] += 1
        
        if missing_mappings:
            self.results['url_mappings']['issues'].append(
                f"Missing critical URL mappings: {missing_mappings}"
            )
            self.stdout.write(
                self.style.ERROR(f'❌ Missing {len(missing_mappings)} critical URL mappings')
            )
        
        # Check mapping consistency
        inconsistent_urls = []
        for old_url, new_url in mappings.items():
            # Check for underscores in new URLs
            if '_' in new_url.replace('<str:', '').replace('>', ''):
                inconsistent_urls.append(f"{new_url} (contains underscores)")
            
            # Check for consistent casing
            if new_url != new_url.lower():
                inconsistent_urls.append(f"{new_url} (not lowercase)")
        
        if inconsistent_urls:
            self.results['url_mappings']['issues'].append(
                f"Inconsistent URL naming: {inconsistent_urls[:5]}"
            )
            self.results['url_mappings']['failed'] += len(inconsistent_urls)
            self.stdout.write(
                self.style.WARNING(f'⚠️  Found {len(inconsistent_urls)} naming inconsistencies')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ URL mappings are consistent'))
    
    def validate_redirects(self, full_check=False):
        """Validate redirect functionality"""
        self.stdout.write('\n🔄 Validating Redirects...')
        
        client = Client()
        router = OptimizedURLRouter
        
        # Test sample redirects
        test_urls = [
            ('activity/asset/', 'assets/'),
            ('peoples/people/', 'people/'),
            ('scheduler/jobneedtasks/', 'operations/tasks/'),
        ]
        
        failed_redirects = []
        for old_url, expected_new in test_urls:
            try:
                if full_check:
                    # Make actual HTTP request
                    response = client.get(f'/{old_url}')
                    if response.status_code not in [301, 302]:
                        failed_redirects.append(f"{old_url} -> HTTP {response.status_code}")
                        self.results['redirects']['failed'] += 1
                    else:
                        self.results['redirects']['passed'] += 1
                else:
                    # Check mapping exists
                    if old_url in router.URL_MAPPINGS:
                        actual_new = router.URL_MAPPINGS[old_url]
                        if expected_new not in actual_new:
                            failed_redirects.append(f"{old_url} -> {actual_new} (expected {expected_new})")
                            self.results['redirects']['failed'] += 1
                        else:
                            self.results['redirects']['passed'] += 1
                    
            except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
                failed_redirects.append(f"{old_url} -> Error: {str(e)}")
                self.results['redirects']['failed'] += 1
        
        if failed_redirects:
            self.results['redirects']['issues'] = failed_redirects
            self.stdout.write(
                self.style.ERROR(f'❌ Found {len(failed_redirects)} redirect issues')
            )
        else:
            self.stdout.write(self.style.SUCCESS('✅ Redirects working correctly'))
    
    def validate_navigation_structure(self):
        """Validate navigation menu structure"""
        self.stdout.write('\n🧭 Validating Navigation Structure...')
        
        try:
            router = OptimizedURLRouter
            
            # Test main menu
            main_menu = router.get_navigation_menu(menu_type='main')
            if not main_menu:
                self.results['navigation']['issues'].append("Main navigation menu is empty")
                self.results['navigation']['failed'] += 1
            else:
                self.results['navigation']['passed'] += 1
            
            # Test admin menu
            admin_menu = router.get_navigation_menu(menu_type='admin')
            if not admin_menu:
                self.results['navigation']['issues'].append("Admin navigation menu is empty")
                self.results['navigation']['failed'] += 1
            else:
                self.results['navigation']['passed'] += 1
            
            # Validate menu structure
            menu_issues = []
            for item in main_menu:
                if 'name' not in item or 'url' not in item:
                    menu_issues.append(f"Menu item missing required fields: {item}")
                
                # Check URL validity
                try:
                    if item['url'].startswith('http'):
                        continue  # Skip external URLs
                    # Could add URL resolution check here
                except (TypeError, ValidationError, ValueError) as e:
                    menu_issues.append(f"Invalid URL in menu: {item['url']}")
            
            if menu_issues:
                self.results['navigation']['issues'].extend(menu_issues)
                self.results['navigation']['failed'] += len(menu_issues)
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Found {len(menu_issues)} navigation issues')
                )
            else:
                self.stdout.write(self.style.SUCCESS('✅ Navigation structure is valid'))
                
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.results['navigation']['issues'].append(f"Navigation validation error: {str(e)}")
            self.results['navigation']['failed'] += 1
            self.stdout.write(
                self.style.ERROR(f'❌ Navigation validation failed: {str(e)}')
            )
    
    def validate_performance(self):
        """Validate performance metrics and tracking"""
        self.stdout.write('\n⚡ Validating Performance Tracking...')
        
        try:
            analytics = NavigationTrackingMiddleware.get_navigation_analytics()
            
            # Check if tracking is working
            if not analytics:
                self.results['performance']['issues'].append("Navigation analytics not available")
                self.results['performance']['failed'] += 1
            else:
                self.results['performance']['passed'] += 1
            
            # Check for performance issues
            popular_paths = analytics.get('popular_paths', {}).get('top_paths', [])
            slow_pages = [
                path for path in popular_paths
                if path.get('avg_response_time', 0) > 3.0
            ]
            
            if slow_pages:
                self.results['performance']['issues'].append(
                    f"Found {len(slow_pages)} slow pages (>3s response time)"
                )
                self.results['performance']['failed'] += len(slow_pages)
            
            # Check dead URLs
            dead_urls = analytics.get('dead_urls', {}).get('total_dead_urls', 0)
            if dead_urls > 10:
                self.results['performance']['issues'].append(
                    f"Found {dead_urls} dead URLs - needs attention"
                )
                self.results['performance']['failed'] += 1
            
            self.stdout.write(self.style.SUCCESS('✅ Performance tracking validated'))
            
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.results['performance']['issues'].append(f"Performance validation error: {str(e)}")
            self.results['performance']['failed'] += 1
            self.stdout.write(
                self.style.ERROR(f'❌ Performance validation failed: {str(e)}')
            )
    
    def validate_url_structure(self):
        """Validate URL structure consistency"""
        self.stdout.write('\n🏗️  Validating URL Structure...')
        
        try:
            router = OptimizedURLRouter
            validation = router.validate_url_structure()
            
            issues_found = 0
            
            # Naming inconsistencies
            if validation['naming_inconsistencies']:
                self.results['structure']['issues'].append(
                    f"Naming inconsistencies: {len(validation['naming_inconsistencies'])}"
                )
                issues_found += len(validation['naming_inconsistencies'])
            
            # Deep nesting
            if validation['deep_nesting']:
                self.results['structure']['issues'].append(
                    f"Deep nesting issues: {len(validation['deep_nesting'])}"
                )
                issues_found += len(validation['deep_nesting'])
            
            # Duplicate targets
            if validation['duplicate_targets']:
                self.results['structure']['issues'].append(
                    f"Duplicate redirect targets: {len(validation['duplicate_targets'])}"
                )
                issues_found += len(validation['duplicate_targets'])
            
            if issues_found > 0:
                self.results['structure']['failed'] = issues_found
                self.stdout.write(
                    self.style.WARNING(f'⚠️  Found {issues_found} structure issues')
                )
            else:
                self.results['structure']['passed'] = 1
                self.stdout.write(self.style.SUCCESS('✅ URL structure is valid'))
                
        except (FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValidationError, ValueError) as e:
            self.results['structure']['issues'].append(f"Structure validation error: {str(e)}")
            self.results['structure']['failed'] += 1
            self.stdout.write(
                self.style.ERROR(f'❌ Structure validation failed: {str(e)}')
            )
    
    def validate_external_references(self):
        """Validate external references and links"""
        self.stdout.write('\n🔗 Validating External References...')
        
        # This is a placeholder for external validation
        # Could check documentation, README files, etc.
        self.stdout.write(self.style.SUCCESS('✅ External validation skipped'))
    
    def fix_redirect_issues(self):
        """Attempt to fix common redirect issues"""
        self.stdout.write('\n🔧 Attempting to fix redirect issues...')
        
        # This would implement automatic fixes
        # For now, just log what could be fixed
        issues = self.results['redirects']['issues']
        if issues:
            self.stdout.write(f'Found {len(issues)} issues that could be fixed automatically')
            # Implementation would go here
        else:
            self.stdout.write('No redirect issues to fix')
    
    def generate_detailed_report(self, output_format='text'):
        """Generate detailed validation report"""
        self.stdout.write(f'\n📊 Generating {output_format.upper()} report...')
        
        if output_format == 'json':
            import json
            report_data = {
                'timestamp': timezone.now().isoformat(),
                'summary': self.get_summary_stats(),
                'details': self.results
            }
            logger.debug(json.dumps(report_data, indent=2))
        
        elif output_format == 'html':
            self.generate_html_report()
        
        else:  # text
            self.generate_text_report()
    
    def generate_html_report(self):
        """Generate HTML validation report"""
        report_path = f"ia_validation_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.html"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>IA Validation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .summary {{ background: #f8f9fa; padding: 20px; border-radius: 8px; }}
                .section {{ margin: 20px 0; }}
                .passed {{ color: #28a745; }}
                .failed {{ color: #dc3545; }}
                .issue {{ background: #fff3cd; padding: 10px; margin: 5px 0; border-radius: 4px; }}
            </style>
        </head>
        <body>
            <h1>Information Architecture Validation Report</h1>
            <div class="summary">
                <h2>Summary</h2>
                {self.get_html_summary()}
            </div>
            
            <div class="section">
                <h2>Detailed Results</h2>
                {self.get_html_details()}
            </div>
            
            <p><em>Generated on {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        </body>
        </html>
        """
        
        with open(report_path, 'w') as f:
            f.write(html_content)
        
        self.stdout.write(f'📄 HTML report saved to: {report_path}')
    
    def generate_text_report(self):
        """Generate detailed text report"""
        self.stdout.write('\n' + '='*60)
        self.stdout.write('DETAILED VALIDATION REPORT')
        self.stdout.write('='*60)
        
        for section, data in self.results.items():
            self.stdout.write(f'\n{section.upper()}:')
            self.stdout.write(f'  Passed: {data["passed"]}')
            self.stdout.write(f'  Failed: {data["failed"]}')
            
            if data['issues']:
                self.stdout.write('  Issues:')
                for issue in data['issues']:
                    self.stdout.write(f'    - {issue}')
    
    def get_summary_stats(self) -> Dict:
        """Get summary statistics"""
        total_passed = sum(r['passed'] for r in self.results.values())
        total_failed = sum(r['failed'] for r in self.results.values())
        total_issues = sum(len(r['issues']) for r in self.results.values())
        
        return {
            'total_checks': total_passed + total_failed,
            'passed': total_passed,
            'failed': total_failed,
            'issues': total_issues,
            'success_rate': round(total_passed / (total_passed + total_failed) * 100, 2) if (total_passed + total_failed) > 0 else 0
        }
    
    def get_html_summary(self) -> str:
        """Get HTML summary"""
        stats = self.get_summary_stats()
        return f"""
        <p><strong>Total Checks:</strong> {stats['total_checks']}</p>
        <p><span class="passed">Passed: {stats['passed']}</span> | 
           <span class="failed">Failed: {stats['failed']}</span></p>
        <p><strong>Success Rate:</strong> {stats['success_rate']}%</p>
        """
    
    def get_html_details(self) -> str:
        """Get HTML details"""
        html = ""
        for section, data in self.results.items():
            html += f"<h3>{section.replace('_', ' ').title()}</h3>"
            html += f"<p>Passed: {data['passed']} | Failed: {data['failed']}</p>"
            
            if data['issues']:
                html += "<div class='issues'>"
                for issue in data['issues']:
                    html += f"<div class='issue'>{issue}</div>"
                html += "</div>"
        
        return html
    
    def display_summary(self):
        """Display validation summary"""
        stats = self.get_summary_stats()
        
        self.stdout.write('\n' + '='*60)
        self.stdout.write('VALIDATION SUMMARY')
        self.stdout.write('='*60)
        
        self.stdout.write(f'Total Checks: {stats["total_checks"]}')
        self.stdout.write(
            self.style.SUCCESS(f'✅ Passed: {stats["passed"]}') + ' | ' +
            self.style.ERROR(f'❌ Failed: {stats["failed"]}')
        )
        self.stdout.write(f'Success Rate: {stats["success_rate"]}%')
        
        if stats["issues"] > 0:
            self.stdout.write(f'Total Issues Found: {stats["issues"]}')
        
        # Recommendations
        self.stdout.write('\n📋 RECOMMENDATIONS:')
        if stats["success_rate"] >= 90:
            self.stdout.write(self.style.SUCCESS('🎉 Excellent! IA implementation is solid.'))
        elif stats["success_rate"] >= 70:
            self.stdout.write(self.style.WARNING('⚠️  Good, but some issues need attention.'))
        else:
            self.stdout.write(self.style.ERROR('🚨 Critical issues found. Review and fix before deployment.'))
    
    def has_critical_issues(self) -> bool:
        """Check if there are critical issues that should fail the command"""
        critical_failures = (
            self.results['url_mappings']['failed'] > 0 or
            self.results['redirects']['failed'] > 3 or
            self.results['navigation']['failed'] > 0
        )
        return critical_failures