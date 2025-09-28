"""
Documentation generator for comprehensive API and model documentation.

This generator provides:
- API documentation: Endpoint descriptions
- Model documentation: Field explanations
- README updates: Feature documentation
- Changelog generation: Commit summaries
- Migration guides: Upgrade instructions
"""

from pathlib import Path
from datetime import datetime




@dataclass
class APIEndpoint:
    """Container for API endpoint documentation."""
    path: str
    method: str
    description: str
    parameters: Dict[str, str]
    responses: Dict[str, str]
    examples: Dict[str, str]


class DocumentationGenerator:
    """Intelligent documentation generator."""

    def __init__(self):
        self.generated_docs = {}

    def generate_api_documentation(self, format: str = "markdown") -> str:
        """Generate comprehensive API documentation."""
        endpoints = self._collect_api_endpoints()

        if format == "markdown":
            return self._generate_markdown_api_docs(endpoints)
        elif format == "openapi":
            return self._generate_openapi_docs(endpoints)

        return self._generate_markdown_api_docs(endpoints)

    def generate_model_documentation(self) -> str:
        """Generate model documentation."""
        models = DjangoModel.objects.all()

        doc_sections = []
        doc_sections.append("# Model Documentation\n")

        for model in models:
            section = self._generate_model_section(model)
            doc_sections.append(section)

        return "\n".join(doc_sections)

    def _collect_api_endpoints(self) -> List[APIEndpoint]:
        """Collect API endpoints from Django URLs and GraphQL."""
        endpoints = []

        # Django REST endpoints
        urls = DjangoURL.objects.filter(route__startswith='/api/')
        for url in urls:
            endpoint = APIEndpoint(
                path=url.route,
                method="GET",  # Default, would need more analysis
                description=f"API endpoint for {url.view_name}",
                parameters={},
                responses={"200": "Success"},
                examples={}
            )
            endpoints.append(endpoint)

        # GraphQL endpoints
        graphql_queries = GraphQLDefinition.objects.filter(kind='query')
        for query in graphql_queries:
            endpoint = APIEndpoint(
                path="/graphql",
                method="POST",
                description=f"GraphQL query: {query.name}",
                parameters=query.type_definition.get('args', {}),
                responses={"200": "GraphQL response"},
                examples={}
            )
            endpoints.append(endpoint)

        return endpoints

    def _generate_markdown_api_docs(self, endpoints: List[APIEndpoint]) -> str:
        """Generate Markdown API documentation."""
        doc_lines = [
            "# API Documentation",
            "",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Endpoints",
            ""
        ]

        for endpoint in endpoints:
            doc_lines.extend([
                f"### {endpoint.method} {endpoint.path}",
                "",
                endpoint.description,
                "",
                "**Parameters:**",
                ""
            ])

            if endpoint.parameters:
                for param, desc in endpoint.parameters.items():
                    doc_lines.append(f"- `{param}`: {desc}")
            else:
                doc_lines.append("- None")

            doc_lines.extend([
                "",
                "**Responses:**",
                ""
            ])

            for code, desc in endpoint.responses.items():
                doc_lines.append(f"- `{code}`: {desc}")

            doc_lines.extend(["", "---", ""])

        return "\n".join(doc_lines)

    def _generate_openapi_docs(self, endpoints: List[APIEndpoint]) -> str:
        """Generate OpenAPI/Swagger documentation."""
        openapi_doc = {
            "openapi": "3.0.0",
            "info": {
                "title": "API Documentation",
                "version": "1.0.0",
                "description": "Auto-generated API documentation"
            },
            "paths": {}
        }

        for endpoint in endpoints:
            if endpoint.path not in openapi_doc["paths"]:
                openapi_doc["paths"][endpoint.path] = {}

            openapi_doc["paths"][endpoint.path][endpoint.method.lower()] = {
                "summary": endpoint.description,
                "responses": {
                    code: {"description": desc}
                    for code, desc in endpoint.responses.items()
                }
            }

        import json
        return json.dumps(openapi_doc, indent=2)

    def _generate_model_section(self, model: DjangoModel) -> str:
        """Generate documentation section for a model."""
        lines = [
            f"## {model.model_name}",
            "",
            f"**App:** {model.app_label}",
            f"**Table:** {model.db_table or f'{model.app_label}_{model.model_name.lower()}'}",
            "",
            "### Fields",
            ""
        ]

        for field_name, field_info in model.fields.items():
            field_type = field_info.get('type', 'Unknown')
            null = field_info.get('null', False)
            blank = field_info.get('blank', False)
            unique = field_info.get('unique', False)
            max_length = field_info.get('max_length')

            field_desc = f"**{field_name}** (`{field_type}`)"

            attributes = []
            if null:
                attributes.append("nullable")
            if blank:
                attributes.append("blank")
            if unique:
                attributes.append("unique")
            if max_length:
                attributes.append(f"max_length={max_length}")

            if attributes:
                field_desc += f" - {', '.join(attributes)}"

            lines.append(f"- {field_desc}")

        lines.extend(["", "---", ""])

        return "\n".join(lines)

    def generate_readme_updates(self, features: List[Dict[str, Any]]) -> str:
        """Generate README updates for new features."""
        lines = [
            "# Recent Updates",
            "",
            f"Last updated: {datetime.now().strftime('%Y-%m-%d')}",
            "",
            "## New Features",
            ""
        ]

        for feature in features:
            lines.extend([
                f"### {feature.get('name', 'New Feature')}",
                "",
                feature.get('description', 'Feature description'),
                "",
                "**Usage:**",
                "```python",
                feature.get('example', '# Example code here'),
                "```",
                ""
            ])

        return "\n".join(lines)

    def generate_changelog(self, commits: List[Dict[str, Any]]) -> str:
        """Generate changelog from commits."""
        lines = [
            "# Changelog",
            "",
            "All notable changes to this project will be documented in this file.",
            ""
        ]

        # Group commits by date
        commits_by_date = {}
        for commit in commits:
            date = commit.get('date', datetime.now().strftime('%Y-%m-%d'))
            if date not in commits_by_date:
                commits_by_date[date] = []
            commits_by_date[date].append(commit)

        # Generate changelog sections
        for date in sorted(commits_by_date.keys(), reverse=True):
            lines.extend([
                f"## {date}",
                ""
            ])

            for commit in commits_by_date[date]:
                commit_type = self._classify_commit(commit.get('message', ''))
                lines.append(f"- **{commit_type}**: {commit.get('message', 'No message')}")

            lines.append("")

        return "\n".join(lines)

    def _classify_commit(self, message: str) -> str:
        """Classify commit type based on message."""
        message_lower = message.lower()

        if message_lower.startswith('feat'):
            return "Feature"
        elif message_lower.startswith('fix'):
            return "Bugfix"
        elif message_lower.startswith('docs'):
            return "Documentation"
        elif message_lower.startswith('refactor'):
            return "Refactor"
        elif message_lower.startswith('test'):
            return "Test"
        elif message_lower.startswith('chore'):
            return "Chore"
        else:
            return "Update"

    def generate_migration_guide(self, version_from: str, version_to: str) -> str:
        """Generate migration guide between versions."""
        lines = [
            f"# Migration Guide: {version_from} → {version_to}",
            "",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Overview",
            "",
            f"This guide helps you migrate from version {version_from} to {version_to}.",
            "",
            "## Breaking Changes",
            "",
            "### Database Migrations",
            "",
            "Run the following commands to update your database:",
            "",
            "```bash",
            "python manage.py makemigrations",
            "python manage.py migrate",
            "```",
            "",
            "### Configuration Changes",
            "",
            "Update your settings files with the following changes:",
            "",
            "```python",
            "# Add new settings",
            "NEW_SETTING = 'default_value'",
            "```",
            "",
            "### Code Changes",
            "",
            "Update your code to use the new APIs:",
            "",
            "**Before:**",
            "```python",
            "# Old way",
            "old_function()",
            "```",
            "",
            "**After:**",
            "```python",
            "# New way",
            "new_function()",
            "```",
            "",
            "## Troubleshooting",
            "",
            "### Common Issues",
            "",
            "1. **Issue**: Migration fails",
            "   - **Solution**: Check database permissions",
            "",
            "2. **Issue**: Import errors",
            "   - **Solution**: Update import statements",
            "",
            "## Support",
            "",
            "If you encounter issues during migration:",
            "",
            "1. Check the documentation",
            "2. Search existing issues",
            "3. Create a new issue with details"
        ]

        return "\n".join(lines)

    def generate_graphql_docs(self) -> str:
        """Generate GraphQL schema documentation."""
        definitions = GraphQLDefinition.objects.all()

        lines = [
            "# GraphQL API Documentation",
            "",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Schema Overview",
            "",
            "This document describes the GraphQL API schema.",
            "",
            "## Types",
            ""
        ]

        # Group definitions by kind
        types_by_kind = {}
        for definition in definitions:
            kind = definition.kind
            if kind not in types_by_kind:
                types_by_kind[kind] = []
            types_by_kind[kind].append(definition)

        # Generate documentation for each kind
        for kind, defs in types_by_kind.items():
            lines.extend([
                f"### {kind.title()}s",
                ""
            ])

            for definition in defs:
                lines.extend([
                    f"#### {definition.name}",
                    "",
                    definition.type_definition.get('description', 'No description available.'),
                    ""
                ])

                # Add fields if available
                fields = definition.type_definition.get('fields', {})
                if fields:
                    lines.extend([
                        "**Fields:**",
                        ""
                    ])

                    for field_name, field_info in fields.items():
                        field_type = field_info.get('type', 'Unknown')
                        field_desc = field_info.get('description', 'No description')
                        lines.append(f"- `{field_name}` ({field_type}): {field_desc}")

                    lines.append("")

        return "\n".join(lines)

    def save_documentation(self, content: str, file_path: str):
        """Save documentation to file."""
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"Documentation saved to: {file_path}")

        except (DatabaseError, FileNotFoundError, IOError, IntegrityError, OSError, ObjectDoesNotExist, PermissionError, TypeError, ValueError, json.JSONDecodeError) as e:
            print(f"Error saving documentation: {e}")

    def generate_complete_documentation_suite(self) -> Dict[str, str]:
        """Generate complete documentation suite."""
        docs = {}

        # API Documentation
        docs['api.md'] = self.generate_api_documentation('markdown')
        docs['openapi.json'] = self.generate_api_documentation('openapi')

        # Model Documentation
        docs['models.md'] = self.generate_model_documentation()

        # GraphQL Documentation
        docs['graphql.md'] = self.generate_graphql_docs()

        # Example README update
        example_features = [
            {
                'name': 'AI Mentor System',
                'description': 'Intelligent code analysis and generation system',
                'example': 'mentor_analyze_code(file_paths=["app/models.py"])'
            }
        ]
        docs['README_updates.md'] = self.generate_readme_updates(example_features)

        # Example changelog
        example_commits = [
            {
                'message': 'feat: Add AI mentor system',
                'date': '2024-01-15'
            },
            {
                'message': 'fix: Security vulnerability in auth',
                'date': '2024-01-14'
            }
        ]
        docs['CHANGELOG.md'] = self.generate_changelog(example_commits)

        # Migration guide
        docs['MIGRATION_v2.md'] = self.generate_migration_guide('1.0', '2.0')

        return docs