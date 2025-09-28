from typing import List, Tuple, Dict, Any
from django.db.models import Q, F, Func
from .base_extractor import BaseDataExtractor

class FormatListAsString(Func):
    function = "REPLACE"
    template = "(%(function)s(%(function)s(%(function)s(%(function)s(CAST(%(expressions)s AS VARCHAR), '[', ''), ']', ''), '''', ''), '\"', ''))"

class PeopleExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        import apps.peoples.models as pm

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)

        queryset = pm.People.objects.filter(
            ~Q(peoplecode="NONE"),
            client_id=session_data["client_id"]
        )

        if session_data.get("is_admin"):
            queryset = queryset.filter(bu_id__in=site_ids)
        else:
            queryset = queryset.filter(bu_id__in=session_data.get("assignedsites", []))

        objs = queryset.select_related(
            "peopletype", "bu", "client", "designation",
            "department", "worktype", "reportto",
        ).annotate(
            user_for=F("people_extras__userfor"),
            isemergencycontact=F("people_extras__isemergencycontact"),
            mobilecapability=FormatListAsString(F("people_extras__mobilecapability")),
            reportcapability=FormatListAsString(F("people_extras__reportcapability")),
            webcapability=FormatListAsString(F("people_extras__webcapability")),
            portletcapability=FormatListAsString(F("people_extras__portletcapability")),
            currentaddress=F("people_extras__currentaddress"),
            blacklist=F("people_extras__blacklist"),
            alertmails=F("people_extras__alertmails"),
        ).values_list(
            "id", "peoplecode", "peoplename", "user_for", "peopletype__tacode",
            "loginid", "gender", "mobno", "email", "dateofbirth", "dateofjoin",
            "client__bucode", "bu__bucode", "designation__tacode",
            "department__tacode", "worktype__tacode", "enable",
            "reportto__peoplename", "dateofreport", "deviceid",
            "isemergencycontact", "mobilecapability", "reportcapability",
            "webcapability", "portletcapability", "currentaddress",
            "blacklist", "alertmails",
        )
        return list(objs)

__all__ = ['PeopleExtractor']