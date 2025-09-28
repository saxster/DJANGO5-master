"""
Management command to generate redirect rules for web servers
Supports Apache, Nginx, and other common web server formats
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
import os
import json

from apps.core.url_router_optimized import OptimizedURLRouter
from apps.core.middleware.navigation_tracking import NavigationTrackingMiddleware


class Command(BaseCommand):
    """
    Generate redirect rules for web servers based on URL mappings
    
    Usage:
        python manage.py generate_redirects --format apache
        python manage.py generate_redirects --format nginx
        python manage.py generate_redirects --output /path/to/redirects.conf
        python manage.py generate_redirects --format htaccess --usage-data
    """
    
    help = 'Generate redirect rules for web servers'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--format',
            type=str,
            choices=['apache', 'nginx', 'htaccess', 'json', 'csv', 'lighttpd'],
            default='apache',
            help='Output format for redirect rules'
        )
        
        parser.add_argument(
            '--output',
            type=str,
            help='Output file path (default: stdout)'
        )
        
        parser.add_argument(
            '--usage-data',
            action='store_true',
            help='Include usage statistics in comments'
        )
        
        parser.add_argument(
            '--permanent',
            action='store_true',
            help='Generate permanent (301) redirects instead of temporary (302)'
        )
        
        parser.add_argument(
            '--domain',
            type=str,
            help='Domain name for absolute URLs (e.g., example.com)'
        )
        
        parser.add_argument(
            '--ssl',
            action='store_true',
            help='Use HTTPS in absolute URLs'
        )
        
        parser.add_argument(
            '--priority',
            action='store_true',
            help='Sort redirects by usage priority'
        )
        
        parser.add_argument(
            '--test-mode',
            action='store_true',
            help='Generate test redirects for validation'
        )
    
    def handle(self, *args, **options):
        """Main command handler"""
        self.stdout.write(
            self.style.SUCCESS('🔄 Generating redirect rules...')
        )
        
        # Get URL mappings
        router = OptimizedURLRouter
        mappings = router.URL_MAPPINGS
        
        # Get usage data if requested
        usage_data = {}
        if options['usage_data']:
            try:
                analytics = NavigationTrackingMiddleware.get_navigation_analytics()
                deprecated_usage = analytics.get('deprecated_usage', {})
                for url_data in deprecated_usage.get('deprecated_url_usage', []):
                    usage_data[url_data['old_url']] = url_data['usage_count']
            except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                self.stdout.write(
                    self.style.WARNING(f'Could not load usage data: {e}')
                )
        
        # Sort by priority if requested
        if options['priority'] and usage_data:
            sorted_mappings = dict(
                sorted(mappings.items(), 
                       key=lambda x: usage_data.get(x[0], 0), 
                       reverse=True)
            )
        else:
            sorted_mappings = mappings
        
        # Generate redirects based on format
        output_format = options['format']
        redirect_content = self.generate_redirects(
            sorted_mappings,
            output_format,
            options
        )
        
        # Add header and metadata
        header = self.generate_header(output_format, options)
        full_content = header + redirect_content
        
        # Output to file or stdout
        if options['output']:
            self.write_to_file(full_content, options['output'])
            self.stdout.write(
                self.style.SUCCESS(f'✅ Redirects written to {options["output"]}')
            )
        else:
            self.stdout.write(full_content)
        
        # Show summary
        self.show_summary(sorted_mappings, usage_data, options)
    
    def generate_redirects(self, mappings: Dict[str, str], output_format: str, options: dict) -> str:
        """Generate redirect rules in the specified format"""
        
        if output_format == 'apache':
            return self.generate_apache_redirects(mappings, options)
        elif output_format == 'nginx':
            return self.generate_nginx_redirects(mappings, options)
        elif output_format == 'htaccess':
            return self.generate_htaccess_redirects(mappings, options)
        elif output_format == 'json':
            return self.generate_json_redirects(mappings, options)
        elif output_format == 'csv':
            return self.generate_csv_redirects(mappings, options)
        elif output_format == 'lighttpd':
            return self.generate_lighttpd_redirects(mappings, options)
        else:
            raise ValueError(f"Unsupported format: {output_format}")
    
    def generate_apache_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate Apache redirect rules"""
        redirects = []
        redirect_type = '301' if options['permanent'] else '302'
        
        for old_url, new_url in mappings.items():
            # Clean URLs
            old_path = self.clean_url_path(old_url)
            new_path = self.format_target_url(new_url, options)
            
            # Handle dynamic parameters
            if '<str:' in old_url:
                # Convert Django URL pattern to Apache regex
                apache_pattern = self.convert_to_apache_pattern(old_path)
                redirects.append(
                    f'RedirectMatch {redirect_type} "^/{apache_pattern}$" "{new_path}"'
                )
            else:
                redirects.append(
                    f'Redirect {redirect_type} /{old_path} {new_path}'
                )
        
        return '\n'.join(redirects) + '\n'
    
    def generate_nginx_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate Nginx redirect rules"""
        redirects = []
        redirect_type = 'permanent' if options['permanent'] else 'redirect'
        
        for old_url, new_url in mappings.items():
            old_path = self.clean_url_path(old_url)
            new_path = self.format_target_url(new_url, options)
            
            # Handle dynamic parameters
            if '<str:' in old_url:
                nginx_pattern = self.convert_to_nginx_pattern(old_path)
                redirects.append(
                    f'rewrite ^/{nginx_pattern}$ {new_path} {redirect_type};'
                )
            else:
                redirects.append(
                    f'rewrite ^/{old_path}$ {new_path} {redirect_type};'
                )
        
        return '\n'.join(redirects) + '\n'
    
    def generate_htaccess_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate .htaccess redirect rules"""
        redirects = ['RewriteEngine On', '']
        redirect_code = 'R=301' if options['permanent'] else 'R=302'
        
        for old_url, new_url in mappings.items():
            old_path = self.clean_url_path(old_url)
            new_path = self.format_target_url(new_url, options)
            
            # Handle dynamic parameters
            if '<str:' in old_url:
                htaccess_pattern = self.convert_to_htaccess_pattern(old_path)
                redirects.append(
                    f'RewriteRule ^{htaccess_pattern}$ {new_path} [L,{redirect_code}]'
                )
            else:
                redirects.append(
                    f'RewriteRule ^{old_path}$ {new_path} [L,{redirect_code}]'
                )
        
        return '\n'.join(redirects) + '\n'
    
    def generate_json_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate JSON format redirects"""
        redirect_data = {
            'redirects': [],
            'metadata': {
                'generated_at': timezone.now().isoformat(),
                'total_redirects': len(mappings),
                'redirect_type': '301' if options['permanent'] else '302',
                'domain': options.get('domain', ''),
                'ssl': options.get('ssl', False)
            }
        }
        
        for old_url, new_url in mappings.items():
            redirect_data['redirects'].append({
                'from': self.clean_url_path(old_url),
                'to': self.format_target_url(new_url, options),
                'type': redirect_data['metadata']['redirect_type'],
                'has_parameters': '<str:' in old_url
            })
        
        return json.dumps(redirect_data, indent=2) + '\n'
    
    def generate_csv_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate CSV format redirects"""
        lines = ['Old URL,New URL,Type,Has Parameters']
        redirect_type = '301' if options['permanent'] else '302'
        
        for old_url, new_url in mappings.items():
            old_path = self.clean_url_path(old_url)
            new_path = self.format_target_url(new_url, options)
            has_params = 'Yes' if '<str:' in old_url else 'No'
            
            lines.append(f'{old_path},{new_path},{redirect_type},{has_params}')
        
        return '\n'.join(lines) + '\n'
    
    def generate_lighttpd_redirects(self, mappings: Dict[str, str], options: dict) -> str:
        """Generate Lighttpd redirect rules"""
        redirects = []
        redirect_type = '301' if options['permanent'] else '302'
        
        for old_url, new_url in mappings.items():
            old_path = self.clean_url_path(old_url)
            new_path = self.format_target_url(new_url, options)
            
            redirects.append(
                f'url.redirect = ( "^/{old_path}$" => "{new_path}" )'
            )
        
        return '\n'.join(redirects) + '\n'
    
    def generate_header(self, output_format: str, options: dict) -> str:
        """Generate appropriate header for the output format"""
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M:%S UTC')
        domain = options.get('domain', 'your-domain.com')
        redirect_type = '301 (Permanent)' if options['permanent'] else '302 (Temporary)'
        
        if output_format in ['apache', 'htaccess']:
            return f"""# URL Redirect Rules - Generated {timestamp}
# Django Information Architecture Migration
# Redirect Type: {redirect_type}
# Total Redirects: {len(OptimizedURLRouter.URL_MAPPINGS)}
#
# Usage: Include this file in your Apache configuration or .htaccess
# Test with: curl -I http://{domain}/old-url/

"""
        elif output_format == 'nginx':
            return f"""# URL Redirect Rules - Generated {timestamp}
# Django Information Architecture Migration  
# Redirect Type: {redirect_type}
# Total Redirects: {len(OptimizedURLRouter.URL_MAPPINGS)}
#
# Usage: Include these rules in your Nginx server block
# Test with: curl -I http://{domain}/old-url/

"""
        elif output_format == 'json':
            return ''  # JSON has metadata built-in
        elif output_format == 'csv':
            return f"""# URL Redirect Rules - Generated {timestamp}
# Django Information Architecture Migration
# Redirect Type: {redirect_type}
# Format: CSV
"""
        else:
            return f"""# URL Redirect Rules - Generated {timestamp}
# Django Information Architecture Migration
# Redirect Type: {redirect_type}

"""
    
    def clean_url_path(self, url_path: str) -> str:
        """Clean and normalize URL path"""
        return url_path.strip('/')
    
    def format_target_url(self, url_path: str, options: dict) -> str:
        """Format target URL based on options"""
        clean_path = url_path.strip('/')
        
        # Add domain if specified
        if options.get('domain'):
            protocol = 'https' if options.get('ssl') else 'http'
            return f"{protocol}://{options['domain']}/{clean_path}"
        else:
            return f"/{clean_path}"
    
    def convert_to_apache_pattern(self, url_path: str) -> str:
        """Convert Django URL pattern to Apache regex"""
        # Simple conversion - could be enhanced
        pattern = url_path.replace('<str:pk>', '([^/]+)')
        return pattern
    
    def convert_to_nginx_pattern(self, url_path: str) -> str:
        """Convert Django URL pattern to Nginx regex"""
        pattern = url_path.replace('<str:pk>', '([^/]+)')
        return pattern
    
    def convert_to_htaccess_pattern(self, url_path: str) -> str:
        """Convert Django URL pattern to .htaccess regex"""
        pattern = url_path.replace('<str:pk>', '([^/]+)')
        return pattern
    
    def write_to_file(self, content: str, file_path: str):
        """Write content to file"""
        # Ensure directory exists
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
    
    def show_summary(self, mappings: Dict[str, str], usage_data: Dict, options: dict):
        """Show summary of generated redirects"""
        self.stdout.write('\n' + '='*50)
        self.stdout.write('REDIRECT GENERATION SUMMARY')
        self.stdout.write('='*50)
        
        self.stdout.write(f'Format: {options["format"].upper()}')
        self.stdout.write(f'Total Redirects: {len(mappings)}')
        self.stdout.write(f'Redirect Type: {"301 (Permanent)" if options["permanent"] else "302 (Temporary)"}')
        
        if options.get('domain'):
            self.stdout.write(f'Target Domain: {options["domain"]}')
        
        if usage_data:
            self.stdout.write(f'With Usage Data: {len(usage_data)} URLs tracked')
            
            # Show top redirects by usage
            top_urls = sorted(usage_data.items(), key=lambda x: x[1], reverse=True)[:5]
            if top_urls:
                self.stdout.write('\nTop 5 Most Used Legacy URLs:')
                for url, count in top_urls:
                    self.stdout.write(f'  {url}: {count} hits')
        
        # Show redirect domains
        domains = set()
        for old_url, new_url in mappings.items():
            old_domain = old_url.split('/')[0] if '/' in old_url else 'root'
            new_domain = new_url.split('/')[0] if '/' in new_url else 'root'
            domains.add(f'{old_domain} → {new_domain}')
        
        self.stdout.write(f'\nURL Domain Migrations:')
        for domain in sorted(domains):
            self.stdout.write(f'  {domain}')
        
        # Usage recommendations
        self.stdout.write('\n📋 USAGE RECOMMENDATIONS:')
        
        if options['format'] == 'apache':
            self.stdout.write('• Add to your Apache VirtualHost configuration')
            self.stdout.write('• Test with: curl -I http://your-domain/old-url/')
        elif options['format'] == 'nginx':
            self.stdout.write('• Add to your Nginx server block')
            self.stdout.write('• Reload config: nginx -s reload')
        elif options['format'] == 'htaccess':
            self.stdout.write('• Upload to your web root directory')
            self.stdout.write('• Ensure mod_rewrite is enabled')
        
        if not options['permanent']:
            self.stdout.write('• Consider using --permanent after testing')
        
        self.stdout.write('• Monitor redirect usage with analytics')
        self.stdout.write('• Remove redirects after migration is complete')