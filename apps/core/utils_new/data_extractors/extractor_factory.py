from typing import Dict
from .base_extractor import BaseDataExtractor
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


class DataExtractorFactory:
    _extractors: Dict[str, BaseDataExtractor] = {
        'TYPEASSIST': TypeAssistExtractor(),
        'BU': BuExtractor(),
        'LOCATION': LocationExtractor(),
        'ASSET': AssetExtractor(),
        'VENDOR': VendorExtractor(),
        'PEOPLE': PeopleExtractor(),
        'QUESTION': QuestionExtractor(),
        'QUESTIONSET': QuestionSetExtractor(),
        'QUESTIONSETBELONGING': QuestionSetBelongingExtractor(),
        'GROUP': GroupExtractor(),
        'GROUPBELONGING': GroupBelongingExtractor(),
        'SCHEDULEDTASKS': ScheduledTasksExtractor(),
        'SCHEDULEDTOURS': ScheduledToursExtractor(),
    }

    @classmethod
    def get_extractor(cls, type_name: str) -> BaseDataExtractor:
        extractor = cls._extractors.get(type_name)
        if not extractor:
            raise ValueError(f"Unknown entity type: {type_name}")
        return extractor


__all__ = ['DataExtractorFactory']