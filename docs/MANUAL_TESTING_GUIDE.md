# Manual Testing Guide for URL Mapping Migration

## Overview
This guide provides comprehensive manual testing procedures to validate the URL mapping migration from legacy `onboarding:` namespace to the new `admin_panel:` domain-driven architecture.

## Pre-Testing Setup

### Environment Preparation
1. **Browser Setup**
   - [ ] Test in Chrome (latest version)
   - [ ] Test in Firefox (latest version)
   - [ ] Test in Safari (if available)
   - [ ] Test in Edge (latest version)
   - [ ] Clear browser cache before testing
   - [ ] Open Developer Tools (F12) for monitoring

2. **User Account Setup**
   - [ ] Create test user account with appropriate permissions
   - [ ] Verify user has access to business unit management
   - [ ] Ensure user can create, edit, and delete business units

3. **Test Data Setup**
   - [ ] Create test business units for editing/deletion
   - [ ] Prepare test client data
   - [ ] Set up test contracts and configurations
   - [ ] Create sample import data files

4. **Debug Mode Activation**
   - [ ] Enable debug mode: `URL_DEBUG_MODE = true` in browser console
   - [ ] Verify console logging is working
   - [ ] Check that URL transformations are logged

## Core Functionality Testing

### 1. Business Unit Management Workflow

#### 1.1 Business Unit List View
**Test URL:** Navigate to business units section

**Steps:**
1. [ ] Navigate to business units from main menu
2. [ ] Verify page loads without errors
3. [ ] Check that URL in address bar uses new structure
4. [ ] Verify no 404 or broken links
5. [ ] Check browser console for JavaScript errors
6. [ ] Verify debug logging shows URL transformations

**Expected Results:**
- [ ] Page loads successfully
- [ ] URL shows modern structure (e.g., `/admin/business-units/`)
- [ ] Console shows: `[URL_MIGRATION] AJAX URL transformed` messages
- [ ] No JavaScript errors in console
- [ ] Business units display correctly

**Debug Verification:**
```javascript
// Run in browser console to verify URL mapper is working
console.log('URL Mapper status:', typeof window.UrlMapper !== 'undefined');
console.log('Transform test:', window.UrlMapper.transformUrl('onboarding:bu'));
// Should output: 'admin_panel:bu_list'
```

#### 1.2 Business Unit Creation
**Test Scenario:** Create new business unit

**Steps:**
1. [ ] Click "Add New" button
2. [ ] Verify form loads properly
3. [ ] Fill out form fields:
   - [ ] Business Unit Name: "Test BU Manual"
   - [ ] Business Unit Code: "TBM001"
   - [ ] Address: "123 Test Street"
   - [ ] Contact Person: "Test Contact"
4. [ ] Submit form
5. [ ] Monitor browser console during submission
6. [ ] Verify success message appears
7. [ ] Check that new business unit appears in list

**Expected Results:**
- [ ] Form loads without errors
- [ ] All form fields are editable
- [ ] AJAX submission uses transformed URL
- [ ] Console shows: `[URL_MIGRATION] fire_ajax_form_post URL transformed`
- [ ] Success message: "Business Unit saved successfully"
- [ ] New business unit visible in list

**Console Verification:**
```javascript
// Check recent AJAX calls
console.log('Recent URL transformations:', window.UrlMapper.getTransformationCount());
```

#### 1.3 Business Unit Editing
**Test Scenario:** Edit existing business unit

**Steps:**
1. [ ] Click on existing business unit to edit
2. [ ] Verify form loads with existing data
3. [ ] Modify business unit name to "Updated Test BU"
4. [ ] Submit form
5. [ ] Monitor console for URL transformations
6. [ ] Verify update success message
7. [ ] Confirm changes are reflected in list

**Expected Results:**
- [ ] Edit form loads with correct data
- [ ] Form submission successful
- [ ] URL transformation logged in console
- [ ] Update confirmation displayed
- [ ] Changes visible immediately in list

#### 1.4 Business Unit Deletion
**Test Scenario:** Delete business unit

**Steps:**
1. [ ] Click delete button for test business unit
2. [ ] Verify confirmation dialog appears
3. [ ] Confirm deletion
4. [ ] Monitor console for AJAX call
5. [ ] Verify success message
6. [ ] Confirm business unit removed from list

**Expected Results:**
- [ ] Confirmation dialog appears
- [ ] AJAX delete request uses correct URL
- [ ] Console shows URL transformation
- [ ] Success message: "Business Unit deleted successfully"
- [ ] Item removed from list

### 2. Client Management Workflow

#### 2.1 Client Operations
**Test URL:** Navigate to clients section

**Steps:**
1. [ ] Navigate to clients management
2. [ ] Verify page loads with new URL structure
3. [ ] Create new client with test data
4. [ ] Edit existing client
5. [ ] Delete test client
6. [ ] Monitor console throughout process

**Expected Results:**
- [ ] All client operations work correctly
- [ ] URLs use `admin_panel:clients_list` namespace
- [ ] Console shows appropriate transformations
- [ ] No functionality regression

### 3. Contract Management Workflow

#### 3.1 Contract Operations
**Test URL:** Navigate to contracts section

**Steps:**
1. [ ] Navigate to contracts management
2. [ ] Test create, edit, delete operations
3. [ ] Verify URL transformations in console
4. [ ] Check form submissions work correctly

**Expected Results:**
- [ ] Contract management fully functional
- [ ] URLs use `admin_panel:contracts_list` namespace
- [ ] All CRUD operations successful

### 4. Configuration Management

#### 4.1 Types Configuration
**Test URL:** Navigate to types configuration

**Steps:**
1. [ ] Navigate to types configuration
2. [ ] Verify URL uses `admin_panel:config_types`
3. [ ] Test adding/editing types
4. [ ] Monitor console for transformations

#### 4.2 Shifts Configuration
**Test URL:** Navigate to shifts configuration

**Steps:**
1. [ ] Navigate to shifts configuration
2. [ ] Create new shift:
   - [ ] Shift Name: "Test Shift"
   - [ ] Start Time: "09:00"
   - [ ] End Time: "17:00"
   - [ ] People Count: "5"
3. [ ] Submit and verify success
4. [ ] Edit shift details
5. [ ] Delete test shift

**Expected Results:**
- [ ] Shifts use `admin_panel:config_shifts` namespace
- [ ] All shift operations functional
- [ ] Time validation works correctly

#### 4.3 Geofence Configuration
**Test URL:** Navigate to geofence configuration

**Steps:**
1. [ ] Navigate to geofence configuration
2. [ ] Test geofence creation/editing
3. [ ] Verify URL namespace transformation

### 5. Data Import/Export Workflow

#### 5.1 Data Import
**Test URL:** Navigate to data import

**Steps:**
1. [ ] Navigate to data import page
2. [ ] Verify URL uses `admin_panel:data_import`
3. [ ] Select table type: "Business Units"
4. [ ] Download template file
5. [ ] Upload test data file
6. [ ] Submit import
7. [ ] Monitor console for URL transformations

**Expected Results:**
- [ ] Import page loads correctly
- [ ] Template download works
- [ ] File upload successful
- [ ] Import process completes
- [ ] Console shows `admin_panel:data_import` usage

#### 5.2 Bulk Update
**Test URL:** Navigate to bulk update

**Steps:**
1. [ ] Navigate to bulk update page
2. [ ] Test bulk update workflow
3. [ ] Verify URL transformations

## Cross-Browser Compatibility Testing

### Browser-Specific Tests

#### Chrome Testing
1. [ ] Complete all core workflows in Chrome
2. [ ] Verify console logging works
3. [ ] Check for Chrome-specific issues
4. [ ] Test developer tools functionality

#### Firefox Testing
1. [ ] Repeat core workflows in Firefox
2. [ ] Verify URL transformations work
3. [ ] Check console output format
4. [ ] Test for Firefox-specific issues

#### Safari Testing (if available)
1. [ ] Test core business unit workflow
2. [ ] Verify URL transformations
3. [ ] Check for Safari-specific issues

#### Edge Testing
1. [ ] Complete core testing in Edge
2. [ ] Verify compatibility
3. [ ] Check console functionality

### Mobile Browser Testing
1. [ ] Test on mobile Chrome
2. [ ] Test on mobile Safari (iOS)
3. [ ] Verify touch interactions work
4. [ ] Check responsive design

## Performance Testing

### Page Load Performance
1. [ ] Measure business unit list load time
2. [ ] Time form loading speed
3. [ ] Check AJAX response times
4. [ ] Verify no performance degradation

**Performance Benchmarks:**
- [ ] Page load: < 2 seconds
- [ ] Form load: < 1 second  
- [ ] AJAX response: < 500ms
- [ ] URL transformation: < 1ms

### Memory Usage
1. [ ] Monitor browser memory usage
2. [ ] Check for memory leaks during navigation
3. [ ] Verify garbage collection works

## Error Handling Testing

### Network Error Scenarios
1. [ ] Disconnect network during form submission
2. [ ] Verify error messages display
3. [ ] Test retry functionality
4. [ ] Check graceful degradation

### Server Error Testing
1. [ ] Simulate 500 server error
2. [ ] Verify error handling
3. [ ] Check user feedback
4. [ ] Test recovery process

### Invalid Data Testing
1. [ ] Submit forms with invalid data
2. [ ] Test required field validation
3. [ ] Verify error messages
4. [ ] Check form state preservation

## Security Testing

### Authentication Testing
1. [ ] Test unauthenticated access
2. [ ] Verify redirects to login
3. [ ] Test session management
4. [ ] Check authorization levels

### Input Validation
1. [ ] Test XSS prevention in forms
2. [ ] Verify SQL injection protection
3. [ ] Test CSRF protection
4. [ ] Check file upload security

## Regression Testing

### Existing Functionality
1. [ ] Verify all existing features work
2. [ ] Check user authentication
3. [ ] Test navigation menus
4. [ ] Confirm data integrity
5. [ ] Verify reports still generate
6. [ ] Check user permissions

### Data Consistency
1. [ ] Verify existing data accessible
2. [ ] Check foreign key relationships
3. [ ] Confirm data integrity
4. [ ] Test database operations

## URL Mapping Verification

### Manual URL Transformation Test
```javascript
// Run in browser console to test all mappings
const testMappings = [
  'onboarding:bu',
  'onboarding:client',
  'onboarding:contract',
  'onboarding:typeassist',
  'onboarding:shift',
  'onboarding:geofence',
  'onboarding:import',
  'onboarding:import_update'
];

testMappings.forEach(url => {
  const transformed = window.UrlMapper.transformUrl(url);
  console.log(`${url} -> ${transformed}`);
});
```

**Expected Transformations:**
- [ ] `onboarding:bu` -> `admin_panel:bu_list`
- [ ] `onboarding:client` -> `admin_panel:clients_list`
- [ ] `onboarding:contract` -> `admin_panel:contracts_list`
- [ ] `onboarding:typeassist` -> `admin_panel:config_types`
- [ ] `onboarding:shift` -> `admin_panel:config_shifts`
- [ ] `onboarding:geofence` -> `admin_panel:config_geofences`
- [ ] `onboarding:import` -> `admin_panel:data_import`
- [ ] `onboarding:import_update` -> `admin_panel:data_bulk_update`

### Path Pattern Testing
```javascript
// Test path pattern transformations
const pathTests = [
  '/onboarding/bu/',
  '/onboarding/client/',
  '/onboarding/contract/',
  '/onboarding/import/'
];

pathTests.forEach(path => {
  const transformed = window.UrlMapper.transformUrl(path);
  console.log(`${path} -> ${transformed}`);
});
```

## Issue Reporting Template

### Bug Report Format
When issues are found, use this template:

**Issue Title:** [Component] - Brief description

**Environment:**
- Browser: 
- Version:
- Operating System:
- User Account:

**Steps to Reproduce:**
1. 
2. 
3. 

**Expected Result:**

**Actual Result:**

**Console Output:**
```
[Paste console logs here]
```

**Screenshots:**
[Attach screenshots if relevant]

**Severity:**
- [ ] Critical (blocking)
- [ ] High (major functionality)
- [ ] Medium (minor functionality)
- [ ] Low (cosmetic)

## Sign-off Checklist

### Testing Completion
- [ ] All core workflows tested
- [ ] Cross-browser compatibility verified
- [ ] Performance benchmarks met
- [ ] Error handling validated
- [ ] Security testing completed
- [ ] Regression testing passed
- [ ] URL transformations verified

### Documentation
- [ ] Test results documented
- [ ] Issues reported and tracked
- [ ] Performance metrics recorded
- [ ] Known limitations noted

### Final Approval
- [ ] Testing lead sign-off
- [ ] Development team approval
- [ ] Product owner acceptance
- [ ] Ready for production deployment

## Post-Deployment Verification

### Production Testing (After Deployment)
1. [ ] Test business unit creation in production
2. [ ] Verify URL transformations work in prod
3. [ ] Check console logging is appropriate for prod
4. [ ] Monitor error rates
5. [ ] Verify performance metrics
6. [ ] Check user feedback

### Monitoring Setup
1. [ ] Set up URL transformation monitoring
2. [ ] Configure error tracking
3. [ ] Establish performance baselines
4. [ ] Set up user feedback collection

---

**Testing Timeline:**
- Manual testing: 2-3 days
- Cross-browser testing: 1 day  
- Performance testing: 1 day
- Regression testing: 1 day
- Documentation: 0.5 day

**Total Estimated Time:** 5.5 days

**Team Requirements:**
- 1 QA Tester (primary)
- 1 Developer (support)
- 1 Product Owner (acceptance)

**Success Criteria:**
- [ ] All test cases pass
- [ ] No critical or high severity issues
- [ ] Performance benchmarks met
- [ ] Cross-browser compatibility confirmed
- [ ] Team sign-off completed