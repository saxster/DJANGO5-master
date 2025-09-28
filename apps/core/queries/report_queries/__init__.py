"""
Report query repository - unified interface.

Provides access to all report query modules through a single class interface.
"""

from .task_reports import TaskReports
from .tour_reports import TourReports
from .ppm_logsheet_reports import PPMLogsheetReports
from .asset_reports import AssetReports
from .ticket_workorder_reports import TicketWorkorderReports
from .attendance_reports import AttendanceReports
from .site_reports import SiteReports

__all__ = [
    'ReportQueryRepository',
    'TaskReports',
    'TourReports',
    'PPMLogsheetReports',
    'AssetReports',
    'TicketWorkorderReports',
    'AttendanceReports',
    'SiteReports',
]


class ReportQueryRepository:
    """
    Unified repository for all report queries.

    Delegates to domain-specific report classes while maintaining
    backward compatibility with existing code.
    """

    tasksummary_report = staticmethod(TaskReports.tasksummary_report)
    listoftasks_report = staticmethod(TaskReports.listoftasks_report)

    toursummary_report = staticmethod(TourReports.toursummary_report)
    listoftours_report = staticmethod(TourReports.listoftours_report)
    staticdetailedtoursummary_report = staticmethod(TourReports.staticdetailedtoursummary_report)
    dynamicdetailedtoursummary_report = staticmethod(TourReports.dynamicdetailedtoursummary_report)
    dynamictourlist_report = staticmethod(TourReports.dynamictourlist_report)
    statictourlist_report = staticmethod(TourReports.statictourlist_report)

    ppmsummary_report = staticmethod(PPMLogsheetReports.ppmsummary_report)
    logsheet_report = staticmethod(PPMLogsheetReports.logsheet_report)

    assetwisetaskstatus_report = staticmethod(AssetReports.assetwisetaskstatus_report)
    peopleqr_report = staticmethod(AssetReports.peopleqr_report)

    listoftickets_report = staticmethod(TicketWorkorderReports.listoftickets_report)
    workorderlist_report = staticmethod(TicketWorkorderReports.workorderlist_report)

    peopleattendancesummary_report = staticmethod(AttendanceReports.peopleattendancesummary_report)

    sitereport_report = staticmethod(SiteReports.sitereport_report)
    sitevisitreport_report = staticmethod(SiteReports.sitevisitreport_report)
    rp_sitevisitreport_report = staticmethod(SiteReports.rp_sitevisitreport_report)