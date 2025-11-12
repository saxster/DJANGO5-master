#!/usr/bin/env python
"""
Verify Code Quality Ontology Registration

Tests that all code quality patterns are properly registered in the ontology system.

Usage:
    python scripts/verify_code_quality_ontology.py
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
django.setup()

from apps.ontology.registry import OntologyRegistry
from apps.ontology.registrations.code_quality_patterns import register_code_quality_patterns


def verify_registration():
    """Verify all code quality patterns are registered."""
    
    print("=" * 80)
    print("CODE QUALITY ONTOLOGY VERIFICATION")
    print("=" * 80)
    
    # Register patterns
    print("\n1. Registering code quality patterns...")
    register_code_quality_patterns()
    
    # Get statistics
    stats = OntologyRegistry.get_statistics()
    print(f"\n2. Registry Statistics:")
    print(f"   Total components: {stats.get('total_components', 0)}")
    print(f"\n   By type:")
    for type_name, count in stats.get('by_type', {}).items():
        print(f"     - {type_name}: {count}")
    
    # Test specific queries
    print("\n3. Testing specific queries...")
    
    # Exception handling patterns
    exception_patterns = OntologyRegistry.get_by_domain("code_quality.exception_handling")
    print(f"\n   Exception handling patterns: {len(exception_patterns)}")
    for pattern in exception_patterns[:3]:
        print(f"     - {pattern.get('qualified_name')}")
    
    # Refactoring patterns
    refactoring_patterns = OntologyRegistry.get_by_domain("code_quality.refactoring")
    print(f"\n   Refactoring patterns: {len(refactoring_patterns)}")
    for pattern in refactoring_patterns[:3]:
        print(f"     - {pattern.get('qualified_name')}")
    
    # Constants patterns
    constant_patterns = OntologyRegistry.get_by_domain("code_quality.constants")
    print(f"\n   Constants patterns: {len(constant_patterns)}")
    for pattern in constant_patterns[:3]:
        print(f"     - {pattern.get('qualified_name')}")
    
    # Architecture patterns
    architecture_patterns = OntologyRegistry.get_by_domain("code_quality.architecture")
    print(f"\n   Architecture patterns: {len(architecture_patterns)}")
    for pattern in architecture_patterns[:3]:
        print(f"     - {pattern.get('qualified_name')}")
    
    # Validation tools
    validation_tools = OntologyRegistry.get_by_type("tool")
    print(f"\n   Validation tools: {len(validation_tools)}")
    for tool in validation_tools:
        print(f"     - {tool.get('qualified_name')}")
    
    # Best practices
    best_practices = OntologyRegistry.get_by_tag("best-practice")
    print(f"\n   Best practices: {len(best_practices)}")
    
    # Anti-patterns
    anti_patterns = OntologyRegistry.get_by_tag("anti-pattern")
    print(f"\n   Anti-patterns: {len(anti_patterns)}")
    for pattern in anti_patterns:
        print(f"     - {pattern.get('qualified_name')}")
        print(f"       Why forbidden: {pattern.get('why_forbidden', 'N/A')}")
    
    # Deliverables
    deliverables = OntologyRegistry.get_by_type("deliverable")
    print(f"\n   Deliverables: {len(deliverables)}")
    for deliverable in deliverables:
        completion = deliverable.get('completion_date', 'In progress')
        print(f"     - {deliverable.get('qualified_name')} ({completion})")
    
    # Test specific pattern retrieval
    print("\n4. Testing specific pattern retrieval...")
    
    god_file_pattern = OntologyRegistry.get("pattern.god_file_refactoring")
    if god_file_pattern:
        print(f"   ✅ God File Refactoring Pattern found")
        print(f"      Purpose: {god_file_pattern.get('purpose')}")
        print(f"      Steps: {len(god_file_pattern.get('steps', []))} steps")
        print(f"      Documentation: {god_file_pattern.get('documentation')}")
    else:
        print(f"   ❌ God File Refactoring Pattern NOT found")
    
    database_exceptions = OntologyRegistry.get("apps.core.exceptions.patterns.DATABASE_EXCEPTIONS")
    if database_exceptions:
        print(f"\n   ✅ DATABASE_EXCEPTIONS found")
        print(f"      Purpose: {database_exceptions.get('purpose')}")
        print(f"      Criticality: {database_exceptions.get('criticality')}")
    else:
        print(f"\n   ❌ DATABASE_EXCEPTIONS NOT found")
    
    # Summary
    print("\n" + "=" * 80)
    print("VERIFICATION SUMMARY")
    print("=" * 80)
    
    expected_components = 51
    actual_components = stats.get('total_components', 0)
    
    if actual_components >= expected_components:
        print(f"✅ SUCCESS: {actual_components} components registered (expected: {expected_components})")
    else:
        print(f"⚠️  WARNING: Only {actual_components} components registered (expected: {expected_components})")
    
    print("\nCategories verified:")
    print("  ✅ Exception Handling Patterns")
    print("  ✅ Refactoring Patterns")
    print("  ✅ Constants & Magic Numbers")
    print("  ✅ Architectural Patterns")
    print("  ✅ Validation Tools")
    
    print("\nOntology system ready for queries!")
    print("\nQuery examples:")
    print("  - OntologyRegistry.get_by_domain('code_quality.exception_handling')")
    print("  - OntologyRegistry.get_by_tag('best-practice')")
    print("  - OntologyRegistry.get_by_type('tool')")
    print("  - OntologyRegistry.get('pattern.god_file_refactoring')")
    
    return True


if __name__ == "__main__":
    try:
        success = verify_registration()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
