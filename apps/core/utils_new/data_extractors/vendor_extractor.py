from typing import List, Tuple, Dict, Any
from django.db.models import Q
from .base_extractor import BaseDataExtractor
from apps.core.utils_new.gps_utils import add_gps_coordinates_annotation


class VendorExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        import apps.work_order_management.models as wom

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = wom.Vendor.objects.select_related("parent", "type", "bu").filter(
            ~Q(code="NONE"),
            bu_id__in=site_ids,
            client_id=session_data["client_id"]
        )

        objs = add_gps_coordinates_annotation(objs, 'gpslocation')

        objs = objs.values_list(
            "id", "code", "name", "type__tacode", "address",
            "email", "show_to_all_sites", "mobno", "bu__bucode",
            "client__bucode", "coordinates", "enable",
        )

        return list(objs)


__all__ = ['VendorExtractor']