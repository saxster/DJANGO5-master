from typing import List, Tuple, Dict, Any
from .base_extractor import BaseDataExtractor


class GroupBelongingExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        import apps.peoples.models as pm

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        objs = (
            pm.Pgbelonging.objects.select_related("pgroup", "people")
            .filter(
                bu_id__in=site_ids,
                client_id=session_data["client_id"],
            )
            .values_list(
                "id", "pgroup__groupname", "people__peoplecode",
                "assignsites__bucode", "client__bucode", "bu__bucode",
            )
        )
        return list(objs)


__all__ = ['GroupBelongingExtractor']