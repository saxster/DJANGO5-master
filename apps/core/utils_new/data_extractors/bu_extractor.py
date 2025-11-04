from typing import List, Tuple, Dict, Any
from django.db.models import F, Case, When, Value, CharField
from .base_extractor import BaseDataExtractor


class BuExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.client_onboarding.models import Bt, Shift
from apps.core_onboarding.models import TypeAssist, GeofenceMaster, Bu

        self._validate_session_data(session_data)

        buids = ob.Bt.objects.get_whole_tree(clientid=session_data["client_id"])
        objs = (
            ob.Bt.objects.select_related("parent", "identifier", "butype", "people")
            .filter(id__in=buids)
            .exclude(identifier__tacode="CLIENT")
            .annotate(
                address=F("bupreferences__address"),
                state=F("bupreferences__address2__state"),
                country=F("bupreferences__address2__country"),
                city=F("bupreferences__address2__city"),
                latlng=F("bupreferences__address2__latlng"),
                siteincharge_peoplecode=Case(
                    When(siteincharge__enable=True, then=F("siteincharge__peoplecode")),
                    default=Value(None),
                    output_field=CharField(),
                ),
            )
            .values_list(
                "id", "bucode", "buname", "parent__bucode",
                "identifier__tacode", "butype__tacode",
                "siteincharge_peoplecode", "solid", "enable",
                "latlng", "address", "city", "state", "country",
            )
        )
        return list(objs)


__all__ = ['BuExtractor']