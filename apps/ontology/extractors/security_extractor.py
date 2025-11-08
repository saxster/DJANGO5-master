"""
Security pattern detector for ontology analysis.

Identifies security-related patterns, decorators, and potential issues
in the codebase by analyzing AST patterns.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Set

from apps.ontology.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class SecurityExtractor(BaseExtractor):
    """
    Extract security-related patterns and metadata.

    This extractor identifies:
    - Authentication and authorization decorators
    - Permission checks
    - Security-sensitive operations
    - Input validation and sanitization
    - Potentially unsafe code patterns
    - CSRF protection
    - Rate limiting
    """

    def __init__(self, root_path=None):
        """Initialize the security extractor."""
        super().__init__(root_path)

        # Security-related decorators to look for
        self.SECURITY_DECORATORS = {
            "login_required",
            "permission_required",
            "user_passes_test",
            "csrf_exempt",
            "csrf_protect",
            "require_http_methods",
            "require_GET",
            "require_POST",
            "require_safe",
            "throttle",
            "ratelimit",
            "authentication_classes",
            "permission_classes",
        }

        # Pattern names to detect (stored as strings for detection only)
        self.RISKY_FUNCTION_NAMES = [
            "eval",
            "exec",
            "compile",
            "__import__",
        ]

    def can_handle(self, file_path: Path) -> bool:
        """Check if this is a Python file."""
        return file_path.suffix == ".py"

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract security patterns from a Python file.

        Args:
            file_path: Path to Python file

        Returns:
            List of security-related metadata dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))
            visitor = SecurityVisitor(
                file_path, source_code, self.SECURITY_DECORATORS, self.RISKY_FUNCTION_NAMES
            )
            visitor.visit(tree)

            return visitor.metadata

        except SyntaxError as e:
            self.add_error(file_path, f"Syntax error: {e}", e.lineno)
            return []
        except (OSError, IOError, UnicodeDecodeError) as e:
            self.add_error(file_path, f"Error reading file: {e}")
            logger.error(f"Failed to read {file_path}: {e}", exc_info=True)
            return []
        except (ValueError, TypeError, AttributeError) as e:
            self.add_error(file_path, f"Error parsing file: {e}")
            logger.error(f"Failed to parse {file_path}: {e}", exc_info=True)
            return []


class SecurityVisitor(ast.NodeVisitor):
    """
    AST visitor that identifies security patterns.
    """

    def __init__(
        self,
        file_path: Path,
        source_code: str,
        security_decorators: Set[str],
        risky_function_names: List[str],
    ):
        """
        Initialize the visitor.

        Args:
            file_path: Path to the file being analyzed
            source_code: Source code of the file
            security_decorators: Set of security decorator names
            risky_function_names: List of risky function names to detect
        """
        self.file_path = file_path
        self.source_code = source_code
        self.security_decorators = security_decorators
        self.risky_function_names = risky_function_names
        self.metadata: List[Dict[str, Any]] = []
        self.module_name = self._get_module_name()

    def _get_module_name(self) -> str:
        """Derive the module name from the file path."""
        parts = self.file_path.parts
        try:
            apps_index = parts.index("apps")
            module_parts = parts[apps_index:-1]
            module_parts = list(module_parts) + [self.file_path.stem]
            return ".".join(module_parts)
        except (ValueError, IndexError):
            return self.file_path.stem

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Analyze function definitions for security patterns."""
        security_info = self._analyze_function(node)

        if security_info:
            metadata = {
                "type": "security_pattern",
                "name": node.name,
                "qualified_name": f"{self.module_name}.{node.name}",
                "module": self.module_name,
                "source_file": str(self.file_path),
                "source_line": node.lineno,
                "domain": "security",
                "tags": ["security"],
            }

            metadata.update(security_info)
            self.metadata.append(metadata)

        self.generic_visit(node)

    def _analyze_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """
        Analyze a function for security patterns.

        Args:
            node: Function definition node

        Returns:
            Dictionary of security-related metadata
        """
        info = {
            "security_decorators": [],
            "potential_issues": [],
            "permission_checks": [],
            "authentication_required": False,
        }

        # Check decorators
        for decorator in node.decorator_list:
            decorator_str = ast.unparse(decorator)

            # Check for security decorators
            for sec_dec in self.security_decorators:
                if sec_dec in decorator_str:
                    info["security_decorators"].append(decorator_str)

                    if sec_dec in ["login_required", "permission_required"]:
                        info["authentication_required"] = True

                    # Note potential security issues
                    if sec_dec == "csrf_exempt":
                        info["potential_issues"].append(
                            {
                                "type": "csrf_exempt",
                                "line": node.lineno,
                                "severity": "warning",
                                "message": "CSRF protection disabled",
                            }
                        )

        # Analyze function body for risky patterns
        body_analyzer = RiskyPatternAnalyzer(self.risky_function_names)
        body_analyzer.visit(node)

        if body_analyzer.findings:
            info["potential_issues"].extend(body_analyzer.findings)

        # Return info only if we found something interesting
        if any(
            [
                info["security_decorators"],
                info["potential_issues"],
                info["authentication_required"],
            ]
        ):
            return info

        return {}


class RiskyPatternAnalyzer(ast.NodeVisitor):
    """
    Analyzes function bodies for potentially risky patterns.
    """

    def __init__(self, risky_function_names: List[str]):
        """
        Initialize the analyzer.

        Args:
            risky_function_names: List of function names to flag
        """
        self.risky_function_names = risky_function_names
        self.findings: List[Dict[str, Any]] = []

    def visit_Call(self, node: ast.Call) -> None:
        """Analyze function calls for risky patterns."""
        call_str = ast.unparse(node.func)

        # Check for risky function calls
        for func_name in self.risky_function_names:
            if func_name in call_str:
                self.findings.append(
                    {
                        "type": "risky_call",
                        "pattern": func_name,
                        "call": call_str,
                        "line": node.lineno,
                        "severity": "high",
                        "message": f"Review use of {func_name} for security implications",
                    }
                )

        self.generic_visit(node)
