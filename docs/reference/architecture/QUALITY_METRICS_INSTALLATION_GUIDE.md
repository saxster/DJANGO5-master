# Quality Metrics Dashboard - Installation & Deployment Guide

Complete setup instructions for Phase 7 automated quality metrics dashboard and weekly reporting system.

## Phase 7 Deliverables Summary

Agent 37 has completed all 4 core deliverables:

### 1. Weekly Report Generator
- **File**: `scripts/generate_quality_report.py` (820 lines)
- **Purpose**: Aggregate all validation results and generate comprehensive weekly reports
- **Outputs**: JSON and Markdown formats
- **Database**: Optional storage in `QualityMetric` model for trend tracking

### 2. Django Quality Metrics Model
- **File**: `apps/core/models/quality_metrics.py` (145 lines)
- **Purpose**: Track metrics over time for trend analysis and alerting
- **Fields**: 13 key metrics + JSON report storage
- **Indexes**: 3 time-based indexes for performance
- **Migration**: `apps/core/migrations/0019_add_quality_metrics_model.py`

### 3. Prometheus Metrics Exporter
- **File**: `monitoring/prometheus/code_quality_metrics.py` (420 lines)
- **Purpose**: Real-time metrics export for monitoring integrations
- **Metrics**: 11 Prometheus gauges + 2 counters
- **Integration**: Django view handler + standalone executable
- **Features**: Auto-collection, error tracking, metric caching

### 4. Grafana Dashboard Configuration
- **File**: `monitoring/grafana/code_quality_dashboard.json`
- **Purpose**: Real-time visualization of quality metrics
- **Panels**: 11 dashboard panels with trend lines and gauges
- **Refresh**: 30-second updates with 30-day historical view
- **Status**: Ready-to-import JSON format

## Installation Steps

### Prerequisites

```bash
# Required Python packages (should already be installed)
pip list | grep -E "Django|django|prometheus_client|celery"

# Verify Python version
python --version  # Should be 3.11.9
```

### Step 1: Apply Database Migration

```bash
# Check migration status
python manage.py showmigrations core | grep 0019

# Apply migration
python manage.py migrate core

# Verify migration applied
python manage.py showmigrations core | grep 0019
# Should show: [X] 0019_add_quality_metrics_model
```

### Step 2: Verify Existing Quality Scripts

All dependencies are existing scripts in the project:

```bash
# Code quality validation (existing)
python scripts/validate_code_quality.py --verbose

# File size compliance (existing)
python scripts/check_file_sizes.py --verbose

# Test coverage (via pytest)
python -m pytest --cov=apps --tb=short

# Security scanning (via bandit - optional)
python -m bandit -r apps/
```

### Step 3: Test Report Generator

```bash
# Generate JSON report
python scripts/generate_quality_report.py --format json

# Generate Markdown report
python scripts/generate_quality_report.py --format markdown

# Generate both formats
python scripts/generate_quality_report.py --format both

# Save to specific file
python scripts/generate_quality_report.py --output quality_report_2025_11_05.json

# Store metrics in database
python scripts/generate_quality_report.py --format json --store-db
```

### Step 4: Test Prometheus Metrics Exporter

```bash
# Standalone execution (for testing)
python monitoring/prometheus/code_quality_metrics.py

# In Django development server
python manage.py runserver

# Then in another terminal:
curl http://localhost:8000/metrics/code-quality/
```

### Step 5: Configure Django URLs (Optional)

To expose Prometheus metrics from Django:

```python
# intelliwiz_config/urls.py

from django.contrib import admin
from django.urls import path, include
from monitoring.prometheus.code_quality_metrics import get_metrics_handler

urlpatterns = [
    # ... existing patterns ...

    # Add Prometheus metrics endpoint
    path('metrics/code-quality/', get_metrics_handler(), name='prometheus-code-quality'),
]
```

### Step 6: Import Grafana Dashboard

**Option A: Manual Import**

1. Open Grafana UI (usually http://localhost:3000)
2. Click "+" (Create) in left sidebar
3. Select "Import"
4. Copy-paste content of `monitoring/grafana/code_quality_dashboard.json`
5. Select Prometheus datasource
6. Click "Import"

**Option B: Automated Import**

```bash
# Use curl to import dashboard
curl -X POST http://localhost:3000/api/dashboards/db \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $GRAFANA_API_TOKEN" \
  -d @monitoring/grafana/code_quality_dashboard.json
```

### Step 7: Configure Prometheus Scraping (Optional)

Add to `prometheus.yml`:

```yaml
global:
  scrape_interval: 30s
  scrape_timeout: 10s

scrape_configs:
  # ... existing configs ...

  - job_name: 'code-quality'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics/code-quality/'
    scrape_interval: 300s  # Collect every 5 minutes
    scrape_timeout: 30s
```

Then restart Prometheus:

```bash
# If using docker
docker restart prometheus

# If running directly
sudo systemctl restart prometheus

# If using brew
brew services restart prometheus
```

### Step 8: Schedule Weekly Reports (Optional)

**Option A: Django Management Command (Recommended)**

Create `apps/core/management/commands/generate_weekly_report.py`:

```python
from django.core.management.base import BaseCommand
from scripts.generate_quality_report import QualityReportGenerator
from datetime import datetime

class Command(BaseCommand):
    help = 'Generate weekly quality report'

    def add_arguments(self, parser):
        parser.add_argument(
            '--store-db',
            action='store_true',
            help='Store metrics in database'
        )

    def handle(self, *args, **options):
        generator = QualityReportGenerator(store_db=options['store_db'])
        report = generator.generate_report()

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        json_file = f"quality_reports/report_{timestamp}.json"
        md_file = f"quality_reports/report_{timestamp}.md"

        generator.save_report_json(report, json_file)
        generator.save_report_markdown(report, md_file)

        self.stdout.write(
            self.style.SUCCESS(
                f'Weekly report generated: {json_file}, {md_file}'
            )
        )
```

Run manually:
```bash
python manage.py generate_weekly_report --store-db
```

**Option B: Celery Beat (For Automation)**

Add to `intelliwiz_config/celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'weekly-quality-report': {
        'task': 'apps.core.tasks.generate_weekly_quality_report',
        'schedule': crontab(hour=0, minute=0, day_of_week=1),  # Monday 00:00 UTC
    },
}
```

Create `apps/core/tasks.py`:

```python
from celery import shared_task
from scripts.generate_quality_report import QualityReportGenerator
from datetime import datetime

@shared_task
def generate_weekly_quality_report():
    """Generate and store weekly quality report"""
    generator = QualityReportGenerator(store_db=True)
    report = generator.generate_report()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    md_file = f"quality_reports/report_{timestamp}.md"

    generator.save_report_markdown(report, md_file)
    return f"Report saved: {md_file}"
```

**Option C: System Cron Job**

```bash
# Add to crontab
crontab -e

# Add this line (runs every Monday at midnight UTC)
0 0 * * 1 cd /path/to/project && /opt/homebrew/bin/python3 scripts/generate_quality_report.py --format both --store-db
```

## Verification Checklist

After installation, verify all components:

```bash
# 1. Database migration applied
python manage.py showmigrations core | grep "0019"
# Expected: [X] 0019_add_quality_metrics_model

# 2. Model accessible from Django shell
python manage.py shell
>>> from apps.core.models import QualityMetric
>>> QualityMetric.objects.count()
0  # or higher if already has data

# 3. Quality report script works
python scripts/generate_quality_report.py --format json
# Expected: JSON file created with timestamp

# 4. Prometheus metrics available (if configured)
curl http://localhost:8000/metrics/code-quality/ | head -20
# Expected: Prometheus metric lines starting with #

# 5. Grafana dashboard visible
# Navigate to http://localhost:3000
# Expected: Code Quality Dashboard in dashboards list

# 6. All script syntaxes are valid
python -m py_compile scripts/generate_quality_report.py
python -m py_compile monitoring/prometheus/code_quality_metrics.py
python -m py_compile apps/core/models/quality_metrics.py
```

## Common Issues & Troubleshooting

### Issue: ModuleNotFoundError when running scripts

**Solution**: Ensure virtual environment is activated
```bash
source venv/bin/activate
# Then run scripts
python scripts/generate_quality_report.py
```

### Issue: Prometheus metrics endpoint returns 404

**Solution**: Verify URL pattern is added to `intelliwiz_config/urls.py`:
```python
from monitoring.prometheus.code_quality_metrics import get_metrics_handler
path('metrics/code-quality/', get_metrics_handler(), name='prometheus-code-quality'),
```

### Issue: Grafana dashboard shows "No Data"

**Causes & Solutions**:
1. Prometheus not scraping metrics
   - Check Prometheus targets: http://prometheus:9090/targets
2. Dashboard using wrong datasource
   - Verify datasource is set to Prometheus
3. Metrics not being collected
   - Run `python scripts/generate_quality_report.py` manually
4. Time range too narrow
   - Dashboard defaults to 30-day view

### Issue: Database migration fails

**Solution**: Check migration dependencies
```bash
# Show all migrations
python manage.py showmigrations core

# If 0018 is not applied, apply it first
python manage.py migrate core 0018_add_task_idempotency_indexes

# Then apply 0019
python manage.py migrate core 0019_add_quality_metrics_model
```

### Issue: Report generation times out

**Causes**:
- Large codebase takes time for analysis
- Bandit security scan is slow (optional)
- Database connection issues

**Solutions**:
- Run validation scripts individually first
- Disable optional checks (security scan)
- Increase subprocess timeout

## Performance Tuning

### Database Optimization

```python
# Create indexes (included in migration)
python manage.py migrate

# Monitor query performance
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as context:
    QualityMetric.objects.filter(
        timestamp__gte=one_week_ago
    ).count()

print(f"Queries executed: {len(context)}")
```

### Prometheus Optimization

```yaml
# In prometheus.yml - adjust scrape interval
global:
  scrape_interval: 300s  # 5 minutes instead of 30s

scrape_configs:
  - job_name: 'code-quality'
    scrape_interval: 600s  # 10 minutes for heavy workloads
    scrape_timeout: 30s
```

### Report Generation Optimization

```python
# Run quality checks in parallel
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    code_quality_future = executor.submit(run_code_quality_check)
    coverage_future = executor.submit(get_test_coverage)
    complexity_future = executor.submit(analyze_complexity)
    security_future = executor.submit(analyze_security)
```

## Integration with Existing Systems

### CI/CD Pipeline Integration

**GitHub Actions Example**:
```yaml
name: Weekly Quality Report

on:
  schedule:
    - cron: '0 0 * * 1'  # Monday midnight UTC

jobs:
  quality-report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements/base-linux.txt
      - run: python scripts/generate_quality_report.py --store-db
      - uses: actions/upload-artifact@v3
        with:
          name: quality-report
          path: quality_report_*.md
```

### Slack Notifications

```python
# In Celery task or management command
import requests

def notify_slack(report):
    webhook_url = os.environ['SLACK_WEBHOOK_URL']
    message = {
        'text': f"Weekly Quality Report: {report.overall_grade}",
        'blocks': [
            {
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f"*Code Quality Report*\nGrade: {report.overall_grade}\n"
                            f"Coverage: {report.test_coverage['percent_covered']:.1f}%"
                }
            }
        ]
    }
    requests.post(webhook_url, json=message)
```

### Email Reports

```python
from django.core.mail import EmailMessage

def send_quality_report_email(report):
    email = EmailMessage(
        subject=f"Weekly Quality Report - Grade {report.overall_grade}",
        body=f"Overall Score: {report.overall_score:.1f}/100\n\n"
             f"{report.recommendations[0]}",
        from_email='quality@example.com',
        to=['dev-team@example.com']
    )
    email.send()
```

## File Manifest

**New Files Created:**

```
scripts/
├── generate_quality_report.py          # Weekly report generator (820 lines)

apps/core/models/
├── quality_metrics.py                  # Quality metrics model (145 lines)

apps/core/migrations/
├── 0019_add_quality_metrics_model.py   # Database migration

monitoring/prometheus/
├── code_quality_metrics.py             # Prometheus metrics exporter (420 lines)

monitoring/grafana/
├── code_quality_dashboard.json         # Grafana dashboard config

monitoring/
└── QUALITY_METRICS_README.md           # System documentation

Project Root:
└── QUALITY_METRICS_INSTALLATION_GUIDE.md  # This file
```

## Maintenance & Operations

### Weekly Tasks

```bash
# Verify last report was generated
ls -lt quality_reports/ | head -1

# Check database has recent metrics
python manage.py shell -c "from apps.core.models import QualityMetric; print(QualityMetric.get_latest())"

# Review Grafana dashboard for trends
# (Open http://localhost:3000/d/code-quality-dashboard)
```

### Monthly Tasks

```bash
# Archive old reports (>30 days)
find quality_reports/ -mtime +30 -delete

# Clean up old metrics (optional - keep 90 days for trends)
python manage.py shell << 'EOF'
from apps.core.models import QualityMetric
from django.utils import timezone
from datetime import timedelta

cutoff = timezone.now() - timedelta(days=90)
deleted, _ = QualityMetric.objects.filter(timestamp__lt=cutoff).delete()
print(f"Deleted {deleted} old metrics")
EOF
```

### Quarterly Tasks

```bash
# Review and adjust quality thresholds in scripts/generate_quality_report.py
# Analyze trends in Grafana dashboard
# Update .claude/rules.md if standards change
# Archive historical reports to cloud storage
```

## Success Criteria

Phase 7 is complete when:

- [x] Weekly report generator working
- [x] Django model tracking metrics over time
- [x] Prometheus metrics exported in real-time
- [x] Grafana dashboard displaying trends
- [x] All scripts syntactically valid
- [x] Migration file created and ready to apply
- [x] Documentation complete
- [x] Integration points documented
- [x] Troubleshooting guide provided
- [x] Performance tuning guidelines included

## Next Steps (Future Phases)

1. **Alerting**: Configure Prometheus alerting rules
2. **Notifications**: Add Slack/Email notifications
3. **Predictions**: ML-based quality trend prediction
4. **Per-App Metrics**: Track quality by application
5. **Developer Dashboard**: Personal quality metrics
6. **Quality Gates**: Automated PR review gates

## Support

For questions or issues:

1. Check **Troubleshooting** section above
2. Review **monitoring/QUALITY_METRICS_README.md**
3. Check **.claude/rules.md** for standards
4. Contact Quality Metrics Team

---

**Installation Completed:** November 5, 2025
**Status:** Ready for Production
**Maintainer:** Quality Metrics Team (Agent 37)
**Phase:** 7 (Final Phase)
