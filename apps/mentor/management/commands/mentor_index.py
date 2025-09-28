"""
mentor_index management command for the AI Mentor system.

This command indexes the codebase, extracting symbols, relationships,
and metadata for analysis and generation capabilities.
"""

import ast
import hashlib
from pathlib import Path
import time

from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.contrib.postgres.search import SearchVector


class Command(BaseCommand):
    help = 'Index the codebase for the AI Mentor system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--full',
            action='store_true',
            help='Perform full re-indexing of all files'
        )
        parser.add_argument(
            '--since',
            type=str,
            help='Only index files changed since this git commit SHA'
        )
        parser.add_argument(
            '--apps',
            type=str,
            nargs='*',
            help='Only index specific Django apps'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be indexed without making changes'
        )
        parser.add_argument(
            '--quiet',
            action='store_true',
            help='Minimize output'
        )

    def handle(self, *args, **options):
        self.verbosity = options['verbosity']
        self.dry_run = options['dry_run']
        self.quiet = options['quiet']

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("🔍 DRY RUN MODE - No changes will be made")
            )

        start_time = time.time()

        try:
            # Get current git commit
            current_commit = self._get_current_commit()

            # Determine what to index
            if options['full']:
                files_to_index = self._get_all_python_files(options.get('apps'))
                self.log(f"📚 Full indexing: {len(files_to_index)} files")
            elif options['since']:
                files_to_index = self._get_changed_files_since(options['since'])
                self.log(f"📈 Incremental indexing since {options['since']}: {len(files_to_index)} files")
            else:
                # Default: incremental since last indexed commit
                last_commit = IndexMetadata.get_indexed_commit()
                if last_commit:
                    files_to_index = self._get_changed_files_since(last_commit)
                    self.log(f"📈 Incremental indexing since {last_commit[:8]}: {len(files_to_index)} files")
                else:
                    files_to_index = self._get_all_python_files(options.get('apps'))
                    self.log(f"📚 Initial indexing: {len(files_to_index)} files")

            if not files_to_index:
                self.log("✅ No files to index - everything is up to date")
                return

            # Index the files
            stats = self._index_files(files_to_index)

            # Update metadata
            if not self.dry_run:
                IndexMetadata.set_indexed_commit(current_commit)

            # Print results
            elapsed = time.time() - start_time
            self._print_stats(stats, elapsed)

        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            self.stdout.write(
                self.style.ERROR(f"❌ Indexing failed: {e}")
            )
            if self.verbosity >= 2:
                import traceback
                traceback.print_exc()
            raise CommandError(f"Indexing failed: {e}")

    def log(self, message: str):
        """Log message if not in quiet mode."""
        if not self.quiet:
            self.stdout.write(message)

    def _get_current_commit(self) -> str:
        """Get current git commit SHA."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError):
            pass
        return 'unknown'

    def _get_all_python_files(self, apps_filter: Optional[List[str]] = None) -> List[Path]:
        """Get all Python files in the project."""
        project_root = Path(settings.BASE_DIR)
        files = []

        # Include Django apps
        apps_dir = project_root / 'apps'
        if apps_dir.exists():
            for app_dir in apps_dir.iterdir():
                if not app_dir.is_dir():
                    continue
                if apps_filter and app_dir.name not in apps_filter:
                    continue
                files.extend(app_dir.rglob('*.py'))

        # Include project config
        config_dirs = ['intelliwiz_config', 'background_tasks']
        for config_dir in config_dirs:
            config_path = project_root / config_dir
            if config_path.exists():
                files.extend(config_path.rglob('*.py'))

        # Filter out common exclusions
        excluded_patterns = {
            '__pycache__',
            '.git',
            'migrations',
            'venv',
            'env',
            '.pytest_cache',
        }

        return [
            f for f in files
            if not any(part in str(f) for part in excluded_patterns)
        ]

    def _get_changed_files_since(self, commit_sha: str) -> List[Path]:
        """Get Python files changed since the given commit."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'diff', '--name-only', commit_sha, 'HEAD'],
                capture_output=True,
                text=True,
                cwd=settings.BASE_DIR
            )
            if result.returncode != 0:
                raise CommandError(f"Git diff failed: {result.stderr}")

            project_root = Path(settings.BASE_DIR)
            changed_files = []
            for line in result.stdout.strip().split('\n'):
                if line.endswith('.py'):
                    file_path = project_root / line
                    if file_path.exists():
                        changed_files.append(file_path)

            return changed_files
        except (AttributeError, FileNotFoundError, IOError, OSError, PermissionError, TypeError, ValueError) as e:
            raise CommandError(f"Failed to get changed files: {e}")

    def _index_files(self, files: List[Path]) -> Dict:
        """Index the given files."""
        stats = {
            'files_processed': 0,
            'files_skipped': 0,
            'symbols_found': 0,
            'errors': 0,
        }

        project_root = Path(settings.BASE_DIR)

        for file_path in files:
            try:
                # Get relative path
                rel_path = str(file_path.relative_to(project_root))

                # Check if file needs indexing
                if self._should_skip_file(file_path, rel_path):
                    stats['files_skipped'] += 1
                    continue

                self.log(f"📄 Processing {rel_path}")

                # Index the file
                if not self.dry_run:
                    symbols_count = self._index_single_file(file_path, rel_path)
                    stats['symbols_found'] += symbols_count

                stats['files_processed'] += 1

            except (ValueError, TypeError) as e:
                stats['errors'] += 1
                self.stderr.write(f"❌ Error processing {file_path}: {e}")
                if self.verbosity >= 2:
                    import traceback
                    traceback.print_exc()

        return stats

    def _should_skip_file(self, file_path: Path, rel_path: str) -> bool:
        """Check if file should be skipped."""
        # Get file stats
        try:
            stat = file_path.stat()
            mtime = int(stat.st_mtime)
            size = stat.st_size
        except OSError:
            return True

        # Check if already indexed with current content
        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            file_sha = hashlib.sha256(content).hexdigest()

            existing = IndexedFile.objects.filter(path=rel_path, sha=file_sha).first()
            return existing is not None
        except (AttributeError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError):
            return False

    def _index_single_file(self, file_path: Path, rel_path: str) -> int:
        """Index a single Python file."""
        # Read file content
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # Try with latin-1 encoding
            with open(file_path, 'r', encoding='latin-1') as f:
                content = f.read()

        # Calculate file hash and stats
        file_sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
        stat = file_path.stat()
        mtime = int(stat.st_mtime)
        size = stat.st_size

        # Detect language and test status
        language = self._detect_language(rel_path, content)
        is_test = self._is_test_file(rel_path)

        with transaction.atomic():
            # Create or update file record
            file_obj, created = IndexedFile.objects.update_or_create(
                path=rel_path,
                defaults={
                    'sha': file_sha,
                    'mtime': mtime,
                    'size': size,
                    'language': language,
                    'is_test': is_test,
                    'content_preview': content[:1000],
                    'search_vector': SearchVector('path') + SearchVector('content_preview'),
                }
            )

            # If file content hasn't changed, skip symbol extraction
            if not created and file_obj.sha == file_sha:
                return 0

            # Clear old symbols for this file
            CodeSymbol.objects.filter(file=file_obj).delete()

            # Parse and extract symbols
            symbols_count = self._extract_symbols(file_obj, content)

            # Update search vector
            file_obj.search_vector = SearchVector('path') + SearchVector('content_preview')
            file_obj.save(update_fields=['search_vector'])

            return symbols_count

    def _detect_language(self, path: str, content: str) -> str:
        """Detect programming language from file path and content."""
        if path.endswith('.py'):
            return 'python'
        return 'unknown'

    def _is_test_file(self, path: str) -> bool:
        """Check if file is a test file."""
        test_indicators = ['test_', '/tests/', 'test.py', '_test.py']
        return any(indicator in path for indicator in test_indicators)

    def _extract_symbols(self, file_obj: IndexedFile, content: str) -> int:
        """Extract symbols from Python code."""
        try:
            tree = ast.parse(content)
            extractor = PythonSymbolExtractor(file_obj)
            extractor.visit(tree)
            return len(extractor.symbols)
        except SyntaxError as e:
            self.stderr.write(f"⚠️ Syntax error in {file_obj.path}: {e}")
            return 0

    def _print_stats(self, stats: Dict, elapsed: float):
        """Print indexing statistics."""
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Indexing completed in {elapsed:.1f}s\n"
                f"📄 Files processed: {stats['files_processed']}\n"
                f"⏭️ Files skipped: {stats['files_skipped']}\n"
                f"🔤 Symbols found: {stats['symbols_found']}\n"
                f"❌ Errors: {stats['errors']}"
            )
        )

        if not self.dry_run:
            # Get overall stats
            overall = IndexMetadata.get_index_stats()
            self.stdout.write(
                f"\n📊 Total indexed:\n"
                f"   Files: {overall['files']}\n"
                f"   Symbols: {overall['symbols']}\n"
                f"   Relations: {overall['relations']}\n"
                f"   URLs: {overall['urls']}\n"
                f"   Models: {overall['models']}\n"
                f"   Tests: {overall['tests']}"
            )


class PythonSymbolExtractor(ast.NodeVisitor):
    """Extract symbols from Python AST."""

    def __init__(self, file_obj: IndexedFile):
        self.file_obj = file_obj
        self.symbols = []
        self.current_class = None
        self.scope_stack = []

    def visit_ClassDef(self, node):
        """Visit class definition."""
        parents = [s['name'] for s in self.scope_stack]
        decorators = [ast.unparse(d) for d in node.decorator_list]

        symbol = CodeSymbol.objects.create(
            file=self.file_obj,
            name=node.name,
            kind='class',
            span_start=node.lineno,
            span_end=node.end_lineno or node.lineno,
            parents=parents,
            decorators=decorators,
            docstring=ast.get_docstring(node) or '',
            search_vector=SearchVector('name') + SearchVector('docstring'),
        )
        self.symbols.append(symbol)

        # Enter class scope
        self.scope_stack.append({'name': node.name, 'type': 'class'})
        self.current_class = node.name
        self.generic_visit(node)
        self.scope_stack.pop()
        self.current_class = None

    def visit_FunctionDef(self, node):
        """Visit function/method definition."""
        parents = [s['name'] for s in self.scope_stack]
        decorators = [ast.unparse(d) for d in node.decorator_list]

        # Determine if it's a method or function
        kind = 'method' if self.current_class else 'function'

        # Build signature
        signature = f"{node.name}({', '.join(arg.arg for arg in node.args.args)})"

        symbol = CodeSymbol.objects.create(
            file=self.file_obj,
            name=node.name,
            kind=kind,
            span_start=node.lineno,
            span_end=node.end_lineno or node.lineno,
            parents=parents,
            decorators=decorators,
            docstring=ast.get_docstring(node) or '',
            signature=signature,
            search_vector=SearchVector('name') + SearchVector('docstring') + SearchVector('signature'),
        )
        self.symbols.append(symbol)

        # Enter function scope
        self.scope_stack.append({'name': node.name, 'type': 'function'})
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Assign(self, node):
        """Visit variable assignments."""
        if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            parents = [s['name'] for s in self.scope_stack]

            # Skip private variables and common patterns
            var_name = node.targets[0].id
            if not var_name.startswith('_') and var_name.isupper():
                # Likely a constant
                symbol = CodeSymbol.objects.create(
                    file=self.file_obj,
                    name=var_name,
                    kind='constant',
                    span_start=node.lineno,
                    span_end=node.lineno,
                    parents=parents,
                    search_vector=SearchVector('name'),
                )
                self.symbols.append(symbol)

        self.generic_visit(node)