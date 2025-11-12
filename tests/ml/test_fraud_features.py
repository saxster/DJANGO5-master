"""
Unit Tests for Fraud Feature Engineering

Tests all 12 fraud detection features with known inputs/expected outputs.

Coverage:
- Temporal features (4)
- Location features (2)
- Behavioral features (3)
- Biometric features (3)
- Edge cases and performance

Follows .claude/rules.md:
- Rule #11: Specific exception handling
- Rule #13: Network timeout testing where applicable
"""

import pytest
from datetime import datetime, timedelta, time
from django.utils import timezone
from unittest.mock import Mock, patch, MagicMock
from apps.ml.features.fraud_features import FraudFeatureExtractor


class TestTemporalFeatures:
    """Test suite for 4 temporal features."""

    def test_hour_of_day_extraction(self):
        """Test hour extraction from punchintime."""
        # Given: Attendance event at 14:30 (2:30 PM)
        event = Mock()
        event.punchintime = timezone.make_aware(
            datetime(2025, 1, 15, 14, 30, 0)
        )

        # When: Extract hour
        hour = FraudFeatureExtractor.extract_hour_of_day(event)

        # Then: Should return 14
        assert hour == 14

    def test_hour_of_day_early_morning(self):
        """Test suspicious early morning hours."""
        event = Mock()
        event.punchintime = timezone.make_aware(
            datetime(2025, 1, 15, 3, 0, 0)  # 3 AM
        )

        hour = FraudFeatureExtractor.extract_hour_of_day(event)

        assert hour == 3  # Suspicious hour

    def test_hour_of_day_missing_punchintime(self):
        """Test default hour when punchintime is missing."""
        event = Mock()
        event.punchintime = None
        event.scheduled_time = timezone.make_aware(
            datetime(2025, 1, 15, 9, 0, 0)
        )

        hour = FraudFeatureExtractor.extract_hour_of_day(event)

        assert hour == 9

    def test_hour_of_day_fallback_default(self):
        """Test fallback to default (8 AM) when all times missing."""
        event = Mock()
        event.punchintime = None
        del event.scheduled_time  # Simulate missing attribute

        hour = FraudFeatureExtractor.extract_hour_of_day(event)

        assert hour == 8  # Default

    def test_day_of_week_extraction(self):
        """Test day of week extraction (0=Monday, 6=Sunday)."""
        event = Mock()
        # January 15, 2025 is a Wednesday (day 2)
        event.datefor = datetime(2025, 1, 15).date()

        day = FraudFeatureExtractor.extract_day_of_week(event)

        assert day == 2  # Wednesday

    def test_day_of_week_weekend(self):
        """Test weekend day extraction."""
        event = Mock()
        # January 18, 2025 is a Saturday (day 5)
        event.datefor = datetime(2025, 1, 18).date()

        day = FraudFeatureExtractor.extract_day_of_week(event)

        assert day == 5  # Saturday

    def test_is_weekend_flag_true(self):
        """Test weekend flag returns 1.0 for Saturday/Sunday."""
        event = Mock()
        event.datefor = datetime(2025, 1, 18).date()  # Saturday

        is_weekend = FraudFeatureExtractor.extract_is_weekend(event)

        assert is_weekend == 1.0

    def test_is_weekend_flag_false(self):
        """Test weekend flag returns 0.0 for weekdays."""
        event = Mock()
        event.datefor = datetime(2025, 1, 15).date()  # Wednesday

        is_weekend = FraudFeatureExtractor.extract_is_weekend(event)

        assert is_weekend == 0.0

    def test_is_holiday_placeholder(self):
        """Test holiday flag (MVP placeholder always returns 0.0)."""
        event = Mock()

        is_holiday = FraudFeatureExtractor.extract_is_holiday(event)

        # MVP: Always returns 0.0 (not implemented yet)
        assert is_holiday == 0.0


class TestLocationFeatures:
    """Test suite for 2 location features."""

    def test_gps_drift_zero_meters(self):
        """Test GPS drift with punch location at geofence center."""
        event = Mock()
        event.startlat = 37.7749  # San Francisco
        event.startlng = -122.4194

        site = Mock()
        site.geofence = Mock()
        site.geofence.latitude = 37.7749  # Same location
        site.geofence.longitude = -122.4194

        drift = FraudFeatureExtractor.extract_gps_drift(event, site)

        # Should be ~0 meters (allow small rounding error)
        assert drift < 1.0

    def test_gps_drift_within_geofence(self):
        """Test GPS drift within normal geofence radius."""
        event = Mock()
        event.startlat = 37.7749
        event.startlng = -122.4194

        site = Mock()
        site.geofence = Mock()
        # ~100m away (approximate)
        site.geofence.latitude = 37.7759
        site.geofence.longitude = -122.4194

        drift = FraudFeatureExtractor.extract_gps_drift(event, site)

        # Should be ~100-150m
        assert 50 < drift < 200

    def test_gps_drift_outside_geofence(self):
        """Test GPS drift far outside geofence (GPS spoofing)."""
        event = Mock()
        event.startlat = 37.7749  # San Francisco
        event.startlng = -122.4194

        site = Mock()
        site.geofence = Mock()
        site.geofence.latitude = 34.0522  # Los Angeles (~550 km away)
        site.geofence.longitude = -118.2437

        drift = FraudFeatureExtractor.extract_gps_drift(event, site)

        # Should be capped at 10,000m
        assert drift == 10000.0

    def test_gps_drift_missing_coordinates(self):
        """Test GPS drift when coordinates are missing."""
        event = Mock()
        event.startlat = None
        event.startlng = None

        site = Mock()
        site.geofence = Mock()
        site.geofence.latitude = 37.7749
        site.geofence.longitude = -122.4194

        drift = FraudFeatureExtractor.extract_gps_drift(event, site)

        assert drift == 0.0  # Default

    def test_haversine_distance_calculation(self):
        """Test Haversine formula accuracy."""
        # Known distance: SF to LA ~559 km
        sf_lat, sf_lng = 37.7749, -122.4194
        la_lat, la_lng = 34.0522, -118.2437

        distance = FraudFeatureExtractor._haversine_distance(
            sf_lat, sf_lng, la_lat, la_lng
        )

        # Should be approximately 559,000 meters (±10%)
        assert 500000 < distance < 620000

    @pytest.mark.django_db
    def test_location_consistency_high(self):
        """Test high location consistency (same GPS coords)."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='test_user',
            email='test@example.com'
        )
        site = Bt.objects.create(name='Test Site')

        # Create 10 check-ins at nearly identical locations
        for i in range(10):
            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                startlat=37.7749 + (i * 0.0001),  # Very small variance
                startlng=-122.4194 + (i * 0.0001),
                punchintime=timezone.now() - timedelta(days=i)
            )

        consistency = FraudFeatureExtractor.extract_location_consistency(
            person, site, days=30
        )

        # High consistency (low variance)
        assert consistency >= 0.8

    @pytest.mark.django_db
    def test_location_consistency_low(self):
        """Test low location consistency (GPS spoofing pattern)."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='test_user2',
            email='test2@example.com'
        )
        site = Bt.objects.create(name='Test Site 2')

        # Create check-ins at widely varying locations
        locations = [
            (37.7749, -122.4194),  # SF
            (34.0522, -118.2437),  # LA
            (40.7128, -74.0060),   # NYC
            (41.8781, -87.6298),   # Chicago
            (29.7604, -95.3698),   # Houston
        ]

        for i, (lat, lng) in enumerate(locations):
            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                startlat=lat,
                startlng=lng,
                punchintime=timezone.now() - timedelta(days=i)
            )

        consistency = FraudFeatureExtractor.extract_location_consistency(
            person, site, days=30
        )

        # Low consistency (high variance)
        assert consistency < 0.5


class TestBehavioralFeatures:
    """Test suite for 3 behavioral features."""

    @pytest.mark.django_db
    def test_check_in_frequency_zscore_normal(self):
        """Test normal check-in frequency (within 1 stddev)."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog

        # Create test person and site
        person = People.objects.create(
            username='normal_user',
            email='normal@example.com'
        )
        site = Bt.objects.create(name='Test Site')

        # Create 20 check-ins (normal frequency)
        for i in range(20):
            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                punchintime=timezone.now() - timedelta(days=i)
            )

        zscore = FraudFeatureExtractor.extract_check_in_frequency_zscore(
            person, site, days=30
        )

        # Should be close to 0 (near mean)
        assert -1.5 < zscore < 1.5

    @pytest.mark.django_db
    def test_check_in_frequency_zscore_high(self):
        """Test abnormally high check-in frequency."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='frequent_user',
            email='frequent@example.com'
        )
        site = Bt.objects.create(name='Test Site 2')

        # Create 60 check-ins (abnormally high)
        for i in range(60):
            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=(timezone.now() - timedelta(days=i // 2)).date(),
                punchintime=timezone.now() - timedelta(days=i // 2)
            )

        zscore = FraudFeatureExtractor.extract_check_in_frequency_zscore(
            person, site, days=30
        )

        # Should be positive (above mean)
        assert zscore > 0.5

    @pytest.mark.django_db
    def test_late_arrival_rate_zero(self):
        """Test 0% late arrival rate (always on time)."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog
        from apps.scheduler.models import Schedule

        person = People.objects.create(
            username='punctual_user',
            email='punctual@example.com'
        )
        site = Bt.objects.create(name='Test Site')

        # Create scheduled shifts and on-time check-ins
        for i in range(10):
            date = (timezone.now() - timedelta(days=i)).date()
            shift_start = time(9, 0, 0)

            Schedule.objects.create(
                people=person,
                bu=site,
                datef=date,
                fromt=shift_start,
                tot=time(17, 0, 0)
            )

            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=date,
                punchintime=timezone.make_aware(
                    datetime.combine(date, time(8, 55, 0))  # 5 min early
                )
            )

        late_rate = FraudFeatureExtractor.extract_late_arrival_rate(
            person, site, days=30
        )

        assert late_rate == 0.0

    @pytest.mark.django_db
    def test_late_arrival_rate_high(self):
        """Test high late arrival rate (frequently late)."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt
        from apps.attendance.models import PeopleEventlog
        from apps.scheduler.models import Schedule

        person = People.objects.create(
            username='late_user',
            email='late@example.com'
        )
        site = Bt.objects.create(name='Test Site 2')

        # Create shifts with late check-ins
        for i in range(10):
            date = (timezone.now() - timedelta(days=i)).date()
            shift_start = time(9, 0, 0)

            Schedule.objects.create(
                people=person,
                bu=site,
                datef=date,
                fromt=shift_start,
                tot=time(17, 0, 0)
            )

            PeopleEventlog.objects.create(
                people=person,
                bu=site,
                datefor=date,
                punchintime=timezone.make_aware(
                    datetime.combine(date, time(9, 30, 0))  # 30 min late
                )
            )

        late_rate = FraudFeatureExtractor.extract_late_arrival_rate(
            person, site, days=30
        )

        assert late_rate == 1.0  # 100% late

    @pytest.mark.django_db
    def test_weekend_work_frequency_zero(self):
        """Test 0% weekend work (weekdays only)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='weekday_user',
            email='weekday@example.com'
        )

        # Create only weekday check-ins (Mon-Fri)
        weekday_dates = [
            datetime(2025, 1, 13).date(),  # Monday
            datetime(2025, 1, 14).date(),  # Tuesday
            datetime(2025, 1, 15).date(),  # Wednesday
            datetime(2025, 1, 16).date(),  # Thursday
            datetime(2025, 1, 17).date(),  # Friday
        ]

        for date in weekday_dates:
            PeopleEventlog.objects.create(
                people=person,
                datefor=date,
                punchintime=timezone.make_aware(
                    datetime.combine(date, time(9, 0, 0))
                )
            )

        frequency = FraudFeatureExtractor.extract_weekend_work_frequency(
            person, days=90
        )

        assert frequency == 0.0

    @pytest.mark.django_db
    def test_weekend_work_frequency_high(self):
        """Test high weekend work frequency (suspicious)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='weekend_user',
            email='weekend@example.com'
        )

        # Create mostly weekend check-ins
        weekend_dates = [
            datetime(2025, 1, 11).date(),  # Saturday
            datetime(2025, 1, 12).date(),  # Sunday
            datetime(2025, 1, 18).date(),  # Saturday
            datetime(2025, 1, 19).date(),  # Sunday
        ]
        weekday_dates = [
            datetime(2025, 1, 15).date(),  # Wednesday
        ]

        for date in weekend_dates + weekday_dates:
            PeopleEventlog.objects.create(
                people=person,
                datefor=date,
                punchintime=timezone.make_aware(
                    datetime.combine(date, time(9, 0, 0))
                )
            )

        frequency = FraudFeatureExtractor.extract_weekend_work_frequency(
            person, days=90
        )

        assert frequency == 0.8  # 80% weekend work


class TestBiometricFeatures:
    """Test suite for 3 biometric features."""

    def test_face_confidence_high(self):
        """Test high face recognition confidence."""
        event = Mock()
        event.peventlogextras = {
            'distance_in': 0.1,  # Low distance = high confidence
            'verified_in': True
        }

        confidence = FraudFeatureExtractor.extract_face_confidence(event)

        # distance 0.1 -> confidence 0.75 (1 - 0.1/0.4)
        assert confidence == 0.75

    def test_face_confidence_low(self):
        """Test low face recognition confidence (fraud indicator)."""
        event = Mock()
        event.peventlogextras = {
            'distance_in': 0.5,  # High distance = low confidence
            'verified_in': False
        }

        confidence = FraudFeatureExtractor.extract_face_confidence(event)

        # distance 0.5 > 0.4 threshold -> confidence 0.0
        assert confidence == 0.0

    def test_face_confidence_missing_extras(self):
        """Test fallback when peventlogextras missing."""
        event = Mock()
        del event.peventlogextras

        confidence = FraudFeatureExtractor.extract_face_confidence(event)

        assert confidence == 0.5  # Default

    @pytest.mark.django_db
    def test_biometric_mismatch_count_zero(self):
        """Test zero biometric mismatches (legitimate user)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='verified_user',
            email='verified@example.com'
        )

        # Create check-ins with successful verification
        for i in range(10):
            PeopleEventlog.objects.create(
                people=person,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                punchintime=timezone.now() - timedelta(days=i),
                peventlogextras={'verified_in': True}
            )

        mismatch_count = FraudFeatureExtractor.extract_biometric_mismatch_count(
            person, days=30
        )

        assert mismatch_count == 0

    @pytest.mark.django_db
    def test_biometric_mismatch_count_high(self):
        """Test high biometric mismatch count (fraud pattern)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='suspicious_user',
            email='suspicious@example.com'
        )

        # Create check-ins with failed verification
        for i in range(7):
            PeopleEventlog.objects.create(
                people=person,
                datefor=(timezone.now() - timedelta(days=i)).date(),
                punchintime=timezone.now() - timedelta(days=i),
                peventlogextras={'verified_in': False}
            )

        mismatch_count = FraudFeatureExtractor.extract_biometric_mismatch_count(
            person, days=30
        )

        assert mismatch_count == 7

    @pytest.mark.django_db
    def test_time_since_last_event_normal(self):
        """Test normal time gap between check-ins (>8 hours)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='normal_gaps_user',
            email='normal_gaps@example.com'
        )

        # Create last event 10 hours ago
        PeopleEventlog.objects.create(
            people=person,
            datefor=(timezone.now() - timedelta(hours=10)).date(),
            punchintime=timezone.now() - timedelta(hours=10)
        )

        time_since = FraudFeatureExtractor.extract_time_since_last_event(person)

        # Should be ~36,000 seconds (10 hours)
        assert 35000 < time_since < 37000

    @pytest.mark.django_db
    def test_time_since_last_event_rapid(self):
        """Test rapid consecutive check-ins (suspicious)."""
        from apps.peoples.models import People
        from apps.attendance.models import PeopleEventlog

        person = People.objects.create(
            username='rapid_user',
            email='rapid@example.com'
        )

        # Create last event 30 minutes ago
        PeopleEventlog.objects.create(
            people=person,
            datefor=timezone.now().date(),
            punchintime=timezone.now() - timedelta(minutes=30)
        )

        time_since = FraudFeatureExtractor.extract_time_since_last_event(person)

        # Should be ~1,800 seconds (30 minutes)
        assert 1700 < time_since < 1900


class TestPerformance:
    """Performance tests for feature extraction."""

    @pytest.mark.slow
    @pytest.mark.django_db
    def test_feature_extraction_performance_1000_samples(self):
        """Test feature extraction completes <1s for 1000 samples."""
        import time
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt

        person = People.objects.create(
            username='perf_user',
            email='perf@example.com'
        )
        site = Bt.objects.create(name='Perf Site')

        event = Mock()
        event.punchintime = timezone.now()
        event.datefor = timezone.now().date()
        event.startlat = 37.7749
        event.startlng = -122.4194
        event.peventlogextras = {'distance_in': 0.2, 'verified_in': True}

        start_time = time.time()

        # Extract features 1000 times
        for _ in range(1000):
            features = FraudFeatureExtractor.extract_all_features(
                event, person, site
            )

        elapsed = time.time() - start_time

        # Should complete in <1 second
        assert elapsed < 1.0
        assert len(features) == 12


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_extract_all_features_null_values(self):
        """Test feature extraction with null/missing values."""
        event = Mock()
        event.punchintime = None
        event.datefor = None
        event.startlat = None
        event.startlng = None
        del event.peventlogextras

        person = Mock()
        person.id = 1

        site = Mock()
        site.id = 1
        site.geofence = None

        features = FraudFeatureExtractor.extract_all_features(
            event, person, site
        )

        # Should return default values (no exceptions)
        assert 'hour_of_day' in features
        assert features['gps_drift_meters'] == 0.0
        assert features['face_recognition_confidence'] == 0.5

    def test_extract_all_features_extreme_values(self):
        """Test feature extraction with extreme values."""
        event = Mock()
        event.punchintime = timezone.make_aware(
            datetime(2025, 1, 1, 23, 59, 59)  # Last second of day
        )
        event.datefor = datetime(2025, 1, 1).date()
        event.startlat = 90.0  # North Pole
        event.startlng = 0.0
        event.peventlogextras = {'distance_in': 999.0}  # Extreme distance

        person = Mock()
        person.id = 1

        site = Mock()
        site.id = 1
        site.geofence = Mock()
        site.geofence.latitude = -90.0  # South Pole
        site.geofence.longitude = 0.0

        features = FraudFeatureExtractor.extract_all_features(
            event, person, site
        )

        # Should handle extreme values gracefully
        assert features['hour_of_day'] == 23
        assert features['gps_drift_meters'] <= 10000.0  # Capped

    @pytest.mark.django_db
    def test_extract_all_features_empty_dataset(self):
        """Test feature extraction with no historical data."""
        from apps.peoples.models import People
        from apps.client_onboarding.models import Bt

        person = People.objects.create(
            username='new_user',
            email='new@example.com'
        )
        site = Bt.objects.create(name='New Site')

        event = Mock()
        event.punchintime = timezone.now()
        event.datefor = timezone.now().date()
        event.startlat = 37.7749
        event.startlng = -122.4194
        event.peventlogextras = {'distance_in': 0.2}

        features = FraudFeatureExtractor.extract_all_features(
            event, person, site
        )

        # Behavioral features should return safe defaults
        assert features['check_in_frequency_zscore'] == 0.0
        assert features['weekend_work_frequency'] == 0.0
        assert features['time_since_last_event'] == 86400.0
