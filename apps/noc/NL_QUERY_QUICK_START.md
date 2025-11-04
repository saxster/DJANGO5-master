# NOC Natural Language Query - Quick Start Guide

**5-Minute Setup & Usage Guide**

---

## Prerequisites

```bash
# 1. Install Anthropic SDK
pip install anthropic

# 2. Verify Redis is running
redis-cli ping  # Should return "PONG"

# 3. Set API key
export ANTHROPIC_API_KEY="sk-ant-..."
```

---

## Quick Test

### 1. Python Shell Test

```python
# Start Django shell
python manage.py shell

# Import service
from apps.noc.services import NLQueryService
from apps.peoples.models import People

# Get a test user (replace with actual username)
user = People.objects.filter(isadmin=True).first()

# Test query
result = NLQueryService.process_natural_language_query(
    query_text="Show me critical alerts from the last 24 hours",
    user=user,
    output_format='summary'
)

# Print results
print(result['summary'])
print(f"Found {len(result['data'])} results")
print(f"Cached: {result['cached']}")
```

### 2. API Test (cURL)

```bash
# Get JWT token first
TOKEN=$(curl -X POST http://localhost:8000/api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"yourpassword"}' | jq -r .access)

# Query NOC data
curl -X POST http://localhost:8000/api/v2/noc/query/nl/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Show me critical alerts from the last 24 hours",
    "output_format": "summary"
  }' | jq .
```

### 3. API Test (Python Requests)

```python
import requests

# Authenticate
response = requests.post(
    'http://localhost:8000/api/token/',
    json={'username': 'admin', 'password': 'yourpassword'}
)
token = response.json()['access']

# Query
response = requests.post(
    'http://localhost:8000/api/v2/noc/query/nl/',
    headers={'Authorization': f'Bearer {token}'},
    json={
        'query': 'Show me critical alerts from the last 24 hours',
        'output_format': 'summary'
    }
)

result = response.json()
print(result['summary'])
```

---

## Common Queries

### Alert Queries

```python
# Critical alerts
"Show me critical alerts from the last 24 hours"

# Open alerts
"Find high and critical alerts that are still open"

# SLA breaches
"What SLA breach alerts occurred today?"

# Site-specific
"Show me all alerts for Site ID 123"
```

### Incident Queries

```python
# Open incidents
"Show me open incidents"

# Recent critical
"Find critical incidents from the last week"

# Resolved today
"What incidents were resolved today?"
```

### Trend Analysis

```python
# Alert trends
"Show me alert trends by severity for the last 7 days"

# Most common
"What are the most common alert types this week?"

# Site ranking
"Which sites have the most alerts?"
```

### Metrics

```python
# Recent metrics
"Show me metrics for the last hour"

# Client-specific
"Get metrics for client 456"
```

---

## Output Formats

### Summary (Default)
```python
result = NLQueryService.process_natural_language_query(
    "Show me alerts",
    user=user,
    output_format='summary'  # Brief overview
)
```

### Detailed
```python
result = NLQueryService.process_natural_language_query(
    "Show me alerts",
    user=user,
    output_format='detailed'  # Full information
)
```

### Table
```python
result = NLQueryService.process_natural_language_query(
    "Show me alerts",
    user=user,
    output_format='table'  # Structured data
)
```

### JSON
```python
result = NLQueryService.process_natural_language_query(
    "Show me alerts",
    user=user,
    output_format='json'  # Raw data
)
```

---

## Cache Management

### Check Cache Stats

```python
from apps.noc.services import NLQueryService

stats = NLQueryService.get_cache_stats()
print(f"Hit rate: {stats['hit_rate_percent']}%")
print(f"Total queries: {stats['total_queries']}")
```

### API Cache Stats

```bash
curl -X GET http://localhost:8000/api/v2/noc/query/nl/stats/ \
  -H "Authorization: Bearer $TOKEN" | jq .
```

### Invalidate Cache

```python
from apps.noc.services import NLQueryService

# Invalidate all cached queries for user's tenant
NLQueryService.invalidate_cache_for_user(user)
```

---

## Troubleshooting

### Issue: ImportError: anthropic

```bash
pip install anthropic
```

### Issue: ANTHROPIC_API_KEY not configured

```bash
export ANTHROPIC_API_KEY="sk-ant-..."
# Or add to .env file
```

### Issue: Rate limit exceeded (429)

**Solution:** Wait 60 seconds, then retry.

Current limit: 10 queries per minute per user.

### Issue: Permission denied (403)

**Solution:** Ensure user has `noc:view` capability:

```python
from apps.peoples.services import UserCapabilityService

capabilities = UserCapabilityService.get_effective_permissions(user)
print('noc:view' in capabilities)  # Should be True
```

### Issue: Redis connection error

```bash
# Check Redis is running
redis-cli ping  # Should return "PONG"

# If not running, start Redis
redis-server
```

---

## Example Workflow

### Investigation Scenario

```python
from apps.noc.services import NLQueryService
from apps.peoples.models import People

user = People.objects.get(username='operator1')

# 1. Get overview
result = NLQueryService.process_natural_language_query(
    "Show me critical alerts from today",
    user=user
)
print(result['summary'])
print(result['insights'])

# 2. Drill down to specific site
result = NLQueryService.process_natural_language_query(
    "Show me detailed alerts for Site 123 from today",
    user=user,
    output_format='detailed'
)

# 3. Check trends
result = NLQueryService.process_natural_language_query(
    "What are the most common alert types at Site 123 this week?",
    user=user
)

# 4. Check related incidents
result = NLQueryService.process_natural_language_query(
    "Show me open incidents for Site 123",
    user=user
)
```

---

## Testing

### Run Test Suite

```bash
# All tests
pytest apps/noc/tests/test_nl_query.py -v

# Specific test
pytest apps/noc/tests/test_nl_query.py::QueryParserTestCase::test_parse_query_alerts -v

# With coverage
pytest apps/noc/tests/test_nl_query.py --cov=apps.noc.services --cov-report=html
```

---

## Performance Tips

1. **Use caching** - Identical queries are cached for 5 minutes
2. **Be specific** - More specific queries return faster
3. **Limit results** - Add "top 10" to queries for faster responses
4. **Monitor cache** - Check hit rate with stats endpoint
5. **Batch investigations** - Use trends for patterns, then drill down

---

## API Rate Limits

| Limit | Value |
|-------|-------|
| Queries per minute | 10 |
| Max query length | 1000 characters |
| Max results per query | 1000 records |
| Cache TTL | 5 minutes |

---

## Next Steps

1. **Read full documentation:** `docs/features/NOC_NATURAL_LANGUAGE_QUERIES.md`
2. **Explore examples:** `apps/noc/nl_query_examples.py`
3. **Review architecture:** See component diagrams in main docs
4. **Check code:** Services in `apps/noc/services/`

---

## Support

- **Documentation:** `docs/features/NOC_NATURAL_LANGUAGE_QUERIES.md`
- **Examples:** `apps/noc/nl_query_examples.py`
- **Tests:** `apps/noc/tests/test_nl_query.py`
- **Implementation Summary:** `NOC_ENHANCEMENT_10_IMPLEMENTATION_SUMMARY.md`

---

**Ready to start querying!** 🚀
