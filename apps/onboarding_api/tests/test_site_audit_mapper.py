"""
Unit Tests for Site Audit Mapper (Phase D).

Tests the mapping of site audit results to system configuration:
- Coverage plan → Shifts
- SOPs → TypeAssist
- Complete site configuration application
"""

import pytest
from datetime import time as datetime_time
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from uuid import uuid4

from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError
from django.db import IntegrityError, DatabaseError
from django.utils import timezone

from apps.onboarding.models import (
    OnboardingSite,
    OnboardingZone,
    CoveragePlan,
    SOP,
    Shift,
    TypeAssist,
    ConversationSession,
    AIChangeSet,
    AIChangeRecord
)
from apps.client_onboarding.models.business_unit import Bt
from apps.peoples.models import People
from apps.onboarding_api.integration.site_audit_mapper import SiteAuditMapper


@pytest.fixture
def test_client(db):
    """Create test business unit."""
    return Bt.objects.create(
        buname="Test Branch",
        bucode="TB001",
        enable=True
    )


@pytest.fixture
def test_user(db):
    """Create test user."""
    return People.objects.create(
        loginid="testauditor",
        peoplename="Test Auditor",
        email="auditor@test.com",
        enable=True
    )


@pytest.fixture
def test_conversation_session(db, test_user, test_client):
    """Create conversation session."""
    return ConversationSession.objects.create(
        user=test_user,
        client=test_client,
        language="en",
        conversation_type=ConversationSession.ConversationTypeChoices.INITIAL_SETUP,
        current_state=ConversationSession.StateChoices.IN_PROGRESS
    )


@pytest.fixture
def test_site(db, test_client, test_conversation_session):
    """Create onboarding site."""
    return OnboardingSite.objects.create(
        business_unit=test_client,
        conversation_session=test_conversation_session,
        site_type=OnboardingSite.SiteTypeChoices.BANK_BRANCH,
        language="en",
        operating_hours_start=datetime_time(9, 0),
        operating_hours_end=datetime_time(17, 0),
        primary_gps=Point(77.5946, 12.9716)
    )


@pytest.fixture
def test_zone(db, test_site):
    """Create test zone."""
    return OnboardingZone.objects.create(
        site=test_site,
        zone_type=OnboardingZone.ZoneTypeChoices.GATE,
        zone_name="Main Entrance",
        importance_level=OnboardingZone.ImportanceLevelChoices.CRITICAL,
        risk_level=OnboardingZone.RiskLevelChoices.HIGH
    )


@pytest.fixture
def test_coverage_plan(db, test_site):
    """Create coverage plan with shift assignments."""
    return CoveragePlan.objects.create(
        site=test_site,
        guard_posts=[
            {
                'post_id': 'POST001',
                'zone': 'Main Entrance',
                'position': 'gate',
                'duties': ['access control', 'visitor logging'],
                'risk_level': 'high'
            }
        ],
        shift_assignments=[
            {
                'shift_name': 'Morning Shift',
                'start_time': '06:00',
                'end_time': '14:00',
                'posts_covered': ['POST001'],
                'staffing': {'count': 2, 'roles': ['security_guard']}
            },
            {
                'shift_name': 'Evening Shift',
                'start_time': '14:00',
                'end_time': '22:00',
                'posts_covered': ['POST001'],
                'staffing': {'count': 2, 'roles': ['security_guard']}
            }
        ],
        patrol_routes=[],
        risk_windows=[],
        generated_by='ai'
    )


@pytest.fixture
def test_sop(db, test_site, test_zone):
    """Create test SOP."""
    return SOP.objects.create(
        site=test_site,
        zone=test_zone,
        sop_title="Main Gate Access Control SOP",
        purpose="Control visitor and vehicle access",
        steps=[
            {'step_number': 1, 'description': 'Verify visitor identity', 'responsible_role': 'security_guard'},
            {'step_number': 2, 'description': 'Log entry in register', 'responsible_role': 'security_guard'},
            {'step_number': 3, 'description': 'Issue visitor pass', 'responsible_role': 'security_guard'}
        ],
        staffing_required={'roles': ['security_guard'], 'count': 1},
        compliance_references=['RBI Master Direction 2021 - Section 4.2.1'],
        frequency='shift',
        llm_generated=True,
        approved_at=timezone.now()
    )


@pytest.fixture
def site_audit_mapper():
    """Create SiteAuditMapper instance."""
    return SiteAuditMapper()


@pytest.mark.django_db
class TestCoveragePlanToShiftsMapping:
    """Test coverage plan to shifts mapping."""

    def test_map_coverage_plan_to_shifts_success(
        self,
        site_audit_mapper,
        test_coverage_plan,
        test_client
    ):
        """Test successful mapping of coverage plan to shifts."""
        result = site_audit_mapper.map_coverage_plan_to_shifts(
            test_coverage_plan,
            dry_run=False
        )

        assert result['shifts_created'] == 2
        assert len(result['shifts']) == 2
        assert len(result['validation_errors']) == 0

        morning_shift = Shift.objects.filter(
            shiftname='Morning Shift',
            client=test_client
        ).first()
        assert morning_shift is not None
        assert morning_shift.starttime == datetime_time(6, 0)
        assert morning_shift.endtime == datetime_time(14, 0)
        assert morning_shift.peoplecount == 2

        evening_shift = Shift.objects.filter(
            shiftname='Evening Shift',
            client=test_client
        ).first()
        assert evening_shift is not None
        assert evening_shift.starttime == datetime_time(14, 0)
        assert evening_shift.endtime == datetime_time(22, 0)

    def test_map_coverage_plan_dry_run(
        self,
        site_audit_mapper,
        test_coverage_plan
    ):
        """Test dry run mode doesn't create shifts."""
        result = site_audit_mapper.map_coverage_plan_to_shifts(
            test_coverage_plan,
            dry_run=True
        )

        assert result['shifts_created'] == 2
        assert len(result['shifts']) == 2
        assert all(shift is None for shift in result['shifts'])
        assert Shift.objects.count() == 0

    def test_map_coverage_plan_with_time_conflicts(
        self,
        site_audit_mapper,
        test_coverage_plan,
        test_client
    ):
        """Test detection of time conflicts with existing shifts."""
        Shift.objects.create(
            shiftname='Existing Shift',
            starttime=datetime_time(8, 0),
            endtime=datetime_time(16, 0),
            peoplecount=1,
            client=test_client,
            bu=test_client,
            enable=True
        )

        result = site_audit_mapper.map_coverage_plan_to_shifts(
            test_coverage_plan,
            dry_run=False
        )

        assert len(result['conflicts']) > 0
        assert any(
            conflict['type'] == 'time_overlap'
            for conflict in result['conflicts']
        )

    def test_map_coverage_plan_idempotency(
        self,
        site_audit_mapper,
        test_coverage_plan
    ):
        """Test idempotent shift creation."""
        result1 = site_audit_mapper.map_coverage_plan_to_shifts(
            test_coverage_plan,
            dry_run=False
        )

        initial_count = Shift.objects.count()
        assert result1['shifts_created'] == 2

        result2 = site_audit_mapper.map_coverage_plan_to_shifts(
            test_coverage_plan,
            dry_run=False
        )

        assert Shift.objects.count() == initial_count
        assert result2['shifts_created'] == 0

    def test_map_empty_coverage_plan(self, site_audit_mapper, test_site):
        """Test handling of empty coverage plan."""
        empty_plan = CoveragePlan.objects.create(
            site=test_site,
            shift_assignments=[],
            guard_posts=[],
            generated_by='ai'
        )

        result = site_audit_mapper.map_coverage_plan_to_shifts(
            empty_plan,
            dry_run=False
        )

        assert result['shifts_created'] == 0
        assert len(result['validation_errors']) > 0


@pytest.mark.django_db
class TestSOPToTypeAssistMapping:
    """Test SOP to TypeAssist mapping."""

    def test_map_sops_to_typeassist_success(
        self,
        site_audit_mapper,
        test_sop,
        test_client
    ):
        """Test successful mapping of SOPs to TypeAssist."""
        result = site_audit_mapper.map_sops_to_typeassist(
            [test_sop],
            dry_run=False
        )

        assert result['typeassists_created'] == 1
        assert len(result['typeassists']) == 1
        assert str(test_sop.sop_id) in result['sop_mapping']

        ta = TypeAssist.objects.filter(client=test_client).first()
        assert ta is not None
        assert ta.taname.startswith("Main Gate Access Control")
        assert 'sop_id' in ta.ta_data
        assert ta.ta_data['frequency'] == 'shift'

    def test_map_sops_dry_run(self, site_audit_mapper, test_sop):
        """Test dry run doesn't create TypeAssist entries."""
        result = site_audit_mapper.map_sops_to_typeassist(
            [test_sop],
            dry_run=True
        )

        assert result['typeassists_created'] == 1
        assert TypeAssist.objects.count() == 0

    def test_typeassist_code_generation(self, site_audit_mapper, test_sop):
        """Test TypeAssist code generation from SOP."""
        code = site_audit_mapper._generate_typeassist_code(test_sop)

        assert code.startswith('SOP_')
        assert 'GATE' in code
        assert 'SH' in code

    def test_map_multiple_sops(
        self,
        site_audit_mapper,
        test_site,
        test_zone,
        test_client
    ):
        """Test mapping multiple SOPs."""
        sops = [
            SOP.objects.create(
                site=test_site,
                zone=test_zone,
                sop_title=f"SOP {i}",
                purpose=f"Purpose {i}",
                steps=[],
                frequency='daily',
                llm_generated=True,
                approved_at=timezone.now()
            )
            for i in range(3)
        ]

        result = site_audit_mapper.map_sops_to_typeassist(
            sops,
            dry_run=False
        )

        assert result['typeassists_created'] == 3
        assert TypeAssist.objects.filter(client=test_client).count() == 3

    def test_map_sops_empty_list(self, site_audit_mapper):
        """Test handling of empty SOP list."""
        result = site_audit_mapper.map_sops_to_typeassist([], dry_run=False)

        assert result['typeassists_created'] == 0
        assert len(result['typeassists']) == 0


@pytest.mark.django_db
class TestApplySiteConfiguration:
    """Test complete site configuration application."""

    def test_apply_site_configuration_success(
        self,
        site_audit_mapper,
        test_site,
        test_coverage_plan,
        test_sop,
        test_user
    ):
        """Test successful application of complete site configuration."""
        changeset = AIChangeSet.objects.create(
            conversation_session=test_site.conversation_session,
            approved_by=test_user,
            description="Apply site audit configuration",
            status=AIChangeSet.StatusChoices.PENDING
        )

        result = site_audit_mapper.apply_site_configuration(
            test_site,
            changeset=changeset,
            dry_run=False
        )

        assert result['shifts_created'] > 0
        assert result['typeassists_created'] > 0
        assert len(result['errors']) == 0

        changeset.refresh_from_db()
        assert changeset.status == AIChangeSet.StatusChoices.APPLIED
        assert changeset.total_changes > 0

    def test_apply_site_configuration_dry_run(
        self,
        site_audit_mapper,
        test_site,
        test_coverage_plan,
        test_sop
    ):
        """Test dry run mode."""
        result = site_audit_mapper.apply_site_configuration(
            test_site,
            changeset=None,
            dry_run=True
        )

        assert Shift.objects.count() == 0
        assert TypeAssist.objects.count() == 0

    def test_apply_site_configuration_with_changeset_tracking(
        self,
        site_audit_mapper,
        test_site,
        test_coverage_plan,
        test_sop,
        test_user
    ):
        """Test changeset tracking during configuration application."""
        changeset = AIChangeSet.objects.create(
            conversation_session=test_site.conversation_session,
            approved_by=test_user,
            description="Test changeset",
            status=AIChangeSet.StatusChoices.PENDING
        )

        result = site_audit_mapper.apply_site_configuration(
            test_site,
            changeset=changeset,
            dry_run=False
        )

        assert len(result['audit_trail']) > 0

        change_records = AIChangeRecord.objects.filter(changeset=changeset)
        assert change_records.count() > 0

        assert any(
            record.model_name == 'shift'
            for record in change_records
        )

    @patch('apps.onboarding_api.integration.site_audit_mapper.transaction.atomic')
    def test_apply_site_configuration_rollback_on_error(
        self,
        mock_atomic,
        site_audit_mapper,
        test_site,
        test_coverage_plan,
        test_user
    ):
        """Test transaction rollback on database error."""
        mock_atomic.side_effect = DatabaseError("Database connection lost")

        changeset = AIChangeSet.objects.create(
            conversation_session=test_site.conversation_session,
            approved_by=test_user,
            description="Test rollback",
            status=AIChangeSet.StatusChoices.PENDING
        )

        result = site_audit_mapper.apply_site_configuration(
            test_site,
            changeset=changeset,
            dry_run=False
        )

        assert len(result['errors']) > 0

    def test_apply_site_configuration_no_coverage_plan(
        self,
        site_audit_mapper,
        test_site,
        test_sop
    ):
        """Test configuration application without coverage plan."""
        result = site_audit_mapper.apply_site_configuration(
            test_site,
            changeset=None,
            dry_run=False
        )

        assert result['shifts_created'] == 0
        assert result['typeassists_created'] > 0


@pytest.mark.django_db
class TestShiftConflictDetection:
    """Test shift time conflict detection."""

    def test_validate_no_conflicts(self, site_audit_mapper):
        """Test validation with no conflicts."""
        conflicts = site_audit_mapper._validate_shift_conflicts(
            datetime_time(6, 0),
            datetime_time(14, 0),
            Shift.objects.none(),
            "New Shift"
        )

        assert len(conflicts) == 0

    def test_validate_time_overlap_conflicts(
        self,
        site_audit_mapper,
        test_client
    ):
        """Test detection of overlapping shift times."""
        existing_shift = Shift.objects.create(
            shiftname='Day Shift',
            starttime=datetime_time(9, 0),
            endtime=datetime_time(17, 0),
            peoplecount=1,
            client=test_client,
            bu=test_client,
            enable=True
        )

        conflicts = site_audit_mapper._validate_shift_conflicts(
            datetime_time(8, 0),
            datetime_time(16, 0),
            Shift.objects.filter(client=test_client),
            "Morning Shift"
        )

        assert len(conflicts) > 0
        assert conflicts[0]['type'] == 'time_overlap'
        assert conflicts[0]['existing_shift'] == 'Day Shift'

    def test_times_overlap_detection(self, site_audit_mapper):
        """Test time overlap detection logic."""
        assert site_audit_mapper._times_overlap(
            datetime_time(8, 0),
            datetime_time(16, 0),
            datetime_time(14, 0),
            datetime_time(22, 0)
        )

        assert not site_audit_mapper._times_overlap(
            datetime_time(6, 0),
            datetime_time(14, 0),
            datetime_time(14, 0),
            datetime_time(22, 0)
        )

        assert not site_audit_mapper._times_overlap(
            datetime_time(6, 0),
            datetime_time(10, 0),
            datetime_time(14, 0),
            datetime_time(18, 0)
        )


@pytest.mark.django_db
class TestTimeParsingAndValidation:
    """Test time parsing and validation utilities."""

    def test_parse_valid_time(self, site_audit_mapper):
        """Test parsing valid time strings."""
        time_obj = site_audit_mapper._parse_time("09:30")
        assert time_obj == datetime_time(9, 30)

        time_obj = site_audit_mapper._parse_time("00:00")
        assert time_obj == datetime_time(0, 0)

        time_obj = site_audit_mapper._parse_time("23:59")
        assert time_obj == datetime_time(23, 59)

    def test_parse_invalid_time(self, site_audit_mapper):
        """Test handling of invalid time strings."""
        time_obj = site_audit_mapper._parse_time("invalid")
        assert time_obj == datetime_time(0, 0)

        time_obj = site_audit_mapper._parse_time("25:00")
        assert time_obj == datetime_time(0, 0)

        time_obj = site_audit_mapper._parse_time("")
        assert time_obj == datetime_time(0, 0)