# Help Center - Comprehensive Implementation Roadmap

**Status**: Phase 2 in progress (API layer)
**Completed**: Phase 1 (100%) + Serializers (8 serializers, ~400 lines)
**Remaining**: 28 tasks, ~5,835 lines

---

## ✅ WHAT'S BEEN COMPLETED

### Phase 1: Foundation (100%)
- Complete data model (6 models, ~550 lines)
- Database migrations with pgvector + FTS triggers
- Service layer (5 services, ~840 lines)
- Django Admin interfaces (~450 lines)
- Celery background tasks (3 tasks, ~180 lines)
- Configuration & signal handlers

### Phase 2.1: REST API Serializers (100%)
- `serializers.py` created (~400 lines)
- 8 serializers with validation
- XSS prevention in inputs
- Nested relationships optimized

**Total Completed**: ~2,876 lines across 19 files

---

## 🚀 CRITICAL NEXT STEPS (Week 1-2)

The most important tasks to complete the help system are:

1. **REST API Views** (~400 lines) - Backend endpoints
2. **WebSocket Consumer** (~150 lines) - Real-time AI chat
3. **Frontend Widgets** (~985 lines) - User interface
4. **LLM Integration** (~200 lines) - Remove placeholders

**Total Priority 1**: ~1,735 lines to make system usable

---

## 📋 DETAILED TASK BREAKDOWN

### Task 1: REST API Views (START HERE)
**File**: `apps/help_center/views.py`
**Lines**: ~400
**Priority**: CRITICAL
**Time**: 1-2 days

**What to Build**:
```python
# 7 API endpoints using Django REST Framework

1. POST /api/v2/help-center/search/
   - Hybrid search (FTS + pgvector)
   - Returns articles + suggestions

2. GET /api/v2/help-center/articles/{id}/
   - Article detail with view tracking

3. POST /api/v2/help-center/articles/{id}/vote/
   - Vote helpful/not helpful

4. GET /api/v2/help-center/contextual/?url=/path/
   - Page-specific help articles

5. POST /api/v2/help-center/analytics/event/
   - Track user interactions

6. GET /api/v2/help-center/analytics/dashboard/
   - Analytics metrics

7. GET /api/v2/help-center/categories/
   - Category list
```

**Implementation Steps**:
1. Create ViewSets (HelpArticleViewSet, HelpCategoryViewSet, HelpAnalyticsViewSet)
2. Add permission checks (IsAuthenticated)
3. Optimize queries (select_related, prefetch_related)
4. Add caching where appropriate
5. Test with Postman/curl

---

### Task 2: Update URL Configuration
**File**: `apps/help_center/urls.py`
**Lines**: ~50
**Priority**: CRITICAL
**Time**: 30 minutes

**Code**:
```python
from rest_framework.routers import DefaultRouter
from apps.help_center import views

router = DefaultRouter()
router.register(r'articles', views.HelpArticleViewSet, basename='help-article')
router.register(r'categories', views.HelpCategoryViewSet, basename='help-category')
router.register(r'analytics', views.HelpAnalyticsViewSet, basename='help-analytics')

urlpatterns = [
    path('api/v2/help-center/', include(router.urls)),
]
```

**Integration**: Add to main `urls_optimized.py`

---

### Task 3: WebSocket Consumer
**File**: `apps/help_center/consumers.py`
**Lines**: ~150
**Priority**: HIGH
**Time**: 1 day

**Purpose**: Real-time AI chat streaming

**Key Components**:
- AsyncWebsocketConsumer for async handling
- Stream AIAssistantService responses
- Session management
- Error handling with graceful degradation

**Routing**: Add to `intelliwiz_config/routing.py`:
```python
websocket_urlpatterns += [
    path('ws/help-center/chat/<uuid:session_id>/', HelpChatConsumer.as_asgi()),
]
```

---

### Task 4: Floating Help Button Widget
**File**: `static/help_center/js/help-button.js`
**Lines**: ~245
**Priority**: HIGH
**Time**: 1 day

**Features**:
- Fixed position (bottom-right)
- Opens chat panel on click
- WebSocket connection to AI chat
- Badge for notifications
- Mobile-responsive

**Security Note**: Use textContent instead of innerHTML for user-generated content:
```javascript
// SECURE - Use textContent for plain text
element.textContent = userInput;

// SECURE - Use createElement for structure
const icon = document.createElement('span');
icon.className = 'help-icon';
icon.textContent = '?';

// If HTML is needed, use DOMPurify
const sanitized = DOMPurify.sanitize(htmlContent);
element.innerHTML = sanitized;
```

---

### Task 5: Contextual Tooltips
**File**: `static/help_center/js/tooltips.js`
**Lines**: ~185
**Priority**: MEDIUM
**Time**: 1 day

**Usage**:
```html
<button data-help-id="work-order-approve" data-help-position="top">
    Approve Work Order
</button>
```

**Features**:
- Data attribute-based
- Fetch help content via API
- Position aware (top/bottom/left/right)
- Keyboard accessible

---

### Task 6: Guided Tours (Driver.js)
**File**: `static/help_center/js/guided-tours.js`
**Lines**: ~215
**Priority**: MEDIUM
**Time**: 1 day

**Installation**:
```bash
npm install driver.js
# OR use CDN
<script src="https://cdn.jsdelivr.net/npm/driver.js@1.3.1/dist/driver.min.js"></script>
```

**Usage Example**:
```javascript
import Driver from 'driver.js';

const driver = new Driver({
    className: 'help-center-tour',
    allowClose: true,
    onHighlightStarted: (element) => {
        // Track tour progress via analytics API
    }
});

driver.defineSteps([
    {
        element: '#create-work-order-btn',
        popover: {
            title: 'Create Work Order',
            description: 'Click here to start creating a new work order',
            position: 'bottom'
        }
    }
]);
```

---

### Task 7: Mobile-Responsive CSS
**File**: `static/help_center/css/help-styles.css`
**Lines**: ~285
**Priority**: HIGH
**Time**: 1 day

**Requirements**:
- WCAG 2.2 Level AA compliant
- Mobile-first design
- Dark mode support
- Touch-friendly (48x48dp targets)
- Performance optimized

**Key Styles**:
```css
/* Help Button - Fixed Position */
.help-button {
    position: fixed;
    bottom: 20px;
    right: 20px;
    width: 60px;
    height: 60px;
    border-radius: 50%;
    background: var(--primary-color, #1976d2);
    color: white;
    border: none;
    box-shadow: 0 4px 8px rgba(0,0,0,0.3);
    cursor: pointer;
    z-index: 9999;
}

/* Accessibility - Focus Visible */
.help-button:focus-visible {
    outline: 3px solid #ffd700;
    outline-offset: 2px;
}

/* Mobile Responsive */
@media (max-width: 768px) {
    .help-chat-panel {
        width: 100vw;
        height: 100vh;
        border-radius: 0;
    }
}

/* Dark Mode */
@media (prefers-color-scheme: dark) {
    .help-chat-panel {
        background: #1e1e1e;
        color: #ffffff;
    }
}

/* Reduced Motion */
@media (prefers-reduced-motion: reduce) {
    .help-button {
        transition: none;
    }
}
```

---

### Task 8: Complete LLM/Embeddings Integration
**Files to Modify**:
- `services/search_service.py`
- `services/ai_assistant_service.py`
- `tasks.py`

**Lines**: ~200 (replacements)
**Priority**: HIGH
**Time**: 1 day

**Changes**:
1. Import actual services:
```python
from apps.ai.services.production_llm_service import ProductionLLMService
from apps.ai.services.production_embeddings_service import ProductionEmbeddingsService
from apps.ai.services.enhanced_pgvector_backend import EnhancedPgVectorBackend
```

2. Replace placeholders in `SearchService._semantic_search()`
3. Replace placeholders in `AIAssistantService.generate_response_stream()`
4. Replace placeholders in `tasks.generate_article_embedding()`
5. Configure budget controls ($5/day limit)
6. Add response caching

---

## 🧪 TESTING PHASE (Week 3-4)

### Task 9: Model Tests
**File**: `tests/test_models.py`
**Lines**: ~200
**Coverage**: 90%

**Test Cases**:
- Model creation with all field types
- Property methods (helpful_ratio, is_stale)
- Unique constraints (tenant + slug)
- Foreign key cascades
- JSON field operations
- Edge cases (division by zero, null handling)

---

### Task 10: Service Tests
**File**: `tests/test_services.py`
**Lines**: ~300
**Coverage**: 85%

**Services to Test**:
- KnowledgeService (CRUD operations)
- SearchService (hybrid search)
- AIAssistantService (RAG pipeline)
- AnalyticsService (metrics calculation)
- TicketIntegrationService (correlation)

---

### Task 11: API Tests
**File**: `tests/test_api.py`
**Lines**: ~250
**Coverage**: 80%

**Endpoints to Test**:
- Authentication/authorization
- Request validation
- Response serialization
- Error handling (404, 400, 500)
- Rate limiting
- Caching

---

### Task 12: Security Tests
**File**: `tests/test_security.py`
**Lines**: ~150

**Test Cases**:
- Tenant isolation (cross-tenant access blocked)
- XSS prevention (input sanitization)
- SQL injection prevention (ORM usage)
- CSRF protection
- Permission checks
- Sensitive data leakage

---

### Task 13: Task Tests
**File**: `tests/test_tasks.py`
**Lines**: ~100

**Test Cases**:
- Celery task execution
- Retry logic
- Timeout handling
- Error handling
- Idempotency

---

### Task 14: User Templates
**Files**:
- `templates/help_center/home.html` (~100 lines)
- `templates/help_center/article_detail.html` (~150 lines)
- `templates/help_center/search_results.html` (~100 lines)
- `templates/help_center/category_list.html` (~50 lines)

**Total**: ~400 lines

**Features**:
- Responsive layout
- Accessible (WCAG 2.2)
- SEO optimized
- Fast loading

---

### Task 15: Template Tags
**File**: `templatetags/help_center_tags.py`
**Lines**: ~200

**Tags to Implement**:
```python
{% load help_center_tags %}

{% help_center_widget %}  # Load help button
{% help_article_link 123 %}  # Article URL
{% help_search_box %}  # Search interface
{% help_category_nav %}  # Category navigation
```

---

### Task 16: Management Commands
**Files**:
- `management/commands/sync_documentation.py` (~100 lines)
- `management/commands/rebuild_help_indexes.py` (~100 lines)

**Usage**:
```bash
# Bulk import from markdown files
python manage.py sync_documentation --dir=docs/

# Rebuild search indexes and embeddings
python manage.py rebuild_help_indexes
```

---

## 🌟 ENHANCEMENT PHASE (Month 2+)

### Task 17: Gamification System
**Lines**: ~250
**Priority**: MEDIUM

**New Models**:
- HelpBadge
- HelpUserBadge
- HelpUserPoints

**Features**:
- Badge criteria engine
- Automatic badge awarding
- Leaderboards
- Point tracking

---

### Task 18: Conversation Memory
**Lines**: ~200
**Priority**: MEDIUM

**New Model**:
- HelpConversationMemory

**Features**:
- Short-term memory (session)
- Long-term memory (user preferences)
- Context carryover
- Expiration management

---

### Task 19: Multi-Agent RAG
**Lines**: ~400
**Priority**: LOW

**Agents**:
1. Retriever - Find articles
2. Reranker - Cross-encoder scoring
3. Summarizer - Extract key points
4. Generator - Produce answer
5. Validator - Check hallucinations

**Expected Impact**: 87% accuracy (vs 63% baseline)

---

### Task 20: Adaptive Document Chunking
**Lines**: ~250
**Priority**: LOW

**Features**:
- Semantic boundary detection
- Recursive splitting
- Metadata preservation
- Overlap strategy

**Expected Impact**: 23% improvement in retrieval relevance

---

### Task 21: Predictive Help
**Lines**: ~300
**Priority**: MEDIUM

**Features**:
- Behavior tracking (mouse, time, navigation)
- ML model for struggle detection
- Proactive suggestions
- A/B testing framework

**Expected Impact**: 35% ticket reduction

---

### Task 22: Advanced Analytics
**Lines**: ~400
**Priority**: MEDIUM

**Features**:
- Funnel analysis
- Cohort analysis
- Time-series trends
- Heatmaps
- Sentiment analysis

---

### Task 23: Auto Content Suggestions
**Lines**: ~350
**Priority**: MEDIUM

**Features**:
- NLP analysis of tickets (spaCy/BERT)
- Topic clustering (DBSCAN)
- LLM-assisted draft generation
- Content team workflow

---

### Task 24: Multi-Language Support
**Lines**: ~500
**Priority**: LOW

**Languages**: EN, HI, TE, TA, KN, MR, GU, BN

**Features**:
- LLM-assisted translation
- Language-specific search vectors
- UI language switching
- Automatic language detection

---

### Task 25: PWA Offline Mode
**Lines**: ~300
**Priority**: LOW

**Features**:
- Service workers
- IndexedDB caching
- Offline search
- Sync queue
- "Add to Home Screen"

**Expected Impact**: 100% help availability

---

### Task 26: Voice-Activated Help
**Lines**: ~400
**Priority**: LOW

**Features**:
- Voice input (Web Speech API)
- Voice output (Text-to-Speech)
- Wake word detection
- Integration with voice_recognition app

**Expected Impact**: 10x engagement for field workers

---

## 📊 PROGRESS TRACKING

### Overall Progress
- **Completed**: 2/30 tasks (7%)
- **In Progress**: REST API Views
- **Remaining**: 28 tasks
- **Lines Written**: 2,876 / 9,111 (32%)

### Phase Progress
- **Phase 1** (Foundation): ✅ 100% Complete
- **Phase 2** (User-Facing): 🟡 12% Complete (1/8 tasks)
- **Phase 3** (Testing): ⚪ 0% Complete (0/9 tasks)
- **Phase 4** (Enhancements): ⚪ 0% Complete (0/10 tasks)

---

## 🎯 QUICK START FOR DEVELOPERS

### For Immediate Implementation:
1. **Create views.py** - Copy API view templates from design doc
2. **Update urls.py** - Register ViewSets with router
3. **Test endpoints** - Use Postman collection (create one)
4. **Create consumers.py** - WebSocket for AI chat
5. **Add frontend widgets** - Start with help-button.js

### Commands to Run:
```bash
# Start development server
python manage.py runserver

# Run tests
pytest apps/help_center/tests/ --cov --cov-report=html

# Create test data
python manage.py shell
>>> from apps.help_center.models import *
>>> # Create categories, articles

# Check migrations
python manage.py showmigrations help_center
```

---

## 📚 KEY DOCUMENTS

1. **Design Document**: `docs/plans/2025-11-03-help-center-system-design.md`
   - Complete system architecture
   - Database schema with examples
   - Service layer design

2. **Implementation Status**: `apps/help_center/IMPLEMENTATION_STATUS.md`
   - What's complete
   - What's remaining
   - Setup instructions

3. **Gap Analysis**: See comprehensive analysis in chat history
   - What's pending
   - What can be better
   - 14 enhancement recommendations

4. **CLAUDE.md**: Project standards
   - Architecture limits (150 lines per model)
   - Security rules (no CSRF exempt, specific exceptions)
   - Code quality standards

---

## 🆘 TROUBLESHOOTING

### Common Issues:

**Q: API returns 404**
A: Check URL routing in `urls.py` and main `urls_optimized.py`

**Q: WebSocket won't connect**
A: Verify Daphne is running and ASGI routing is configured

**Q: Semantic search returns nothing**
A: Check embeddings exist: `HelpArticle.objects.exclude(embedding__isnull=True).count()`

**Q: Tests fail with permission errors**
A: Ensure test fixtures include tenant + user with proper groups

**Q: Frontend widgets not loading**
A: Check static files are collected: `python manage.py collectstatic`

---

## ✅ SUCCESS CRITERIA

### Phase 2 Complete When:
- ✅ All 7 REST API endpoints return 200 OK
- ✅ WebSocket chat streams responses in <3s
- ✅ Help button visible on all pages
- ✅ Semantic search returns relevant results
- ✅ AI assistant generates responses

### Phase 3 Complete When:
- ✅ Test coverage ≥80%
- ✅ All security tests pass
- ✅ WCAG 2.2 Level AA validated
- ✅ Templates render on mobile/desktop
- ✅ Management commands work

### Phase 4 Complete When:
- ✅ All 10 enhancements implemented
- ✅ Multi-agent RAG ≥85% accuracy
- ✅ Multi-language works for all 8 languages
- ✅ PWA installs on mobile
- ✅ Voice input/output functional

---

## 📅 TIMELINE ESTIMATE

| Phase | Tasks | Lines | Weeks | Developer |
|-------|-------|-------|-------|-----------|
| Phase 2 | 8 | ~1,735 | 2 | 1 senior |
| Phase 3 | 9 | ~1,600 | 2 | 1 senior + 1 QA |
| Phase 4 | 10 | ~3,100 | 4-6 | 1 senior |
| **Total** | **27** | **~6,435** | **8-10** | **1-2 people** |

---

## 💰 ROI PROJECTION

### With Phase 2-3 (Production Ready):
- Investment: $120k ($40k Phase 1 + $80k Phase 2-3)
- Savings: $7.5k/month
- Adoption: 40-50%
- Payback: 16 months
- 3-Year ROI: $150k net

### With All Phases (World-Class):
- Investment: $200k ($120k + $80k Phase 4)
- Savings: $12k/month
- Adoption: 60-80%
- Payback: 17 months
- 3-Year ROI: $232k net

---

**Status**: Phase 2 in progress
**Next Task**: Create views.py with 7 API endpoints
**Last Updated**: November 3, 2025
**Document Version**: 1.0
