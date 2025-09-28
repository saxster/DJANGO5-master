"""
Test suite for queries refactoring - validates backward compatibility.

Ensures that the refactored modular query structure maintains
full backward compatibility with existing code.
"""

import pytest
from django.test import TestCase


class QueryRefactoringBackwardCompatibilityTest(TestCase):
    """Test backward compatibility of refactored queries."""

    def test_import_query_repository_from_queries(self):
        """Test that QueryRepository can be imported from queries module."""
        from apps.core.queries import QueryRepository
        self.assertIsNotNone(QueryRepository)

    def test_import_report_query_repository_from_queries(self):
        """Test that ReportQueryRepository can be imported from queries module."""
        from apps.core.queries import ReportQueryRepository
        self.assertIsNotNone(ReportQueryRepository)

    def test_import_get_query_function(self):
        """Test that get_query function can be imported."""
        from apps.core.queries import get_query
        self.assertIsNotNone(get_query)
        self.assertTrue(callable(get_query))

    def test_import_tree_traversal_helper(self):
        """Test that TreeTraversal helper can be imported."""
        from apps.core.queries import TreeTraversal
        self.assertIsNotNone(TreeTraversal)

    def test_import_attachment_helper(self):
        """Test that AttachmentHelper can be imported."""
        from apps.core.queries import AttachmentHelper
        self.assertIsNotNone(AttachmentHelper)

    def test_query_repository_has_expected_methods(self):
        """Test that QueryRepository has all expected static methods."""
        from apps.core.queries import QueryRepository

        expected_methods = [
            'get_web_caps_for_client',
            'get_childrens_of_bt',
            'tsitereportdetails',
            'sitereportlist',
            'incidentreportlist',
            'workpermitlist',
            'tasksummary',
            'asset_status_period',
            'all_asset_status_duration',
            'all_asset_status_duration_count',
            'get_ticketlist_for_escalation',
            'ticketmail',
        ]

        for method_name in expected_methods:
            self.assertTrue(
                hasattr(QueryRepository, method_name),
                f"QueryRepository missing method: {method_name}"
            )
            method = getattr(QueryRepository, method_name)
            self.assertTrue(callable(method), f"{method_name} is not callable")

    def test_report_query_repository_has_expected_methods(self):
        """Test that ReportQueryRepository has all expected report methods."""
        from apps.core.queries import ReportQueryRepository

        expected_methods = [
            'tasksummary_report',
            'toursummary_report',
            'listoftasks_report',
            'listoftours_report',
            'ppmsummary_report',
            'listoftickets_report',
            'workorderlist_report',
            'sitereport_report',
            'sitevisitreport_report',
            'peopleqr_report',
            'assetwisetaskstatus_report',
            'staticdetailedtoursummary_report',
            'dynamicdetailedtoursummary_report',
            'logsheet_report',
            'rp_sitevisitreport_report',
            'dynamictourlist_report',
            'statictourlist_report',
            'peopleattendancesummary_report',
        ]

        for method_name in expected_methods:
            self.assertTrue(
                hasattr(ReportQueryRepository, method_name),
                f"ReportQueryRepository missing method: {method_name}"
            )
            method = getattr(ReportQueryRepository, method_name)
            self.assertTrue(callable(method), f"{method_name} is not callable")

    def test_get_query_function_signature(self):
        """Test that get_query function has correct signature."""
        from apps.core.queries import get_query
        import inspect

        sig = inspect.signature(get_query)
        self.assertIn('query_name', sig.parameters)

    def test_domain_specific_classes_exist(self):
        """Test that domain-specific query classes exist."""
        from apps.core.queries.capability_queries import CapabilityQueries
        from apps.core.queries.asset_queries import AssetQueries
        from apps.core.queries.job_queries import JobQueries
        from apps.core.queries.ticket_queries import TicketQueries

        self.assertIsNotNone(CapabilityQueries)
        self.assertIsNotNone(AssetQueries)
        self.assertIsNotNone(JobQueries)
        self.assertIsNotNone(TicketQueries)

    def test_report_domain_classes_exist(self):
        """Test that report domain classes exist."""
        from apps.core.queries.report_queries.task_reports import TaskReports
        from apps.core.queries.report_queries.tour_reports import TourReports
        from apps.core.queries.report_queries.ppm_logsheet_reports import PPMLogsheetReports
        from apps.core.queries.report_queries.asset_reports import AssetReports
        from apps.core.queries.report_queries.ticket_workorder_reports import TicketWorkorderReports
        from apps.core.queries.report_queries.attendance_reports import AttendanceReports
        from apps.core.queries.report_queries.site_reports import SiteReports

        self.assertIsNotNone(TaskReports)
        self.assertIsNotNone(TourReports)
        self.assertIsNotNone(PPMLogsheetReports)
        self.assertIsNotNone(AssetReports)
        self.assertIsNotNone(TicketWorkorderReports)
        self.assertIsNotNone(AttendanceReports)
        self.assertIsNotNone(SiteReports)


@pytest.mark.unit
class QueryModuleStructureTest(TestCase):
    """Test the structure and organization of refactored query modules."""

    def test_all_query_files_under_200_lines(self):
        """Validate that all query files comply with 200-line limit."""
        import os
        from pathlib import Path

        queries_dir = Path(__file__).parent.parent / 'queries'
        violations = []

        for py_file in queries_dir.rglob('*.py'):
            if py_file.name == '__pycache__':
                continue

            with open(py_file, 'r') as f:
                line_count = len(f.readlines())

            if line_count > 200:
                violations.append(f"{py_file.relative_to(queries_dir)}: {line_count} lines")

        self.assertEqual(
            len(violations), 0,
            f"Files exceeding 200-line limit:\n" + "\n".join(violations)
        )

    def test_no_generic_exception_handling(self):
        """Validate that refactored code doesn't use generic Exception catching."""
        import os
        from pathlib import Path
        import re

        queries_dir = Path(__file__).parent.parent / 'queries'
        violations = []

        generic_except_pattern = re.compile(r'except\s+Exception\s*:')

        for py_file in queries_dir.rglob('*.py'):
            if py_file.name.startswith('__'):
                continue

            with open(py_file, 'r') as f:
                content = f.read()

            if generic_except_pattern.search(content):
                violations.append(str(py_file.relative_to(queries_dir)))

        self.assertEqual(
            len(violations), 0,
            f"Files with generic exception handling:\n" + "\n".join(violations)
        )