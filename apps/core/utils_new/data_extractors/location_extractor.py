from typing import List, Tuple, Dict, Any
from django.db.models import Q
from .base_extractor import BaseDataExtractor
from apps.core.utils_new.gps_utils import add_gps_coordinates_annotation


class LocationExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models.location_model import Location

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = Location.objects.select_related("parent", "type", "bu").filter(
            ~Q(loccode="NONE"),
            bu_id__in=site_ids,
            client_id=session_data["client_id"]
        )

        objs = add_gps_coordinates_annotation(objs, 'gpslocation')

        objs = objs.values_list(
            "id", "loccode", "locname", "type__tacode",
            "locstatus", "iscritical", "parent__loccode",
            "bu__bucode", "client__bucode", "coordinates", "enable",
        )

        return list(objs)


__all__ = ['LocationExtractor']