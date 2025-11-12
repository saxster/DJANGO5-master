from celery import shared_task
from django.utils import timezone
from datetime import timedelta
from apps.threat_intelligence.models import (
    IntelligenceSource,
    ThreatEvent,
    IntelligenceAlert,
)
from apps.threat_intelligence.services import IntelligenceAnalyzer, AlertDistributor
from apps.core.utils_new.retry_mechanism import with_retry
from apps.core.exceptions.patterns import NETWORK_EXCEPTIONS
import logging
import requests

logger = logging.getLogger(__name__)


@shared_task(
    name='threat_intelligence.fetch_intelligence_from_sources',
    bind=True,
    max_retries=3,
    queue='intelligence',
)
def fetch_intelligence_from_sources(self):
    """
    Celery Beat task: Fetch intelligence from all active sources.
    
    Schedule: Every 15 minutes via Celery Beat.
    """
    sources = IntelligenceSource.objects.filter(
        is_active=True,
        last_fetch_status__in=['ACTIVE', 'FAILED']  # Exclude rate-limited
    )
    
    for source in sources:
        # Check if due for refresh
        if source.last_fetch_at:
            next_fetch = source.last_fetch_at + timedelta(minutes=source.refresh_interval_minutes)
            if timezone.now() < next_fetch:
                continue
        
        # Dispatch to specific source handler
        fetch_from_source.delay(source.id)
    
    logger.info(f"Dispatched fetch tasks for {sources.count()} intelligence sources")


@shared_task(
    name='threat_intelligence.fetch_from_source',
    bind=True,
    max_retries=3,
    queue='intelligence',
)
@with_retry(exceptions=NETWORK_EXCEPTIONS, max_retries=3, retry_policy='NETWORK_CALL')
def fetch_from_source(self, source_id: int):
    """Fetch data from a specific intelligence source."""
    
    source = IntelligenceSource.objects.get(id=source_id)
    start_time = timezone.now()
    
    try:
        if source.source_type == 'NEWS_API':
            events = _fetch_news_api(source)
        elif source.source_type == 'WEATHER_API':
            events = _fetch_weather_api(source)
        elif source.source_type == 'RSS_FEED':
            events = _fetch_rss_feed(source)
        else:
            logger.warning(f"Source type {source.source_type} not implemented yet")
            return
        
        # Update source metrics
        fetch_duration = (timezone.now() - start_time).total_seconds()
        source.last_fetch_at = timezone.now()
        source.last_fetch_status = 'ACTIVE'
        source.last_fetch_error = ''
        source.total_fetches += 1
        source.total_events_created += len(events)
        source.average_fetch_duration_seconds = (
            (source.average_fetch_duration_seconds * (source.total_fetches - 1) + fetch_duration)
            / source.total_fetches
        )
        source.save()
        
        # Process each event
        for event in events:
            process_threat_event.delay(event.id)
        
        logger.info(f"Fetched {len(events)} events from {source.name}")
        
    except Exception as e:
        logger.error(f"Failed to fetch from {source.name}: {e}", exc_info=True)
        source.last_fetch_at = timezone.now()
        source.last_fetch_status = 'FAILED'
        source.last_fetch_error = str(e)[:500]
        source.save()
        raise


def _fetch_news_api(source: IntelligenceSource) -> list:
    """Fetch from NewsAPI or similar news aggregator."""
    # FUTURE: Implement actual NewsAPI integration
    logger.info(f"Fetching from NewsAPI: {source.name}")
    return []


def _fetch_weather_api(source: IntelligenceSource) -> list:
    """Fetch from weather service API."""
    # FUTURE: Implement OpenWeather, NOAA, etc.
    logger.info(f"Fetching from Weather API: {source.name}")
    return []


def _fetch_rss_feed(source: IntelligenceSource) -> list:
    """Fetch from RSS/Atom feed."""
    # FUTURE: Implement RSS parsing
    logger.info(f"Fetching from RSS: {source.name}")
    return []


@shared_task(
    name='threat_intelligence.process_threat_event',
    bind=True,
    max_retries=2,
    queue='intelligence',
)
def process_threat_event(self, event_id: int):
    """
    Process a threat event: NLP analysis, geospatial matching, alert creation.
    """
    event = ThreatEvent.objects.get(id=event_id)
    
    if event.is_processed:
        logger.info(f"Event {event_id} already processed, skipping")
        return
    
    try:
        # Run NLP classification
        category, severity, confidence = IntelligenceAnalyzer.classify_event(
            event.title,
            event.description,
            event.raw_content
        )
        
        # Update event with analysis results
        event.category = category
        event.severity = severity
        event.confidence_score = confidence
        event.entities = IntelligenceAnalyzer.extract_entities(event.raw_content)
        event.keywords = IntelligenceAnalyzer.extract_keywords(event.raw_content)
        event.impact_radius_km = IntelligenceAnalyzer.calculate_impact_radius(category, severity)
        event.is_processed = True
        event.save()
        
        # Find affected tenants
        affected_profiles = AlertDistributor.find_affected_tenants(event)
        
        # Create and distribute alerts
        for profile in affected_profiles:
            alert = AlertDistributor.create_alert(event, profile)
            distribute_alert.delay(alert.id)
        
        logger.info(
            f"Processed event {event_id}: {category}/{severity} "
            f"({confidence:.2f} confidence), {len(affected_profiles)} tenants affected"
        )
        
    except Exception as e:
        logger.error(f"Failed to process event {event_id}: {e}", exc_info=True)
        event.processing_error = str(e)[:500]
        event.save()
        raise


@shared_task(
    name='threat_intelligence.distribute_alert',
    bind=True,
    max_retries=3,
    queue='alerts',
)
def distribute_alert(self, alert_id: int):
    """Distribute alert through configured channels."""
    
    alert = IntelligenceAlert.objects.select_related(
        'threat_event',
        'intelligence_profile',
        'tenant'
    ).get(id=alert_id)
    
    success = AlertDistributor.distribute_alert(alert)
    
    if success:
        logger.info(f"Successfully distributed alert {alert_id} to {alert.tenant.name}")
    else:
        logger.error(f"Failed to distribute alert {alert_id}")
        raise Exception(f"Alert distribution failed for {alert_id}")


@shared_task(
    name='threat_intelligence.update_learning_profiles',
    bind=True,
    queue='ml',
)
def update_learning_profiles(self):
    """
    Celery Beat task: Update ML learning profiles based on tenant feedback.
    
    Schedule: Daily via Celery Beat.
    
    FUTURE: Implement ML retraining based on feedback data.
    """
    from apps.threat_intelligence.models import TenantLearningProfile
    
    profiles = TenantLearningProfile.objects.filter(
        intelligence_profile__is_active=True
    )
    
    for profile in profiles:
        # FUTURE: Run ML training on feedback data
        logger.info(f"Would retrain learning profile for {profile.tenant.name}")
    
    logger.info(f"Updated {profiles.count()} learning profiles")
