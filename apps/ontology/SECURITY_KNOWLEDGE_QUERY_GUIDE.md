# Security Knowledge Query Guide

**Last Updated:** November 6, 2025  
**Purpose:** Guide for querying security patterns and knowledge from the ontology system

---

## Overview

The ontology system now contains **65+ security components** capturing all patterns, best practices, and knowledge from the November 2025 security remediation work.

### Security Categories

1. **IDOR Prevention** (15 components) - Cross-tenant access protection, ownership validation
2. **Rate Limiting & DoS Protection** (8 components) - Attack prevention, API protection
3. **File Security** (12 components) - Path traversal prevention, secure uploads/downloads
4. **Authentication & Session Security** (10 components) - CSRF, session management, API keys
5. **Multi-Tenant Security** (8 components) - Tenant isolation, cross-tenant validation
6. **Security Testing Patterns** (12 components) - Test organization, attack simulation

---

## Quick Start

### 1. Query by Security Domain

```python
from apps.ontology.registry import OntologyRegistry

# Get all IDOR prevention components
idor_components = OntologyRegistry.get_by_domain("security.idor")
print(f"Found {len(idor_components)} IDOR prevention components")

# Get all file security components
file_security = OntologyRegistry.get_by_domain("security.file")

# Get all rate limiting components
rate_limiting = OntologyRegistry.get_by_domain("security.rate-limiting")

# Get all authentication components
auth_components = OntologyRegistry.get_by_domain("security.authentication")

# Get all multi-tenant security components
multi_tenant = OntologyRegistry.get_by_domain("security.multi-tenant")

# Get all security testing components
testing = OntologyRegistry.get_by_domain("security.testing")
```

### 2. Query by Security Tag

```python
# Get all security-tagged components
all_security = OntologyRegistry.get_by_tag("security")
print(f"Total security components: {len(all_security)}")

# Get IDOR-specific components
idor_tagged = OntologyRegistry.get_by_tag("idor")

# Get path traversal prevention
path_traversal = OntologyRegistry.get_by_tag("path-traversal")

# Get CSRF protection components
csrf = OntologyRegistry.get_by_tag("csrf")

# Get rate limiting components
rate_limit = OntologyRegistry.get_by_tag("rate-limiting")

# Get patterns (best practices)
patterns = OntologyRegistry.get_by_tag("pattern")
```

### 3. Query Specific Security Components

```python
# Get SecureFileDownloadService details
secure_download = OntologyRegistry.get(
    "apps.core.services.secure_file_download_service.SecureFileDownloadService"
)
print(secure_download['purpose'])
print(secure_download['security_notes'])

# Get WorkOrderSecurityService
work_order_sec = OntologyRegistry.get(
    "apps.work_order_management.services.work_order_security_service.WorkOrderSecurityService"
)

# Get IDOR prevention pattern
idor_pattern = OntologyRegistry.get("pattern.idor.query_filtering")
print(idor_pattern['examples'])
```

### 4. Search for Security Knowledge

```python
# Search for path traversal information
path_traversal_results = OntologyRegistry.search("path traversal")

# Search for IDOR prevention
idor_results = OntologyRegistry.search("IDOR prevention")

# Search for rate limiting
rate_limit_results = OntologyRegistry.search("rate limit")

# Search for CSRF protection
csrf_results = OntologyRegistry.search("CSRF protect")
```

---

## Common Queries

### Find All Security Patterns (Best Practices)

```python
# Get all pattern-type components
patterns = [
    component for component in OntologyRegistry.get_all()
    if component.get('type') == 'pattern' and 'security' in component.get('domain', '')
]

for pattern in patterns:
    print(f"Pattern: {pattern['qualified_name']}")
    print(f"Purpose: {pattern['purpose']}")
    print(f"Examples: {pattern.get('examples', [])}")
    print("---")
```

### Find Security Services

```python
# Get all security services
security_services = [
    component for component in OntologyRegistry.get_all()
    if component.get('type') == 'service' and 'security' in component.get('tags', [])
]

for service in security_services:
    print(f"Service: {service['qualified_name']}")
    print(f"Purpose: {service['purpose']}")
    print(f"Security Notes: {service.get('security_notes', 'N/A')}")
    print("---")
```

### Find Security Tests

```python
# Get all security test components
security_tests = [
    component for component in OntologyRegistry.get_all()
    if component.get('type') == 'test' and 'security' in component.get('tags', [])
]

for test in security_tests:
    print(f"Test: {test['qualified_name']}")
    print(f"Purpose: {test['purpose']}")
    print(f"Documentation: {test.get('documentation', [])}")
    print("---")
```

### Find High-Criticality Security Components

```python
# Get all high-criticality security components
critical_security = [
    component for component in OntologyRegistry.get_all()
    if component.get('criticality') == 'high' and 'security' in component.get('tags', [])
]

print(f"Found {len(critical_security)} high-criticality security components")
```

### Find Security Documentation

```python
# Get all security documentation
docs = [
    component for component in OntologyRegistry.get_all()
    if component.get('type') == 'documentation' and 'security' in component.get('domain', '')
]

for doc in docs:
    print(f"Documentation: {doc['qualified_name']}")
    print(f"Purpose: {doc['purpose']}")
    print(f"Files: {doc.get('documentation', [])}")
    print("---")
```

---

## Advanced Queries

### Get IDOR Prevention Implementation Guide

```python
# Get IDOR validation service
validation_service = OntologyRegistry.get(
    "apps.core.services.secure_file_download_service.SecureFileDownloadService.validate_attachment_access"
)

# Get IDOR test suite
idor_tests = OntologyRegistry.get_by_tag("idor")

# Get IDOR patterns
idor_patterns = [
    component for component in OntologyRegistry.get_by_domain("security.idor")
    if component.get('type') == 'pattern'
]

# Combine into implementation guide
print("IDOR Prevention Implementation Guide")
print("=" * 60)
print("\n1. VALIDATION SERVICE:")
print(f"   {validation_service['purpose']}")
print(f"   Security: {validation_service['security_notes']}")
print(f"\n   Example:")
for example in validation_service.get('examples', []):
    print(f"   {example}")

print("\n2. PATTERNS:")
for pattern in idor_patterns:
    print(f"\n   {pattern['qualified_name']}")
    print(f"   Purpose: {pattern['purpose']}")
    print(f"   Examples:")
    for example in pattern.get('examples', []):
        print(f"   {example}")

print("\n3. TESTS:")
for test in [t for t in idor_tests if t.get('type') == 'test']:
    print(f"\n   {test['qualified_name']}")
    print(f"   Purpose: {test['purpose']}")
```

### Get File Security Best Practices

```python
# Get all file security patterns
file_patterns = [
    component for component in OntologyRegistry.get_by_domain("security.file")
    if component.get('type') == 'pattern'
]

# Get SecureFileDownloadService
secure_service = OntologyRegistry.get(
    "apps.core.services.secure_file_download_service.SecureFileDownloadService"
)

# Get file security tests
file_tests = [
    component for component in OntologyRegistry.get_by_domain("security.file")
    if component.get('type') == 'test'
]

print("File Security Best Practices")
print("=" * 60)
print(f"\nSERVICE: {secure_service['qualified_name']}")
print(f"Purpose: {secure_service['purpose']}")
print(f"Security: {secure_service['security_notes']}")

print(f"\nPATTERNS ({len(file_patterns)}):")
for pattern in file_patterns:
    print(f"\n- {pattern['qualified_name']}")
    print(f"  {pattern['purpose']}")

print(f"\nTESTS ({len(file_tests)}):")
for test in file_tests:
    print(f"\n- {test['qualified_name']}")
    print(f"  {test['purpose']}")
```

### Get Rate Limiting Implementation Guide

```python
# Get rate limiting patterns
rate_limit_patterns = [
    component for component in OntologyRegistry.get_by_domain("security.rate-limiting")
    if component.get('type') == 'pattern'
]

# Get rate limiting implementations
rate_limit_impls = [
    component for component in OntologyRegistry.get_by_domain("security.rate-limiting")
    if component.get('type') == 'implementation'
]

print("Rate Limiting Implementation Guide")
print("=" * 60)

print(f"\nPATTERNS ({len(rate_limit_patterns)}):")
for pattern in rate_limit_patterns:
    print(f"\n{pattern['qualified_name']}")
    print(f"Purpose: {pattern['purpose']}")
    print(f"Security: {pattern.get('security_notes', 'N/A')}")
    if 'examples' in pattern:
        print("Examples:")
        for example in pattern['examples']:
            print(f"  {example}")

print(f"\nIMPLEMENTATIONS ({len(rate_limit_impls)}):")
for impl in rate_limit_impls:
    print(f"\n{impl['qualified_name']}")
    print(f"Purpose: {impl['purpose']}")
```

---

## Export Security Knowledge

### Export to JSON

```python
from pathlib import Path
from apps.ontology.registry import OntologyRegistry

# Export all security components
security_components = [
    component for component in OntologyRegistry.get_all()
    if 'security' in component.get('tags', []) or 'security' in component.get('domain', '')
]

import json
with open('security_knowledge_base.json', 'w') as f:
    json.dump(security_components, f, indent=2, default=str)

print(f"Exported {len(security_components)} security components")
```

### Export Security Patterns Only

```python
# Export only patterns
security_patterns = [
    component for component in OntologyRegistry.get_all()
    if component.get('type') == 'pattern' and 'security' in component.get('domain', '')
]

with open('security_patterns.json', 'w') as f:
    json.dump(security_patterns, f, indent=2, default=str)

print(f"Exported {len(security_patterns)} security patterns")
```

### Generate Markdown Documentation

```python
# Generate markdown documentation
security_components = OntologyRegistry.get_by_tag("security")

md_output = ["# Security Knowledge Base\n\n"]

# Group by domain
domains = {}
for component in security_components:
    domain = component.get('domain', 'other')
    if domain not in domains:
        domains[domain] = []
    domains[domain].append(component)

for domain, components in sorted(domains.items()):
    md_output.append(f"## {domain}\n\n")
    for component in components:
        md_output.append(f"### {component['qualified_name']}\n\n")
        md_output.append(f"**Purpose:** {component['purpose']}\n\n")
        if 'security_notes' in component:
            md_output.append(f"**Security:** {component['security_notes']}\n\n")
        if 'examples' in component:
            md_output.append("**Examples:**\n\n```python\n")
            md_output.append("\n".join(component['examples']))
            md_output.append("\n```\n\n")
        md_output.append("---\n\n")

with open('SECURITY_KNOWLEDGE_BASE.md', 'w') as f:
    f.write("".join(md_output))

print(f"Generated SECURITY_KNOWLEDGE_BASE.md with {len(security_components)} components")
```

---

## Integration with Development

### Pre-commit Hook: Validate Security

```python
#!/usr/bin/env python
"""
Pre-commit hook to validate security patterns usage.
"""
from apps.ontology.registry import OntologyRegistry

def check_security_patterns(changed_files):
    """Check if security patterns are followed in changed files."""
    security_patterns = OntologyRegistry.get_by_tag("pattern")
    
    violations = []
    
    for file_path in changed_files:
        # Check file content against security patterns
        with open(file_path, 'r') as f:
            content = f.read()
            
            # Check for IDOR vulnerabilities
            if '.objects.get(' in content and 'filter(tenant=' not in content:
                violations.append(f"{file_path}: Possible IDOR - missing tenant filter")
            
            # Check for CSRF exemptions
            if '@csrf_exempt' in content:
                violations.append(f"{file_path}: @csrf_exempt usage requires justification")
    
    return violations

if __name__ == '__main__':
    import sys
    violations = check_security_patterns(sys.argv[1:])
    
    if violations:
        print("Security Pattern Violations:")
        for violation in violations:
            print(f"  ❌ {violation}")
        sys.exit(1)
    else:
        print("✅ All security patterns validated")
        sys.exit(0)
```

### CI/CD Integration

```yaml
# .github/workflows/security.yml
name: Security Validation

on: [pull_request]

jobs:
  security-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install -r requirements/base.txt
      
      - name: Load ontology
        run: python -c "from apps.ontology.registrations import load_all_registrations; load_all_registrations()"
      
      - name: Run security tests
        run: pytest -m security --tb=short -v
      
      - name: Run IDOR tests
        run: pytest -m idor --tb=short -v
      
      - name: Validate security patterns
        run: python scripts/validate_security_patterns.py
```

---

## Statistics

### Get Security Coverage Statistics

```python
from apps.ontology.registry import OntologyRegistry

# Get all components
all_components = OntologyRegistry.get_all()
security_components = [c for c in all_components if 'security' in c.get('tags', [])]

print(f"Total components: {len(all_components)}")
print(f"Security components: {len(security_components)}")
print(f"Security coverage: {len(security_components)/len(all_components)*100:.1f}%")

# By domain
security_by_domain = {}
for component in security_components:
    domain = component.get('domain', 'unknown')
    security_by_domain[domain] = security_by_domain.get(domain, 0) + 1

print("\nSecurity components by domain:")
for domain, count in sorted(security_by_domain.items(), key=lambda x: -x[1]):
    print(f"  {domain}: {count}")

# By criticality
security_by_criticality = {}
for component in security_components:
    criticality = component.get('criticality', 'unknown')
    security_by_criticality[criticality] = security_by_criticality.get(criticality, 0) + 1

print("\nSecurity components by criticality:")
for criticality, count in sorted(security_by_criticality.items()):
    print(f"  {criticality}: {count}")

# By type
security_by_type = {}
for component in security_components:
    comp_type = component.get('type', 'unknown')
    security_by_type[comp_type] = security_by_type.get(comp_type, 0) + 1

print("\nSecurity components by type:")
for comp_type, count in sorted(security_by_type.items(), key=lambda x: -x[1]):
    print(f"  {comp_type}: {count}")
```

---

## See Also

- [apps/ontology/README.md](README.md) - Ontology system overview
- [apps/ontology/IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) - Implementation details
- [CLAUDE.md](../../CLAUDE.md#secure-file-access-standards) - Security standards
- [ULTRATHINK_SECURITY_REMEDIATION_PLAYBOOK.md](../../ULTRATHINK_SECURITY_REMEDIATION_PLAYBOOK.md) - Security playbook
- [SECURITY_TEST_SUITE_SUMMARY.md](../../SECURITY_TEST_SUITE_SUMMARY.md) - Security tests

---

**Maintained By:** Development Team  
**Review Cycle:** On security updates or remediation work  
**Last Review:** November 6, 2025
