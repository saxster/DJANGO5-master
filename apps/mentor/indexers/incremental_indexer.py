"""
Incremental indexing optimizer with Git integration for efficient codebase analysis.

This optimizer provides:
- Git diff integration: Precise change detection
- Dependency invalidation: Update affected symbols
- Parallel processing: Multi-threaded file processing
- Cache warming: Pre-compute common queries
- Index versioning: Schema migration support
"""

import concurrent.futures
import hashlib
import subprocess
import threading
import time
from collections import defaultdict
from pathlib import Path
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

    IndexedFile, CodeSymbol, SymbolRelation, DjangoURL,
    DjangoModel, TestCase, IndexMetadata
)
from apps.mentor.indexers.python_indexer import EnhancedPythonIndexer
from apps.mentor.introspection.django_introspector import DjangoIntrospector
from apps.mentor.indexers.graphql_indexer import GraphQLIndexer
from apps.mentor.indexers.test_discovery import TestDiscoveryEngine


@dataclass
class ChangeInfo:
    """Container for file change information."""
    file_path: str
    change_type: str  # 'added', 'modified', 'deleted', 'renamed'
    old_path: Optional[str] = None
    sha: Optional[str] = None
    size: int = 0
    mtime: int = 0


@dataclass
class DependencyGraph:
    """Container for dependency graph information."""
    file_dependencies: Dict[str, Set[str]]
    symbol_dependencies: Dict[str, Set[str]]
    reverse_dependencies: Dict[str, Set[str]]


class IncrementalIndexer:
    """High-performance incremental indexer with Git integration."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.project_root = Path(settings.BASE_DIR)
        self.cache_key_prefix = 'mentor_index'
        self._lock = threading.RLock()

        # Indexer components
        self.python_indexer = None
        self.django_introspector = DjangoIntrospector()
        self.graphql_indexer = GraphQLIndexer()
        self.test_engine = TestDiscoveryEngine()

    def incremental_update(self,
                         since_commit: Optional[str] = None,
                         force_full: bool = False) -> Dict[str, Any]:
        """Perform incremental indexing update."""
        start_time = time.time()

        try:
            with self._lock:
                # Get current state
                current_commit = self._get_current_commit()
                last_indexed_commit = since_commit or IndexMetadata.get_indexed_commit()

                if force_full or not last_indexed_commit:
                    print("🔄 Performing full indexing...")
                    return self._full_reindex()

                print(f"📈 Incremental indexing from {last_indexed_commit[:8]} to {current_commit[:8]}")

                # Get changed files
                changes = self._get_git_changes(last_indexed_commit, current_commit)

                if not changes:
                    print("✅ No changes detected")
                    return {'status': 'no_changes', 'elapsed': 0}

                print(f"📊 Processing {len(changes)} changed files")

                # Build dependency graph
                dependency_graph = self._build_dependency_graph()

                # Find files that need reprocessing
                files_to_process = self._find_affected_files(changes, dependency_graph)

                # Process files in parallel
                results = self._process_files_parallel(files_to_process)

                # Update metadata
                IndexMetadata.set_indexed_commit(current_commit)

                # Warm cache
                self._warm_cache()

                elapsed = time.time() - start_time

                return {
                    'status': 'success',
                    'elapsed': elapsed,
                    'changes_processed': len(changes),
                    'files_processed': len(files_to_process),
                    'results': results
                }

        except (ValueError, TypeError) as e:
            print(f"❌ Incremental indexing failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def _get_current_commit(self) -> str:
        """Get current Git commit SHA."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except (ValueError, TypeError):
            pass
        return 'unknown'

    def _get_git_changes(self, from_commit: str, to_commit: str) -> List[ChangeInfo]:
        """Get list of changed files from Git."""
        changes = []

        try:
            # Get changed files with status
            result = subprocess.run([
                'git', 'diff', '--name-status', f"{from_commit}..{to_commit}"
            ], capture_output=True, text=True, cwd=self.project_root, timeout=30)

            if result.returncode != 0:
                print(f"Git diff failed: {result.stderr}")
                return []

            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue

                parts = line.split('\t')
                if len(parts) < 2:
                    continue

                status = parts[0]
                file_path = parts[1]

                # Only process Python files and related files
                if not self._should_process_file(file_path):
                    continue

                # Determine change type
                if status.startswith('A'):
                    change_type = 'added'
                elif status.startswith('M'):
                    change_type = 'modified'
                elif status.startswith('D'):
                    change_type = 'deleted'
                elif status.startswith('R'):
                    change_type = 'renamed'
                    old_path = file_path
                    file_path = parts[2] if len(parts) > 2 else file_path
                else:
                    change_type = 'modified'

                # Get file metadata if it exists
                full_path = self.project_root / file_path
                sha, size, mtime = None, 0, 0

                if full_path.exists() and change_type != 'deleted':
                    try:
                        stat = full_path.stat()
                        size = stat.st_size
                        mtime = int(stat.st_mtime)

                        with open(full_path, 'rb') as f:
                            sha = hashlib.sha256(f.read()).hexdigest()
                    except (FileNotFoundError, IOError, OSError, PermissionError):
                        pass

                change_info = ChangeInfo(
                    file_path=file_path,
                    change_type=change_type,
                    old_path=old_path if change_type == 'renamed' else None,
                    sha=sha,
                    size=size,
                    mtime=mtime
                )
                changes.append(change_info)

        except subprocess.TimeoutExpired:
            print("Git diff timed out")
        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error getting git changes: {e}")

        return changes

    def _should_process_file(self, file_path: str) -> bool:
        """Check if file should be processed."""
        # File extensions to process
        extensions = ['.py', '.html', '.js', '.css', '.md']

        # Skip certain directories
        skip_dirs = ['__pycache__', '.git', 'node_modules', 'venv', 'env']

        path = Path(file_path)

        # Check extension
        if not any(path.suffix.endswith(ext) for ext in extensions):
            return False

        # Check directories to skip
        if any(skip_dir in path.parts for skip_dir in skip_dirs):
            return False

        return True

    def _build_dependency_graph(self) -> DependencyGraph:
        """Build dependency graph from existing index data."""
        file_deps = defaultdict(set)
        symbol_deps = defaultdict(set)
        reverse_deps = defaultdict(set)

        # Build from symbol relations
        relations = SymbolRelation.objects.select_related('source__file', 'target__file').all()

        for relation in relations:
            source_file = relation.source.file.path
            target_file = relation.target.file.path

            # File dependencies
            if source_file != target_file:
                file_deps[source_file].add(target_file)
                reverse_deps[target_file].add(source_file)

            # Symbol dependencies
            source_symbol = f"{source_file}:{relation.source.name}"
            target_symbol = f"{target_file}:{relation.target.name}"

            symbol_deps[source_symbol].add(target_symbol)

        return DependencyGraph(
            file_dependencies=dict(file_deps),
            symbol_dependencies=dict(symbol_deps),
            reverse_dependencies=dict(reverse_deps)
        )

    def _find_affected_files(self, changes: List[ChangeInfo],
                           dependency_graph: DependencyGraph) -> Set[str]:
        """Find all files that need reprocessing based on changes."""
        affected_files = set()

        # Direct changes
        for change in changes:
            affected_files.add(change.file_path)

        # Dependency propagation
        to_check = set(change.file_path for change in changes)
        checked = set()

        while to_check:
            file_path = to_check.pop()
            if file_path in checked:
                continue

            checked.add(file_path)

            # Add reverse dependencies
            if file_path in dependency_graph.reverse_dependencies:
                for dependent in dependency_graph.reverse_dependencies[file_path]:
                    if dependent not in checked:
                        affected_files.add(dependent)
                        to_check.add(dependent)

        return affected_files

    def _process_files_parallel(self, files: Set[str]) -> Dict[str, Any]:
        """Process files in parallel using thread pool."""
        results = {
            'files_processed': 0,
            'symbols_found': 0,
            'relations_created': 0,
            'errors': 0,
            'processing_times': {}
        }

        # Group files by type for efficient processing
        python_files = []
        test_files = []

        for file_path in files:
            if self._is_test_file(file_path):
                test_files.append(file_path)
            elif file_path.endswith('.py'):
                python_files.append(file_path)

        # Process Python files
        if python_files:
            print(f"🐍 Processing {len(python_files)} Python files")
            python_results = self._process_python_files_parallel(python_files)
            self._merge_results(results, python_results)

        # Process test files
        if test_files:
            print(f"🧪 Processing {len(test_files)} test files")
            test_results = self._process_test_files_parallel(test_files)
            self._merge_results(results, test_results)

        # Run Django introspection if models changed
        model_files = [f for f in python_files if '/models.py' in f or '/models/' in f]
        if model_files:
            print("🏗️ Running Django introspection")
            django_results = self._run_django_introspection()
            self._merge_results(results, django_results)

        return results

    def _process_python_files_parallel(self, files: List[str]) -> Dict[str, Any]:
        """Process Python files in parallel."""
        results = {'files_processed': 0, 'symbols_found': 0, 'errors': 0}

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit tasks
            future_to_file = {
                executor.submit(self._process_single_python_file, file_path): file_path
                for file_path in files
            }

            # Collect results
            for future in concurrent.futures.as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    file_results = future.result()
                    results['files_processed'] += 1
                    results['symbols_found'] += file_results.get('symbols', 0)
                except (FileNotFoundError, IOError, OSError, PermissionError) as e:
                    print(f"Error processing {file_path}: {e}")
                    results['errors'] += 1

        return results

    def _process_single_python_file(self, file_path: str) -> Dict[str, int]:
        """Process a single Python file."""
        try:
            full_path = self.project_root / file_path

            if not full_path.exists():
                # Handle deleted files
                self._handle_deleted_file(file_path)
                return {'symbols': 0}

            # Create or update IndexedFile
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()

            file_sha = hashlib.sha256(content.encode('utf-8')).hexdigest()
            stat = full_path.stat()

            indexed_file, created = IndexedFile.objects.update_or_create(
                path=file_path,
                defaults={
                    'sha': file_sha,
                    'mtime': int(stat.st_mtime),
                    'size': stat.st_size,
                    'language': 'python',
                    'is_test': self._is_test_file(file_path),
                    'content_preview': content[:1000],
                }
            )

            # Skip if content hasn't changed
            if not created and indexed_file.sha == file_sha:
                return {'symbols': 0}

            # Index with enhanced Python indexer
            indexer = EnhancedPythonIndexer(indexed_file)
            return indexer.index_file(content)

        except (FileNotFoundError, IOError, OSError, PermissionError) as e:
            print(f"Error processing Python file {file_path}: {e}")
            return {'symbols': 0, 'errors': 1}

    def _process_test_files_parallel(self, files: List[str]) -> Dict[str, Any]:
        """Process test files in parallel."""
        results = {'tests_found': 0, 'errors': 0}

        # Use test discovery engine
        stats = self.test_engine.discover_tests(files)
        results.update(stats)

        return results

    def _run_django_introspection(self) -> Dict[str, Any]:
        """Run Django introspection for all apps."""
        return self.django_introspector.introspect_all_apps()

    def _handle_deleted_file(self, file_path: str):
        """Handle deletion of indexed file."""
        try:
            # Remove from database
            IndexedFile.objects.filter(path=file_path).delete()
            print(f"🗑️ Removed deleted file: {file_path}")
        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError) as e:
            print(f"Error handling deleted file {file_path}: {e}")

    def _is_test_file(self, file_path: str) -> bool:
        """Check if file is a test file."""
        return any(pattern in file_path.lower() for pattern in [
            'test_', '_test.', '/tests/', '/test.'
        ])

    def _merge_results(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge results from parallel processing."""
        for key, value in source.items():
            if isinstance(value, (int, float)):
                target[key] = target.get(key, 0) + value
            elif isinstance(value, dict):
                if key not in target:
                    target[key] = {}
                target[key].update(value)

    def _warm_cache(self):
        """Pre-warm frequently accessed cache entries."""
        try:
            # Cache common queries
            common_queries = [
                ('file_count', lambda: IndexedFile.objects.count()),
                ('symbol_count', lambda: CodeSymbol.objects.count()),
                ('model_count', lambda: DjangoModel.objects.count()),
                ('test_count', lambda: TestCase.objects.count()),
            ]

            for cache_key, query_func in common_queries:
                full_key = f"{self.cache_key_prefix}:{cache_key}"
                result = query_func()
                cache.set(full_key, result, timeout=3600)  # 1 hour

            print("🔥 Cache warmed successfully")

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            print(f"Cache warming failed: {e}")

    def _full_reindex(self) -> Dict[str, Any]:
        """Perform full reindex of the codebase."""
        start_time = time.time()

        try:
            # Clear existing data
            with transaction.atomic():
                IndexedFile.objects.all().delete()
                print("🧹 Cleared existing index data")

            # Find all files to index
            all_files = []
            for pattern in ['**/*.py', '**/*.html', '**/*.js']:
                all_files.extend(self.project_root.glob(pattern))

            # Filter and convert to strings
            files_to_process = set()
            for file_path in all_files:
                rel_path = str(file_path.relative_to(self.project_root))
                if self._should_process_file(rel_path):
                    files_to_process.add(rel_path)

            print(f"📚 Full indexing: {len(files_to_process)} files")

            # Process all files
            results = self._process_files_parallel(files_to_process)

            # Update metadata
            current_commit = self._get_current_commit()
            IndexMetadata.set_indexed_commit(current_commit)

            # Warm cache
            self._warm_cache()

            elapsed = time.time() - start_time

            return {
                'status': 'success',
                'type': 'full_reindex',
                'elapsed': elapsed,
                'files_processed': len(files_to_process),
                'results': results
            }

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            print(f"Full reindex failed: {e}")
            return {'status': 'error', 'error': str(e)}

    def get_index_health(self) -> Dict[str, Any]:
        """Get index health and statistics."""
        try:
            current_commit = self._get_current_commit()
            indexed_commit = IndexMetadata.get_indexed_commit()

            # Check if index is stale
            is_stale = False
            commits_behind = 0

            if indexed_commit and indexed_commit != current_commit:
                try:
                    result = subprocess.run([
                        'git', 'rev-list', '--count', f"{indexed_commit}..{current_commit}"
                    ], capture_output=True, text=True, cwd=self.project_root, timeout=10)

                    if result.returncode == 0:
                        commits_behind = int(result.stdout.strip())
                        is_stale = commits_behind > 0
                except (ValueError, TypeError):
                    is_stale = True

            # Get statistics
            stats = IndexMetadata.get_index_stats()

            return {
                'current_commit': current_commit,
                'indexed_commit': indexed_commit,
                'is_stale': is_stale,
                'commits_behind': commits_behind,
                'statistics': stats,
                'cache_status': self._get_cache_status()
            }

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            return {'error': str(e)}

    def _get_cache_status(self) -> Dict[str, Any]:
        """Get cache status information."""
        try:
            cache_keys = [
                'file_count', 'symbol_count', 'model_count', 'test_count'
            ]

            status = {}
            for key in cache_keys:
                full_key = f"{self.cache_key_prefix}:{key}"
                value = cache.get(full_key)
                status[key] = {
                    'cached': value is not None,
                    'value': value
                }

            return status

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            return {'error': str(e)}