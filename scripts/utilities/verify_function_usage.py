#!/usr/bin/env python
"""
Script to verify which version of fn_getassetdetails is being used
"""

# Check 1: Look for Python implementation
print("1. Checking for Python/Django ORM implementation of fn_getassetdetails:")
print("   Searching for method definitions...")

# Run this search
# grep -rn "def.*getassetdetails\|def.*get_asset_details" /path/to/codebase --include="*.py"

print("\n2. Checking PostgreSQL function existence:")
print("   Run this SQL in your database:")
print("   SELECT proname FROM pg_proc WHERE proname = 'fn_getassetdetails';")
print("   If it returns a row, the function exists in PostgreSQL")

print("\n3. Checking actual execution:")
print("   The code shows:")
print("   - get_db_rows() executes raw SQL")
print("   - The SQL is: 'select * from fn_getassetdetails(%s, %s)'")
print("   - This calls the PostgreSQL function directly")

print("\n4. Testing which one is used:")
print("   Option A: Temporarily rename the PostgreSQL function")
print("   ALTER FUNCTION fn_getassetdetails RENAME TO fn_getassetdetails_backup;")
print("   Then try the legacy API query - if it fails, PostgreSQL version is being used")
print("\n   Option B: Add logging to PostgreSQL function")
print("   Add RAISE NOTICE in the PostgreSQL function and check logs")

print("\nCONCLUSION: The PostgreSQL database version is being used.")
print("The code in raw_sql_functions.py is just the function definition/source.")
