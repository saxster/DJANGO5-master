# Ontology System

A code-native ontology system for Django that extracts, enriches, and maintains semantic metadata about the codebase to enable LLM-assisted development.

## Overview

The ontology system provides:

- **@ontology decorator**: Mark code with semantic metadata at the source
- **AST-based extractors**: Automatically extract metadata from code structure
- **Central registry**: Thread-safe storage and querying of metadata
- **Specialized extractors**: Domain-specific analysis for models, APIs, Celery tasks, etc.
- **Documentation generation**: Auto-generate Sphinx documentation
- **Semantic search**: Find code by purpose, domain, or tags
- **Business rule validation**: Verify architectural patterns and constraints
- **LLM query API**: Provide context to Claude Code and other AI assistants

## Quick Start

### 1. Mark Code with @ontology Decorator

```python
from apps.ontology import ontology

@ontology(
    domain="authentication",
    purpose="Validates user credentials and returns JWT token",
    inputs=[
        {"name": "username", "type": "str", "description": "User's email"},
        {"name": "password", "type": "str", "description": "User's password"}
    ],
    outputs=[{"name": "token", "type": "str", "description": "JWT access token"}],
    side_effects=["Updates last_login timestamp in database"],
    tags=["security", "authentication", "jwt"],
    security_notes="Rate limited to 5 attempts per minute per IP"
)
def login_user(username: str, password: str) -> dict:
    """Authenticate user and return access token."""
    # Implementation...
    pass
```

### 2. Extract Metadata from Codebase

```bash
# Extract from all apps
python manage.py extract_ontology

# Extract from specific apps
python manage.py extract_ontology --apps core activity peoples

# Extract only models
python manage.py extract_ontology --models-only

# Extract only API components
python manage.py extract_ontology --api-only

# Export to custom location
python manage.py extract_ontology --output /path/to/ontology.json
```

### 3. Query the Registry

```python
from apps.ontology.registry import OntologyRegistry

# Get metadata for a specific component
metadata = OntologyRegistry.get("apps.core.utils.format_date")

# Find all components in a domain
auth_components = OntologyRegistry.get_by_domain("authentication")

# Find by tag
security_components = OntologyRegistry.get_by_tag("security")

# Search by text
results = OntologyRegistry.search("jwt token")

# Get statistics
stats = OntologyRegistry.get_statistics()
print(f"Total components: {stats['total_components']}")
print(f"By type: {stats['by_type']}")
print(f"Domains: {stats['domains']}")
```

## Architecture

### Phase 1: Foundation (Current)

- ✅ @ontology decorator
- ✅ OntologyRegistry with thread-safe storage
- ✅ AST extractor for generic Python code
- ✅ Model extractor for Django models
- ✅ API extractor for REST endpoints
- ✅ Management command for extraction
- ⏳ Sphinx integration (next)
- ⏳ Documentation generator (next)

### Phase 2: Enrichment (Planned)

- Celery task extractor
- Security pattern detector
- Configuration miner
- Dependency analyzer

### Phase 3: Documentation (Planned)

- Mermaid diagram generator
- Cross-reference system
- Semantic search indexing
- Interactive documentation

### Phase 4: Validation (Planned)

- Business rule validators
- Architecture consistency checkers
- Coverage metrics
- CI/CD integration

### Phase 5: AI Integration (COMPLETE)

- ✅ Claude Code slash command (`/ontology`)
- ✅ Smart context injection for code references
- ✅ MCP server for industry-standard LLM integration
- ⏳ JSON-LD exporter for semantic web (next)
- ⏳ Auto-completion suggestions (next)

## Extractors

### ASTExtractor

Extracts metadata from general Python code:
- Functions and their parameters
- Classes and methods
- Decorators
- Imports and dependencies
- Type hints
- Docstrings

### ModelExtractor

Specialized for Django models:
- Model fields and types
- Relationships (ForeignKey, ManyToMany, OneToOne)
- Custom managers
- Model methods
- Meta options

### APIExtractor

Specialized for REST API components:
- ViewSets and actions
- APIViews and HTTP methods
- Serializers and fields
- Permissions and authentication
- Throttling configuration

## Decorator Metadata Fields

| Field | Type | Description |
|-------|------|-------------|
| domain | str | Business domain (e.g., "authentication") |
| purpose | str | What this code does |
| inputs | list | Input parameter descriptions |
| outputs | list | Output/return value descriptions |
| side_effects | list | Side effects (DB writes, API calls, etc.) |
| depends_on | list | Dependencies (modules, services) |
| used_by | list | Components that use this code |
| tags | list | Tags for categorization |
| deprecated | bool | Whether deprecated |
| replacement | str | What to use instead if deprecated |
| security_notes | str | Security considerations |
| performance_notes | str | Performance characteristics |
| examples | list | Usage examples |

## Registry API

### Registration

```python
from apps.ontology.registry import OntologyRegistry

# Register single item
OntologyRegistry.register("module.function", metadata)

# Bulk register
OntologyRegistry.bulk_register([
    {"qualified_name": "module.func1", "domain": "auth", ...},
    {"qualified_name": "module.func2", "domain": "api", ...},
])
```

### Querying

```python
# Get by qualified name
metadata = OntologyRegistry.get("apps.core.utils.format_date")

# Get by domain
components = OntologyRegistry.get_by_domain("authentication")

# Get by tag
components = OntologyRegistry.get_by_tag("security")

# Get by type
functions = OntologyRegistry.get_by_type("function")
classes = OntologyRegistry.get_by_type("class")
models = OntologyRegistry.get_by_type("model")

# Get by module
components = OntologyRegistry.get_by_module("apps.core.utils")

# Get deprecated components
deprecated = OntologyRegistry.get_deprecated()

# Search
results = OntologyRegistry.search("authentication")

# Get all
all_metadata = OntologyRegistry.get_all()

# Get statistics
stats = OntologyRegistry.get_statistics()
```

### Export

```python
from pathlib import Path

# Export to JSON
OntologyRegistry.export_json(Path("ontology_data.json"))
```

## Best Practices

### 1. Use Specific Domains

Group related functionality into domains:
- `authentication` - User login, logout, token management
- `authorization` - Permissions, access control
- `data` - Models, database operations
- `api` - REST endpoints, serializers
- `tasks` - Background jobs, Celery tasks
- `reports` - Report generation, analytics

### 2. Write Clear Purposes

Good: "Validates user credentials and returns JWT token"
Bad: "Login function"

### 3. Document Side Effects

Always list side effects:
- Database writes
- External API calls
- File I/O
- Cache updates
- Signal emissions

### 4. Tag Appropriately

Use consistent tags:
- `security` - Security-sensitive code
- `performance` - Performance-critical code
- `deprecated` - Deprecated code
- `experimental` - Experimental features
- `public-api` - Public API endpoints

### 5. Keep Metadata Updated

When code changes, update the decorator metadata:
- Purpose changes → Update `purpose`
- New side effects → Add to `side_effects`
- Deprecation → Set `deprecated=True` and add `replacement`

## Claude Code Integration

The ontology system provides three mechanisms for AI-assisted development:

### 1. Slash Command: `/ontology`

Load ontology metadata on-demand within Claude Code:

```
/ontology auth              # Load authentication components
/ontology geofencing        # Load GPS/geospatial code
/ontology critical          # Load critical components
/ontology people            # Load people domain
```

See [.claude/commands/ontology.md](../../.claude/commands/ontology.md) for details.

### 2. Smart Context Injection

Automatically detects code references in queries and injects relevant metadata:

```python
from apps.ontology.claude import inject_ontology_context

# In your Claude Code integration
user_query = "How does the People model work?"
context = inject_ontology_context(user_query)
# Returns formatted metadata about People model, authentication, etc.
```

Detects:
- File paths: `apps/peoples/models.py`
- Function/class names: `authenticate_user`
- Domain keywords: "authentication", "GPS", "payment"
- Question patterns: "How does X work?", "What is Y?"

See [apps/ontology/claude/smart_injection.py](claude/smart_injection.py) for API.

### 3. MCP Server

Model Context Protocol server for Claude Desktop, Code, and other MCP clients:

**Tools:**
- `ontology_query` - Query by domain/tag/purpose/criticality
- `ontology_get` - Get specific component metadata
- `ontology_stats` - Get coverage statistics
- `ontology_relationships` - Query component relationships

**Resources:**
- `ontology://graph` - Complete knowledge graph
- `ontology://domains` - Domain list
- `ontology://critical` - Critical components
- `ontology://domain/{name}` - Domain-specific components

**Setup for Claude Desktop:**

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "ontology": {
      "command": "python",
      "args": ["/absolute/path/to/apps/ontology/mcp/run_server.py"],
      "env": {
        "DJANGO_SETTINGS_MODULE": "intelliwiz_config.settings.development"
      }
    }
  }
}
```

See [apps/ontology/mcp/README.md](mcp/README.md) for complete documentation.

## Integration with Development Workflow

### Pre-commit Hook

Add to `.git/hooks/pre-commit`:
```bash
#!/bin/bash
python manage.py extract_ontology --output .ontology/metadata.json
git add .ontology/metadata.json
```

### CI/CD Pipeline

```yaml
- name: Extract Ontology
  run: python manage.py extract_ontology --output ontology.json

- name: Validate Architecture
  run: python manage.py validate_ontology
```

### Documentation Generation

```bash
# Generate Sphinx documentation
python manage.py generate_ontology_docs --output docs/ontology/
```

## Future Features

- **Real-time extraction**: Auto-update on file changes
- **Visual browser**: Web UI for exploring ontology
- **Dependency graphs**: Visualize component relationships
- **Impact analysis**: Find affected code for changes
- **Migration assistant**: Suggest refactoring patterns
- **Code search**: Natural language code search
- **Auto-documentation**: Generate docs from metadata
- **Type inference**: Infer types from usage
- **Test coverage**: Link tests to components
- **Performance profiling**: Link profiling data to code

## Contributing

When adding new extractors:

1. Extend `BaseExtractor`
2. Implement `extract()` and `can_handle()`
3. Add to `apps/ontology/extractors/__init__.py`
4. Register in management command
5. Add tests
6. Update documentation

## License

Part of the IntelliWiz Django application.
