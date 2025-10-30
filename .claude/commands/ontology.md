Load ontology metadata for the codebase.

Usage: /ontology [query]

Query can be:
- Domain name (e.g., "people", "operations")
- Tag (e.g., "authentication", "geofencing")
- Purpose keyword (e.g., "payment", "GPS")
- Criticality level (e.g., "critical")

Examples:
- /ontology auth
- /ontology geofencing
- /ontology critical

This loads semantic metadata about the codebase into context.

---

## Execution

When this command runs, it will:

1. Extract the query parameter from the command
2. Execute the ontology extraction management command
3. Format results for optimal Claude Code context
4. Display relevant components with their metadata

## Command Execution

```bash
# Extract query parameter (defaults to "all" if not provided)
QUERY="${1:-all}"

# Run ontology extraction
python manage.py extract_ontology --query "$QUERY" --format json

# Display formatted results
echo ""
echo "=== Ontology Context Loaded ==="
echo "Query: $QUERY"
echo ""
echo "The following metadata has been loaded into context:"
echo "- Components matching query"
echo "- Related dependencies"
echo "- Domain relationships"
echo "- Critical paths and patterns"
echo ""
echo "You can now ask questions about these components."
```

## Response Format

The ontology data provides:
- **Component identity**: Module paths, class/function names
- **Purpose**: What each component does
- **Relationships**: Dependencies and interactions
- **Domain context**: Business domain classification
- **Criticality**: System importance level
- **Tags**: Searchable semantic tags

## Use Cases

### Domain Exploration
```
/ontology people
```
Loads all components in the people/authentication domain.

### Feature Investigation
```
/ontology authentication
```
Loads authentication-related code across all apps.

### Security Analysis
```
/ontology critical
```
Loads all critical system components.

### Geospatial Features
```
/ontology geofencing
```
Loads GPS, location, and geofencing code.

## Integration Notes

This command integrates with the codebase ontology system that automatically:
- Analyzes code structure and relationships
- Extracts semantic metadata
- Maintains knowledge graph
- Enables intelligent code navigation

For more information, see `apps/ontology/README.md`.
