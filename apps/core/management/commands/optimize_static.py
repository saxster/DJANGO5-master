"""
Django management command for static asset optimization

This command optimizes static assets for production including:
1. Image compression and WebP conversion
2. CSS/JS minification and bundling
3. Asset pre-compression (Brotli, Gzip)
4. Cache manifest generation
5. CDN preparation

Usage:
    python manage.py optimize_static
    python manage.py optimize_static --compress-images
    python manage.py optimize_static --create-webp
    python manage.py optimize_static --minify-assets
"""

import os
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List, Any
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.contrib.staticfiles import finders
from django.contrib.staticfiles.management.commands.collectstatic import Command as CollectStaticCommand

logger = logging.getLogger('static_optimization')

try:
    from PIL import Image, ImageOpt
    PIL_AVAILABLE = True
except ImportError:
    try:
        from PIL import Image
        PIL_AVAILABLE = True
        ImageOpt = None
    except ImportError:
        PIL_AVAILABLE = False

try:
    import brotli
    BROTLI_AVAILABLE = True
except ImportError:
    BROTLI_AVAILABLE = False


class Command(BaseCommand):
    help = 'Optimize static assets for production deployment'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--compress-images',
            action='store_true',
            help='Compress images to reduce file sizes',
        )
        parser.add_argument(
            '--create-webp',
            action='store_true',
            help='Create WebP versions of images',
        )
        parser.add_argument(
            '--minify-assets',
            action='store_true',
            help='Minify CSS and JavaScript files',
        )
        parser.add_argument(
            '--pre-compress',
            action='store_true',
            help='Pre-compress static files with Brotli and Gzip',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all optimization tasks',
        )
        parser.add_argument(
            '--quality',
            type=int,
            default=85,
            help='Image quality for compression (1-100, default: 85)',
        )
        parser.add_argument(
            '--skip-large',
            type=int,
            default=5,  # 5MB
            help='Skip files larger than N MB (default: 5)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be optimized without making changes',
        )
    
    def handle(self, *args, **options):
        if not settings.STATIC_ROOT:
            raise CommandError('STATIC_ROOT must be configured')
        
        self.dry_run = options['dry_run']
        self.verbosity = options.get('verbosity', 1)
        self.quality = options['quality']
        self.skip_large_mb = options['skip_large']
        
        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No files will be modified')
            )
        
        # Collect statistics
        self.stats = {
            'total_files': 0,
            'images_compressed': 0,
            'webp_created': 0,
            'assets_minified': 0,
            'files_precompressed': 0,
            'bytes_saved': 0,
            'errors': 0
        }
        
        start_time = datetime.now()
        
        # Determine which optimizations to run
        tasks = []
        if options['all']:
            tasks = ['compress_images', 'create_webp', 'minify_assets', 'pre_compress']
        else:
            if options['compress_images']:
                tasks.append('compress_images')
            if options['create_webp']:
                tasks.append('create_webp')
            if options['minify_assets']:
                tasks.append('minify_assets')
            if options['pre_compress']:
                tasks.append('pre_compress')
        
        if not tasks:
            self.stdout.write(
                self.style.WARNING('No optimization tasks specified. Use --all or specific options.')
            )
            return
        
        # Run optimizations
        for task in tasks:
            try:
                getattr(self, task)()
            except Exception as e:
                self.stats['errors'] += 1
                self.stderr.write(
                    self.style.ERROR(f'Error in {task}: {str(e)}')
                )
        
        # Generate manifest
        self.generate_manifest()
        
        # Show results
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        self.display_results(duration)
    
    def compress_images(self):
        """Compress image files"""
        if not PIL_AVAILABLE:
            self.stderr.write(
                self.style.ERROR('PIL/Pillow not available for image compression')
            )
            return
        
        self.stdout.write('Compressing images...')
        
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
        image_files = self._find_files_by_extension(image_extensions)
        
        for file_path in image_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                self._compress_image(file_path)
                self.stats['images_compressed'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.verbosity >= 2:
                    self.stderr.write(f'Error compressing {file_path}: {e}')
    
    def create_webp(self):
        """Create WebP versions of images"""
        if not PIL_AVAILABLE:
            self.stderr.write(
                self.style.ERROR('PIL/Pillow not available for WebP conversion')
            )
            return
        
        self.stdout.write('Creating WebP versions...')
        
        # WebP can convert from these formats
        source_extensions = ['.jpg', '.jpeg', '.png']
        source_files = self._find_files_by_extension(source_extensions)
        
        for file_path in source_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                self._create_webp_version(file_path)
                self.stats['webp_created'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.verbosity >= 2:
                    self.stderr.write(f'Error creating WebP for {file_path}: {e}')
    
    def minify_assets(self):
        """Minify CSS and JavaScript files"""
        self.stdout.write('Minifying CSS and JavaScript...')
        
        # CSS files
        css_files = self._find_files_by_extension(['.css'])
        for file_path in css_files:
            if self._is_already_minified(file_path):
                continue
            
            try:
                self._minify_css_file(file_path)
                self.stats['assets_minified'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.verbosity >= 2:
                    self.stderr.write(f'Error minifying CSS {file_path}: {e}')
        
        # JavaScript files
        js_files = self._find_files_by_extension(['.js'])
        for file_path in js_files:
            if self._is_already_minified(file_path):
                continue
            
            try:
                self._minify_js_file(file_path)
                self.stats['assets_minified'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.verbosity >= 2:
                    self.stderr.write(f'Error minifying JS {file_path}: {e}')
    
    def pre_compress(self):
        """Pre-compress files with Brotli and Gzip"""
        self.stdout.write('Pre-compressing files...')
        
        # Compressible file types
        compressible_extensions = ['.css', '.js', '.html', '.xml', '.txt', '.svg', '.json']
        compressible_files = self._find_files_by_extension(compressible_extensions)
        
        for file_path in compressible_files:
            if self._should_skip_file(file_path):
                continue
            
            try:
                self._pre_compress_file(file_path)
                self.stats['files_precompressed'] += 1
            except Exception as e:
                self.stats['errors'] += 1
                if self.verbosity >= 2:
                    self.stderr.write(f'Error pre-compressing {file_path}: {e}')
    
    def generate_manifest(self):
        """Generate asset manifest for cache busting"""
        if self.dry_run:
            return
        
        self.stdout.write('Generating asset manifest...')
        
        manifest = {}
        manifest_path = os.path.join(settings.STATIC_ROOT, 'manifest.json')
        
        # Walk through all static files
        for root, dirs, files in os.walk(settings.STATIC_ROOT):
            for file in files:
                if file.endswith('.gz') or file.endswith('.br') or file == 'manifest.json':
                    continue
                
                full_path = os.path.join(root, file)
                relative_path = os.path.relpath(full_path, settings.STATIC_ROOT)
                
                # Generate hash for cache busting
                file_hash = self._get_file_hash(full_path)
                
                manifest[relative_path] = {
                    'hash': file_hash,
                    'size': os.path.getsize(full_path),
                    'mtime': os.path.getmtime(full_path)
                }
        
        # Save manifest
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        if self.verbosity >= 1:
            self.stdout.write(f'Generated manifest with {len(manifest)} files')
    
    def _find_files_by_extension(self, extensions: List[str]) -> List[str]:
        """Find all files with specified extensions"""
        files = []
        
        for root, dirs, filenames in os.walk(settings.STATIC_ROOT):
            for filename in filenames:
                if any(filename.lower().endswith(ext) for ext in extensions):
                    files.append(os.path.join(root, filename))
                    self.stats['total_files'] += 1
        
        return files
    
    def _should_skip_file(self, file_path: str) -> bool:
        """Check if file should be skipped"""
        # Skip large files
        file_size = os.path.getsize(file_path) / (1024 * 1024)  # MB
        if file_size > self.skip_large_mb:
            if self.verbosity >= 2:
                self.stdout.write(f'Skipping large file: {file_path} ({file_size:.1f}MB)')
            return True
        
        return False
    
    def _compress_image(self, file_path: str):
        """Compress a single image file"""
        if self.dry_run:
            self.stdout.write(f'Would compress: {file_path}')
            return
        
        original_size = os.path.getsize(file_path)
        
        with Image.open(file_path) as img:
            # Convert RGBA to RGB if saving as JPEG
            if file_path.lower().endswith(('.jpg', '.jpeg')) and img.mode == 'RGBA':
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[-1])
                img = background
            
            # Save with optimization
            img.save(
                file_path,
                optimize=True,
                quality=self.quality
            )
        
        new_size = os.path.getsize(file_path)
        bytes_saved = original_size - new_size
        
        if bytes_saved > 0:
            self.stats['bytes_saved'] += bytes_saved
            
            if self.verbosity >= 2:
                percent_saved = (bytes_saved / original_size) * 100
                self.stdout.write(
                    f'Compressed {file_path}: {original_size} -> {new_size} bytes '
                    f'({percent_saved:.1f}% smaller)'
                )
    
    def _create_webp_version(self, file_path: str):
        """Create WebP version of image"""
        webp_path = os.path.splitext(file_path)[0] + '.webp'
        
        if self.dry_run:
            self.stdout.write(f'Would create WebP: {webp_path}')
            return
        
        with Image.open(file_path) as img:
            img.save(
                webp_path,
                'WebP',
                optimize=True,
                quality=self.quality
            )
        
        original_size = os.path.getsize(file_path)
        webp_size = os.path.getsize(webp_path)
        bytes_saved = original_size - webp_size
        
        if bytes_saved > 0:
            self.stats['bytes_saved'] += bytes_saved
            
            if self.verbosity >= 2:
                percent_saved = (bytes_saved / original_size) * 100
                self.stdout.write(
                    f'Created WebP {webp_path}: {original_size} -> {webp_size} bytes '
                    f'({percent_saved:.1f}% smaller)'
                )
    
    def _is_already_minified(self, file_path: str) -> bool:
        """Check if file is already minified"""
        filename = os.path.basename(file_path)
        return '.min.' in filename or '-min.' in filename
    
    def _minify_css_file(self, file_path: str):
        """Minify CSS file"""
        if self.dry_run:
            self.stdout.write(f'Would minify CSS: {file_path}')
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_size = len(content)
        minified = self._minify_css(content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(minified)
        
        bytes_saved = original_size - len(minified)
        if bytes_saved > 0:
            self.stats['bytes_saved'] += bytes_saved
            
            if self.verbosity >= 2:
                percent_saved = (bytes_saved / original_size) * 100
                self.stdout.write(
                    f'Minified CSS {file_path}: {original_size} -> {len(minified)} bytes '
                    f'({percent_saved:.1f}% smaller)'
                )
    
    def _minify_js_file(self, file_path: str):
        """Minify JavaScript file"""
        if self.dry_run:
            self.stdout.write(f'Would minify JS: {file_path}')
            return
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_size = len(content)
        minified = self._minify_js(content)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(minified)
        
        bytes_saved = original_size - len(minified)
        if bytes_saved > 0:
            self.stats['bytes_saved'] += bytes_saved
            
            if self.verbosity >= 2:
                percent_saved = (bytes_saved / original_size) * 100
                self.stdout.write(
                    f'Minified JS {file_path}: {original_size} -> {len(minified)} bytes '
                    f'({percent_saved:.1f}% smaller)'
                )
    
    def _pre_compress_file(self, file_path: str):
        """Pre-compress file with Brotli and Gzip"""
        if self.dry_run:
            self.stdout.write(f'Would pre-compress: {file_path}')
            return
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        original_size = len(content)
        bytes_saved = 0
        
        # Create Brotli version
        if BROTLI_AVAILABLE:
            br_content = brotli.compress(content, quality=6)
            br_path = file_path + '.br'
            
            with open(br_path, 'wb') as f:
                f.write(br_content)
            
            bytes_saved += original_size - len(br_content)
            
            if self.verbosity >= 2:
                percent_saved = ((original_size - len(br_content)) / original_size) * 100
                self.stdout.write(
                    f'Brotli compressed {file_path}: {original_size} -> {len(br_content)} bytes '
                    f'({percent_saved:.1f}% smaller)'
                )
        
        # Create Gzip version
        import gzip
        gz_content = gzip.compress(content, compresslevel=6)
        gz_path = file_path + '.gz'
        
        with open(gz_path, 'wb') as f:
            f.write(gz_content)
        
        bytes_saved += original_size - len(gz_content)
        
        if self.verbosity >= 2:
            percent_saved = ((original_size - len(gz_content)) / original_size) * 100
            self.stdout.write(
                f'Gzip compressed {file_path}: {original_size} -> {len(gz_content)} bytes '
                f'({percent_saved:.1f}% smaller)'
            )
        
        if bytes_saved > 0:
            self.stats['bytes_saved'] += bytes_saved
    
    def _minify_css(self, css: str) -> str:
        """Simple CSS minification"""
        import re
        
        # Remove comments
        css = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', css)
        
        # Remove whitespace
        css = re.sub(r'\s+', ' ', css)
        css = re.sub(r';\s*}', '}', css)
        css = re.sub(r'{\s*', '{', css)
        css = re.sub(r';\s*', ';', css)
        css = re.sub(r':\s*', ':', css)
        css = re.sub(r',\s*', ',', css)
        
        return css.strip()
    
    def _minify_js(self, js: str) -> str:
        """Simple JavaScript minification"""
        import re
        
        # Remove single-line comments
        js = re.sub(r'//.*$', '', js, flags=re.MULTILINE)
        
        # Remove multi-line comments
        js = re.sub(r'/\*[^*]*\*+(?:[^/*][^*]*\*+)*/', '', js)
        
        # Remove extra whitespace
        js = re.sub(r'\s+', ' ', js)
        js = re.sub(r';\s*', ';', js)
        js = re.sub(r'{\s*', '{', js)
        js = re.sub(r'}\s*', '}', js)
        js = re.sub(r',\s*', ',', js)
        
        return js.strip()
    
    def _get_file_hash(self, file_path: str) -> str:
        """Get MD5 hash of file"""
        with open(file_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()[:16]
    
    def display_results(self, duration: float):
        """Display optimization results"""
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Static Asset Optimization Results:'))
        self.stdout.write(f"  Duration: {duration:.2f}s")
        self.stdout.write(f"  Total files processed: {self.stats['total_files']}")
        self.stdout.write(f"  Images compressed: {self.stats['images_compressed']}")
        self.stdout.write(f"  WebP versions created: {self.stats['webp_created']}")
        self.stdout.write(f"  Assets minified: {self.stats['assets_minified']}")
        self.stdout.write(f"  Files pre-compressed: {self.stats['files_precompressed']}")
        
        if self.stats['bytes_saved'] > 0:
            mb_saved = self.stats['bytes_saved'] / (1024 * 1024)
            self.stdout.write(f"  Total bytes saved: {self.stats['bytes_saved']:,} ({mb_saved:.2f}MB)")
        
        if self.stats['errors'] > 0:
            self.stdout.write(
                self.style.WARNING(f"  Errors encountered: {self.stats['errors']}")
            )
        
        if self.dry_run:
            self.stdout.write('')
            self.stdout.write(
                self.style.WARNING('This was a dry run - no files were actually modified')
            )