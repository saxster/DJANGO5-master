from typing import List, Tuple, Dict, Any
from django.db.models import Q
from .base_extractor import BaseDataExtractor


class GroupExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        import apps.peoples.models as pm

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = (
            pm.Pgroup.objects.select_related("client", "identifier", "bu")
            .filter(
                ~Q(id=-1),
                bu_id__in=site_ids,
                identifier__tacode="PEOPLEGROUP",
                client_id=session_data["client_id"],
            )
            .values_list(
                "id", "groupname", "identifier__tacode",
                "client__bucode", "bu__bucode", "enable",
            )
        )
        return list(objs)


__all__ = ['GroupExtractor']