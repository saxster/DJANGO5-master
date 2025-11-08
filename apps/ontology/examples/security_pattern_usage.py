"""
import logging
logger = logging.getLogger(__name__)
Security Pattern Usage Examples

This module demonstrates how to query and use security patterns from the ontology.

Run: python apps/ontology/examples/security_pattern_usage.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')

from apps.ontology.registry import OntologyRegistry


def example_1_find_idor_prevention_pattern():
    """Example 1: Find IDOR prevention pattern and display implementation guide."""
    logger.info("=" * 80)
    logger.info("Example 1: IDOR Prevention Pattern")
    logger.info("=" * 80)
    
    # Get the query filtering pattern
    pattern = OntologyRegistry.get("pattern.idor.query_filtering")
    
    if pattern:
        logger.info(f"\nPattern: {pattern['qualified_name']}")
        logger.info(f"Purpose: {pattern['purpose']}")
        logger.info(f"\nSecurity Notes: {pattern.get('security_notes', 'N/A')}")
        logger.info(f"\nCriticality: {pattern.get('criticality', 'N/A')}")
        
        logger.info("\nImplementation Examples:")
        for example in pattern.get('examples', []):
            logger.info(f"  {example}")
        
        logger.info("\nDocumentation:")
        for doc in pattern.get('documentation', []):
            logger.info(f"  - {doc}")
    else:
        logger.info("Pattern not found!")
    
    logger.info()


def example_2_get_all_file_security_components():
    """Example 2: Get all file security components and group by type."""
    logger.info("=" * 80)
    logger.info("Example 2: File Security Components")
    logger.info("=" * 80)
    
    # Get all file security components
    file_components = OntologyRegistry.get_by_domain("security.file")
    
    logger.info(f"\nFound {len(file_components)} file security components\n")
    
    # Group by type
    by_type = {}
    for component in file_components:
        comp_type = component.get('type', 'unknown')
        if comp_type not in by_type:
            by_type[comp_type] = []
        by_type[comp_type].append(component)
    
    for comp_type, components in sorted(by_type.items()):
        logger.info(f"{comp_type.upper()} ({len(components)}):")
        for component in components:
            logger.info(f"  - {component['qualified_name']}")
            logger.info(f"    {component['purpose']}")
        logger.info()


def example_3_find_security_service():
    """Example 3: Find SecureFileDownloadService and show usage."""
    logger.info("=" * 80)
    logger.info("Example 3: SecureFileDownloadService Usage")
    logger.info("=" * 80)
    
    # Get the service
    service = OntologyRegistry.get(
        "apps.core.services.secure_file_download_service.SecureFileDownloadService"
    )
    
    if service:
        logger.info(f"\nService: {service['qualified_name']}")
        logger.info(f"Purpose: {service['purpose']}")
        logger.info(f"\nSecurity Notes:")
        logger.info(f"  {service.get('security_notes', 'N/A')}")
        
        logger.info(f"\nBusiness Value:")
        logger.info(f"  {service.get('business_value', 'N/A')}")
        
        logger.info(f"\nTags:")
        logger.info(f"  {', '.join(service.get('tags', []))}")
        
        logger.info("\nDocumentation:")
        for doc in service.get('documentation', []):
            logger.info(f"  - {doc}")
    else:
        logger.info("Service not found!")
    
    logger.info()


def example_4_search_for_patterns():
    """Example 4: Search for patterns by keyword."""
    logger.info("=" * 80)
    logger.info("Example 4: Search for Path Traversal")
    logger.info("=" * 80)
    
    # Search for path traversal
    results = OntologyRegistry.search("path traversal")
    
    logger.info(f"\nFound {len(results)} components related to path traversal\n")
    
    for result in results[:5]:  # Show first 5
        logger.info(f"Name: {result['qualified_name']}")
        logger.info(f"Type: {result['type']}")
        logger.info(f"Purpose: {result['purpose']}")
        logger.info(f"Domain: {result.get('domain', 'N/A')}")
        logger.info("-" * 80)
    
    logger.info()


def example_5_get_security_tests():
    """Example 5: Find all IDOR security tests."""
    logger.info("=" * 80)
    logger.info("Example 5: IDOR Security Tests")
    logger.info("=" * 80)
    
    # Get all IDOR components
    idor_components = OntologyRegistry.get_by_domain("security.idor")
    
    # Filter for tests
    idor_tests = [c for c in idor_components if c.get('type') == 'test']
    
    logger.info(f"\nFound {len(idor_tests)} IDOR test suites:\n")
    
    for test in idor_tests:
        logger.info(f"Test: {test['qualified_name']}")
        logger.info(f"Purpose: {test['purpose']}")
        if 'security_notes' in test:
            logger.info(f"Security Focus: {test['security_notes']}")
        if 'examples' in test:
            logger.info(f"Run: {test['examples'][0]}")
        logger.info()


def example_6_get_rate_limiting_patterns():
    """Example 6: Get all rate limiting patterns and implementations."""
    logger.info("=" * 80)
    logger.info("Example 6: Rate Limiting Best Practices")
    logger.info("=" * 80)
    
    # Get rate limiting components
    rate_limit = OntologyRegistry.get_by_domain("security.rate-limiting")
    
    # Separate patterns and implementations
    patterns = [c for c in rate_limit if c.get('type') == 'pattern']
    implementations = [c for c in rate_limit if c.get('type') == 'implementation']
    
    logger.info(f"\nPATTERNS ({len(patterns)}):\n")
    for pattern in patterns:
        logger.info(f"• {pattern['qualified_name']}")
        logger.info(f"  {pattern['purpose']}")
        if 'security_notes' in pattern:
            logger.info(f"  Security: {pattern['security_notes']}")
        logger.info()
    
    logger.info(f"IMPLEMENTATIONS ({len(implementations)}):\n")
    for impl in implementations:
        logger.info(f"• {impl['qualified_name']}")
        logger.info(f"  {impl['purpose']}")
        logger.info()


def example_7_high_criticality_security():
    """Example 7: Find all high-criticality security components."""
    logger.info("=" * 80)
    logger.info("Example 7: High-Criticality Security Components")
    logger.info("=" * 80)
    
    # Get all security components
    security_components = OntologyRegistry.get_by_tag("security")
    
    # Filter for high criticality
    high_crit = [c for c in security_components if c.get('criticality') == 'high']
    
    logger.info(f"\nFound {len(high_crit)} high-criticality components\n")
    
    # Group by domain
    by_domain = {}
    for component in high_crit:
        domain = component.get('domain', 'unknown')
        by_domain[domain] = by_domain.get(domain, 0) + 1
    
    logger.info("By Domain:")
    for domain, count in sorted(by_domain.items(), key=lambda x: -x[1]):
        logger.info(f"  {domain}: {count} components")
    
    logger.info()


def example_8_generate_security_checklist():
    """Example 8: Generate security checklist from patterns."""
    logger.info("=" * 80)
    logger.info("Example 8: Security Implementation Checklist")
    logger.info("=" * 80)
    
    # Get all patterns
    all_patterns = [
        c for c in OntologyRegistry.get_all()
        if c.get('type') == 'pattern' and 'security' in c.get('domain', '')
    ]
    
    # Group by domain
    by_domain = {}
    for pattern in all_patterns:
        domain = pattern.get('domain', 'unknown')
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(pattern)
    
    logger.info("\nSecurity Implementation Checklist:\n")
    
    for domain, patterns in sorted(by_domain.items()):
        logger.info(f"\n{domain.upper().replace('.', ' - ')}")
        logger.info("-" * 80)
        for pattern in patterns:
            logger.info(f"  [ ] {pattern['qualified_name']}")
            logger.info(f"      {pattern['purpose']}")
    
    logger.info()


def example_9_export_security_knowledge():
    """Example 9: Export security knowledge to JSON."""
    logger.info("=" * 80)
    logger.info("Example 9: Export Security Knowledge")
    logger.info("=" * 80)
    
    import json
    from pathlib import Path
    
    # Get all security components
    security_components = OntologyRegistry.get_by_tag("security")
    
    # Prepare export data
    export_data = {
        "total_components": len(security_components),
        "by_domain": {},
        "by_criticality": {},
        "components": security_components
    }
    
    # Group by domain
    for component in security_components:
        domain = component.get('domain', 'unknown')
        export_data['by_domain'][domain] = export_data['by_domain'].get(domain, 0) + 1
        
        criticality = component.get('criticality', 'unknown')
        export_data['by_criticality'][criticality] = export_data['by_criticality'].get(criticality, 0) + 1
    
    # Export to file
    output_path = Path("security_knowledge_export.json")
    with open(output_path, 'w') as f:
        json.dump(export_data, f, indent=2, default=str)
    
    logger.info(f"\nExported {len(security_components)} components to {output_path}")
    logger.info(f"\nStatistics:")
    logger.info(f"  By Domain: {dict(export_data['by_domain'])}")
    logger.info(f"  By Criticality: {dict(export_data['by_criticality'])}")
    logger.info()


def example_10_find_related_components():
    """Example 10: Find all components related to a specific service."""
    logger.info("=" * 80)
    logger.info("Example 10: Components Related to SecureFileDownloadService")
    logger.info("=" * 80)
    
    # Get the service
    service_name = "apps.core.services.secure_file_download_service.SecureFileDownloadService"
    
    # Get all components
    all_components = OntologyRegistry.get_all()
    
    # Find related by tag, domain, or dependency
    related = []
    for component in all_components:
        # Check if service is mentioned in depends_on
        if service_name in component.get('depends_on', []):
            related.append(component)
        # Check if in same domain
        elif 'file' in component.get('domain', '') or 'download' in component.get('domain', ''):
            related.append(component)
    
    logger.info(f"\nFound {len(related)} related components:\n")
    
    # Group by type
    by_type = {}
    for component in related:
        comp_type = component.get('type', 'unknown')
        if comp_type not in by_type:
            by_type[comp_type] = []
        by_type[comp_type].append(component)
    
    for comp_type, components in sorted(by_type.items()):
        logger.info(f"{comp_type.upper()}:")
        for component in components:
            logger.info(f"  • {component['qualified_name']}")
        logger.info()


def main():
    """Run all examples."""
    logger.info("\n" * 2)
    logger.info("*" * 80)
    logger.info("SECURITY PATTERN USAGE EXAMPLES")
    logger.info("*" * 80)
    logger.info()
    
    # Load registrations
    from apps.ontology.registrations import load_all_registrations
    counts = load_all_registrations()
    
    logger.info(f"Loaded {sum(counts.values())} ontology components")
    logger.info()
    
    # Run examples
    example_1_find_idor_prevention_pattern()
    example_2_get_all_file_security_components()
    example_3_find_security_service()
    example_4_search_for_patterns()
    example_5_get_security_tests()
    example_6_get_rate_limiting_patterns()
    example_7_high_criticality_security()
    example_8_generate_security_checklist()
    example_9_export_security_knowledge()
    example_10_find_related_components()
    
    logger.info("*" * 80)
    logger.info("END OF EXAMPLES")
    logger.info("*" * 80)
    logger.info()


if __name__ == "__main__":
    import sys
    import os
    
    # Add project root to path
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
    
    # Set Django settings
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
    
    main()
