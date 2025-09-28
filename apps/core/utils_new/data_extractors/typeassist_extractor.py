from typing import List, Tuple, Dict, Any
from django.db.models import Q
from .base_extractor import BaseDataExtractor


class TypeAssistExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        import apps.onboarding.models as ob

        self._validate_session_data(session_data)

        objs = (
            ob.TypeAssist.objects.select_related("parent", "tatype", "cuser", "muser")
            .filter(
                ~Q(tacode="NONE"),
                ~Q(tatype__tacode="NONE"),
                Q(client_id=session_data["client_id"]),
                ~Q(client_id=1),
                enable=True,
            )
            .values_list("id", "taname", "tacode", "tatype__tacode", "client__bucode")
        )
        return list(objs)


__all__ = ['TypeAssistExtractor']