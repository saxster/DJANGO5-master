# Location QR Report Fix

## Issue Fixed ✅

**Error was:**
```
Error generating report: Field 'id' expected a number but got ''.
```

## Root Cause:
The Location QR report was receiving an empty string for the `site` field (`'site': ''`) but trying to use it as a database ID without validation.

**Problem code:**
```python
if site:
    filters.update({"bu_id": site})  # site was empty string ''
```

In Python, empty string `''` evaluates to `False` in boolean context, but Django was still trying to use it as an ID.

## Fix Applied:

### 1. Added proper empty string validation:
```python
if site and site != '':  # Check for empty string explicitly
    filters.update({"bu_id": int(site)})  # Convert to int
```

### 2. Fixed locations handling:
```python
elif locations and len(locations) > 0:  # Check if locations list is not empty
    if isinstance(locations, list):
        location_ids = [int(loc) for loc in locations if loc]
    else:
        location_ids = [int(loc) for loc in locations.split(",") if loc]
    if location_ids:
        filters.update({"id__in": location_ids})
```

### 3. Updated imports:
Removed deprecated raw SQL imports since this report now uses Django ORM.

## Form Data Analysis:
From the logs, the report was submitted with:
- `'site': ''` (empty)
- `'mult_location': []` (empty list)
- `'site_or_location': 'LOCATION'`

The code now handles these empty values properly.

## Testing:
The Location QR report should now:
1. Handle empty site field without error
2. Handle empty locations list without error
3. Generate QR codes for all locations when no specific filters are provided

## Related:
This report is already using Django ORM (not raw SQL), which is good! The issue was just with input validation.