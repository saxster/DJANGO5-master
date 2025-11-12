"""
Django model extractor for ontology analysis.

Extracts metadata from Django models including fields, relationships,
managers, and business logic methods.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from apps.ontology.extractors.ast_extractor import ASTExtractor, OntologyVisitor

logger = logging.getLogger(__name__)


class ModelExtractor(ASTExtractor):
    """
    Extract ontology metadata from Django models.

    This extractor identifies Django models and extracts:
    - Model fields and their types
    - Relationships (ForeignKey, ManyToMany, OneToOne)
    - Custom managers
    - Model methods
    - Meta options
    - Validation rules
    """

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract metadata from Django models in a file.

        Args:
            file_path: Path to Python file containing models

        Returns:
            List of model metadata dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))
            visitor = ModelVisitor(file_path, source_code)
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


class ModelVisitor(OntologyVisitor):
    """
    AST visitor specialized for Django models.
    """

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract metadata from class definitions, focusing on Django models."""
        # Check if this looks like a Django model
        is_model = self._is_django_model(node)

        if is_model:
            old_class = self.current_class
            self.current_class = node.name

            metadata = {
                "type": "model",
                "name": node.name,
                "qualified_name": f"{self.module_name}.{node.name}",
                "module": self.module_name,
                "source_file": str(self.file_path),
                "source_line": node.lineno,
                "docstring": ast.get_docstring(node),
                "bases": [self._get_name(base) for base in node.bases],
                "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                "domain": "data",  # Default domain for models
                "tags": ["django", "model"],
            }

            # Extract model-specific information
            fields_info = self._extract_fields(node)
            metadata["fields"] = fields_info["fields"]
            metadata["relationships"] = fields_info["relationships"]
            metadata["managers"] = self._extract_managers(node)
            metadata["methods"] = self._extract_methods(node)
            metadata["meta_options"] = self._extract_meta_options(node)

            # Check for @ontology decorator
            ontology_metadata = self._extract_ontology_decorator(node)
            if ontology_metadata:
                metadata.update(ontology_metadata)

            # Add to metadata list
            from apps.ontology.extractors.base_extractor import BaseExtractor

            self.metadata.append(BaseExtractor.normalize_metadata(metadata))

            self.current_class = old_class
        else:
            # Not a model, use parent's visit_ClassDef
            super().visit_ClassDef(node)

    def _is_django_model(self, node: ast.ClassDef) -> bool:
        """
        Check if a class is a Django model.

        Args:
            node: Class definition node

        Returns:
            True if this appears to be a Django model
        """
        # Check if it inherits from models.Model or similar
        for base in node.bases:
            base_name = self._get_name(base)
            if "Model" in base_name or "models.Model" in base_name:
                return True

        return False

    def _extract_fields(self, node: ast.ClassDef) -> Dict[str, Any]:
        """
        Extract field definitions from a model.

        Args:
            node: Class definition node

        Returns:
            Dictionary with 'fields' and 'relationships' lists
        """
        fields = []
        relationships = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                # Class-level assignments are typically fields
                for target in item.targets:
                    if isinstance(target, ast.Name):
                        field_name = target.id

                        # Skip private/dunder attributes
                        if field_name.startswith("_"):
                            continue

                        field_info = {
                            "name": field_name,
                            "line": item.lineno,
                        }

                        # Try to extract field type
                        if isinstance(item.value, ast.Call):
                            field_type = self._get_name(item.value.func)
                            field_info["field_type"] = field_type

                            # Extract field arguments
                            field_info["arguments"] = self._extract_call_arguments(item.value)

                            # Classify as relationship or regular field
                            if any(
                                rel in field_type
                                for rel in ["ForeignKey", "ManyToManyField", "OneToOneField"]
                            ):
                                relationships.append(field_info)
                            else:
                                fields.append(field_info)
                        else:
                            # Non-call assignment
                            field_info["field_type"] = "unknown"
                            fields.append(field_info)

        return {"fields": fields, "relationships": relationships}

    def _extract_call_arguments(self, call_node: ast.Call) -> Dict[str, str]:
        """
        Extract arguments from a function call.

        Args:
            call_node: Call AST node

        Returns:
            Dictionary of argument names to values (as strings)
        """
        arguments = {}

        # Positional arguments
        for i, arg in enumerate(call_node.args):
            arguments[f"arg_{i}"] = ast.unparse(arg)

        # Keyword arguments
        for keyword in call_node.keywords:
            if keyword.arg:
                arguments[keyword.arg] = ast.unparse(keyword.value)

        return arguments

    def _extract_managers(self, node: ast.ClassDef) -> List[Dict[str, Any]]:
        """
        Extract custom managers from a model.

        Args:
            node: Class definition node

        Returns:
            List of manager metadata
        """
        managers = []

        for item in node.body:
            if isinstance(item, ast.Assign):
                # Look for Manager assignments
                if isinstance(item.value, ast.Call):
                    call_name = self._get_name(item.value.func)
                    if "Manager" in call_name:
                        for target in item.targets:
                            if isinstance(target, ast.Name):
                                managers.append(
                                    {
                                        "name": target.id,
                                        "type": call_name,
                                        "line": item.lineno,
                                    }
                                )

        return managers

    def _extract_methods(self, node: ast.ClassDef) -> List[Dict[str, Any]]:
        """
        Extract method information from a model.

        Args:
            node: Class definition node

        Returns:
            List of method metadata
        """
        methods = []

        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Skip special methods except important ones
                if item.name.startswith("__") and item.name not in [
                    "__str__",
                    "__repr__",
                    "__init__",
                ]:
                    continue

                method_info = {
                    "name": item.name,
                    "line": item.lineno,
                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                    "decorators": [self._get_decorator_name(dec) for dec in item.decorator_list],
                    "docstring": ast.get_docstring(item),
                }

                # Identify special method types
                if any(dec.endswith("property") for dec in method_info["decorators"]):
                    method_info["method_type"] = "property"
                elif "classmethod" in method_info["decorators"]:
                    method_info["method_type"] = "classmethod"
                elif "staticmethod" in method_info["decorators"]:
                    method_info["method_type"] = "staticmethod"
                else:
                    method_info["method_type"] = "instance"

                methods.append(method_info)

        return methods

    def _extract_meta_options(self, node: ast.ClassDef) -> Dict[str, Any]:
        """
        Extract Meta class options from a model.

        Args:
            node: Class definition node

        Returns:
            Dictionary of Meta options
        """
        meta_options = {}

        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                # Extract Meta class attributes
                for meta_item in item.body:
                    if isinstance(meta_item, ast.Assign):
                        for target in meta_item.targets:
                            if isinstance(target, ast.Name):
                                option_name = target.id
                                option_value = ast.unparse(meta_item.value)
                                meta_options[option_name] = option_value

        return meta_options
