from typing import List, Tuple, Dict, Any
from django.db.models import Case, When, Value, CharField
from django.db.models.functions import Cast, Substr, StrIndex
from .base_extractor import BaseDataExtractor


class QuestionExtractor(BaseDataExtractor):
    def extract(self, session_data: Dict[str, Any]) -> List[Tuple]:
        from apps.activity.models import Question

        self._validate_session_data(session_data)

        objs = (
            Question.objects.select_related("unit", "category", "client")
            .filter(client_id=session_data["client_id"])
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
                    default=Value("NONE"),
                    output_field=CharField(),
                ),
                alert_below=Case(
                    When(
                        alerton__contains=">",
                        then=Substr("alerton", StrIndex("alerton", Value(">")) + 1),
                    ),
                    default=Value("NONE"),
                    output_field=CharField(),
                ),
                min_str=Cast("min", output_field=CharField()),
                max_str=Cast("max", output_field=CharField()),
            )
            .values_list(
                "id", "quesname", "answertype", "min_str", "max_str",
                "alert_above", "alert_below", "isworkflow", "options",
                "alerton", "enable", "isavpt", "avpttype",
                "client__bucode", "unit__tacode", "category__tacode",
            )
        )
        return list(objs)


__all__ = ['QuestionExtractor']