# People Onboarding - Required Commands to Complete Deployment

## Status: 95% Complete - Ready for Testing

All code is implemented. Run these commands to complete the final 5% and test the module.

---

## 🚀 STEP 1: Create Database Migrations (REQUIRED)

```bash
# Navigate to project root
cd /Users/amar/Desktop/MyCode/DJANGO5-master

# Create migrations for people_onboarding app
python manage.py makemigrations people_onboarding

# Expected output:
# Migrations for 'people_onboarding':
#   apps/people_onboarding/migrations/0001_initial.py
#     - Create model OnboardingRequest
#     - Create model CandidateProfile
#     - Create model DocumentSubmission
#     - Create model ApprovalWorkflow
#     - Create model OnboardingTask
#     - Create model BackgroundCheck
#     - Create model AccessProvisioning
#     - Create model TrainingAssignment

# Apply migrations to database
python manage.py migrate people_onboarding

# Expected output:
# Running migrations:
#   Applying people_onboarding.0001_initial... OK
```

---

## 🧪 STEP 2: Verify Installation

```bash
# Check if URLs are registered correctly
python manage.py show_urls | grep people_onboarding

# Expected output (17+ URLs):
# /people-onboarding/                                  people_onboarding:dashboard
# /people-onboarding/start/                            people_onboarding:start_onboarding
# /people-onboarding/wizard/<uuid:uuid>/               people_onboarding:onboarding_wizard
# /people-onboarding/approvals/                        people_onboarding:approval_list
# ... (13 more URLs)

# Run Django's system check
python manage.py check

# Expected output:
# System check identified no issues (0 silenced).

# Check for deployment issues
python manage.py check --deploy

# May show warnings about DEBUG=True in development (expected)
```

---

## 🎨 STEP 3: Collect Static Files (Development - Optional)

```bash
# Collect static files (only if using production setup)
python manage.py collectstatic --no-input

# For development, static files are served automatically by Django
# This step is only required for production deployment
```

---

## 🏃 STEP 4: Start Development Server and Test

```bash
# Start the development server
python manage.py runserver

# Server will start at: http://127.0.0.1:8000/

# Open these URLs in your browser to test:
# 1. http://127.0.0.1:8000/people-onboarding/
# 2. http://127.0.0.1:8000/people-onboarding/start/
# 3. http://127.0.0.1:8000/people-onboarding/approvals/
```

---

## 📝 STEP 5: Create Test Data (Optional)

```bash
# Open Django shell
python manage.py shell

# Run these commands to create test data:
```

```python
from apps.people_onboarding.models import OnboardingRequest, CandidateProfile
from apps.peoples.models import People
from django.utils import timezone

# Get current user (replace with actual username)
user = People.objects.filter(is_staff=True).first()

# Create test onboarding request
request = OnboardingRequest.objects.create(
    request_number='ONB-2025-00001',
    person_type='EMPLOYEE_FULLTIME',
    current_state='DRAFT',
    cdby=user
)

# Create candidate profile
profile = CandidateProfile.objects.create(
    first_name='John',
    last_name='Doe',
    primary_email='john.doe@example.com',
    primary_phone='+1-555-0123',
    date_of_birth='1990-01-15',
    gender='M',
    cdby=user
)

# Link profile to request
request.candidate_profile = profile
request.save()

print(f"Created test request: {request.request_number}")
print(f"View at: http://127.0.0.1:8000/people-onboarding/requests/{request.uuid}/")
```

---

## ✅ VERIFICATION CHECKLIST

After running the above commands, verify:

### Database
- [ ] Migrations created successfully
- [ ] Migrations applied without errors
- [ ] 8 new tables created in database

### URLs
- [ ] `show_urls` command shows 17+ people_onboarding URLs
- [ ] No URL conflicts reported
- [ ] Module accessible at `/people-onboarding/`

### Static Files
- [ ] CSS files load without 404 errors
- [ ] JavaScript files load without errors
- [ ] No console errors in browser developer tools

### Functionality
- [ ] Dashboard page loads successfully
- [ ] "Start Onboarding" button works
- [ ] Person type selection works
- [ ] Form wizard loads
- [ ] Documents tab accessible
- [ ] Approvals list accessible (may be empty)

---

## 🐛 TROUBLESHOOTING

### Issue: "No module named 'people_onboarding'"
**Solution:**
```bash
# Verify app is in INSTALLED_APPS
grep "people_onboarding" intelliwiz_config/settings/base.py

# Should show: 'apps.people_onboarding'
```

### Issue: "No such table: people_onboarding_onboardingrequest"
**Solution:**
```bash
# Run migrations
python manage.py migrate people_onboarding
```

### Issue: Static files not loading (404 errors)
**Solution:**
```bash
# In development, ensure DEBUG=True in settings
# Django will serve static files automatically

# Check static files exist:
ls frontend/static/people_onboarding/css/
ls frontend/static/people_onboarding/js/

# If files are missing, they're in the wrong location
# Static files should be in: frontend/static/people_onboarding/
```

### Issue: "Page not found" at /people-onboarding/
**Solution:**
```bash
# Verify URL is in urls_optimized.py
grep "people-onboarding" intelliwiz_config/urls_optimized.py

# Should show: path('people-onboarding/', include('apps.people_onboarding.urls')),
```

### Issue: Template errors or undefined variables
**Solution:**
Most templates require context variables. Access them through proper views:
- Dashboard: `/people-onboarding/` (works immediately)
- Start: `/people-onboarding/start/` (works immediately)
- Wizard: `/people-onboarding/wizard/<uuid>/` (requires existing request)

---

## 🎉 SUCCESS CRITERIA

The module is working correctly when:

1. ✅ Database migrations applied successfully
2. ✅ Dashboard page loads without errors
3. ✅ "Start Onboarding" flow works
4. ✅ Static files (CSS/JS) load correctly
5. ✅ No errors in browser console
6. ✅ No errors in Django server logs

---

## 📞 NEXT STEPS AFTER TESTING

Once basic testing is complete:

1. **User Acceptance Testing (UAT)**
   - Have HR team test the workflow
   - Gather feedback on usability
   - Identify any edge cases

2. **Performance Testing**
   - Test with multiple concurrent users
   - Verify document upload performance
   - Check database query performance

3. **Security Review**
   - Verify permission checks work
   - Test file upload validation
   - Confirm CSRF protection active

4. **Production Deployment**
   - Follow PEOPLE_ONBOARDING_DEPLOYMENT_CHECKLIST.md
   - Set DEBUG=False
   - Configure proper static file serving (Nginx/Apache)
   - Set up SSL/TLS certificates
   - Configure backup strategy

---

## 📊 CURRENT STATUS SUMMARY

| Component | Status | Notes |
|-----------|--------|-------|
| Models | ✅ 100% | 8 models, all fields defined |
| Views | ✅ 100% | 10 views, all implemented |
| URLs | ✅ 100% | 17+ URLs, integrated in main |
| Templates | ✅ 100% | 6 core + 10 partials |
| Forms | ✅ 100% | 3 forms with validation |
| Serializers | ✅ 100% | 10 serializers |
| API Views | ✅ 100% | 8 REST endpoints |
| CSS | ✅ 100% | 4 files (1,500+ lines) |
| JavaScript | ✅ 100% | 4 files (1,750+ lines) |
| **Migrations** | ⚠️ **PENDING** | **Run makemigrations now** |
| **Testing** | ⚠️ **PENDING** | **Test after migrations** |

**Overall: 95% Complete - Just run the commands above!**

---

**Last Updated:** 2025-09-30
**Quick Start:** Run STEP 1 commands, then STEP 4 to test