"""
Query repository package - modular and maintainable.

This package provides domain-specific query repositories that replace
the monolithic queries.py file while maintaining backward compatibility.

Architecture:
    - base.py: Shared utilities (TreeTraversal, AttachmentHelper)
    - capability_queries.py: Capability and BT hierarchy queries
    - asset_queries.py: Asset and asset log queries
    - job_queries.py: Job, task, and tour queries
    - ticket_queries.py: Ticket and escalation queries
    - report_queries/: Domain-specific report queries

All query classes follow the Single Responsibility Principle and are
under 200 lines per file as required by .claude/rules.md.
"""

from typing import List, Dict, Union
import logging

from .base import TreeTraversal, AttachmentHelper
from .capability_queries import CapabilityQueries
from .asset_queries import AssetQueries
from .job_queries import JobQueries
from .ticket_queries import TicketQueries
from .report_queries import ReportQueryRepository

logger = logging.getLogger(__name__)

__all__ = [
    'TreeTraversal',
    'AttachmentHelper',
    'QueryRepository',
    'ReportQueryRepository',
    'get_query',
]


class QueryRepository:
    """
    Unified repository for operational queries.

    Delegates to domain-specific query classes while maintaining
    backward compatibility with existing code.
    """

    get_web_caps_for_client = staticmethod(CapabilityQueries.get_web_caps_for_client)
    get_childrens_of_bt = staticmethod(CapabilityQueries.get_childrens_of_bt)

    asset_status_period = staticmethod(AssetQueries.asset_status_period)
    all_asset_status_duration = staticmethod(AssetQueries.all_asset_status_duration)
    all_asset_status_duration_count = staticmethod(AssetQueries.all_asset_status_duration_count)

    tsitereportdetails = staticmethod(JobQueries.tsitereportdetails)
    sitereportlist = staticmethod(JobQueries.sitereportlist)
    incidentreportlist = staticmethod(JobQueries.incidentreportlist)
    workpermitlist = staticmethod(JobQueries.workpermitlist)
    tasksummary = staticmethod(JobQueries.tasksummary)

    get_ticketlist_for_escalation = staticmethod(TicketQueries.get_ticketlist_for_escalation)
    ticketmail = staticmethod(TicketQueries.ticketmail)


def get_query(query_name: str, **kwargs) -> Union[List[Dict], str]:
    """
    Execute queries by name with parameters.

    This function provides backward compatibility with the original get_query
    interface while using the new modular implementation.

    Examples:
        reports = get_query('sitereportlist', bu_ids=[1,2,3], start_date=date1, end_date=date2)
        capabilities = get_query('get_web_caps_for_client')

    Args:
        query_name: Name of the query to execute
        **kwargs: Query-specific parameters

    Returns:
        Query results as list of dicts or error string

    Raises:
        ValueError: If query name is not recognized
    """
    repo = QueryRepository()
    report_repo = ReportQueryRepository()

    query_mapping = {
        'get_web_caps_for_client': repo.get_web_caps_for_client,
        'get_childrens_of_bt': repo.get_childrens_of_bt,
        'tsitereportdetails': repo.tsitereportdetails,
        'sitereportlist': repo.sitereportlist,
        'incidentreportlist': repo.incidentreportlist,
        'workpermitlist': repo.workpermitlist,
        'get_ticketlist_for_escalation': repo.get_ticketlist_for_escalation,
        'ticketmail': repo.ticketmail,
        'tasksummary': repo.tasksummary,
        'asset_status_period': repo.asset_status_period,
        'all_asset_status_duration': repo.all_asset_status_duration,
        'all_asset_status_duration_count': repo.all_asset_status_duration_count,
        'TASKSUMMARY': report_repo.tasksummary_report,
        'TOURSUMMARY': report_repo.toursummary_report,
        'LISTOFTASKS': report_repo.listoftasks_report,
        'LISTOFTOURS': report_repo.listoftours_report,
        'PPMSUMMARY': report_repo.ppmsummary_report,
        'LISTOFTICKETS': report_repo.listoftickets_report,
        'WORKORDERLIST': report_repo.workorderlist_report,
        'SITEREPORT': report_repo.sitereport_report,
        'SITEVISITREPORT': report_repo.sitevisitreport_report,
        'PEOPLEQR': report_repo.peopleqr_report,
        'ASSETWISETASKSTATUS': report_repo.assetwisetaskstatus_report,
        'STATICDETAILEDTOURSUMMARY': report_repo.staticdetailedtoursummary_report,
        'DYNAMICDETAILEDTOURSUMMARY': report_repo.dynamicdetailedtoursummary_report,
        'LOGSHEET': report_repo.logsheet_report,
        'RP_SITEVISITREPORT': report_repo.rp_sitevisitreport_report,
        'DYNAMICTOURLIST': report_repo.dynamictourlist_report,
        'STATICTOURLIST': report_repo.statictourlist_report,
        'PEOPLEATTENDANCESUMMARY': report_repo.peopleattendancesummary_report,
    }

    method = query_mapping.get(query_name)
    if not method:
        logger.warning(f"Query '{query_name}' not found in new implementation")
        raise ValueError(f"Unknown query: {query_name}")

    try:
        return method(**kwargs)
    except (ValueError, TypeError) as e:
        logger.error(f"Invalid parameters for query '{query_name}': {e}", exc_info=True)
        raise
    except (ValueError, TypeError) as e:
        logger.error(f"Error executing query '{query_name}': {e}", exc_info=True)
        raise