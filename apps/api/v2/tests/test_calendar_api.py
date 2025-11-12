"""Tests for calendar API endpoint."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.calendar_view.constants import CalendarEntityType, CalendarEventStatus, CalendarEventType
from apps.calendar_view.types import CalendarAggregationResult, CalendarEvent
from apps.client_onboarding.models.business_unit.bt_model import Bt
from apps.peoples.models import People
from apps.tenants.models import Tenant


@override_settings(TENANT_MANAGER_ALLOW_UNSCOPED=True)
class CalendarAPITests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(tenantname="Test", subdomain_prefix="test-tenant")
        self.client_bt = Bt.objects.create(tenant=self.tenant, bucode="C1", buname="Client One")
        self.site_bt = Bt.objects.create(tenant=self.tenant, bucode="S1", buname="Site One", parent=self.client_bt)
        self.user = People.objects.create(
            tenant=self.tenant,
            peoplecode="P001",
            peoplename="Calendar Tester",
            loginid="calendar.user",
            email="calendar@example.com",
            deviceid="device-1",
        )
        self.user.client_id = self.client_bt.id
        self.user.bu_id = self.site_bt.id

    def test_events_endpoint_returns_payload(self):
        url = reverse("api_v2:calendar:events")
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=1)

        aggregation_result = CalendarAggregationResult(
            events=[
                CalendarEvent(
                    id="jobneed:1",
                    event_type=CalendarEventType.TASK,
                    status=CalendarEventStatus.COMPLETED,
                    title="Sample Task",
                    start=start,
                    related_entity_type=CalendarEntityType.JOBNEED,
                    metadata={"priority": "HIGH"},
                )
            ],
            summary={"by_type": {"TASK": 1}, "by_status": {"COMPLETED": 1}},
        )

        with patch("apps.api.v2.views.calendar_views.CalendarAggregationService.get_events", return_value=aggregation_result):
            self.client.force_authenticate(user=self.user)
            response = self.client.get(
                url,
                {
                    "start": start.isoformat(),
                    "end": end.isoformat(),
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["success"])
        data = response.data["data"]
        self.assertEqual(data["count"], 1)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["by_type"]["TASK"], 1)
        self.assertEqual(data["results"][0]["title"], "Sample Task")
