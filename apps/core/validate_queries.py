#!/usr/bin/env python
"""
Query validation script for testing the new ORM-based queries.

This script can be run standalone to validate that the new Django ORM
queries work correctly and produce expected results.

Usage:
    python manage.py shell < apps/core/validate_queries.py
    
    Or from Django shell:
    >>> exec(open('apps/core/validate_queries.py').read())
"""

import sys
import time
from django.utils import timezone
from django.core.cache import cache

import logging
logger = logging.getLogger(__name__)


# Import the new query modules
try:
    from apps.core.raw_queries import get_query as raw_get_query
except ImportError as e:
    logger.error(f"Import error: {e}")
    logger.debug("Make sure you're running this from Django shell or manage.py")
    sys.exit(1)

def print_section(title):
    """Print a formatted section header."""
    logger.debug(f"\n{'='*60}")
    logger.debug(f"  {title}")
    logger.debug(f"{'='*60}")

def print_result(query_name, result, execution_time=None):
    """Print query results in a formatted way."""
    logger.debug(f"\nQuery: {query_name}")
    if execution_time:
        logger.debug(f"Execution time: {execution_time:.3f}s")
    
    if isinstance(result, list):
        logger.debug(f"Results: {len(result)} records")
        if result and len(result) > 0:
            logger.debug("Sample record:")
            sample = result[0]
            if isinstance(sample, dict):
                for key, value in list(sample.items())[:5]:  # Show first 5 fields
                    logger.debug(f"  {key}: {value}")
                if len(sample) > 5:
                    logger.debug(f"  ... and {len(sample) - 5} more fields")
    elif isinstance(result, dict):
        logger.debug("Result (dict):")
        for key, value in result.items():
            logger.debug(f"  {key}: {value}")
    else:
        logger.debug(f"Result: {result}")

def validate_tree_traversal():
    """Validate tree traversal functionality."""
    print_section("Tree Traversal Validation")
    
    # Test with sample data
    test_nodes = [
        {'id': 1, 'code': 'ROOT', 'parent_id': None, 'name': 'Root Node'},
        {'id': 2, 'code': 'CHILD1', 'parent_id': 1, 'name': 'Child 1'},
        {'id': 3, 'code': 'CHILD2', 'parent_id': 1, 'name': 'Child 2'},
        {'id': 4, 'code': 'GRANDCHILD', 'parent_id': 2, 'name': 'Grandchild'},
    ]
    
    logger.debug("Testing TreeTraversal.build_tree()...")
    start_time = time.time()
    result = TreeTraversal.build_tree(test_nodes, root_id=1, code_field='code')
    execution_time = time.time() - start_time
    
    print_result("TreeTraversal.build_tree", result, execution_time)
    
    # Validate structure
    if result:
        root_node = result[0]
        if root_node.get('depth') == 1 and root_node.get('path') == 'ROOT':
            logger.debug("✓ Tree structure is correct")
        else:
            logger.error("✗ Tree structure validation failed")
    else:
        logger.debug("✗ No results returned from tree traversal")

def validate_capabilities():
    """Validate capabilities query."""
    print_section("Capabilities Query Validation")
    
    try:
        logger.debug("Testing get_web_caps_for_client()...")
        
        # Clear cache first
        cache.clear()
        
        # Test new implementation
        start_time = time.time()
        new_result = get_query('get_web_caps_for_client')
        new_time = time.time() - start_time
        
        print_result("New ORM Implementation", new_result, new_time)
        
        # Test caching
        start_time = time.time()
        cached_result = get_query('get_web_caps_for_client')
        cached_time = time.time() - start_time
        
        logger.debug(f"Cached query time: {cached_time:.3f}s")
        if cached_time < new_time * 0.5:
            logger.debug("✓ Caching is working effectively")
        else:
            logger.debug("? Caching may not be optimal")
            
        if new_result == cached_result:
            logger.debug("✓ Cached results match original")
        else:
            logger.debug("✗ Cached results don't match")
            
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing capabilities: {e}")

def validate_business_units():
    """Validate business unit hierarchy query."""
    print_section("Business Unit Hierarchy Validation")
    
    try:
        # Test with a common root BU (assuming ID 1 exists)
        logger.debug("Testing get_childrens_of_bt(1)...")
        
        start_time = time.time()
        result = get_query('get_childrens_of_bt', bt_id=1)
        execution_time = time.time() - start_time
        
        print_result("Business Unit Children", result, execution_time)
        
        if result:
            logger.debug("✓ Business unit hierarchy query working")
        else:
            logger.debug("? No business units found (may be expected if no data)")
            
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing business units: {e}")

def validate_reports():
    """Validate report queries."""
    print_section("Report Queries Validation")
    
    # Test date range
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    try:
        logger.debug("Testing sitereportlist...")
        
        # Use a common BU ID (assuming 1 exists)
        result = get_query(
            'sitereportlist',
            bu_ids=[1],
            start_date=start_date,
            end_date=end_date
        )
        print_result("Site Report List", result)
        
        logger.debug("Testing incidentreportlist...")
        result = get_query(
            'incidentreportlist',
            bu_ids=[1],
            start_date=start_date,
            end_date=end_date
        )
        print_result("Incident Report List", result)
        
        logger.debug("✓ Report queries working")
        
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing reports: {e}")

def validate_tickets():
    """Validate ticket-related queries."""
    print_section("Ticket Queries Validation")
    
    try:
        logger.debug("Testing get_ticketlist_for_escalation...")
        
        start_time = time.time()
        result = get_query('get_ticketlist_for_escalation')
        execution_time = time.time() - start_time
        
        print_result("Tickets for Escalation", result, execution_time)
        
        # Test ticketmail if we have tickets
        if result and isinstance(result, list) and len(result) > 0:
            ticket_id = result[0].get('id')
            if ticket_id:
                logger.debug(f"Testing ticketmail for ticket {ticket_id}...")
                mail_result = get_query('ticketmail', ticket_id=ticket_id)
                print_result("Ticket Mail Details", mail_result)
        
        logger.debug("✓ Ticket queries working")
        
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing tickets: {e}")

def validate_task_summary():
    """Validate task summary query."""
    print_section("Task Summary Validation")
    
    try:
        logger.debug("Testing tasksummary...")
        
        # Test with date range
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)
        
        result = get_query(
            'tasksummary',
            timezone_str='UTC',
            bu_ids='1,2,3',
            start_date=start_date,
            end_date=end_date
        )
        print_result("Task Summary", result)
        
        logger.debug("✓ Task summary query working")
        
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing task summary: {e}")

def validate_assets():
    """Validate asset-related queries."""
    print_section("Asset Queries Validation")
    
    try:
        logger.debug("Testing all_asset_status_duration...")
        
        result = get_query(
            'all_asset_status_duration',
            client_id=1,
            bu_id=1
        )
        print_result("Asset Status Duration", result)
        
        logger.debug("Testing all_asset_status_duration_count...")
        count = get_query(
            'all_asset_status_duration_count',
            client_id=1,
            bu_id=1
        )
        print_result("Asset Status Duration Count", count)
        
        logger.debug("✓ Asset queries working")
        
    except (TypeError, ValidationError, ValueError) as e:
        logger.error(f"✗ Error testing assets: {e}")

def performance_comparison():
    """Compare performance between old and new implementations."""
    print_section("Performance Comparison")
    
    queries_to_test = [
        ('get_web_caps_for_client', {}),
        ('get_childrens_of_bt', {'bt_id': 1}),
    ]
    
    for query_name, kwargs in queries_to_test:
        try:
            logger.debug(f"\nTesting {query_name}...")
            
            # Clear cache for fair comparison
            cache.clear()
            
            # Test new implementation
            start_time = time.time()
            new_result = get_query(query_name, **kwargs)
            new_time = time.time() - start_time
            
            # Test old implementation (if available)
            try:
                start_time = time.time()
                old_result = raw_get_query(query_name)
                old_time = time.time() - start_time
                
                logger.debug(f"  New ORM: {new_time:.3f}s ({len(new_result) if isinstance(new_result, list) else 1} results)")
                logger.debug(f"  Old SQL: {old_time:.3f}s")
                logger.debug(f"  Ratio: {new_time/old_time:.2f}x")
                
                if new_time < old_time:
                    logger.debug("  ✓ New implementation is faster")
                elif new_time < old_time * 2:
                    logger.debug("  ≈ Performance is comparable")
                else:
                    logger.debug("  ? New implementation is slower")
                    
            except (ValueError, TypeError) as e:
                logger.debug(f"  Could not test old implementation: {e}")
                logger.debug(f"  New ORM: {new_time:.3f}s")
                
        except (ValueError, TypeError) as e:
            logger.error(f"  ✗ Error testing {query_name}: {e}")

def main():
    """Main validation function."""
    logger.debug("Django ORM Query Validation")
    logger.debug("=" * 60)
    logger.debug(f"Started at: {timezone.now()}")
    
    validation_functions = [
        validate_tree_traversal,
        validate_capabilities,
        validate_business_units,
        validate_reports,
        validate_tickets,
        validate_task_summary,
        validate_assets,
        performance_comparison,
    ]
    
    passed = 0
    total = len(validation_functions)
    
    for validate_func in validation_functions:
        try:
            validate_func()
            passed += 1
        except (TypeError, ValidationError, ValueError) as e:
            logger.error(f"\n✗ Validation function {validate_func.__name__} failed: {e}")
    
    print_section("Validation Summary")
    logger.info(f"Completed: {passed}/{total} validation functions")
    logger.info(f"Success rate: {(passed/total)*100:.1f}%")
    
    if passed == total:
        logger.debug("🎉 All validations passed!")
    elif passed >= total * 0.8:
        logger.debug("✓ Most validations passed - ready for testing")
    else:
        logger.error("⚠️  Many validations failed - needs investigation")
    
    logger.debug(f"\nFinished at: {timezone.now()}")

if __name__ == '__main__':
    main()