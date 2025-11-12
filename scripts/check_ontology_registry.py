#!/usr/bin/env python
"""
Check ontology registry state for Phase 1 verification.
"""
import os
import sys
import json
import django

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Setup Django to trigger app.ready() methods
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

# Import registry after Django setup (so app.ready() has run)
from apps.ontology.registry import OntologyRegistry

# Get statistics
stats = OntologyRegistry.get_statistics()

print("=" * 60)
print("ONTOLOGY REGISTRY STATE")
print("=" * 60)
print(f"\nTotal components: {stats['total_components']}")
print(f"\nDomains registered:")
for domain, count in sorted(stats['by_domain'].items()):
    print(f"  {domain}: {count} components")

# Check help/helpdesk specifically
all_components = OntologyRegistry.get_all()
help_components = [c for c in all_components if c.get('domain') in ['help', 'helpdesk']]

print(f"\n" + "=" * 60)
print(f"HELP DOMAIN VERIFICATION")
print("=" * 60)
print(f"Help/helpdesk components: {len(help_components)}")

if help_components:
    print("\nRegistered help services:")
    for comp in help_components:
        print(f"  - {comp.get('qualified_name', 'Unknown')}")
        print(f"    Domain: {comp.get('domain', 'N/A')}")
        print(f"    Purpose: {comp.get('purpose', 'N/A')[:80]}")
        print()
else:
    print("\n⚠️  WARNING: No help/helpdesk components found!")
    print("This may indicate:")
    print("  1. Services haven't been imported yet (decorators haven't executed)")
    print("  2. Domain names in decorators don't match 'help' or 'helpdesk'")
    print("  3. Ontology cache needs to be refreshed")

# Save detailed report
report_path = os.path.join(os.path.dirname(__file__), '..', 'ontology_registry_report.json')
with open(report_path, 'w') as f:
    json.dump({
        'statistics': stats,
        'help_components': help_components,
        'all_component_names': [c.get('qualified_name') for c in all_components]
    }, f, indent=2)

print(f"\nDetailed report saved to: {report_path}")
print("=" * 60)
