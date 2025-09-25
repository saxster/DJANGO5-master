# Mobile App Issue Report: Incorrect TypeAssist ID for JOBNEEDDETAILS

## Issue Summary
**Severity**: High  
**Component**: Tour Attachment Upload  
**Impact**: Attachments fail to save to database despite successful file upload  
**Date Identified**: 2025-09-06  

## Problem Description
The mobile app is sending an incorrect `ownername_id` value when uploading tour attachments for JOBNEEDDETAILS, causing database foreign key constraint violations.

## Technical Details

### Current Behavior (INCORRECT)
The mobile app sends in the attachment record:
```json
{
  "ownername_id": 487,  // ❌ INCORRECT - This ID doesn't exist
  "ownername": "JOBNEEDDETAILS",
  "attachmenttype": "IMAGE",
  "owner": "39c308b6-abec-4a1f-8723-97f9c0e0593f",
  "filename": "photo_1757150863586.jpg",
  // ... other fields
}
```

### Expected Behavior (CORRECT)
The mobile app should send:
```json
{
  "ownername_id": 89,  // ✅ CORRECT - Valid ID for JOBNEEDDETAILS
  "ownername": "JOBNEEDDETAILS",
  "attachmenttype": "IMAGE",
  "owner": "39c308b6-abec-4a1f-8723-97f9c0e0593f",
  "filename": "photo_1757150863586.jpg",
  // ... other fields
}
```

## Error Details

### Server Error Log
```
ERROR: IntegrityError in attachment: insert or update on table "attachment" 
violates foreign key constraint "attachment_ownername_id_adb06b3e_fk_typeassist_id"
DETAIL: Key (ownername_id)=(487) is not present in table "typeassist"
```

### Impact
- Files upload successfully (3-4MB tour photos)
- Files are saved to media directory
- Database records FAIL to create
- Attachments appear as "uploaded" but are not retrievable via API

## Root Cause
The mobile app has a hardcoded or incorrectly mapped TypeAssist ID (487) for JOBNEEDDETAILS, but the actual ID in the database is 89.

## Required Fix in Mobile App

### Option 1: Dynamic Lookup (Recommended)
Instead of hardcoding TypeAssist IDs, fetch them dynamically from the server:

```kotlin
// Fetch TypeAssist mappings on app initialization or login
fun fetchTypeAssistMappings() {
    // API call to get TypeAssist mappings
    // GET /api/typeassist/mappings
    // Returns: {"JOBNEEDDETAILS": 89, "TICKET": 70, ...}
}

// Use the fetched ID
val ownerNameId = typeAssistMappings["JOBNEEDDETAILS"] // Returns 89
```

### Option 2: Update Hardcoded Values (Quick Fix)
If IDs are hardcoded, update them to match the database:

```kotlin
// BEFORE (Incorrect)
const val JOBNEEDDETAILS_TYPE_ID = 487  // ❌ Wrong

// AFTER (Correct)
const val JOBNEEDDETAILS_TYPE_ID = 89   // ✅ Correct
```

## Verification Steps

### For Mobile Developer
1. Search codebase for value `487` - this is the incorrect ID
2. Check where `ownername_id` is set for attachment uploads
3. Verify TypeAssist ID mappings in your app configuration
4. Test attachment upload with corrected ID

### Test Scenarios
1. Upload tour attachment (JOBNEEDDETAILS)
2. Verify no IntegrityError in server logs
3. Confirm attachment record appears in database
4. Test retrieval of uploaded attachments

## Server-Side Validation (Already Implemented)
The Django backend now includes automatic correction for this issue, but the mobile app should still be fixed to send correct data:

```python
# Server auto-corrects invalid IDs
if ownername_id == 487:  # Known incorrect ID
    ownername_id = 89     # Corrected to valid ID
```

## Additional TypeAssist IDs for Reference
Here are the correct TypeAssist IDs from the database:

| TypeAssist Name | tacode | Correct ID |
|----------------|--------|------------|
| Jobneed | JOBNEED | 70 |
| Jobneed details | JOBNEEDDETAILS | 89 |
| Ticket | TICKET | (check DB) |
| Work Order | WOM | (check DB) |

## Recommended Actions
1. **Immediate**: Update the incorrect ID from 487 to 89 for JOBNEEDDETAILS
2. **Short-term**: Audit all TypeAssist ID mappings in mobile app
3. **Long-term**: Implement dynamic TypeAssist lookup instead of hardcoding

## Contact
If you need the complete list of TypeAssist IDs or have questions about the correct mappings, please request them from the backend team.

## Testing After Fix
Once fixed, test the following GraphQL mutation:
```graphql
mutation uploadAttachment($bytes: [Int]!, $biodata: String!, $record: String!) {
    uploadAttachment(bytes: $bytes, biodata: $biodata, record: $record) {
        output {
            rc
            msg
            recordcount
        }
    }
}
```

With corrected record containing `"ownername_id": 89` for JOBNEEDDETAILS.

---
**Note**: While the server now auto-corrects this issue, fixing it in the mobile app will improve data integrity and prevent potential future issues.