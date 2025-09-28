from typing import List, Tuple, Dict, Any
from django.db.models import Case, When, Value, CharField
from django.db.models.functions import Cast, Substr, StrIndex
from .base_extractor import BaseDataExtractor

class QuestionSetBelongingExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models import QuestionSetBelonging

        self._validate_session_data(session_data)
        site_ids = self._get_site_ids(session_data)
        objs = (
            QuestionSetBelonging.objects.select_related("qset", "question", "client", "bu")
            .filter(
                bu_id__in=site_ids,
                client_id=session_data["client_id"],
            )
            .annotate(
                alert_above=Case(
                    When(
                        alerton__startswith="<",
                        then=Substr("alerton", 2, StrIndex(Substr("alerton", 2), Value(",")) - 1),
                    ),
                    When(
                        alerton__contains=",<",
                        then=Substr("alerton", StrIndex("alerton", Value(",<")) + 2),
                    ),
                    default=Value(None),
                    output_field=CharField(),
                ),
                alert_below=Case(
                    When(
                        alerton__contains=">",
                        then=Substr("alerton", StrIndex("alerton", Value(">")) + 1),
                    ),
                    default=Value(None),
                    output_field=CharField(),
                ),
                min_str=Cast("min", output_field=CharField()),
                max_str=Cast("max", output_field=CharField()),
            )
            .values_list(
                "id", "question__quesname", "qset__qsetname", "client__bucode",
                "bu__bucode", "answertype", "seqno", "isavpt", "min_str",
                "max_str", "alert_above", "alert_below", "options",
                "alerton", "ismandatory", "avpttype",
            )
        )
        return list(objs)

__all__ = ['QuestionSetBelongingExtractor']