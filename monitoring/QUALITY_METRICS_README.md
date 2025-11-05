# Quality Metrics Dashboard - Phase 7

Automated quality metrics dashboard and weekly reporting system for enterprise code quality monitoring.

## Overview

This system provides comprehensive code quality tracking across multiple dimensions:

- **Code Quality Score** (0-100) - Validation of coding standards
- **Test Coverage** (0-100%) - Automated test coverage percentage
- **Code Complexity** - Average cyclomatic complexity metrics
- **Security Issues** - Scan results and vulnerability counts
- **File Compliance** - Architecture limits enforcement
- **Trend Analysis** - Week-over-week comparisons

## Components

### 1. Weekly Report Generator (`scripts/generate_quality_report.py`)

Comprehensive Python script that aggregates all quality metrics and generates actionable reports.

**Usage:**
```bash
# Generate JSON report
python scripts/generate_quality_report.py --format json

# Generate Markdown report
python scripts/generate_quality_report.py --format markdown

# Generate both and store in database
python scripts/generate_quality_report.py --format both --store-db

# Specify output file
python scripts/generate_quality_report.py --output quality_report_2025_11_05.json
```

**Features:**
- Aggregates multiple validation tools
- Calculates overall grade (A-F)
- Generates trend analysis
- Creates actionable recommendations
- Stores metrics in database for historical tracking

**Output:**
- JSON format for programmatic processing
- Markdown format for human review
- Database storage for trend analysis

### 2. Django Quality Metric Model (`apps/core/models/quality_metrics.py`)

Database model for tracking quality metrics over time.

**Fields:**
```python
timestamp              # When metric was recorded
code_quality_score    # 0-100 score
test_coverage         # 0-100 percentage
complexity_score      # Average cyclomatic complexity
security_issues       # Total count
security_critical     # Critical severity count
security_high         # High severity count
file_violations       # File size violations count
overall_grade         # A-F letter grade
overall_score         # 0-100 weighted score
report_json           # Full report data
is_weekly             # Whether this is a weekly snapshot
```

**Usage:**
```python
from apps.core.models import QualityMetric

# Get latest metrics
latest = QualityMetric.get_latest()

# Get weekly averages for trend analysis
trends = QualityMetric.get_weekly_average(weeks=4)

# Check if metrics are passing
if latest.is_passing:
    print("All metrics meet quality standards")
```

### 3. Prometheus Metrics Exporter (`monitoring/prometheus/code_quality_metrics.py`)

Real-time metrics export in Prometheus format for integration with monitoring systems.

**Metrics Exposed:**
- `code_quality_score` (Gauge 0-100)
- `test_coverage_percent` (Gauge 0-100)
- `cyclomatic_complexity_average` (Gauge)
- `security_issues_total` (Gauge)
- `security_issues_critical` (Gauge)
- `security_issues_high` (Gauge)
- `file_size_violations_total` (Gauge)
- `quality_grade_numeric` (Gauge)
- `code_quality_metrics_timestamp` (Gauge)
- `code_quality_collections_total` (Counter)
- `code_quality_collection_errors_total` (Counter)

**Usage:**
```bash
# Standalone execution (for testing)
python monitoring/prometheus/code_quality_metrics.py

# In Django view
from monitoring.prometheus.code_quality_metrics import get_metrics_handler
from django.http import HttpResponse

def prometheus_metrics(request):
    handler = get_metrics_handler()
    return handler(request)
```

**Prometheus Configuration:**
```yaml
scrape_configs:
  - job_name: 'code-quality'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/code-quality/'
    scrape_interval: 30s
    scrape_timeout: 10s
```

### 4. Grafana Dashboard (`monitoring/grafana/code_quality_dashboard.json`)

Real-time visualization dashboard with 11 panels:

1. **Code Quality Score** - Gauge showing current score
2. **Test Coverage** - Gauge showing coverage percentage
3. **Quality Metrics Trend** - Time series of quality and coverage
4. **Overall Grade** - Letter grade gauge
5. **Security - Critical Issues** - Count of critical vulnerabilities
6. **Security - High Issues** - Count of high severity issues
7. **File Size Violations** - Count of compliance violations
8. **Code Complexity Trend** - Time series of complexity metrics
9. **Security Issues Trend** - Stacked time series of issue types
10. **File Size Compliance Trend** - Time series of violations

**Import Instructions:**

1. Open Grafana UI
2. Navigate to Dashboards > Import
3. Upload `monitoring/grafana/code_quality_dashboard.json`
4. Select Prometheus datasource
5. Dashboard will display real-time metrics

**Features:**
- 30-second refresh interval
- 30-day historical view
- Color-coded thresholds
- Detailed tooltips
- Legend with statistics

## Quality Standards & Thresholds

Default quality thresholds (adjustable in config):

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| Code Quality Score | 90+ | 70-89 | <70 |
| Test Coverage | 85%+ | 75-84% | <75% |
| Cyclomatic Complexity | ≤6.5 | 6.5-8.0 | >8.0 |
| Security Critical Issues | 0 | 1+ | 3+ |
| Security High Issues | ≤2 | 3-5 | 6+ |
| File Size Violations | 0 | 1+ | 5+ |

**Overall Grade Calculation:**

- **A (90-100)** - Excellent - All metrics above thresholds
- **B (80-89)** - Good - Minor issues, addressing
- **C (70-79)** - Acceptable - Some improvements needed
- **D (60-69)** - Poor - Significant quality degradation
- **F (<60)** - Failing - Critical issues present

**Grade Formula:**
```
Score = (CodeQuality × 0.35) + (Coverage × 0.30) +
        (Complexity × 0.20) + (Security × 0.15)
```

## Integration Points

### 1. Code Quality Validation
- Uses existing `scripts/validate_code_quality.py`
- Checks:
  - Wildcard imports
  - Generic exception handling
  - Network call timeouts
  - Code injection vulnerabilities
  - Blocking I/O patterns
  - sys.path manipulation
  - Debug print statements

### 2. File Size Compliance
- Uses existing `scripts/check_file_sizes.py`
- Enforces architecture limits:
  - Settings: <200 lines
  - Models: <150 lines
  - Views: <30 lines
  - Forms: <100 lines
  - Utilities: <50 lines per function

### 3. Test Coverage
- Parses pytest coverage reports
- JSON format from coverage.py
- Integrates with CI/CD pipeline

### 4. Security Scanning
- Optional Bandit integration
- Detects:
  - SQL injection vulnerabilities
  - Hardcoded secrets
  - Insecure cryptography
  - Path traversal issues

## Setup Instructions

### 1. Create Database Migration

```bash
# Migration is auto-created
python manage.py migrate core 0019_add_quality_metrics_model
```

### 2. Configure Prometheus (Optional)

```yaml
# Add to prometheus.yml
scrape_configs:
  - job_name: 'code-quality'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/code-quality/'
    scrape_interval: 30s
```

### 3. Add Django URL Route

```python
# intelliwiz_config/urls.py
from monitoring.prometheus.code_quality_metrics import get_metrics_handler

urlpatterns = [
    # ... other patterns
    path('metrics/code-quality/', get_metrics_handler(), name='prometheus-code-quality'),
]
```

### 4. Schedule Weekly Reports

```python
# intelliwiz_config/celery.py or management command
from scripts.generate_quality_report import QualityReportGenerator

@periodic_task(run_every=crontab(hour=0, minute=0, day_of_week=1))
def weekly_quality_report():
    """Generate weekly quality report every Monday at midnight"""
    generator = QualityReportGenerator(store_db=True)
    report = generator.generate_report()
    generator.save_report_markdown(report, f"quality_reports/{datetime.now():%Y%m%d}.md")
```

## Usage Examples

### Generate Weekly Report

```bash
# JSON format
python scripts/generate_quality_report.py --format json --store-db

# Markdown format
python scripts/generate_quality_report.py --format markdown

# Both formats
python scripts/generate_quality_report.py --format both --store-db
```

### Query Historical Metrics

```python
from apps.core.models import QualityMetric
from datetime import timedelta

# Get latest metrics
latest = QualityMetric.objects.latest('timestamp')
print(f"Current grade: {latest.overall_grade}")
print(f"Coverage: {latest.test_coverage}%")

# Get weekly trend (last 4 weeks)
trend = QualityMetric.get_weekly_average(weeks=4)
print(f"Average coverage: {trend['avg_coverage']:.1f}%")

# Get metrics for specific date range
from django.utils import timezone
week_ago = timezone.now() - timedelta(days=7)
recent = QualityMetric.objects.filter(
    timestamp__gte=week_ago,
    is_weekly=True
).order_by('-timestamp')
```

### Prometheus Metrics

```bash
# View exported metrics
curl http://localhost:8000/metrics/code-quality/ | grep code_quality

# Example output:
# code_quality_score 92.5
# test_coverage_percent 87.3
# cyclomatic_complexity_average 5.8
# security_issues_total 2
# quality_grade_numeric 4
```

## Troubleshooting

### Metrics Not Updating

1. Check that all quality validation scripts are working:
```bash
python scripts/validate_code_quality.py --verbose
python scripts/check_file_sizes.py --verbose
```

2. Verify Prometheus metrics endpoint:
```bash
curl http://localhost:8000/metrics/code-quality/
```

3. Check Prometheus scrape logs in `/var/log/prometheus/prometheus.log`

### Database Storage Issues

1. Verify migration applied:
```bash
python manage.py showmigrations core | grep 0019
```

2. Check model exists:
```bash
python manage.py shell
from apps.core.models import QualityMetric
QualityMetric.objects.count()
```

### Grafana Dashboard Issues

1. Verify Prometheus datasource is configured in Grafana
2. Check that metrics are being scraped:
   - Go to Prometheus > Targets
   - Verify "code-quality" job status
3. Re-import dashboard JSON if metrics not appearing

## Performance Considerations

- Report generation: ~30-60 seconds (runs all checks)
- Prometheus collection: ~5-10 seconds (lightweight)
- Database storage: ~100KB per metric record
- Grafana queries: <1 second (30-day retention)

**Optimization Tips:**
- Store DB only for weekly snapshots (not daily)
- Limit Prometheus retention to 30 days
- Archive old reports to cloud storage
- Use Grafana datasource caching

## Related Files

- **Code Quality Script**: `scripts/validate_code_quality.py`
- **File Size Script**: `scripts/check_file_sizes.py`
- **Test Report Script**: `scripts/generate_test_report.py`
- **Quality Standards**: `.claude/rules.md`
- **Architecture Limits**: `CLAUDE.md` (Architecture At-a-Glance section)
- **Database Model**: `apps/core/models/quality_metrics.py`
- **Metrics Exporter**: `monitoring/prometheus/code_quality_metrics.py`
- **Dashboard**: `monitoring/grafana/code_quality_dashboard.json`

## Future Enhancements

- [ ] Slack/Email notifications for grade drops
- [ ] Custom alerting rules in Prometheus
- [ ] Historical trend analysis and predictions
- [ ] Per-app quality tracking
- [ ] Developer dashboard with personal metrics
- [ ] Integration with GitHub Actions/CI
- [ ] Automated quality gates for PR reviews
- [ ] Cost-benefit analysis for refactoring

## Support & Contributions

For issues or improvements:
1. Check troubleshooting section above
2. Review Quality Standards & Thresholds
3. Consult `.claude/rules.md` for coding standards
4. Contact Quality Metrics Team

---

**Last Updated:** November 5, 2025
**Maintainer:** Quality Metrics Team
**Phase:** 7 (Final Phase)
**Status:** Production Ready
