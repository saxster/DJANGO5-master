# Business Unit UI - Field Name Fix

## Issue
The initial implementation used `siteincharge__peoplemname` which caused a FieldError because the correct field name in the People model is `peoplename`, not `peoplemname`.

## Error Message
```
FieldError: Cannot resolve keyword 'peoplemname' into field
```

## Fix Applied

### Files Updated:

1. **apps/onboarding/views.py**
   - Changed `siteincharge__peoplemname` to `siteincharge__peoplename` in fields list
   - Updated filter for no_incharge to use `siteincharge__peoplename`
   - Updated search filter to use `siteincharge__peoplename`

2. **frontend/templates/onboarding/bu_list.html**
   - Changed DataTable column from `siteincharge__peoplemname` to `siteincharge__peoplename`
   - Updated column render function to use correct field name

## Correct Field Mapping

Based on the People model:
- `peoplename` - The name field (CharField, max_length=120)
- `peoplecode` - The employee code
- `peopleimg` - Profile image field

The `siteincharge` in Bt model is a ForeignKey to People (AUTH_USER_MODEL), so the correct lookup is:
- `siteincharge__peoplename` - To get the site incharge's name
- `siteincharge__peoplecode` - To get the site incharge's code
- `siteincharge__id` - To get the site incharge's ID

## Testing
After these fixes, the Business Unit list view should:
1. Load without errors
2. Display site incharge names correctly
3. Allow filtering by site incharge
4. Support searching by site incharge name

## Additional Fix: GPS Location JSON Serialization

### Issue 2
After fixing the field name, encountered a new error:
```
TypeError: Object of type Point is not JSON serializable
```

The `gpslocation` field is a PostGIS PointField which cannot be directly serialized to JSON.

### Solution
1. **Removed** `gpslocation` from the direct fields list
2. **Added annotation** `has_gpslocation` using Django's Case/When to check if GPS location exists
3. **Updated template** to use `has_gpslocation` boolean instead of the Point object

### Implementation Details
```python
# In views.py - Added annotation
.annotate(
    has_gpslocation=Case(
        When(gpslocation__isnull=False, then=Value(True)),
        default=Value(False),
        output_field=BooleanField()
    )
)
.values(*self.params["fields"], "has_gpslocation")
```

```javascript
// In template - Updated to use boolean
if(row['has_gpslocation'] === true) {
    locationHtml = '<span class="location-info"><i class="bi bi-geo-fill text-primary"></i> Configured</span>';
}
```

## Status
✅ Fixed - Both field name and GPS location serialization issues resolved.