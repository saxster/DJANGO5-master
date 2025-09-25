#!/usr/bin/env python
"""
Test corrected GraphQL query with proper parameter naming
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


def test_corrected_graphql_query():
    """Test the corrected GraphQL query with proper parameter naming"""
    print("\n" + "="*60)
    print("Testing Corrected GraphQL Query")
    print("="*60)
    
    # Test parameters matching your GraphQL query
    mdtz = "2025-08-01T00:00:00"
    ctzoffset = 330
    buid = 5
    clientid = 4
    peopleid = 3
    includeDependencyLogic = True  # Using camelCase as in your query
    
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
            includeDependencyLogic=includeDependencyLogic
        )
        
        print(f"✅ GraphQL query executed successfully")
        print(f"   Status: {result}")
        print(f"   Records returned: {result.nrows}")
        print(f"   Message: {result.msg}")
        
        # Test JSON parsing of the response
        try:
            parsed_records = json.loads(result.records)
            print(f"✅ JSON parsing successful - no 'AttributeError' issues")
            print(f"   Parsed {len(parsed_records)} records")
            
            # Show sample of the enhanced data
            if parsed_records:
                print(f"\n📋 Sample Record Structure:")
                sample = parsed_records[0]
                for key in ['id', 'quesname', 'display_conditions', 'dependency_map', 'has_conditional_logic']:
                    if key in sample:
                        value = sample[key]
                        if isinstance(value, dict) and value:
                            print(f"   {key}: {{...}} (dict with {len(value)} keys)")
                        elif isinstance(value, list) and value:
                            print(f"   {key}: [...] (list with {len(value)} items)")
                        else:
                            print(f"   {key}: {value}")
                    else:
                        print(f"   {key}: (missing)")
                        
                # Check for questions with dependencies
                questions_with_deps = [r for r in parsed_records if r.get('display_conditions')]
                print(f"\n📋 Questions with dependencies: {len(questions_with_deps)}")
                
                for q in questions_with_deps[:3]:  # Show first 3
                    qname = q.get('quesname', f"Question {q.get('id')}")
                    deps = q.get('display_conditions', {}).get('depends_on', {})
                    if deps:
                        parent_id = deps.get('question_id')
                        values = deps.get('values', [])
                        print(f"   • {qname} depends on Question {parent_id} = {values}")
            
            return True
            
        except json.JSONDecodeError as json_error:
            print(f"❌ JSON parsing failed: {str(json_error)}")
            print(f"   This indicates the 'AttributeError' issue is not fully resolved")
            return False
            
    except Exception as e:
        print(f"❌ GraphQL query failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def show_sample_graphql_queries():
    """Show sample GraphQL queries for mobile apps"""
    print("\n" + "="*60)
    print("Sample GraphQL Queries for Mobile Apps")
    print("="*60)
    
    print("""
🔗 Basic Query (includes display_conditions field):
query {
  getQsetbelongingmodifiedafter(
    mdtz: "2025-08-01T00:00:00",
    ctzoffset: 330,
    buid: 5,
    clientid: 4,
    peopleid: 3
  ) {
    nrows
    records
    msg
  }
}

🔗 Enhanced Query (includes dependency analysis):
query {
  getQsetbelongingmodifiedafter(
    mdtz: "2025-08-01T00:00:00",
    ctzoffset: 330,
    buid: 5,
    clientid: 4,
    peopleid: 3,
    includeDependencyLogic: true
  ) {
    nrows
    records
    msg
  }
}

🔗 Dedicated Conditional Logic Query:
query {
  getQuestionsetWithConditionalLogic(
    qsetId: 2,
    clientid: 4,
    buid: 5
  ) {
    nrows
    records
    msg
  }
}
""")


def main():
    print("\n" + "="*70)
    print("CORRECTED GRAPHQL QUERY TEST")
    print("="*70)
    
    # Test the corrected query
    success = test_corrected_graphql_query()
    
    # Show sample queries
    show_sample_graphql_queries()
    
    print("\n" + "="*70)
    print("RESULT")
    print("="*70)
    
    if success:
        print("🎉 GRAPHQL QUERY WORKS!")
        print("\nYour original query should now work without JSON errors:")
        print("• Parameter name: includeDependencyLogic ✅")
        print("• JSON serialization: Fixed ✅") 
        print("• Dependency processing: Enhanced ✅")
    else:
        print("⚠️ GraphQL query still has issues")
    
    print("="*70)


if __name__ == "__main__":
    main()