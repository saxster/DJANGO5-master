"""
AST-based extractor for Python code analysis.

Uses Python's ast module to parse and analyze code structure,
extracting metadata about functions, classes, and their relationships.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from apps.ontology.extractors.base_extractor import BaseExtractor

logger = logging.getLogger(__name__)


class ASTExtractor(BaseExtractor):
    """
    Extract ontology metadata using AST (Abstract Syntax Tree) analysis.

    This extractor parses Python source files and extracts:
    - Function definitions with parameters and return types
    - Class definitions with methods and inheritance
    - Decorators and their arguments
    - Imports and dependencies
    - Docstrings and type hints
    """

    def can_handle(self, file_path: Path) -> bool:
        """Check if this is a Python file."""
        return file_path.suffix == ".py"

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract metadata from a Python file using AST analysis.

        Args:
            file_path: Path to Python file

        Returns:
            List of metadata dictionaries for all functions and classes
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))
            visitor = OntologyVisitor(file_path, source_code)
            visitor.visit(tree)

            return visitor.metadata

        except SyntaxError as e:
            self.add_error(file_path, f"Syntax error: {e}", e.lineno)
            return []
        except Exception as e:
            self.add_error(file_path, f"Error parsing file: {e}")
            return []


class OntologyVisitor(ast.NodeVisitor):
    """
    AST visitor that extracts ontology metadata.

    Walks through the AST and collects information about functions,
    classes, and their metadata.
    """

    def __init__(self, file_path: Path, source_code: str):
        """
        Initialize the visitor.

        Args:
            file_path: Path to the file being analyzed
            source_code: Source code of the file
        """
        self.file_path = file_path
        self.source_code = source_code
        self.source_lines = source_code.splitlines()
        self.metadata: List[Dict[str, Any]] = []
        self.current_class: Optional[str] = None
        self.imports: Set[str] = set()
        self.module_name = self._get_module_name()

    def _get_module_name(self) -> str:
        """
        Derive the module name from the file path.

        Returns:
            Module name (e.g., "apps.core.utils")
        """
        # Try to find the module path relative to the project root
        parts = self.file_path.parts
        try:
            # Find 'apps' in the path
            apps_index = parts.index("apps")
            module_parts = parts[apps_index:-1]  # Exclude filename
            # Add the filename without extension
            module_parts = list(module_parts) + [self.file_path.stem]
            return ".".join(module_parts)
        except (ValueError, IndexError):
            # Fallback to just the filename
            return self.file_path.stem

    def visit_Import(self, node: ast.Import) -> None:
        """Record regular imports."""
        for alias in node.names:
            self.imports.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Record from-imports."""
        if node.module:
            self.imports.add(node.module)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract metadata from class definitions."""
        old_class = self.current_class
        self.current_class = node.name

        metadata = {
            "type": "class",
            "name": node.name,
            "qualified_name": f"{self.module_name}.{node.name}",
            "module": self.module_name,
            "source_file": str(self.file_path),
            "source_line": node.lineno,
            "docstring": ast.get_docstring(node),
            "bases": [self._get_name(base) for base in node.bases],
            "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
            "methods": [],
        }

        # Check for @ontology decorator
        ontology_metadata = self._extract_ontology_decorator(node)
        if ontology_metadata:
            metadata.update(ontology_metadata)

        # Extract methods
        for item in node.body:
            if isinstance(item, ast.FunctionDef):
                method_metadata = self._extract_function(item, is_method=True)
                metadata["methods"].append(method_metadata["name"])

        self.metadata.append(BaseExtractor.normalize_metadata(metadata))

        # Visit child nodes
        self.generic_visit(node)

        self.current_class = old_class

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract metadata from function definitions."""
        # Only process top-level functions (methods are handled by visit_ClassDef)
        if self.current_class is None:
            metadata = self._extract_function(node, is_method=False)
            self.metadata.append(BaseExtractor.normalize_metadata(metadata))

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Extract metadata from async function definitions."""
        if self.current_class is None:
            metadata = self._extract_function(node, is_method=False, is_async=True)
            self.metadata.append(BaseExtractor.normalize_metadata(metadata))

        self.generic_visit(node)

    def _extract_function(
        self, node: ast.FunctionDef, is_method: bool, is_async: bool = False
    ) -> Dict[str, Any]:
        """
        Extract metadata from a function or method.

        Args:
            node: AST node for the function
            is_method: Whether this is a class method
            is_async: Whether this is an async function

        Returns:
            Metadata dictionary
        """
        if is_method and self.current_class:
            qualified_name = f"{self.module_name}.{self.current_class}.{node.name}"
        else:
            qualified_name = f"{self.module_name}.{node.name}"

        metadata = {
            "type": "method" if is_method else "function",
            "name": node.name,
            "qualified_name": qualified_name,
            "module": self.module_name,
            "source_file": str(self.file_path),
            "source_line": node.lineno,
            "docstring": ast.get_docstring(node),
            "is_async": is_async,
            "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
            "parameters": self._extract_parameters(node),
            "return_type": self._get_return_annotation(node),
        }

        # Check for @ontology decorator
        ontology_metadata = self._extract_ontology_decorator(node)
        if ontology_metadata:
            metadata.update(ontology_metadata)

        # Analyze function body for dependencies and side effects
        analyzer = FunctionAnalyzer()
        analyzer.visit(node)

        metadata["calls"] = list(analyzer.calls)
        metadata["side_effects"] = []

        # Detect common side effects
        if analyzer.has_database_access:
            metadata["side_effects"].append("Database access")
        if analyzer.has_file_io:
            metadata["side_effects"].append("File I/O")
        if analyzer.has_network_io:
            metadata["side_effects"].append("Network I/O")

        return metadata

    def _extract_parameters(self, node: ast.FunctionDef) -> List[Dict[str, Any]]:
        """
        Extract parameter information from a function.

        Args:
            node: Function AST node

        Returns:
            List of parameter metadata
        """
        parameters = []
        args = node.args

        # Regular arguments
        for arg in args.args:
            param = {
                "name": arg.arg,
                "type": self._get_annotation(arg),
                "default": None,
                "kind": "positional_or_keyword",
            }
            parameters.append(param)

        # Handle defaults (they align from the right)
        num_defaults = len(args.defaults)
        if num_defaults > 0:
            default_offset = len(args.args) - num_defaults
            for i, default in enumerate(args.defaults):
                parameters[default_offset + i]["default"] = ast.unparse(default)

        # Keyword-only arguments
        for arg in args.kwonlyargs:
            param = {
                "name": arg.arg,
                "type": self._get_annotation(arg),
                "default": None,
                "kind": "keyword_only",
            }
            parameters.append(param)

        # Keyword-only defaults
        for i, default in enumerate(args.kw_defaults):
            if default is not None:
                parameters[len(args.args) + i]["default"] = ast.unparse(default)

        # *args
        if args.vararg:
            parameters.append(
                {
                    "name": args.vararg.arg,
                    "type": self._get_annotation(args.vararg),
                    "default": None,
                    "kind": "var_positional",
                }
            )

        # **kwargs
        if args.kwarg:
            parameters.append(
                {
                    "name": args.kwarg.arg,
                    "type": self._get_annotation(args.kwarg),
                    "default": None,
                    "kind": "var_keyword",
                }
            )

        return parameters

    def _get_annotation(self, arg: ast.arg) -> Optional[str]:
        """Get type annotation as string."""
        if arg.annotation:
            return ast.unparse(arg.annotation)
        return None

    def _get_return_annotation(self, node: ast.FunctionDef) -> Optional[str]:
        """Get return type annotation as string."""
        if node.returns:
            return ast.unparse(node.returns)
        return None

    def _get_decorator_name(self, decorator: ast.expr) -> str:
        """Extract decorator name as string."""
        return ast.unparse(decorator)

    def _get_name(self, node: ast.expr) -> str:
        """Extract name from an AST node."""
        return ast.unparse(node)

    def _extract_ontology_decorator(self, node) -> Optional[Dict[str, Any]]:
        """
        Extract metadata from @ontology decorator if present.

        Args:
            node: AST node (FunctionDef or ClassDef)

        Returns:
            Metadata from decorator, or None
        """
        for decorator in node.decorator_list:
            # Check if this is an @ontology decorator
            decorator_name = ast.unparse(decorator)
            if "ontology" in decorator_name.lower():
                # Try to extract keyword arguments
                if isinstance(decorator, ast.Call):
                    metadata = {}
                    for keyword in decorator.keywords:
                        # Store decorator arguments as unparsed strings
                        # This avoids security issues with arbitrary code execution
                        metadata[keyword.arg] = self._safe_extract_value(keyword.value)
                    return metadata

        return None

    def _safe_extract_value(self, node: ast.expr) -> Any:
        """
        Safely extract values from AST nodes without executing code.

        Args:
            node: AST expression node

        Returns:
            Extracted value (string, number, list, dict, or unparsed string)
        """
        # Handle simple literal types safely
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.List):
            return [self._safe_extract_value(elt) for elt in node.elts]
        elif isinstance(node, ast.Dict):
            return {
                self._safe_extract_value(k): self._safe_extract_value(v)
                for k, v in zip(node.keys, node.values)
            }
        elif isinstance(node, ast.Tuple):
            return tuple(self._safe_extract_value(elt) for elt in node.elts)
        else:
            # For complex expressions, return the unparsed string representation
            return ast.unparse(node)


class FunctionAnalyzer(ast.NodeVisitor):
    """
    Analyzes function bodies to detect side effects and dependencies.
    """

    def __init__(self):
        """Initialize the analyzer."""
        self.calls: Set[str] = set()
        self.has_database_access = False
        self.has_file_io = False
        self.has_network_io = False

    def visit_Call(self, node: ast.Call) -> None:
        """Analyze function calls."""
        call_name = ast.unparse(node.func)
        self.calls.add(call_name)

        # Detect common patterns
        if any(
            pattern in call_name.lower()
            for pattern in ["save", "delete", "update", "create", "filter", "get", "query"]
        ):
            self.has_database_access = True

        if any(pattern in call_name.lower() for pattern in ["open", "read", "write", "file"]):
            self.has_file_io = True

        if any(
            pattern in call_name.lower()
            for pattern in ["request", "http", "api", "fetch", "post", "get"]
        ):
            self.has_network_io = True

        self.generic_visit(node)
