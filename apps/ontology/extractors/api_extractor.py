"""
REST API extractor for ontology analysis.

Extracts metadata from Django REST Framework views, viewsets, and serializers.
"""

import ast
import logging
from pathlib import Path
from typing import Any, Dict, List

from apps.ontology.extractors.ast_extractor import ASTExtractor, OntologyVisitor

logger = logging.getLogger(__name__)


class APIExtractor(ASTExtractor):
    """
    Extract ontology metadata from REST API components.

    This extractor identifies DRF components and extracts:
    - ViewSets and their actions
    - APIViews and their HTTP methods
    - Serializers and their fields
    - Permissions and authentication
    - URL patterns and routing
    """

    def extract(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        Extract metadata from API components in a file.

        Args:
            file_path: Path to Python file containing API code

        Returns:
            List of API component metadata dictionaries
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                source_code = f.read()

            tree = ast.parse(source_code, filename=str(file_path))
            visitor = APIVisitor(file_path, source_code)
            visitor.visit(tree)

            return visitor.metadata

        except SyntaxError as e:
            self.add_error(file_path, f"Syntax error: {e}", e.lineno)
            return []
        except Exception as e:
            self.add_error(file_path, f"Error parsing file: {e}")
            return []


class APIVisitor(OntologyVisitor):
    """
    AST visitor specialized for REST API components.
    """

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Extract metadata from class definitions, focusing on API components."""
        component_type = self._identify_api_component(node)

        if component_type:
            old_class = self.current_class
            self.current_class = node.name

            metadata = {
                "type": component_type,
                "name": node.name,
                "qualified_name": f"{self.module_name}.{node.name}",
                "module": self.module_name,
                "source_file": str(self.file_path),
                "source_line": node.lineno,
                "docstring": ast.get_docstring(node),
                "bases": [self._get_name(base) for base in node.bases],
                "decorators": [self._get_decorator_name(dec) for dec in node.decorator_list],
                "domain": "api",
                "tags": ["api", "rest"],
            }

            # Extract component-specific information
            if component_type in ["viewset", "apiview"]:
                metadata.update(self._extract_view_info(node))
            elif component_type == "serializer":
                metadata.update(self._extract_serializer_info(node))

            # Check for @ontology decorator
            ontology_metadata = self._extract_ontology_decorator(node)
            if ontology_metadata:
                metadata.update(ontology_metadata)

            # Add to metadata list
            from apps.ontology.extractors.base_extractor import BaseExtractor

            self.metadata.append(BaseExtractor.normalize_metadata(metadata))

            self.current_class = old_class
        else:
            # Not an API component, use parent's visit_ClassDef
            super().visit_ClassDef(node)

    def _identify_api_component(self, node: ast.ClassDef) -> str:
        """
        Identify the type of API component.

        Args:
            node: Class definition node

        Returns:
            Component type string or empty string if not an API component
        """
        base_names = [self._get_name(base) for base in node.bases]

        # Check for ViewSet
        if any("ViewSet" in base for base in base_names):
            return "viewset"

        # Check for APIView
        if any("APIView" in base or "View" in base for base in base_names):
            return "apiview"

        # Check for Serializer
        if any("Serializer" in base for base in base_names):
            return "serializer"

        # Check for Permission
        if any("Permission" in base for base in base_names):
            return "permission"

        return ""

    def _process_class_attribute(self, attr_name, item, info):
        """Process a single class attribute and update info dict."""
        if attr_name == "permission_classes":
            info["permissions"] = self._extract_list_value(item.value)
        elif attr_name == "authentication_classes":
            info["authentication"] = self._extract_list_value(item.value)
        elif attr_name == "throttle_classes":
            info["throttle"] = self._extract_list_value(item.value)
        elif attr_name == "http_method_names":
            info["http_methods"] = self._extract_list_value(item.value)
        elif attr_name == "queryset":
            info["queryset"] = ast.unparse(item.value)
        elif attr_name == "serializer_class":
            info["serializer_class"] = ast.unparse(item.value)

    def _extract_class_attributes(self, node, info):
        """Extract class attributes for permissions, authentication, etc."""
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name):
                    self._process_class_attribute(target.id, item, info)

    def _process_method_definitions(self, node, info):
        """Extract HTTP methods and action decorators."""
        for item in node.body:
            if not isinstance(item, ast.FunctionDef):
                continue
            method_name = item.name

            # Check if this is an HTTP method handler
            if method_name in ["get", "post", "put", "patch", "delete", "head", "options"]:
                info["http_methods"].append(method_name.upper())

            # Check for action decorators
            for decorator in item.decorator_list:
                decorator_name = self._get_decorator_name(decorator)
                if "action" in decorator_name.lower():
                    info["actions"].append(
                        {"name": method_name, "decorator": decorator_name, "line": item.lineno}
                    )

    def _extract_view_info(self, node: ast.ClassDef) -> Dict[str, Any]:
        """
        Extract view-specific information.

        Args:
            node: Class definition node

        Returns:
            Dictionary with view metadata
        """
        info = {
            "http_methods": [],
            "actions": [],
            "permissions": [],
            "authentication": [],
            "throttle": [],
        }

        self._extract_class_attributes(node, info)
        self._process_method_definitions(node, info)

        return info

    def _extract_serializer_fields(self, node, info):
        """Extract field definitions from serializer."""
        for item in node.body:
            if not isinstance(item, ast.Assign):
                continue
            for target in item.targets:
                if isinstance(target, ast.Name):
                    field_name = target.id
                    if field_name.startswith("_"):
                        continue
                    if isinstance(item.value, ast.Call):
                        field_type = self._get_name(item.value.func)
                        if "Field" in field_type or "Serializer" in field_type:
                            info["fields"].append(
                                {
                                    "name": field_name,
                                    "type": field_type,
                                    "line": item.lineno,
                                    "required": self._extract_field_required(item.value),
                                }
                            )

    def _extract_meta_class(self, node, info):
        """Extract Meta class attributes from serializer."""
        for item in node.body:
            if isinstance(item, ast.ClassDef) and item.name == "Meta":
                self._process_meta_attributes(item, info)

    def _process_meta_attributes(self, meta_node, info):
        """Process attributes in Meta class."""
        for meta_item in meta_node.body:
            if not isinstance(meta_item, ast.Assign):
                continue
            for target in meta_item.targets:
                if isinstance(target, ast.Name):
                    if target.id == "model":
                        info["meta_model"] = ast.unparse(meta_item.value)
                    elif target.id == "fields":
                        info["meta_fields"] = ast.unparse(meta_item.value)

    def _extract_serializer_info(self, node: ast.ClassDef) -> Dict[str, Any]:
        """
        Extract serializer-specific information.

        Args:
            node: Class definition node

        Returns:
            Dictionary with serializer metadata
        """
        info = {"fields": [], "meta_model": None, "meta_fields": None}

        self._extract_serializer_fields(node, info)
        self._extract_meta_class(node, info)

        return info

    def _extract_list_value(self, node: ast.expr) -> List[str]:
        """
        Extract string values from a list or tuple.

        Args:
            node: AST expression node

        Returns:
            List of string values
        """
        if isinstance(node, (ast.List, ast.Tuple)):
            return [ast.unparse(elt) for elt in node.elts]
        return []

    def _extract_field_required(self, call_node: ast.Call) -> bool:
        """
        Check if a field is marked as required.

        Args:
            call_node: Call node for field definition

        Returns:
            True if field is explicitly required, False otherwise
        """
        for keyword in call_node.keywords:
            if keyword.arg == "required":
                if isinstance(keyword.value, ast.Constant):
                    return bool(keyword.value.value)

        return True  # Default to required if not specified
