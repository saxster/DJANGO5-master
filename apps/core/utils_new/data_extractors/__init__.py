"""
Data Extractors Package - Strategy Pattern Implementation.

This package implements the Strategy design pattern to replace the monolithic
get_type_data() function (827 lines) with focused, testable extractor classes.

Refactored from: apps.core.utils_new.file_utils.get_type_data() (827 lines)
Purpose: SRP and OCP compliance - each extractor handles one entity type
Compliance: .claude/rules.md Rule #7 (Model complexity limits)

Architecture:
    - BaseDataExtractor: Abstract base class with common functionality
    - DataExtractorFactory: Factory for instantiating extractors
    - Concrete Extractors: One per entity type (TypeAssist, BU, Location, etc.)

Usage:
    from apps.core.utils_new.data_extractors import get_type_data
    data = get_type_data('TYPEASSIST', session_data)

    # Or use factory directly for better control:
    from apps.core.utils_new.data_extractors import DataExtractorFactory
    extractor = DataExtractorFactory.get_extractor('TYPEASSIST')
    data = extractor.extract(session_data)
"""

from typing import List, Tuple, Dict, Any
from .base_extractor import BaseDataExtractor
from .extractor_factory import DataExtractorFactory
from .typeassist_extractor import TypeAssistExtractor
from .bu_extractor import BuExtractor
from .location_extractor import LocationExtractor
from .asset_extractor import AssetExtractor
from .vendor_extractor import VendorExtractor
from .people_extractor import PeopleExtractor
from .question_extractor import QuestionExtractor
from .questionset_extractor import QuestionSetExtractor
from .questionset_belonging_extractor import QuestionSetBelongingExtractor
from .group_extractor import GroupExtractor
from .group_belonging_extractor import GroupBelongingExtractor
from .scheduled_tasks_extractor import ScheduledTasksExtractor
from .scheduled_tours_extractor import ScheduledToursExtractor


def get_type_data(type_name: str, session_data: Dict[str, Any]) -> List[Tuple]:
    extractor = DataExtractorFactory.get_extractor(type_name)
    return extractor.extract(session_data)


__all__ = [
    'BaseDataExtractor',
    'DataExtractorFactory',
    'TypeAssistExtractor',
    'BuExtractor',
    'LocationExtractor',
    'AssetExtractor',
    'VendorExtractor',
    'PeopleExtractor',
    'QuestionExtractor',
    'QuestionSetExtractor',
    'QuestionSetBelongingExtractor',
    'GroupExtractor',
    'GroupBelongingExtractor',
    'ScheduledTasksExtractor',
    'ScheduledToursExtractor',
    'get_type_data'
]