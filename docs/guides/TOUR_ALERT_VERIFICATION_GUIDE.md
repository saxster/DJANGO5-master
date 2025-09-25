# Tour/Task Alert Feature Verification Guide

This guide helps verify that the Tour/Task alert functionality is working correctly in your Django 5 refactored codebase.

## Quick Verification Steps

### 1. **Database Structure Check**
```bash
# Check if required tables exist and have correct structure
python manage.py shell -c "
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
print('✓ All models imported successfully')
print(f'Jobneed count: {Jobneed.objects.count()}')
print(f'JobneedDetails count: {JobneedDetails.objects.count()}')
print(f'Question count: {Question.objects.count()}')
print(f'QuestionSet count: {QuestionSet.objects.count()}')
"
```

### 2. **Email Configuration Check**
```bash
# Verify email settings
python manage.py shell -c "
from django.conf import settings
print(f'EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
print(f'DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
print('Email configuration loaded')
"
```

### 3. **Run Automated Alert Test**
```bash
# Test with console email backend (safe for testing)
export EMAIL_BACKEND='django.core.mail.backends.console.EmailBackend'
python manage.py test_tour_alerts --dry-run

# Test with actual email sending (use your email)
python manage.py test_tour_alerts --email="your-email@domain.com"
```

### 4. **Run Pytest Tests**
```bash
# Run the alert-specific tests
pytest apps/activity/tests/test_tour_alerts.py -v

# Run all activity tests
pytest apps/activity/tests/ -v
```

## Manual Testing Steps

### Step 1: Create Test Data
1. Ensure you have at least one CLIENT and SITE in your database
2. Create a test user in the People table
3. Create a test asset/checkpoint

### Step 2: Create Alert-Enabled Questions
Using Django Admin or shell:
```python
from apps.activity.models.question_model import Question, QuestionSet, QuestionSetBelonging
from apps.onboarding.models import Bt

client = Bt.objects.filter(butype='CLIENT').first()

# Create QuestionSet
qset = QuestionSet.objects.create(
    qsetname='Test Alert Checklist',
    type='CHECKLIST',
    client=client,
    enable=True
)

# Create Question with numeric alert
question = Question.objects.create(
    quesname='Temperature Reading (°C)',
    answertype='NUMERIC',
    min=20.00,
    max=25.00,
    alerton='20,25',
    client=client,
    enable=True
)

# Link to QuestionSet
QuestionSetBelonging.objects.create(
    qset=qset,
    question=question,
    seqno=1,
    answertype='NUMERIC',
    min=20.00,
    max=25.00,
    alerton='20,25',
    client=client,
    ismandatory=True
)
```

### Step 3: Test Alert Logic
```python
from apps.activity.models.job_model import Jobneed, JobneedDetails
from apps.peoples.models import People
from apps.activity.models.asset_model import Asset

# Create test tour
user = People.objects.exclude(id=1).first()
site = Bt.objects.filter(butype='SITE').first()
asset = Asset.objects.filter(bu=site).first()

jobneed = Jobneed.objects.create(
    jobname='Test Alert Tour',
    identifier='INTERNALTOUR',
    performedby=user,
    bu=site,
    client=client,
    qset=qset,
    asset=asset,
    alerts=False
)

# Answer with value that should trigger alert (outside 20-25 range)
jnd = JobneedDetails.objects.create(
    seqno=1,
    question=question,
    answertype='NUMERIC',
    answer='30',  # Outside range!
    min=20.00,
    max=25.00,
    alerton='20,25',
    jobneed=jobneed,
    qset=qset,
    alerts=True
)

# Update jobneed alerts flag
jobneed.alerts = True
jobneed.save()

# Test email sending
from background_tasks.utils import alert_observation
result = alert_observation(jobneed, atts=False)
print(result)
```

## What to Look For

### ✅ **Success Indicators:**
- [ ] Management command runs without errors
- [ ] Test tours are created successfully 
- [ ] Alert flags are set correctly on JobneedDetails with out-of-range values
- [ ] Jobneed.alerts flag is updated when child details have alerts
- [ ] Email sending function executes without exceptions
- [ ] Email templates render correctly
- [ ] Alert recipients are retrieved correctly

### ❌ **Failure Indicators:**
- [ ] Import errors when loading models
- [ ] Database constraint violations
- [ ] Email backend configuration errors
- [ ] Template rendering failures
- [ ] Alert logic not triggering correctly
- [ ] Email sending exceptions

## Debugging Common Issues

### 1. **Import Errors**
If you get import errors, check:
- Apps are in INSTALLED_APPS
- Model imports use correct paths
- Database migrations are applied

### 2. **Email Not Sending**
Check:
- EMAIL_BACKEND setting
- SMTP configuration if using SMTP
- get_email_recipients() function returns valid emails
- Jobneed has alerts=True and ismailsent=False

### 3. **Alert Logic Not Working**
Verify:
- alerton field format is correct
- min/max values are properly set
- Answer parsing handles the data types correctly
- Alert evaluation logic matches your business rules

### 4. **Template Errors**
Check:
- observation_mail.html template exists
- Template context variables match what's passed
- Django template engine is configured correctly

## Production Considerations

Before deploying:
1. **Test with real email addresses**
2. **Verify email rate limits**
3. **Check alert recipient configuration**
4. **Test with large datasets**
5. **Monitor email delivery logs**
6. **Set up proper error handling and logging**

## API Endpoints for Integration Testing

If you have frontend integration, test these endpoints:
- `/schedhuler/jobneedtours/` - Tour listing
- `/schedhuler/jobneedtasks/` - Task listing 
- `/activity/adhoctours/` - Adhoc tour creation

## Comparison with Django 3 Version

To verify feature parity:
1. **Test same scenarios** in both versions
2. **Compare email content** format and recipients
3. **Check alert timing** and conditions
4. **Verify data structure** consistency

This verification ensures your Django 5 refactor maintains the same alert functionality as your working Django 3 instance.