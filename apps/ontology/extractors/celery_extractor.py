"""
Celery task extractor for ontology analysis.

Extracts metadata from Celery tasks including task configuration,
retry policies, and queue assignments.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List

from apps.ontology.extractors.ast_extractor import ASTExtractor, OntologyVisitor

logger = logging.getLogger(__name__)


class CeleryExtractor(ASTExtractor):
    """
    Extract ontology metadata from Celery tasks.

    This extractor identifies Celery tasks and extracts:
    - Task configuration (name, queue, rate_limit, etc.)
    - Retry policies
    - Task dependencies
    - Scheduled (periodic) tasks
    - Task chains and groups
    """

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract metadata from Celery tasks in a file.

        Args:
            file_path: Path to Python file containing tasks

        Returns:
            List of task metadata dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))
            visitor = CeleryVisitor(file_path, source_code)
            visitor.visit(tree)

            return visitor.metadata

        except SyntaxError as e:
            self.add_error(file_path, f"Syntax error: {e}", e.lineno)
            return []
        except Exception as e:
            self.add_error(file_path, f"Error parsing file: {e}")
            return []


class CeleryVisitor(OntologyVisitor):
    """
    AST visitor specialized for Celery tasks.
    """

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Extract metadata from function definitions, focusing on Celery tasks."""
        # Check if this is a Celery task
        is_task, task_config = self._is_celery_task(node)

        if is_task:
            metadata = {
                "type": "celery_task",
                "name": node.name,
                "qualified_name": f"{self.module_name}.{node.name}",
                "module": self.module_name,
                "source_file": str(self.file_path),
                "source_line": node.lineno,
                "docstring": ast.get_docstring(node),
                "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                "domain": "tasks",
                "tags": ["celery", "async", "background"],
            }

            # Add Celery-specific configuration
            metadata.update(task_config)

            # Extract parameters
            metadata["parameters"] = self._extract_parameters(node)

            # Check for @ontology decorator
            ontology_metadata = self._extract_ontology_decorator(node)
            if ontology_metadata:
                metadata.update(ontology_metadata)

            # Add to metadata list
            from apps.ontology.extractors.base_extractor import BaseExtractor

            self.metadata.append(BaseExtractor.normalize_metadata(metadata))
        else:
            # Not a task, use parent's visit_FunctionDef
            super().visit_FunctionDef(node)

    def _is_celery_task(self, node: ast.FunctionDef) -> tuple:
        """
        Check if a function is a Celery task.

        Args:
            node: Function definition node

        Returns:
            Tuple of (is_task: bool, config: dict)
        """
        config = {}

        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)

            # Check for common Celery task decorators
            if any(
                pattern in decorator_name.lower()
                for pattern in ["@task", "@shared_task", "@app.task", ".task"]
            ):
                # Extract decorator arguments
                if isinstance(decorator, ast.Call):
                    for keyword in decorator.keywords:
                        arg_name = keyword.arg
                        arg_value = self._safe_extract_value(keyword.value)
                        config[f"task_{arg_name}"] = arg_value

                return True, config

        return False, {}


    def _safe_extract_value(self, node: ast.expr) -> Any:
        """
        Safely extract values from AST nodes without executing code.

        Args:
            node: AST expression node

        Returns:
            Extracted value
        """
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
            # For complex expressions, return unparsed string
            return ast.unparse(node)
