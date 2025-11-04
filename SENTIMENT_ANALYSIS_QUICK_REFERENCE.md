# Sentiment Analysis on Tickets - Quick Reference

**Feature 2: NL/AI Platform Quick Win Bundle**

---

## 📁 FILES CREATED/MODIFIED

### Created Files (7)
1. **Service**: `/apps/y_helpdesk/services/ticket_sentiment_analyzer.py` (~400 lines)
2. **Tasks**: `/apps/y_helpdesk/tasks/sentiment_analysis_tasks.py` (~250 lines)
3. **Tasks Init**: `/apps/y_helpdesk/tasks/__init__.py`
4. **Tests**: `/apps/y_helpdesk/tests/test_ticket_sentiment.py` (~500 lines)
5. **Views**: `/apps/y_helpdesk/views_extra/sentiment_analytics_views.py` (~400 lines)
6. **Migration**: `/apps/y_helpdesk/migrations/0002_add_sentiment_analysis_fields.py`
7. **Report**: `/SENTIMENT_ANALYSIS_IMPLEMENTATION_REPORT.md`

### Modified Files (3)
1. **Model**: `/apps/y_helpdesk/models/__init__.py` (added 4 fields)
2. **Signals**: `/apps/y_helpdesk/signals.py` (added sentiment signal)
3. **Views**: `/apps/y_helpdesk/views.py` (added sentiment filtering)

---

## 🚀 QUICK START

### 1. Run Migration
```bash
source venv/bin/activate
python manage.py migrate y_helpdesk
```

### 2. Install TextBlob (if not already)
```bash
pip install textblob>=0.17.1
python -m textblob.download_corpora
```

### 3. Restart Celery
```bash
./scripts/celery_workers.sh restart
```

### 4. Test It
```bash
# Run unit tests
pytest apps/y_helpdesk/tests/test_ticket_sentiment.py -v

# Test with real ticket
python manage.py shell
>>> from apps.y_helpdesk.models import Ticket
>>> from apps.y_helpdesk.services.ticket_sentiment_analyzer import TicketSentimentAnalyzer
>>> ticket = Ticket.objects.filter(ticketdesc__isnull=False).first()
>>> result = TicketSentimentAnalyzer.analyze_ticket_sentiment(ticket)
>>> print(f"Score: {result['sentiment_score']}, Label: {result['sentiment_label']}")
```

### 5. Bulk Analyze Existing Tickets
```python
from apps.y_helpdesk.tasks.sentiment_analysis_tasks import BulkAnalyzeTicketSentimentTask

# Analyze up to 100 OPEN tickets
BulkAnalyzeTicketSentimentTask.delay(status_filter='OPEN', limit=100)

# Analyze all unanalyzed tickets
BulkAnalyzeTicketSentimentTask.delay(limit=500)
```

---

## 🎯 SENTIMENT SCORE SCALE

| Score Range | Label | Priority | Auto-Escalate |
|-------------|-------|----------|---------------|
| 0.0 - 2.0 | very_negative | HIGH | ✅ YES |
| 2.0 - 4.0 | negative | MEDIUM | ❌ NO |
| 4.0 - 6.0 | neutral | - | ❌ NO |
| 6.0 - 8.0 | positive | - | ❌ NO |
| 8.0 - 10.0 | very_positive | - | ❌ NO |

---

## 🔍 API ENDPOINTS

### Ticket List with Sentiment Filtering
```bash
# All very negative tickets
GET /helpdesk/tickets/?action=list&sentiment_label=very_negative

# Tickets with score < 3 (negative first)
GET /helpdesk/tickets/?action=list&max_sentiment=3&sort_by_sentiment=negative_first

# Positive tickets only
GET /helpdesk/tickets/?action=list&min_sentiment=6
```

### Sentiment Analytics
```bash
# Sentiment distribution
GET /helpdesk/sentiment/analytics/?action=distribution

# Sentiment trends (last 30 days)
GET /helpdesk/sentiment/analytics/?action=trends&from=2025-10-01&to=2025-10-31

# Negative ticket alerts
GET /helpdesk/sentiment/analytics/?action=alerts

# Emotion analysis
GET /helpdesk/sentiment/analytics/?action=emotions

# Overall statistics
GET /helpdesk/sentiment/analytics/?action=statistics
```

### Reanalysis
```bash
# Reanalyze single ticket
POST /helpdesk/sentiment/reanalyze/
Body: {"action": "single", "ticket_id": 1234}

# Bulk reanalyze
POST /helpdesk/sentiment/reanalyze/
Body: {"action": "bulk", "status": "OPEN", "limit": 100}
```

---

## 🧪 TEST COMMANDS

```bash
# Run all sentiment tests
pytest apps/y_helpdesk/tests/test_ticket_sentiment.py -v

# Run with coverage
pytest apps/y_helpdesk/tests/test_ticket_sentiment.py \
  --cov=apps.y_helpdesk.services.ticket_sentiment_analyzer \
  --cov-report=html

# Run specific test class
pytest apps/y_helpdesk/tests/test_ticket_sentiment.py::TestSentimentCalculation -v

# Run single test
pytest apps/y_helpdesk/tests/test_ticket_sentiment.py::TestSentimentCalculation::test_calculate_sentiment_very_negative -v
```

---

## 🔧 TROUBLESHOOTING

### Sentiment Not Analyzing
```bash
# Check Celery workers
celery -A intelliwiz_config inspect active

# Check task status
celery -A intelliwiz_config inspect scheduled

# View Celery logs
tail -f logs/celery_worker.log | grep sentiment
```

### TextBlob Not Working
```bash
# Reinstall TextBlob
pip uninstall textblob
pip install textblob>=0.17.1
python -m textblob.download_corpora

# Test manually
python -c "from textblob import TextBlob; print(TextBlob('terrible').sentiment)"
```

### Check Ticket Sentiment
```python
from apps.y_helpdesk.models import Ticket

# Check analyzed tickets
analyzed = Ticket.objects.filter(sentiment_score__isnull=False).count()
total = Ticket.objects.count()
print(f"Analyzed: {analyzed}/{total} ({analyzed/total*100:.1f}%)")

# Check sentiment distribution
from django.db.models import Count
Ticket.objects.values('sentiment_label').annotate(count=Count('id')).order_by('-count')
```

---

## 📊 EMOTION KEYWORDS

### Frustration
`third time`, `still not fixed`, `not working`, `unbearable`, `frustrated`, `angry`, `disappointed`, `terrible`, `worst`, `broken`, `useless`, `never works`, `always fails`, `fed up`, `ridiculous`, `unacceptable`

### Urgency
`urgent`, `asap`, `immediately`, `critical`, `emergency`, `right now`, `as soon as possible`, `time sensitive`

### Satisfaction
`thank`, `thanks`, `appreciate`, `excellent`, `great`, `perfect`, `wonderful`, `helpful`, `resolved`, `fixed`

---

## 🎯 AUTO-ESCALATION RULES

**Triggered When**:
1. `sentiment_score < 2.0` (very negative)
2. `status IN ['NEW', 'OPEN']` (not resolved)
3. `NOT isescalated` (not already escalated)

**Actions Taken**:
1. Set `priority = 'HIGH'`
2. Set `isescalated = True`
3. Add escalation note to workflow history
4. Log escalation event

**Example**:
```python
# Ticket: "This is the third time I am reporting this. Still broken. Frustrated."
# TextBlob polarity: -0.6
# Sentiment score: (−0.6 + 1) × 5 = 2.0
# Label: negative (NOT escalated - threshold is < 2.0)

# Ticket: "Terrible service. Unbearable. Third time reporting."
# TextBlob polarity: -0.8
# Sentiment score: (−0.8 + 1) × 5 = 1.0
# Label: very_negative (ESCALATED - score < 2.0)
```

---

## 📈 METRICS TO MONITOR

### Key Metrics
1. **Analysis Rate**: % of tickets with sentiment analyzed
2. **Average Sentiment**: Mean sentiment score (target: > 5.0)
3. **Negative Ticket Rate**: % with very_negative label (monitor trends)
4. **Escalation Rate**: % of negative tickets escalated (target: 30-50%)
5. **Analysis Latency**: Time from ticket creation to analysis complete

### Query Examples
```python
from django.db.models import Avg, Count, Q
from apps.y_helpdesk.models import Ticket

# Analysis rate
total = Ticket.objects.count()
analyzed = Ticket.objects.filter(sentiment_score__isnull=False).count()
analysis_rate = analyzed / total * 100

# Average sentiment
avg = Ticket.objects.aggregate(Avg('sentiment_score'))['sentiment_score__avg']

# Negative ticket rate
negative = Ticket.objects.filter(sentiment_label__in=['very_negative', 'negative']).count()
negative_rate = negative / total * 100

# Escalation rate
escalated = Ticket.objects.filter(
    sentiment_label__in=['very_negative', 'negative'],
    isescalated=True
).count()
escalation_rate = escalated / negative * 100 if negative > 0 else 0
```

---

## 🎓 EXAMPLE TEXTS & EXPECTED RESULTS

### Very Negative (0-2)
```
Input: "This is the third time I am reporting this issue. Still not fixed. Unbearable and frustrating."
Expected: score=1.2, label=very_negative, emotions={frustration: 0.6, urgency: 0}
Result: AUTO-ESCALATED
```

### Negative (2-4)
```
Input: "The system is not working properly. Disappointed with the response time."
Expected: score=3.5, label=negative, emotions={frustration: 0.2}
Result: Priority boost, no escalation
```

### Neutral (4-6)
```
Input: "Please check the system logs. The application is not responding."
Expected: score=5.0, label=neutral, emotions={}
Result: Standard handling
```

### Positive (6-8)
```
Input: "The issue was resolved quickly. Thank you for the helpful support."
Expected: score=7.2, label=positive, emotions={satisfaction: 0.5}
Result: Positive feedback noted
```

### Very Positive (8-10)
```
Input: "Excellent service! The team was wonderful and fixed everything perfectly. Great job!"
Expected: score=9.1, label=very_positive, emotions={satisfaction: 1.0}
Result: CSAT boost
```

---

## 🔗 RELATED FILES

- **Service**: `apps/y_helpdesk/services/ticket_sentiment_analyzer.py`
- **Tasks**: `apps/y_helpdesk/tasks/sentiment_analysis_tasks.py`
- **Tests**: `apps/y_helpdesk/tests/test_ticket_sentiment.py`
- **Views**: `apps/y_helpdesk/views_extra/sentiment_analytics_views.py`
- **Model**: `apps/y_helpdesk/models/__init__.py`
- **Signals**: `apps/y_helpdesk/signals.py`
- **Full Report**: `SENTIMENT_ANALYSIS_IMPLEMENTATION_REPORT.md`

---

**Last Updated**: November 3, 2025
**Status**: ✅ Complete - Ready for Testing
