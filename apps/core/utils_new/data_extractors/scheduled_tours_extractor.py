from typing import List, Tuple, Dict, Any
from django.db.models import Q, F, Case, When, Value, CharField
from django.db.models.functions import Cast, Concat, TruncSecond
from .base_extractor import BaseDataExtractor


class ScheduledToursExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models import Job

        self._validate_session_data(session_data)

        objs = Job.objects.select_related(
            "pgroup", "people", "asset", "bu", "qset", "ticketcategory"
        ).annotate(
            assignedto=Case(
                When(
                    Q(pgroup_id=1) | Q(pgroup_id__isnull=True),
                    then=Concat(F("people__peoplename"), Value(" [PEOPLE]")),
                ),
                When(
                    Q(people_id=1) | Q(people_id__isnull=True),
                    then=Concat(F("pgroup__groupname"), Value(" [GROUP]")),
                ),
            ),
            formatted_fromdate=Cast(TruncSecond("fromdate"), output_field=CharField()),
            formatted_uptodate=Cast(TruncSecond("uptodate"), output_field=CharField()),
            formatted_starttime=Cast(TruncSecond("starttime"), output_field=CharField()),
            formatted_endtime=Cast(TruncSecond("endtime"), output_field=CharField()),
        ).filter(
            Q(parent__jobname="NONE") | Q(parent_id=1),
            ~Q(jobname="NONE") | ~Q(id=1),
            bu_id__in=session_data["assignedsites"],
            client_id=session_data["client_id"],
            identifier__exact="INTERNALTOUR",
            enable=True,
        ).values_list(
            "id", "jobname", "jobdesc", "cron", "asset__assetcode",
            "qset__qsetname", "people__peoplecode", "pgroup__groupname",
            "planduration", "gracetime", "expirytime", "ticketcategory__tacode",
            "formatted_fromdate", "formatted_uptodate", "scantype",
            "client__bucode", "bu__bucode", "priority", "seqno",
            "formatted_starttime", "formatted_endtime", "parent__jobname",
        )

        return list(objs)


__all__ = ['ScheduledToursExtractor']