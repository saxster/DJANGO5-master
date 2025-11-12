# Help Center - Quick Start Guide

**Time to Running System**: 30 minutes
**Difficulty**: Easy
**Prerequisites**: PostgreSQL, Redis, Python 3.11.9

---

## 🚀 SETUP IN 6 STEPS (30 Minutes)

### Step 1: Enable pgvector Extension (2 minutes)

```bash
# Connect to PostgreSQL as superuser
psql -U postgres -d intelliwiz_db

# Enable pgvector (required for semantic search)
CREATE EXTENSION IF NOT EXISTS vector;

# Verify
\dx vector
# Should show: vector | 0.5.0 | vector data type and ivfflat access method

# Exit
\q
```

**Why**: pgvector enables semantic search with embeddings (384-dimensional vectors).

---

### Step 2: Run Migrations (3 minutes)

```bash
# Run help_center migrations
python manage.py migrate help_center

# Expected output:
# Running migrations:
#   Applying help_center.0001_initial... OK
#   Applying help_center.0002_gamification_and_memory... OK

# Verify tables created
python manage.py dbshell
\dt help_center*
# Should show 10 tables

\q
```

**Tables Created**:
- help_center_article (knowledge base)
- help_center_category (hierarchical categorization)
- help_center_search_history (analytics)
- help_center_interaction (engagement tracking)
- help_center_ticket_correlation (effectiveness measurement)
- help_center_badge (gamification)
- help_center_user_badge (earned badges)
- help_center_user_points (points tracking)
- help_center_conversation_memory (AI context)
- help_center_tag (article tagging)

---

### Step 3: Load Initial Badges (2 minutes)

```bash
# Load predefined badges
python manage.py loaddata apps/help_center/fixtures/initial_badges.json

# Expected output:
# Installed 6 object(s) from 1 fixture(s)

# Verify
python manage.py shell
>>> from apps.help_center.gamification_models import HelpBadge
>>> HelpBadge.objects.count()
6
>>> exit()
```

**Badges Loaded**:
- 🎯 First Feedback (5 points)
- ⭐ Helpful Reviewer (20 points)
- 🏆 Power User (50 points)
- 📝 Content Contributor (30 points)
- 👑 Help Champion (100 points)
- 🚀 Early Adopter (15 points)

---

### Step 4: Create Initial Content (10 minutes)

**Option A: Via Django Admin (Recommended)**

```bash
# Start development server
python manage.py runserver

# Navigate to: http://localhost:8000/admin/help_center/

# Login with superuser credentials
# If no superuser: python manage.py createsuperuser

# 1. Create Categories (2-3 min):
#    - Click "Help Categories" → "Add Help Category"
#    - Create: "Getting Started", "Operations", "Work Orders", "PPM Scheduling"

# 2. Create Articles (5-7 min):
#    - Click "Help Articles" → "Add Help Article"
#    - Title: "How to Create a Work Order"
#    - Summary: "Step-by-step guide to creating work orders"
#    - Content: (paste from docs or write)
#    - Category: Work Orders
#    - Difficulty: BEGINNER
#    - Target Roles: ["all"]
#    - Status: PUBLISHED
#    - Click "Save"

#    Repeat for 5-10 core articles
```

**Option B: Bulk Import from Markdown (Advanced)**

```bash
# If you have markdown files in docs/
python manage.py sync_documentation \
    --dir=docs/ \
    --tenant=1 \
    --user=1 \
    --dry-run  # Preview first

# Then run for real
python manage.py sync_documentation --dir=docs/ --tenant=1 --user=1
```

---

### Step 5: Verify Deployment (5 minutes)

```bash
# Run verification script
python apps/help_center/verify_deployment.py

# Expected output:
# ✓ Table help_center_article
# ✓ Table help_center_category
# ... (all tables)
# ✓ All models importable
# ✓ All services importable
# ✓ API ViewSets importable
# ✓ WebSocket consumer importable
# ✓ Static files exist
# ✓ Test files exist
# ✓ pgvector extension enabled
#
# Passed: 8/8 (100.0%)
# ✓ All checks passed! System is ready.
```

**If Any Checks Fail**: Review error messages and fix before proceeding.

---

### Step 6: Test API Endpoints (8 minutes)

**Get Authentication Token First**:

```bash
# Option 1: JWT Token (if configured)
curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "yourpassword"}'

# Save the token
export TOKEN="your_access_token_here"

# Option 2: Use Django Admin session (login via browser first)
```

**Test Each Endpoint**:

```bash
# 1. List articles
curl http://localhost:8000/api/v2/help-center/articles/ \
  -H "Authorization: Bearer $TOKEN"

# 2. Search articles
curl -X POST http://localhost:8000/api/v2/help-center/search/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query": "work order", "limit": 10}'

# 3. Get article detail (replace {id} with actual ID from step 1)
curl http://localhost:8000/api/v2/help-center/articles/1/ \
  -H "Authorization: Bearer $TOKEN"

# 4. Vote on article
curl -X POST http://localhost:8000/api/v2/help-center/articles/1/vote/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"is_helpful": true, "comment": "Very helpful!"}'

# 5. Get analytics dashboard
curl http://localhost:8000/api/v2/help-center/analytics/dashboard/ \
  -H "Authorization: Bearer $TOKEN"

# 6. List categories
curl http://localhost:8000/api/v2/help-center/categories/ \
  -H "Authorization: Bearer $TOKEN"
```

**Expected**: All return status 200 with valid JSON responses.

---

## 🧪 TESTING THE SYSTEM

### Run Test Suite (10 minutes)

```bash
# Run all help_center tests
pytest apps/help_center/tests/ \
  --cov=apps/help_center \
  --cov-report=html \
  --cov-report=term-missing \
  -v

# Expected output:
# apps/help_center/tests/test_models.py ............ PASSED
# apps/help_center/tests/test_services.py ........ PASSED
# apps/help_center/tests/test_api.py ......... PASSED
# apps/help_center/tests/test_security.py ..... PASSED
# apps/help_center/tests/test_tasks.py .... PASSED
#
# Coverage: 85% (target: 80%+)
# ✓ All tests passed

# View HTML coverage report
open coverage_reports/help_center/index.html
```

**If Tests Fail**: Review error messages, fix issues, re-run.

---

## 🎨 ADD WIDGETS TO YOUR TEMPLATES

### Add to Base Template

Edit `templates/base.html` (or your main template):

```django
{% load static %}
{% load help_center_tags %}

<!DOCTYPE html>
<html>
<head>
    <!-- Your existing head content -->

    <!-- Help Center CSS -->
    <link rel="stylesheet" href="{% static 'help_center/css/help-styles.css' %}">

    <!-- Driver.js for guided tours -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.min.css">
</head>
<body>
    <!-- Your existing content -->

    <!-- Help Center Widgets (before closing body tag) -->
    <script src="https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.min.js"></script>
    <script src="{% static 'help_center/js/help-button.js' %}"></script>
    <script src="{% static 'help_center/js/tooltips.js' %}"></script>
    <script src="{% static 'help_center/js/guided-tours.js' %}"></script>
    <script src="{% static 'help_center/js/inline-cards.js' %}"></script>
</body>
</html>
```

### Add Contextual Help to Specific Pages

```django
{# In work order creation form #}
<button
    data-help-id="work-order-approve"
    data-help-position="top"
    class="btn btn-primary"
>
    Approve Work Order
</button>

{# Add inline help card #}
<div data-help-card="ppm-scheduling-intro"></div>

{# Start a guided tour #}
<button onclick="HelpTours.start('work-order-creation')">
    Take a Tour
</button>
```

---

## 🔧 TESTING WEBSOCKET CHAT

### Test in Browser Console

```javascript
// Open browser, navigate to your app, open console (F12)

// Connect to WebSocket
const sessionId = crypto.randomUUID();
const ws = new WebSocket(`ws://localhost:8000/ws/help-center/chat/${sessionId}/`);

// Listen for messages
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Received:', data.type, data.content);
};

// Send query
ws.send(JSON.stringify({
    query: "How do I create a work order?",
    current_url: "/work-orders/"
}));

// You should see:
// - Connection message
// - Status: "Searching knowledge base..."
// - Chunks of AI response
// - Citations with article links
```

---

## 📊 MONITOR ANALYTICS

### View Analytics Dashboard

```bash
# Via API
curl http://localhost:8000/api/v2/help-center/analytics/dashboard/ \
  -H "Authorization: Bearer $TOKEN" | jq

# Via Django Admin
# Navigate to: http://localhost:8000/admin/help_center/
# Click "Help search histories" or "Help article interactions"
```

**Metrics Available**:
- Daily active users
- Total article views
- Search count
- Ticket deflection rate
- Top viewed articles
- Zero-result searches (content gaps)

---

## 🎮 TEST GAMIFICATION

### Earn Your First Badge

```bash
# 1. View an article (via API or browser)
# 2. Vote on it (helpful or not helpful)
# 3. Check if badge was awarded

python manage.py shell
>>> from apps.peoples.models import People
>>> user = People.objects.first()

>>> # Check user's badges
>>> from apps.help_center.gamification_models import HelpUserBadge
>>> badges = HelpUserBadge.objects.filter(user=user)
>>> for badge in badges:
...     print(f"{badge.badge.icon} {badge.badge.name} - {badge.badge.points_awarded} points")

>>> # Check user's points
>>> from apps.help_center.gamification_models import HelpUserPoints
>>> points = HelpUserPoints.objects.get(user=user)
>>> print(f"Total points: {points.total_points}")
```

---

## 🎓 COMMON WORKFLOWS

### Workflow 1: User Searches for Help

1. User clicks floating help button (bottom-right)
2. Chat panel opens
3. User types question: "How do I approve a work order?"
4. AI searches knowledge base (hybrid FTS + semantic)
5. AI generates contextual response with citations
6. User clicks citation to read full article
7. User votes "helpful" → earns points

### Workflow 2: Content Team Creates Article

1. Login to Django Admin
2. Navigate to Help Center → Help Articles
3. Click "Add Help Article"
4. Fill in: Title, Summary, Content, Category, Target Roles
5. Status: DRAFT
6. Click "Save and continue editing"
7. Review content
8. Change status to PUBLISHED
9. Click "Save"
10. Article now appears in search results

### Workflow 3: Analytics Review

1. Django Admin → Help Center → Help search histories
2. Filter by "Results count = 0" (zero-result searches)
3. Identify content gaps
4. Create new articles for common zero-result queries
5. Monitor ticket deflection rate in Help ticket correlations

---

## 🆘 TROUBLESHOOTING

### Issue: Migrations Fail

**Error**: `relation "help_center_article" already exists`

**Solution**:
```bash
# Check migration status
python manage.py showmigrations help_center

# If already applied, skip to next step
# If not, check for migration conflicts
python manage.py migrate help_center --fake-initial
```

---

### Issue: pgvector Extension Not Found

**Error**: `extension "vector" does not exist`

**Solution**:
```bash
# Install pgvector
# macOS:
brew install pgvector

# Ubuntu:
sudo apt-get install postgresql-14-pgvector

# Then enable in database
psql -U postgres -d intelliwiz_db -c "CREATE EXTENSION vector;"
```

---

### Issue: WebSocket Connection Fails

**Error**: `WebSocket connection failed`

**Solution**:
1. Check Daphne is running (not runserver for WebSockets)
```bash
daphne -b 0.0.0.0 -p 8000 intelliwiz_config.asgi:application
```

2. Verify routing in `intelliwiz_config/asgi.py`
3. Check ASGI_APPLICATION setting
4. Test with browser dev tools (Network tab → WS filter)

---

### Issue: Static Files Not Loading

**Error**: 404 on `/static/help_center/...`

**Solution**:
```bash
# Collect static files
python manage.py collectstatic --noinput

# Verify
ls -la staticfiles/help_center/
# Should show: css/, js/
```

---

### Issue: Tests Fail with Import Errors

**Error**: `ModuleNotFoundError: No module named 'apps.help_center'`

**Solution**:
```bash
# Ensure app is in INSTALLED_APPS
python manage.py shell
>>> from django.conf import settings
>>> 'apps.help_center' in settings.INSTALLED_APPS
True

# If False, add to intelliwiz_config/settings/base.py
```

---

## ✅ VERIFICATION CHECKLIST

Run this checklist after setup:

```bash
# ✓ pgvector extension enabled
psql -U postgres -d intelliwiz_db -c "SELECT 1 FROM pg_extension WHERE extname = 'vector'"

# ✓ Migrations applied
python manage.py showmigrations help_center | grep "\[X\]"

# ✓ Tables exist
python manage.py dbshell
\dt help_center*
\q

# ✓ Models work
python manage.py shell
>>> from apps.help_center.models import HelpArticle
>>> HelpArticle.objects.count()
>>> exit()

# ✓ Admin accessible
# Open: http://localhost:8000/admin/help_center/

# ✓ API works
curl http://localhost:8000/api/v2/help-center/categories/ -H "Authorization: Bearer $TOKEN"

# ✓ Tests pass
pytest apps/help_center/tests/ -v

# ✓ Static files load
curl http://localhost:8000/static/help_center/css/help-styles.css

# ✓ WebSocket connects
# (Test in browser console as shown above)

# ✓ Verification script passes
python apps/help_center/verify_deployment.py
```

**If All ✓**: System is ready for production deployment!

---

## 🎯 NEXT STEPS AFTER SETUP

### Immediate (Day 1):
1. Create 10-20 help articles covering most common questions
2. Test help button on existing pages
3. Train 2-3 power users
4. Monitor analytics dashboard

### Week 1:
5. Gather user feedback
6. Fix any bugs found
7. Create additional articles based on zero-result searches
8. Monitor ticket deflection rate

### Month 1:
9. Review analytics (adoption, effectiveness)
10. Optimize search relevance
11. Add more guided tours
12. Consider Phase 4 enhancements based on data

---

## 📚 RESOURCES

- **Full Documentation**: `docs/plans/2025-11-03-help-center-system-design.md`
- **Implementation Status**: `apps/help_center/IMPLEMENTATION_STATUS.md`
- **Complete Implementation Report**: `HELP_CENTER_COMPLETE_IMPLEMENTATION.md`
- **API Documentation**: Available at `/api/schema/` (if drf-spectacular configured)

---

## 🎉 SUCCESS!

If you've completed all steps, you now have:
✅ Fully functional help center
✅ AI-powered chat assistant
✅ Contextual help widgets
✅ Gamification system active
✅ Analytics tracking enabled
✅ Production-ready system

**Time to deploy and start reducing those support tickets!** 🚀

---

**Last Updated**: November 3, 2025
**Status**: Production Ready
**Support**: Check troubleshooting section or review comprehensive docs
