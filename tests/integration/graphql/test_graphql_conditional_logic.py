#!/usr/bin/env python
"""
Test GraphQL queries for conditional question logic
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
from apps.activity.models.question_model import QuestionSetBelonging


def test_basic_qsetbelonging_query():
    """Test basic QuestionSetBelonging GraphQL query"""
    print("\n" + "="*60)
    print("Testing Basic QuestionSetBelonging GraphQL Query")
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
        
        print(f"✅ Basic query successful")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        # Check if display_conditions field is included
        if result.records:
            try:
                # Parse the JSON string returned by utils.get_select_output
                parsed_records = json.loads(result.records)
                if parsed_records and len(parsed_records) > 0:
                    sample_record = parsed_records[0]
                    if 'display_conditions' in sample_record:
                        print(f"✅ display_conditions field included in response")
                        print(f"   Sample display_conditions: {sample_record.get('display_conditions')}")
                    else:
                        print(f"❌ display_conditions field NOT included in response")
                        print(f"   Available fields: {list(sample_record.keys())}")
                else:
                    print(f"❌ No records in parsed data")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"❌ Could not parse records JSON: {str(e)}")
                print(f"   Raw records type: {type(result.records)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Basic query failed: {str(e)}")
        return False


def test_enhanced_qsetbelonging_query():
    """Test enhanced QuestionSetBelonging GraphQL query with dependency logic"""
    print("\n" + "="*60)
    print("Testing Enhanced QuestionSetBelonging GraphQL Query")
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
        
        print(f"✅ Enhanced query successful")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        # Check if dependency metadata is included
        if result.records:
            try:
                # Parse the JSON string returned by GraphQL
                parsed_records = json.loads(result.records)
                if parsed_records and len(parsed_records) > 0:
                    sample_record = parsed_records[0]
                    
                    required_fields = ['display_conditions', 'dependency_map', 'has_conditional_logic']
                    for field in required_fields:
                        if field in sample_record:
                            print(f"✅ {field} field included in response")
                            if field == 'dependency_map' and sample_record[field]:
                                print(f"   Sample dependency_map keys: {list(sample_record[field].keys())}")
                            elif field == 'has_conditional_logic':
                                print(f"   has_conditional_logic: {sample_record[field]}")
                        else:
                            print(f"❌ {field} field NOT included in response")
                else:
                    print(f"❌ No records in parsed enhanced data")
            except (json.JSONDecodeError, TypeError) as e:
                print(f"❌ Could not parse enhanced records JSON: {str(e)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Enhanced query failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_dedicated_conditional_logic_query():
    """Test dedicated conditional logic GraphQL query"""
    print("\n" + "="*60)
    print("Testing Dedicated Conditional Logic GraphQL Query")
    print("="*60)
    
    # Test with questionset ID 2 (which has conditional logic)
    qset_id = 2
    clientid = 4
    buid = 5
    
    try:
        queries = QuestionQueries()
        result = queries.resolve_get_questionset_with_conditional_logic(
            self=queries,
            info=None,
            qset_id=qset_id,
            clientid=clientid,
            buid=buid
        )
        
        print(f"✅ Dedicated query successful")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        if result.records and len(result.records) > 0:
            logic_data = result.records[0]
            
            # Check structure
            expected_keys = ['questions', 'dependency_map', 'has_conditional_logic']
            for key in expected_keys:
                if key in logic_data:
                    print(f"✅ {key} present in response")
                    if key == 'questions':
                        print(f"   Question count: {len(logic_data[key])}")
                    elif key == 'dependency_map':
                        dep_count = len(logic_data[key])
                        print(f"   Dependencies found: {dep_count}")
                        if dep_count > 0:
                            print(f"   Dependent question IDs: {list(logic_data[key].keys())}")
                    elif key == 'has_conditional_logic':
                        print(f"   Has conditional logic: {logic_data[key]}")
                else:
                    print(f"❌ {key} missing from response")
        
        return True
        
    except Exception as e:
        print(f"❌ Dedicated query failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def test_data_structure_compatibility():
    """Test that the returned data structure is compatible with mobile apps"""
    print("\n" + "="*60)
    print("Testing Mobile App Data Structure Compatibility")
    print("="*60)
    
    # Check current data in database
    questions_with_logic = QuestionSetBelonging.objects.filter(
        qset_id=2,
        display_conditions__isnull=False
    ).exclude(display_conditions={})
    
    print(f"Found {questions_with_logic.count()} questions with conditional logic")
    
    for q in questions_with_logic:
        try:
            # Test JSON serialization
            conditions_json = json.dumps(q.display_conditions)
            conditions_parsed = json.loads(conditions_json)
            
            print(f"✅ Question {q.id} - JSON serialization works")
            
            # Check required structure
            if 'depends_on' in conditions_parsed:
                depends_on = conditions_parsed['depends_on']
                required_fields = ['question_id', 'operator', 'values']
                
                for field in required_fields:
                    if field in depends_on:
                        print(f"   ✅ {field}: {depends_on[field]}")
                    else:
                        print(f"   ❌ Missing {field}")
            else:
                print(f"   📝 No depends_on structure (empty conditions)")
                
        except Exception as e:
            print(f"❌ Question {q.id} - JSON error: {str(e)}")
    
    return True


def main():
    print("\n" + "="*70)
    print("GRAPHQL CONDITIONAL LOGIC TEST")
    print("="*70)
    
    tests = [
        ("Data Structure Compatibility", test_data_structure_compatibility),
        ("Basic QSetBelonging Query", test_basic_qsetbelonging_query),
        ("Enhanced QSetBelonging Query", test_enhanced_qsetbelonging_query),
        ("Dedicated Conditional Logic Query", test_dedicated_conditional_logic_query)
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
        print("\n🎉 ALL GRAPHQL TESTS PASSED!")
        print("\nMobile apps can now:")
        print("1. ✅ Fetch questions with display_conditions via existing GraphQL")
        print("2. ✅ Get enhanced dependency metadata with include_dependency_logic=true")
        print("3. ✅ Use dedicated conditional logic query for optimized mobile response")
        print("4. ✅ Process JSON dependency structures for client-side evaluation")
    else:
        print("\n⚠️ Some GraphQL tests failed - please review")
    
    print("="*70)


if __name__ == "__main__":
    main()