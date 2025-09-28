"""
LibCST codemod execution engine for the AI Mentor system.

This engine orchestrates the execution of codemods, handles file transformations,
and provides a unified interface for applying AST-based code modifications.
"""

import traceback
from pathlib import Path
try:
    import libcst as cst
    from libcst.codemod import CodemodContext, VisitorBasedCodemodCommand
    from libcst.metadata import PositionProvider, ScopeProvider
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False
    cst = None
    CodemodContext = None
    VisitorBasedCodemodCommand = None

from .security_codemods import SECURITY_CODEMODS, get_security_codemod
from .performance_codemods import PERFORMANCE_CODEMODS, get_performance_codemod


@dataclass
class CodemodResult:
    """Result of applying a codemod to a file."""
    file_path: str
    codemod_name: str
    success: bool
    original_code: str
    transformed_code: Optional[str]
    error_message: Optional[str] = None
    changes_made: int = 0
    backup_created: bool = False


@dataclass
class CodemodSession:
    """Complete codemod session results."""
    session_id: str
    total_files: int
    successful_transforms: int
    failed_transforms: int
    total_changes: int
    results: List[CodemodResult]
    backup_directory: Optional[str] = None


class CodemodEngine:
    """
    Engine for executing LibCST-based codemods on Python source files.

    Features:
    - Safe AST-based transformations
    - Automatic backup creation
    - Batch processing of multiple files
    - Error handling and rollback
    - Preservation of formatting and comments
    """

    def __init__(self, create_backups: bool = True, backup_dir: Optional[str] = None):
        if not LIBCST_AVAILABLE:
            raise ImportError(
                "LibCST is not available. Install it with: pip install libcst"
            )

        self.create_backups = create_backups
        self.backup_dir = backup_dir or "/tmp/mentor_backups"
        self.context = CodemodContext()

        # Initialize metadata providers
        self.metadata_dependencies = (PositionProvider, ScopeProvider)

    def apply_codemod(
        self,
        file_path: str,
        codemod_name: str,
        codemod_type: str = "security"
    ) -> CodemodResult:
        """
        Apply a single codemod to a single file.

        Args:
            file_path: Path to the Python file to transform
            codemod_name: Name of the codemod to apply
            codemod_type: Type of codemod (security, performance)

        Returns:
            CodemodResult with transformation details
        """
        file_path = Path(file_path)

        # Validate file
        if not file_path.exists():
            return CodemodResult(
                file_path=str(file_path),
                codemod_name=codemod_name,
                success=False,
                original_code="",
                transformed_code=None,
                error_message=f"File not found: {file_path}"
            )

        if not file_path.suffix == '.py':
            return CodemodResult(
                file_path=str(file_path),
                codemod_name=codemod_name,
                success=False,
                original_code="",
                transformed_code=None,
                error_message="File is not a Python file"
            )

        try:
            # Read original file
            original_code = file_path.read_text(encoding='utf-8')

            # Get codemod class
            codemod_class = self._get_codemod_class(codemod_name, codemod_type)
            if not codemod_class:
                return CodemodResult(
                    file_path=str(file_path),
                    codemod_name=codemod_name,
                    success=False,
                    original_code=original_code,
                    transformed_code=None,
                    error_message=f"Codemod not found: {codemod_name}"
                )

            # Apply transformation
            transformed_code = self._transform_code(
                original_code, codemod_class, str(file_path)
            )

            # Check if changes were made
            changes_made = 0 if transformed_code == original_code else 1

            # Create backup if changes were made
            backup_created = False
            if changes_made > 0 and self.create_backups:
                backup_created = self._create_backup(file_path, original_code)

            return CodemodResult(
                file_path=str(file_path),
                codemod_name=codemod_name,
                success=True,
                original_code=original_code,
                transformed_code=transformed_code,
                changes_made=changes_made,
                backup_created=backup_created
            )

        except (TypeError, ValidationError, ValueError) as e:
            return CodemodResult(
                file_path=str(file_path),
                codemod_name=codemod_name,
                success=False,
                original_code=original_code if 'original_code' in locals() else "",
                transformed_code=None,
                error_message=f"Transform error: {str(e)}\n{traceback.format_exc()}"
            )

    def apply_codemods_batch(
        self,
        file_paths: List[str],
        codemods: List[Dict[str, str]],
        apply_changes: bool = False
    ) -> CodemodSession:
        """
        Apply multiple codemods to multiple files.

        Args:
            file_paths: List of file paths to transform
            codemods: List of codemod specifications [{'name': 'codemod_name', 'type': 'security'}]
            apply_changes: Whether to write changes back to files

        Returns:
            CodemodSession with complete results
        """
        import time
        session_id = f"session_{int(time.time())}"

        results = []
        total_changes = 0

        for file_path in file_paths:
            for codemod_spec in codemods:
                codemod_name = codemod_spec['name']
                codemod_type = codemod_spec.get('type', 'security')

                result = self.apply_codemod(file_path, codemod_name, codemod_type)
                results.append(result)
                total_changes += result.changes_made

                # Apply changes to file if requested and successful
                if apply_changes and result.success and result.transformed_code:
                    try:
                        Path(file_path).write_text(result.transformed_code, encoding='utf-8')
                    except (ValueError, TypeError) as e:
                        result.success = False
                        result.error_message = f"Failed to write file: {e}"

        # Calculate summary statistics
        successful = sum(1 for r in results if r.success)
        failed = len(results) - successful

        return CodemodSession(
            session_id=session_id,
            total_files=len(file_paths),
            successful_transforms=successful,
            failed_transforms=failed,
            total_changes=total_changes,
            results=results,
            backup_directory=self.backup_dir if self.create_backups else None
        )

    def apply_security_fixes(
        self,
        file_paths: List[str],
        fix_types: Optional[List[str]] = None,
        apply_changes: bool = False
    ) -> CodemodSession:
        """
        Apply all security codemods to specified files.

        Args:
            file_paths: List of file paths to fix
            fix_types: Specific security fixes to apply (None = all)
            apply_changes: Whether to write changes back to files

        Returns:
            CodemodSession with results
        """
        if fix_types is None:
            fix_types = list(SECURITY_CODEMODS.keys())

        codemods = [{'name': fix_type, 'type': 'security'} for fix_type in fix_types]
        return self.apply_codemods_batch(file_paths, codemods, apply_changes)

    def apply_performance_optimizations(
        self,
        file_paths: List[str],
        optimization_types: Optional[List[str]] = None,
        apply_changes: bool = False
    ) -> CodemodSession:
        """
        Apply all performance codemods to specified files.

        Args:
            file_paths: List of file paths to optimize
            optimization_types: Specific optimizations to apply (None = all)
            apply_changes: Whether to write changes back to files

        Returns:
            CodemodSession with results
        """
        if optimization_types is None:
            optimization_types = list(PERFORMANCE_CODEMODS.keys())

        codemods = [{'name': opt_type, 'type': 'performance'} for opt_type in optimization_types]
        return self.apply_codemods_batch(file_paths, codemods, apply_changes)

    def preview_changes(
        self,
        file_path: str,
        codemod_name: str,
        codemod_type: str = "security"
    ) -> str:
        """
        Preview the changes that would be made by a codemod without applying them.

        Returns:
            Unified diff showing the changes
        """
        result = self.apply_codemod(file_path, codemod_name, codemod_type)

        if not result.success or not result.transformed_code:
            return f"Error: {result.error_message}"

        if result.original_code == result.transformed_code:
            return "No changes would be made."

        # Generate unified diff
        import difflib
        diff = difflib.unified_diff(
            result.original_code.splitlines(keepends=True),
            result.transformed_code.splitlines(keepends=True),
            fromfile=f"{file_path} (original)",
            tofile=f"{file_path} (transformed)",
            lineterm=""
        )

        return ''.join(diff)

    def rollback_file(self, file_path: str) -> bool:
        """
        Rollback a file to its backup version.

        Args:
            file_path: Path to the file to rollback

        Returns:
            True if rollback was successful
        """
        if not self.create_backups:
            return False

        backup_path = self._get_backup_path(file_path)
        if not backup_path.exists():
            return False

        try:
            # Restore from backup
            original_content = backup_path.read_text(encoding='utf-8')
            Path(file_path).write_text(original_content, encoding='utf-8')
            return True
        except (TypeError, ValidationError, ValueError):
            return False

    def cleanup_backups(self, older_than_days: int = 7) -> int:
        """
        Clean up old backup files.

        Args:
            older_than_days: Remove backups older than this many days

        Returns:
            Number of backup files removed
        """
        if not self.create_backups:
            return 0

        import time
        cutoff_time = time.time() - (older_than_days * 24 * 60 * 60)
        removed_count = 0

        backup_dir = Path(self.backup_dir)
        if backup_dir.exists():
            for backup_file in backup_dir.rglob("*.backup"):
                try:
                    if backup_file.stat().st_mtime < cutoff_time:
                        backup_file.unlink()
                        removed_count += 1
                except (ValueError, TypeError):
                    pass

        return removed_count

    def _get_codemod_class(
        self,
        codemod_name: str,
        codemod_type: str
    ) -> Optional[Type[VisitorBasedCodemodCommand]]:
        """Get the codemod class by name and type."""
        if codemod_type == "security":
            return get_security_codemod(codemod_name)
        elif codemod_type == "performance":
            return get_performance_codemod(codemod_name)
        else:
            return None

    def _transform_code(
        self,
        source_code: str,
        codemod_class: Type[VisitorBasedCodemodCommand],
        file_path: str
    ) -> str:
        """Transform source code using the specified codemod."""
        try:
            # Parse the source code
            tree = cst.parse_module(source_code)

            # Create wrapper with metadata
            wrapper = cst.MetadataWrapper(tree)

            # Initialize codemod with context
            codemod_instance = codemod_class(self.context)

            # Apply the transformation
            transformed_tree = wrapper.visit(codemod_instance)

            # Generate transformed code
            transformed_code = transformed_tree.code

            return transformed_code

        except (TypeError, ValidationError, ValueError) as e:
            # If transformation fails, return original code
            raise Exception(f"Codemod transformation failed: {str(e)}")

    def _create_backup(self, file_path: Path, content: str) -> bool:
        """Create a backup of the original file."""
        try:
            backup_path = self._get_backup_path(str(file_path))
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(content, encoding='utf-8')
            return True
        except (TypeError, ValidationError, ValueError):
            return False

    def _get_backup_path(self, file_path: str) -> Path:
        """Get the backup path for a given file."""
        import time
        file_path = Path(file_path)
        timestamp = int(time.time())

        backup_name = f"{file_path.stem}_{timestamp}.backup"
        backup_dir = Path(self.backup_dir)

        # Preserve directory structure in backup
        relative_path = file_path.relative_to(Path.cwd()) if file_path.is_absolute() else file_path
        return backup_dir / relative_path.parent / backup_name


class CodemodManager:
    """
    High-level manager for codemod operations.

    Provides convenient methods for common codemod scenarios.
    """

    def __init__(self, create_backups: bool = True):
        self.engine = CodemodEngine(create_backups=create_backups)

    def fix_security_issues(
        self,
        file_or_directory: str,
        specific_fixes: Optional[List[str]] = None,
        apply_changes: bool = False,
        recursive: bool = True
    ) -> CodemodSession:
        """
        Fix security issues in files or directories.

        Args:
            file_or_directory: Path to file or directory
            specific_fixes: List of specific security fixes to apply
            apply_changes: Whether to apply changes to files
            recursive: Whether to search directories recursively

        Returns:
            CodemodSession with results
        """
        file_paths = self._collect_python_files(file_or_directory, recursive)
        return self.engine.apply_security_fixes(file_paths, specific_fixes, apply_changes)

    def optimize_performance(
        self,
        file_or_directory: str,
        specific_optimizations: Optional[List[str]] = None,
        apply_changes: bool = False,
        recursive: bool = True
    ) -> CodemodSession:
        """
        Apply performance optimizations to files or directories.

        Args:
            file_or_directory: Path to file or directory
            specific_optimizations: List of specific optimizations to apply
            apply_changes: Whether to apply changes to files
            recursive: Whether to search directories recursively

        Returns:
            CodemodSession with results
        """
        file_paths = self._collect_python_files(file_or_directory, recursive)
        return self.engine.apply_performance_optimizations(
            file_paths, specific_optimizations, apply_changes
        )

    def preview_all_changes(
        self,
        file_path: str,
        codemod_types: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """
        Preview all possible changes for a file.

        Args:
            file_path: Path to the file
            codemod_types: Types of codemods to preview ('security', 'performance')

        Returns:
            Dict mapping codemod names to their diff previews
        """
        if codemod_types is None:
            codemod_types = ['security', 'performance']

        previews = {}

        if 'security' in codemod_types:
            for codemod_name in SECURITY_CODEMODS.keys():
                preview = self.engine.preview_changes(file_path, codemod_name, 'security')
                if preview != "No changes would be made.":
                    previews[f"security:{codemod_name}"] = preview

        if 'performance' in codemod_types:
            for codemod_name in PERFORMANCE_CODEMODS.keys():
                preview = self.engine.preview_changes(file_path, codemod_name, 'performance')
                if preview != "No changes would be made.":
                    previews[f"performance:{codemod_name}"] = preview

        return previews

    def _collect_python_files(self, path: str, recursive: bool) -> List[str]:
        """Collect all Python files from a path."""
        path = Path(path)
        files = []

        if path.is_file() and path.suffix == '.py':
            files.append(str(path))
        elif path.is_dir():
            if recursive:
                files.extend(str(p) for p in path.rglob("*.py"))
            else:
                files.extend(str(p) for p in path.glob("*.py"))

        return files


# Convenience functions
def create_codemod_manager(create_backups: bool = True) -> CodemodManager:
    """Create a codemod manager with default settings."""
    return CodemodManager(create_backups=create_backups)


def quick_security_fix(
    file_path: str,
    apply_changes: bool = False
) -> CodemodSession:
    """Quick security fix for a single file."""
    manager = create_codemod_manager()
    return manager.fix_security_issues(file_path, apply_changes=apply_changes)


def quick_performance_optimization(
    file_path: str,
    apply_changes: bool = False
) -> CodemodSession:
    """Quick performance optimization for a single file."""
    manager = create_codemod_manager()
    return manager.optimize_performance(file_path, apply_changes=apply_changes)