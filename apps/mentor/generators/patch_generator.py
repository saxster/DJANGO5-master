"""
Patch generator with AST manipulation for intelligent code generation.

This generator provides:
- AST manipulation: Safe code transformation
- Context preservation: Maintain imports, formatting
- Multi-file patches: Coordinated changes
- Conflict resolution: Smart merge strategies
- Rollback generation: Automatic undo patches
"""

import difflib
from pathlib import Path
from enum import Enum

try:
    from libcst.codemod import CodemodContext
    LIBCST_AVAILABLE = True
except ImportError:
    LIBCST_AVAILABLE = False


class PatchType(Enum):
    """Types of patches that can be generated."""
    ADD_FUNCTION = "add_function"
    MODIFY_FUNCTION = "modify_function"
    REMOVE_FUNCTION = "remove_function"
    ADD_CLASS = "add_class"
    MODIFY_CLASS = "modify_class"
    REMOVE_CLASS = "remove_class"
    ADD_IMPORT = "add_import"
    REMOVE_IMPORT = "remove_import"
    REFACTOR = "refactor"
    FIX_SECURITY = "fix_security"
    OPTIMIZE_PERFORMANCE = "optimize_performance"


class PatchPriority(Enum):
    """Priority levels for patches."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class CodePatch:
    """Container for a code patch."""
    type: PatchType
    priority: PatchPriority
    description: str
    file_path: str
    original_code: str
    modified_code: str
    line_start: int
    line_end: int
    dependencies: List[str]
    rollback_patch: Optional['CodePatch'] = None
    confidence: float = 0.8


@dataclass
class MultiFilePatch:
    """Container for coordinated multi-file patches."""
    name: str
    description: str
    patches: List[CodePatch]
    execution_order: List[str]  # File paths in order
    rollback_patches: List[CodePatch]


class PatchGenerator:
    """Intelligent code patch generator with AST manipulation."""

    def __init__(self):
        self.generated_patches = []
        self.context = CodemodContext() if LIBCST_AVAILABLE else None

    def generate_security_fixes(self, security_issues: List[Dict[str, Any]]) -> List[CodePatch]:
        """Generate patches for security vulnerabilities."""
        patches = []

        for issue in security_issues:
            patch = self._generate_security_patch(issue)
            if patch:
                patches.append(patch)

        return patches

    def generate_performance_optimizations(self, performance_issues: List[Dict[str, Any]]) -> List[CodePatch]:
        """Generate patches for performance optimizations."""
        patches = []

        for issue in performance_issues:
            patch = self._generate_performance_patch(issue)
            if patch:
                patches.append(patch)

        return patches

    def generate_code_quality_fixes(self, quality_issues: List[Dict[str, Any]]) -> List[CodePatch]:
        """Generate patches for code quality improvements."""
        patches = []

        for issue in quality_issues:
            patch = self._generate_quality_patch(issue)
            if patch:
                patches.append(patch)

        return patches

    def generate_refactoring_patches(self, refactor_requests: List[Dict[str, Any]]) -> List[MultiFilePatch]:
        """Generate multi-file refactoring patches."""
        multi_patches = []

        for request in refactor_requests:
            multi_patch = self._generate_refactoring_patch(request)
            if multi_patch:
                multi_patches.append(multi_patch)

        return multi_patches

    def _generate_security_patch(self, issue: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate a patch for a specific security issue."""
        issue_type = issue.get('type')
        file_path = issue.get('file_path')
        vulnerable_code = issue.get('vulnerable_code', '')
        line_number = issue.get('line_number', 1)

        if issue_type == 'sql_injection':
            return self._fix_sql_injection(file_path, vulnerable_code, line_number)
        elif issue_type == 'xss_vulnerability':
            return self._fix_xss_vulnerability(file_path, vulnerable_code, line_number)
        elif issue_type == 'csrf_bypass':
            return self._fix_csrf_bypass(file_path, vulnerable_code, line_number)
        elif issue_type == 'hardcoded_secret':
            return self._fix_hardcoded_secret(file_path, vulnerable_code, line_number)

        return None

    def _fix_sql_injection(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to fix SQL injection vulnerability using LibCST."""
        try:
            from apps.mentor.codemods.codemod_engine import CodemodEngine

            # Use LibCST-based SQL injection fix
            engine = CodemodEngine(create_backups=False)
            result = engine.apply_codemod(file_path, "sql_injection_fix", "security")

            if result.success and result.transformed_code and result.changes_made > 0:
                return CodePatch(
                    type=PatchType.FIX_SECURITY,
                    priority=PatchPriority.CRITICAL,
                    description="Fix SQL injection using AST-based parameterized queries",
                    file_path=file_path,
                    original_code=result.original_code,
                    modified_code=result.transformed_code,
                    line_start=line_number,
                    line_end=line_number,
                    dependencies=[],
                    confidence=0.95  # Higher confidence with AST-based approach
                )
        except ImportError:
            # Fallback to string-based approach if LibCST not available
            pass
        except (ValueError, TypeError):
            # Fallback on any error
            pass

        # Fallback to string-based approach
        if '.raw(' in vulnerable_code and '%s' in vulnerable_code:
            # Replace string formatting with parameterized query
            modified_code = vulnerable_code.replace(
                '.raw(', '.raw('
            ).replace('%s', '%(param)s')

            # Add parameter dictionary suggestion
            if 'params=' not in modified_code:
                modified_code += '  # TODO: Add params={"param": value} argument'

            return CodePatch(
                type=PatchType.FIX_SECURITY,
                priority=PatchPriority.CRITICAL,
                description="Fix SQL injection by using parameterized queries (fallback)",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=[],
                confidence=0.8  # Lower confidence with string replacement
            )

        return None

    def _try_libcst_performance_optimization(self, file_path: str, optimization_type: str) -> Optional[CodePatch]:
        """Try to apply LibCST-based performance optimization."""
        try:
            from apps.mentor.codemods.codemod_engine import CodemodEngine

            # Map optimization types to codemod names
            codemod_mapping = {
                'n_plus_one_query': 'query_optimization',
                'missing_db_index': 'database_index_suggestions',
                'inefficient_loop': 'list_comprehension_optimization',
                'missing_caching': 'caching_optimization',
                'transaction_optimization': 'transaction_optimization'
            }

            codemod_name = codemod_mapping.get(optimization_type)
            if not codemod_name:
                return None

            engine = CodemodEngine(create_backups=False)
            result = engine.apply_codemod(file_path, codemod_name, "performance")

            if result.success and result.transformed_code and result.changes_made > 0:
                return CodePatch(
                    type=PatchType.OPTIMIZE_PERFORMANCE,
                    priority=PatchPriority.MEDIUM,
                    description=f"AST-based {optimization_type} optimization",
                    file_path=file_path,
                    original_code=result.original_code,
                    modified_code=result.transformed_code,
                    line_start=1,
                    line_end=len(result.original_code.split('\n')),
                    dependencies=[],
                    confidence=0.9
                )
        except ImportError:
            pass
        except (ValueError, TypeError):
            pass

        return None

    def _fix_xss_vulnerability(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to fix XSS vulnerability using LibCST."""
        try:
            from apps.mentor.codemods.codemod_engine import CodemodEngine

            # Use LibCST-based XSS prevention fix
            engine = CodemodEngine(create_backups=False)
            result = engine.apply_codemod(file_path, "xss_prevention", "security")

            if result.success and result.transformed_code and result.changes_made > 0:
                return CodePatch(
                    type=PatchType.FIX_SECURITY,
                    priority=PatchPriority.HIGH,
                    description="Fix XSS vulnerability using AST-based mark_safe replacement",
                    file_path=file_path,
                    original_code=result.original_code,
                    modified_code=result.transformed_code,
                    line_start=line_number,
                    line_end=line_number,
                    dependencies=[],
                    confidence=0.95  # Higher confidence with AST-based approach
                )
        except ImportError:
            pass
        except (ValueError, TypeError):
            pass

        # Fallback to string-based approaches
        if '|safe' in vulnerable_code:
            # Replace |safe with proper escaping
            modified_code = vulnerable_code.replace('|safe', '|escape')

            return CodePatch(
                type=PatchType.FIX_SECURITY,
                priority=PatchPriority.HIGH,
                description="Fix XSS vulnerability by replacing |safe with |escape (fallback)",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=[],
                confidence=0.8
            )

        elif 'mark_safe(' in vulnerable_code:
            # Replace mark_safe with proper escaping
            modified_code = vulnerable_code.replace('mark_safe(', 'escape(')

            return CodePatch(
                type=PatchType.FIX_SECURITY,
                priority=PatchPriority.HIGH,
                description="Fix XSS vulnerability by replacing mark_safe with escape (fallback)",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=['from django.utils.html import escape'],
                confidence=0.8
            )

        return None

    def _fix_csrf_bypass(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to fix CSRF bypass."""
        if '@csrf_exempt' in vulnerable_code:
            # Remove csrf_exempt and suggest alternative
            modified_code = vulnerable_code.replace('@csrf_exempt\n', '')
            modified_code += '\n# TODO: Implement proper CSRF protection or use @require_http_methods'

            return CodePatch(
                type=PatchType.FIX_SECURITY,
                priority=PatchPriority.HIGH,
                description="Remove CSRF exemption and implement proper protection",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=['from django.views.decorators.http import require_http_methods'],
                confidence=0.7  # Lower confidence as it needs manual review
            )

        return None

    def _fix_hardcoded_secret(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to fix hardcoded secrets."""
        # Extract the secret variable name and value
        lines = vulnerable_code.split('\n')
        for line in lines:
            if '=' in line:
                var_name, _ = line.split('=', 1)
                var_name = var_name.strip()

                # Replace with environment variable
                modified_code = line.replace(
                    line,
                    f"{var_name} = os.getenv('{var_name.upper()}', 'default_value')"
                )

                return CodePatch(
                    type=PatchType.FIX_SECURITY,
                    priority=PatchPriority.CRITICAL,
                    description=f"Replace hardcoded secret {var_name} with environment variable",
                    file_path=file_path,
                    original_code=vulnerable_code,
                    modified_code=modified_code,
                    line_start=line_number,
                    line_end=line_number,
                    dependencies=['import os'],
                    confidence=0.9
                )

        return None

    def _generate_performance_patch(self, issue: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate a patch for a performance issue."""
        issue_type = issue.get('type')
        file_path = issue.get('file_path')
        vulnerable_code = issue.get('code_snippet', '')
        line_number = issue.get('line_number', 1)

        if issue_type == 'n_plus_one_query':
            return self._fix_n_plus_one_query(file_path, vulnerable_code, line_number)
        elif issue_type == 'missing_cache':
            return self._add_caching(file_path, vulnerable_code, line_number)
        elif issue_type == 'inefficient_loop':
            return self._optimize_loop(file_path, vulnerable_code, line_number)

        return None

    def _fix_n_plus_one_query(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to fix N+1 query issue."""
        # Analyze the query pattern
        if '.objects.' in vulnerable_code and 'for' in vulnerable_code:
            # Add select_related or prefetch_related
            if 'select_related' not in vulnerable_code and 'prefetch_related' not in vulnerable_code:
                # Try to identify the related field
                modified_code = vulnerable_code

                # Simple heuristic: add select_related if it looks like a foreign key access
                if '.objects.all()' in vulnerable_code:
                    modified_code = vulnerable_code.replace(
                        '.objects.all()',
                        '.objects.select_related().all()  # TODO: Specify related fields'
                    )
                elif '.objects.filter(' in vulnerable_code:
                    modified_code = vulnerable_code.replace(
                        '.objects.filter(',
                        '.objects.select_related().filter('
                    )

                return CodePatch(
                    type=PatchType.OPTIMIZE_PERFORMANCE,
                    priority=PatchPriority.HIGH,
                    description="Add select_related to prevent N+1 queries",
                    file_path=file_path,
                    original_code=vulnerable_code,
                    modified_code=modified_code,
                    line_start=line_number,
                    line_end=line_number,
                    dependencies=[],
                    confidence=0.7
                )

        return None

    def _add_caching(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to add caching."""
        # Wrap expensive computation with cache
        if 'def ' in vulnerable_code:
            # Extract function name
            func_name = self._extract_function_name(vulnerable_code)

            modified_code = f"""
from django.core.cache import cache

{vulnerable_code}

# Add caching wrapper
def cached_{func_name}(*args, **kwargs):
    cache_key = f"{func_name}_{{hash(str(args) + str(kwargs))}}"
    result = cache.get(cache_key)
    if result is None:
        result = {func_name}(*args, **kwargs)
        cache.set(cache_key, result, timeout=300)  # 5 minutes
    return result
"""

            return CodePatch(
                type=PatchType.OPTIMIZE_PERFORMANCE,
                priority=PatchPriority.MEDIUM,
                description=f"Add caching for function {func_name}",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=['from django.core.cache import cache'],
                confidence=0.6
            )

        return None

    def _optimize_loop(self, file_path: str, vulnerable_code: str, line_number: int) -> CodePatch:
        """Generate patch to optimize inefficient loops."""
        # Convert simple loops to list comprehensions where appropriate
        if 'for ' in vulnerable_code and 'append(' in vulnerable_code:
            # This is a very simplified optimization
            modified_code = f"{vulnerable_code}\n# TODO: Consider using list comprehension for better performance"

            return CodePatch(
                type=PatchType.OPTIMIZE_PERFORMANCE,
                priority=PatchPriority.LOW,
                description="Consider optimizing loop with list comprehension",
                file_path=file_path,
                original_code=vulnerable_code,
                modified_code=modified_code,
                line_start=line_number,
                line_end=line_number,
                dependencies=[],
                confidence=0.5
            )

        return None

    def _generate_quality_patch(self, issue: Dict[str, Any]) -> Optional[CodePatch]:
        """Generate a patch for a code quality issue."""
        issue_type = issue.get('type')
        file_path = issue.get('file_path')
        symbol_name = issue.get('symbol_name', '')
        line_number = issue.get('line_number', 1)

        if issue_type == 'missing_docstring':
            return self._add_docstring(file_path, symbol_name, line_number)
        elif issue_type == 'long_method':
            return self._suggest_method_extraction(file_path, symbol_name, line_number)
        elif issue_type == 'dead_code':
            return self._remove_dead_code(file_path, symbol_name, line_number)

        return None

    def _add_docstring(self, file_path: str, symbol_name: str, line_number: int) -> CodePatch:
        """Generate patch to add missing docstring."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            if line_number <= len(lines):
                original_line = lines[line_number - 1]

                if 'def ' in original_line:
                    # Add function docstring
                    indent = len(original_line) - len(original_line.lstrip())
                    docstring = ' ' * (indent + 4) + f'"""TODO: Document {symbol_name} function."""\n'

                    modified_code = original_line + docstring

                    return CodePatch(
                        type=PatchType.MODIFY_FUNCTION,
                        priority=PatchPriority.LOW,
                        description=f"Add docstring to function {symbol_name}",
                        file_path=file_path,
                        original_code=original_line,
                        modified_code=modified_code,
                        line_start=line_number,
                        line_end=line_number,
                        dependencies=[],
                        confidence=0.9
                    )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            print(f"Error generating docstring patch: {e}")

        return None

    def _suggest_method_extraction(self, file_path: str, symbol_name: str, line_number: int) -> CodePatch:
        """Generate suggestion for method extraction."""
        return CodePatch(
            type=PatchType.REFACTOR,
            priority=PatchPriority.MEDIUM,
            description=f"Consider extracting parts of method {symbol_name} into smaller methods",
            file_path=file_path,
            original_code=f"# Long method: {symbol_name}",
            modified_code=f"# TODO: Extract complex logic from {symbol_name} into helper methods",
            line_start=line_number,
            line_end=line_number,
            dependencies=[],
            confidence=0.6
        )

    def _remove_dead_code(self, file_path: str, symbol_name: str, line_number: int) -> CodePatch:
        """Generate patch to remove dead code."""
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()

            if line_number <= len(lines):
                original_line = lines[line_number - 1]

                # Only remove if it's clearly an unused import
                if 'import ' in original_line and symbol_name in original_line:
                    return CodePatch(
                        type=PatchType.REMOVE_IMPORT,
                        priority=PatchPriority.LOW,
                        description=f"Remove unused import: {symbol_name}",
                        file_path=file_path,
                        original_code=original_line,
                        modified_code="",  # Remove the line
                        line_start=line_number,
                        line_end=line_number,
                        dependencies=[],
                        confidence=0.8
                    )

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            print(f"Error generating dead code removal patch: {e}")

        return None

    def _generate_refactoring_patch(self, request: Dict[str, Any]) -> Optional[MultiFilePatch]:
        """Generate a multi-file refactoring patch."""
        refactor_type = request.get('type')

        if refactor_type == 'extract_service':
            return self._extract_service_class(request)
        elif refactor_type == 'move_method':
            return self._move_method_between_classes(request)

        return None

    def _extract_service_class(self, request: Dict[str, Any]) -> MultiFilePatch:
        """Generate patches to extract a service class."""
        source_file = request.get('source_file')
        methods_to_extract = request.get('methods', [])
        service_name = request.get('service_name', 'Service')

        patches = []

        # Create new service file
        service_content = f"""
\"\"\"
{service_name} - Extracted business logic.
\"\"\"

class {service_name}:
    \"\"\"Service class for business logic.\"\"\"

    def __init__(self):
        pass
"""

        for method in methods_to_extract:
            service_content += f"\n    # TODO: Move method {method} here\n"

        # Patch to create new service file
        service_file_path = source_file.replace('.py', f'_{service_name.lower()}.py')

        patches.append(CodePatch(
            type=PatchType.ADD_CLASS,
            priority=PatchPriority.MEDIUM,
            description=f"Create {service_name} service class",
            file_path=service_file_path,
            original_code="",
            modified_code=service_content,
            line_start=1,
            line_end=1,
            dependencies=[],
            confidence=0.7
        ))

        return MultiFilePatch(
            name=f"Extract {service_name}",
            description=f"Extract business logic into {service_name} service class",
            patches=patches,
            execution_order=[service_file_path, source_file],
            rollback_patches=[]
        )

    def _move_method_between_classes(self, request: Dict[str, Any]) -> MultiFilePatch:
        """Generate patches to move a method between classes."""
        # This is a complex refactoring that would require sophisticated AST manipulation
        # For now, return a placeholder
        return MultiFilePatch(
            name="Move Method",
            description="Move method between classes (requires manual implementation)",
            patches=[],
            execution_order=[],
            rollback_patches=[]
        )

    def apply_patch(self, patch: CodePatch) -> bool:
        """Apply a single patch to a file."""
        try:
            file_path = Path(patch.file_path)

            if not file_path.exists():
                if patch.type == PatchType.ADD_CLASS:
                    # Create new file
                    file_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(file_path, 'w') as f:
                        f.write(patch.modified_code)
                    return True
                else:
                    print(f"File {file_path} does not exist")
                    return False

            # Read current file
            with open(file_path, 'r') as f:
                lines = f.readlines()

            # Apply the patch
            if patch.line_start <= len(lines):
                if patch.modified_code == "":
                    # Remove line(s)
                    del lines[patch.line_start - 1:patch.line_end]
                else:
                    # Replace line(s)
                    new_lines = patch.modified_code.split('\n')
                    if not new_lines[-1]:  # Remove empty last line
                        new_lines = new_lines[:-1]

                    lines[patch.line_start - 1:patch.line_end] = [line + '\n' for line in new_lines]

                # Write modified file
                with open(file_path, 'w') as f:
                    f.writelines(lines)

                return True
            else:
                print(f"Line number {patch.line_start} out of range in {file_path}")
                return False

        except (ConnectionError, DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, ValueError) as e:
            print(f"Error applying patch to {patch.file_path}: {e}")
            return False

    def generate_rollback_patch(self, patch: CodePatch) -> CodePatch:
        """Generate a rollback patch for the given patch."""
        return CodePatch(
            type=patch.type,
            priority=patch.priority,
            description=f"Rollback: {patch.description}",
            file_path=patch.file_path,
            original_code=patch.modified_code,
            modified_code=patch.original_code,
            line_start=patch.line_start,
            line_end=patch.line_end,
            dependencies=[],
            confidence=patch.confidence
        )

    def _extract_function_name(self, code: str) -> str:
        """Extract function name from code snippet."""
        lines = code.split('\n')
        for line in lines:
            if 'def ' in line:
                # Simple regex to extract function name
                import re
                match = re.search(r'def\s+(\w+)\s*\(', line)
                if match:
                    return match.group(1)
        return "unknown_function"

    def get_patch_diff(self, patch: CodePatch) -> str:
        """Generate a unified diff for the patch."""
        original_lines = patch.original_code.split('\n')
        modified_lines = patch.modified_code.split('\n')

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"{patch.file_path} (original)",
            tofile=f"{patch.file_path} (modified)",
            lineterm='',
            n=3
        )

        return '\n'.join(diff)