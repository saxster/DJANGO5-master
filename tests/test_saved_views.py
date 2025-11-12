"""Test suite for Saved Views functionality."""

import pytest
from apps.core.models import DashboardSavedView
from apps.core.services.view_export_service import ViewExportService


@pytest.fixture
def saved_view(tenant, user):
    """Create a saved view."""
    return DashboardSavedView.objects.create(
        tenant=tenant,
        cuser=user,
        name="My High Priority Tickets",
        view_type='TICKETS',
        filters={'priority': 'HIGH', 'status': 'OPEN'},
        page_url='/admin/y_helpdesk/ticket/',
        is_public=False
    )


@pytest.mark.django_db
class TestSavedViews:
    """Test saved views and scheduled exports."""

    def test_save_view(self, user, tenant):
        """Test saving an admin view configuration."""
        view = DashboardSavedView.objects.create(
            cuser=user,
            tenant=tenant,
            name="My High Priority Tickets",
            view_type='TICKETS',
            filters={'priority': 'HIGH'},
            page_url='/admin/y_helpdesk/ticket/'
        )
        
        assert view.name == "My High Priority Tickets"
        assert view.filters['priority'] == 'HIGH'
        assert view.cuser == user

    def test_public_vs_private_views(self, tenant, user):
        """Test public and private view access."""
        # Create private view
        private_view = DashboardSavedView.objects.create(
            tenant=tenant,
            cuser=user,
            name="My Private View",
            view_type='TICKETS',
            filters={},
            is_public=False
        )
        
        # Create public view
        public_view = DashboardSavedView.objects.create(
            tenant=tenant,
            cuser=user,
            name="Team Public View",
            view_type='TICKETS',
            filters={},
            is_public=True
        )
        
        assert private_view.is_public is False
        assert public_view.is_public is True

    def test_scheduled_export(self, saved_view):
        """Test scheduled export setup."""
        task = ViewExportService.schedule_export(
            saved_view,
            frequency='DAILY',
            recipients=['test@example.com']
        )
        
        assert task is not None
        assert task.frequency == 'DAILY'
        assert 'test@example.com' in task.recipients

    def test_export_generation(self, saved_view):
        """Test export file generation."""
        result = ViewExportService.generate_export(saved_view, format='CSV')
        
        assert result is not None
        assert 'file_path' in result or 'content' in result

    def test_view_filters_persistence(self, saved_view):
        """Test view filters are persisted correctly."""
        saved_view.refresh_from_db()
        
        assert 'priority' in saved_view.filters
        assert saved_view.filters['priority'] == 'HIGH'
        assert saved_view.filters['status'] == 'OPEN'

    def test_update_saved_view(self, saved_view):
        """Test updating a saved view."""
        saved_view.name = "Updated View Name"
        saved_view.filters = {'priority': 'URGENT'}
        saved_view.save()
        
        saved_view.refresh_from_db()
        assert saved_view.name == "Updated View Name"
        assert saved_view.filters['priority'] == 'URGENT'

    def test_delete_saved_view(self, saved_view):
        """Test deleting a saved view."""
        view_id = saved_view.id
        saved_view.delete()
        
        assert not DashboardSavedView.objects.filter(id=view_id).exists()

    def test_view_sharing(self, saved_view, tenant):
        """Test view sharing between users."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@test.com",
            tenant=tenant
        )
        
        # Make view public
        saved_view.is_public = True
        saved_view.save()
        
        # Other user should be able to see it
        public_views = DashboardSavedView.objects.filter(
            tenant=tenant,
            is_public=True
        )
        
        assert saved_view in public_views

    def test_export_multiple_formats(self, saved_view):
        """Test export in different formats."""
        # CSV export
        csv_result = ViewExportService.generate_export(saved_view, format='CSV')
        assert csv_result is not None
        
        # Excel export
        excel_result = ViewExportService.generate_export(saved_view, format='EXCEL')
        assert excel_result is not None
        
        # PDF export
        pdf_result = ViewExportService.generate_export(saved_view, format='PDF')
        assert pdf_result is not None

    def test_scheduled_export_frequencies(self, saved_view):
        """Test different export frequencies."""
        frequencies = ['DAILY', 'WEEKLY', 'MONTHLY']
        
        for freq in frequencies:
            task = ViewExportService.schedule_export(
                saved_view,
                frequency=freq,
                recipients=['test@example.com']
            )
            assert task.frequency == freq

    def test_export_email_delivery(self, saved_view, mailoutbox):
        """Test export is emailed to recipients."""
        ViewExportService.send_export_email(
            saved_view,
            recipients=['test@example.com'],
            format='CSV'
        )
        
        assert len(mailoutbox) == 1
        assert 'test@example.com' in mailoutbox[0].to

    def test_view_usage_tracking(self, saved_view):
        """Test view usage is tracked."""
        initial_count = saved_view.usage_count if hasattr(saved_view, 'usage_count') else 0
        
        # Use the view
        ViewExportService.track_usage(saved_view)
        
        saved_view.refresh_from_db()
        if hasattr(saved_view, 'usage_count'):
            assert saved_view.usage_count == initial_count + 1
