#!/usr/bin/env python
"""
Test script to compare PostgreSQL function output with Django ORM implementation
for fn_getassetdetails and fn_getassetvsquestionset.
"""

import os
import sys
import django
from datetime import datetime, timedelta
import json

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
django.setup()

from django.db import connection
from apps.activity.managers.asset_manager_orm import AssetManagerORM
from apps.core import utils


def test_asset_vs_questionset():
    """Test fn_getassetvsquestionset Django ORM implementation"""
    print("\n=== Testing fn_getassetvsquestionset ===")
    
    # Test parameters
    test_cases = [
        {'bu_id': 1, 'asset_id': '1', 'return_type': ''},
        {'bu_id': 1, 'asset_id': '1', 'return_type': 'name'},
    ]
    
    for test in test_cases:
        print(f"\nTest case: {test}")
        
        # Get Django ORM result
        orm_result = AssetManagerORM.get_asset_vs_questionset(
            test['bu_id'], 
            test['asset_id'], 
            test['return_type']
        )
        
        # Get PostgreSQL result
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT fn_getassetvsquestionset(%s, %s, %s)",
                [test['bu_id'], test['asset_id'], test['return_type']]
            )
            pg_result = cursor.fetchone()[0] or ''
        
        print(f"  Django ORM: '{orm_result}'")
        print(f"  PostgreSQL: '{pg_result}'")
        print(f"  Match: {orm_result == pg_result}")


def test_asset_details():
    """Test fn_getassetdetails Django ORM implementation"""
    print("\n=== Testing fn_getassetdetails ===")
    
    # Test with a date 30 days ago
    test_date = datetime.now() - timedelta(days=30)
    test_bu_id = 1  # Change this to a valid BU ID in your system
    
    print(f"\nTest parameters:")
    print(f"  Modified after: {test_date}")
    print(f"  BU ID: {test_bu_id}")
    
    # Get Django ORM result
    orm_assets = AssetManagerORM.get_asset_details(test_date, test_bu_id)
    
    # Get PostgreSQL result
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fn_getassetdetails(%s, %s)",
            [test_date, test_bu_id]
        )
        columns = [col[0] for col in cursor.description]
        pg_assets = []
        for row in cursor.fetchall():
            pg_assets.append(dict(zip(columns, row)))
    
    print(f"\nResults:")
    print(f"  Django ORM count: {len(orm_assets)}")
    print(f"  PostgreSQL count: {len(pg_assets)}")
    
    # Compare results
    if len(orm_assets) == len(pg_assets):
        print("\n✓ Same number of assets returned")
        
        # Compare first asset if any
        if orm_assets and pg_assets:
            print("\nComparing first asset:")
            orm_first = orm_assets[0]
            pg_first = pg_assets[0]
            
            # Key fields to compare
            key_fields = ['id', 'assetcode', 'assetname', 'qsetids', 'qsetname']
            for field in key_fields:
                orm_val = orm_first.get(field)
                pg_val = pg_first.get(field)
                match = str(orm_val) == str(pg_val)
                print(f"  {field}: {'✓' if match else '✗'} (ORM: {orm_val}, PG: {pg_val})")
    else:
        print("\n✗ Different number of assets returned!")
        print("  This might indicate a data issue or query difference")


def compare_performance():
    """Compare performance between PostgreSQL and Django ORM"""
    print("\n=== Performance Comparison ===")
    
    import time
    
    test_date = datetime.now() - timedelta(days=30)
    test_bu_id = 1
    
    # Time PostgreSQL function
    start = time.time()
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT * FROM fn_getassetdetails(%s, %s)",
            [test_date, test_bu_id]
        )
        pg_results = cursor.fetchall()
    pg_time = time.time() - start
    
    # Time Django ORM
    start = time.time()
    orm_results = AssetManagerORM.get_asset_details(test_date, test_bu_id)
    orm_time = time.time() - start
    
    print(f"\nPerformance:")
    print(f"  PostgreSQL: {pg_time:.4f} seconds")
    print(f"  Django ORM: {orm_time:.4f} seconds")
    print(f"  Ratio: {orm_time/pg_time:.2f}x" if pg_time > 0 else "N/A")


if __name__ == "__main__":
    print("Testing Asset PostgreSQL to Django ORM Migration")
    print("=" * 50)
    
    try:
        test_asset_vs_questionset()
        test_asset_details()
        compare_performance()
        
        print("\n" + "=" * 50)
        print("Testing complete!")
        print("\nNOTE: To use Django ORM in production, set environment variable:")
        print("  export USE_DJANGO_ORM_FOR_ASSETS=true")
        
    except Exception as e:
        print(f"\nError during testing: {e}")
        import traceback
        traceback.print_exc()