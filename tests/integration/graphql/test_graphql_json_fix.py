#!/usr/bin/env python
"""
Test GraphQL JSON serialization fix
"""
import os
import sys
import django
import json
from datetime import datetime, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings')
sys.path.insert(0, '/home/redmine/DJANGO5/YOUTILITY5')
django.setup()

from apps.service.queries.question_queries import QuestionQueries


def test_enhanced_query_json_serialization():
    """Test the enhanced GraphQL query with JSON serialization fix"""
    print("\n" + "="*60)
    print("Testing Enhanced GraphQL Query JSON Serialization")
    print("="*60)
    
    # Test parameters
    mdtz = (datetime.now() - timedelta(days=30)).isoformat()
    ctzoffset = 330
    buid = 5
    clientid = 4
    peopleid = 3
    
    try:
        queries = QuestionQueries()
        result = queries.resolve_get_qsetbelongingmodifiedafter(
            self=queries,
            info=None,
            mdtz=mdtz,
            ctzoffset=ctzoffset,
            buid=buid,
            clientid=clientid,
            peopleid=peopleid,
            includeDependencyLogic=True
        )
        
        print(f"✅ Enhanced query completed successfully")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        # Test JSON parsing of the response
        try:
            parsed_records = json.loads(result.records)
            print(f"✅ JSON parsing successful")
            print(f"   Parsed {len(parsed_records)} records")
            
            # Check a few sample records for expected fields
            if parsed_records:
                sample_record = parsed_records[0]
                expected_fields = ['id', 'display_conditions', 'dependency_map', 'has_conditional_logic']
                
                for field in expected_fields:
                    if field in sample_record:
                        print(f"   ✅ {field}: present")
                        
                        # Show some sample data
                        if field == 'dependency_map' and sample_record[field]:
                            print(f"      Sample keys: {list(sample_record[field].keys())}")
                        elif field == 'has_conditional_logic':
                            print(f"      Value: {sample_record[field]}")
                        elif field == 'display_conditions' and sample_record[field]:
                            print(f"      Has conditions: {bool(sample_record[field])}")
                    else:
                        print(f"   ❌ {field}: missing")
            
            return True
            
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON parsing failed: {str(json_error)}")
            print(f"   Raw response type: {type(result.records)}")
            print(f"   Raw response preview: {str(result.records)[:200]}...")
            return False
            
    except Exception as e:
        print(f"❌ Enhanced query failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_basic_query_json_serialization():
    """Test the basic GraphQL query JSON serialization"""
    print("\n" + "="*60)
    print("Testing Basic GraphQL Query JSON Serialization")
    print("="*60)
    
    # Test parameters
    mdtz = (datetime.now() - timedelta(days=30)).isoformat()
    ctzoffset = 330
    buid = 5
    clientid = 4
    peopleid = 3
    
    try:
        queries = QuestionQueries()
        result = queries.resolve_get_qsetbelongingmodifiedafter(
            self=queries,
            info=None,
            mdtz=mdtz,
            ctzoffset=ctzoffset,
            buid=buid,
            clientid=clientid,
            peopleid=peopleid,
            includeDependencyLogic=False
        )
        
        print(f"✅ Basic query completed successfully")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        # Test JSON parsing of the response
        try:
            parsed_records = json.loads(result.records)
            print(f"✅ JSON parsing successful")
            print(f"   Parsed {len(parsed_records)} records")
            
            # Check for display_conditions field
            if parsed_records:
                sample_record = parsed_records[0]
                if 'display_conditions' in sample_record:
                    print(f"   ✅ display_conditions field present: {sample_record['display_conditions']}")
                else:
                    print(f"   ❌ display_conditions field missing")
                    print(f"   Available fields: {list(sample_record.keys())}")
            
            return True
            
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON parsing failed: {str(json_error)}")
            return False
            
    except Exception as e:
        print(f"❌ Basic query failed: {str(e)}")
        return False


def main():
    print("\n" + "="*70)
    print("GRAPHQL JSON SERIALIZATION FIX TEST")
    print("="*70)
    
    tests = [
        ("Basic Query JSON", test_basic_query_json_serialization),
        ("Enhanced Query JSON", test_enhanced_query_json_serialization)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ {test_name} failed with error: {str(e)[:100]}")
            results.append((test_name, False))
    
    print("\n" + "="*70)
    print("TEST RESULTS")
    print("="*70)
    
    all_passed = all(result for _, result in results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    if all_passed:
        print("\n🎉 ALL JSON SERIALIZATION TESTS PASSED!")
        print("\nThe GraphQL query should now work without JSON errors.")
    else:
        print("\n⚠️ Some tests failed - JSON serialization needs more fixes")
    
    print("="*70)


if __name__ == "__main__":
    main()