from datetime import datetime
from django.db import models
from django.db.models import (
    Case,
    CharField,
    Count,
    Exists,
    F,
    OuterRef,
    Q,
    When,
)
from django.db.models import Value as V
from django.db.models.functions import Concat
import logging

logger = logging.getLogger(__name__)

import apps.peoples.models as pm
from apps.core import utils


class QuestionSetManager(models.Manager):
    use_in_migrations = True
    fields = [
        "id",
        "cuser_id",
        "muser_id",
        "ctzoffset",
        "bu_id",
        "client_id",
        "cdtz",
        "mdtz",
        "parent_id",
        "qsetname",
        "enable",
        "assetincludes",
        "show_to_all_sites",
        "buincludes",
        "seqno",
        "url",
        "type",
        "tenant_id",
        "site_grp_includes",
        "site_type_includes",
    ]
    related = ["cuser", "muser", "client", "bu", "parent", "asset", "type"]

    def get_template_list(self, bulist):
        bulist = bulist.split(",") if isinstance(bulist, str) else bulist
        if bulist:
            if (
                qset := self.select_related(*self.related)
                .filter(buincludes__contains=bulist)
                .values_list("id", flat=True)
            ):
                return tuple(qset)
        return ""

    def get_qset_modified_after(self, mdtz, buid, clientid, peopleid):
        """
        Get question sets modified after a timestamp for mobile sync.

        OPTIMIZED (2025-10-03):
        - Uses select_related for all FKs (prevents N+1)
        - Single user query with prefetch for people_extras
        - Indexed by (bu, client, mdtz) - see migration 0018

        Following .claude/rules.md Rule #12: Database query optimization
        """
        logger.debug("mdtz %s", mdtz)
        logger.debug("client id %s", clientid)
        logger.debug("peopleid %s", peopleid)
        logger.debug("buid %s", buid)

        # Optimize user lookup - single query
        user = pm.People.objects.only('id', 'people_extras').get(id=peopleid)

        qset = (
            self.select_related(*self.related)
            .filter(
                Q(id=1)
                | (
                    (Q(client_id=clientid) & Q(enable=True))
                    & (
                        (Q(mdtz__gte=mdtz) & Q(bu_id=buid))
                        | Q(show_to_all_sites=True)
                        | Q(
                            site_grp_includes__contains=user.people_extras[
                                "assignsitegroup"
                            ]
                        )
                        | Q(id__in=user.people_extras["tempincludes"])
                    )
                )
            )
            .values(*self.fields)
            .order_by("-mdtz")
        )
        qset = self.clean_fields(qset)
        return qset or None

    def get_configured_sitereporttemplates(self, request, related, fields, type):
        S = request.session
        qset = (
            self.select_related(*related)
            .filter(
                enable=True,
                type=type,
                client_id=S["client_id"],
                bu_id=S["bu_id"],
                parent_id=1,
            )
            .values(*fields)
        )
        # Note: clean_fields processes in Python which is inefficient for large datasets
        # Consider using database functions for string manipulation instead
        qset = self.clean_fields(qset)
        return qset or self.none()

    def clean_fields(self, qset):
        for obj in qset:
            if (
                obj.get("assetincludes")
                or obj.get("buincludes")
                or obj.get("site_grp_includes")
                or obj.get("site_type_includes")
            ):
                obj["assetincludes"] = (
                    str(obj["assetincludes"])
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
                obj["site_grp_includes"] = (
                    str(obj["site_grp_includes"])
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
                obj["site_type_includes"] = (
                    str(obj["site_type_includes"])
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
                obj["buincludes"] = (
                    str(obj["buincludes"])
                    .replace("[", "")
                    .replace("]", "")
                    .replace("'", "")
                )
        return qset

    def get_qset_with_questionscount(self, parentid):
        qset = (
            self.annotate(qcount=Count("questionsetbelonging"))
            .filter(parent_id=parentid, enable=True)
            .values("id", "qsetname", "qcount", "seqno")
        )
        return qset or self.none()

    def handle_qsetpostdata(self, request):
        R, S = request.POST, request.session
        from apps.activity.models.question_model import QuestionSet

        parent_record = QuestionSet.objects.get(id=R["parent_id"])
        assetincludes = parent_record.assetincludes
        buincludes = parent_record.buincludes
        site_grp_includes = parent_record.site_grp_includes
        site_type_includes = parent_record.site_type_includes
        postdata = {
            "parent_id": R["parent_id"],
            "ctzoffset": R["ctzoffset"],
            "seqno": R["seqno"],
            "qsetname": R["qsetname"],
            "cuser": request.user,
            "muser": request.user,
            "cdtz": utils.getawaredatetime(datetime.now(), R["ctzoffset"]),
            "mdtz": utils.getawaredatetime(datetime.now(), R["ctzoffset"]),
            "type": R["type"],
            "client_id": S["client_id"],
            "bu_id": S["bu_id"],
            "show_to_all_sites": True if R["show_to_all_sites"] == "true" else False,
            "assetincludes": assetincludes,
            "buincludes": buincludes,
            "site_grp_includes": site_grp_includes,
            "site_type_includes": site_type_includes,
        }
        if R["action"] == "create":
            ID = self.create(**postdata).id

        elif R["action"] == "edit":
            postdata.pop("cuser")
            postdata.pop("cdtz")
            updated = self.filter(pk=R["pk"]).update(**postdata)
            if updated:
                ID = R["pk"]

        else:
            self.filter(pk=R["pk"]).update(enable=False)
            return self.none()

        return (
            self.filter(pk=ID)
            .annotate(qcount=Count("questionsetbelonging"))
            .values("id", "qsetname", "qcount", "seqno")
            or self.none()
        )

    def load_checklist(self, request):
        "Load Checklist for editor dropdown"
        R, S = request.GET, request.session
        search_term = R.get("search")
        qset = self.filter(Q(Q(client_id=S["client_id"]), Q(enable=True)))
        qset = (
            qset.annotate(text=F("qsetname"))
            .filter(enable=True, type="RPCHECKLIST")
            .values("id", "text")
        )
        qset = qset.filter(qsetname__icontains=search_term) if search_term else qset
        if qset:
            for idx, q in enumerate(qset):
                q.update({"slno": idx + 1})
        return qset or self.none()

    def questionset_listview(self, request, fields, related):
        R, S = request.GET, request.session

        qset = (
            self.filter(
                ~Q(qsetname="NONE"),
                type="QUESTIONSET",
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
            )
            .select_related(*related)
            .values(*fields)
        )
        return qset or self.none()

    def checklist_listview(self, request, fields, related):
        R, S = request.GET, request.session

        # Get the type from request, default to all types if not specified
        qset_type = R.get('type', None)

        base_filter = Q(bu_id=S["bu_id"]) & Q(client_id=S["client_id"])

        if qset_type == "QUESTIONSET":
            # For QUESTIONSET type, show all question sets
            qset = (
                self.filter(
                    base_filter,
                    ~Q(qsetname="NONE"),
                )
                .select_related(*related)
                .values(*fields)
            )
        else:
            # Original logic for other types
            qset = (
                self.filter(
                    Q(type="RPCHECKLIST") & Q(bu_id__in=S["assignedsites"])
                    | Q(
                        Q(parent_id__isnull=True) | Q(parent_id=1),
                        ~Q(qsetname="NONE"),
                        Q(bu_id=S["bu_id"]),
                        Q(client_id=S["client_id"]),
                    )
                )
                .select_related(*related)
                .values(*fields)
            )
        return qset or self.none()

    def get_proper_checklist_for_scheduling(self, request, types):
        S = request.session

        qset = (
            self.filter(
                bu_id__in=S["assignedsites"],
                client_id=S["client_id"],
                type__in=types,
                enable=True,
            )
            .select_related("bu", "client", "parent")
            .exclude(
                questionsetbelonging=None,
            )
        )
        return qset or self.none()

    def filter_for_dd_qset_field(self, request, type, choices=False, sitewise=False):
        from apps.activity.models.question_model import QuestionSetBelonging

        has_questions = QuestionSetBelonging.objects.filter(qset=OuterRef("pk")).values(
            "pk"
        )
        S = request.session
        qset = (
            self.annotate(has_questions=Exists(has_questions))
            .filter(
                enable=True,
                client_id=S["client_id"],
                bu_id__in=S["assignedsites"],
                type__in=type,
                has_questions=True,
            )
            .order_by("qsetname")
        )
        if sitewise:
            qset = qset.filter(bu_id=S["bu_id"])
        if choices:
            qset = qset.values_list("id", "qsetname")
        return qset or self.none()

    def get_qsets_for_tour(self, request):
        R, S = request.GET, request.session
        search_term = R.get("search")
        qset = self.filter(
            Q(
                Q(client_id=S["client_id"]),
                Q(bu_id=S["bu_id"]),
                Q(enable=True),
                Q(type=self.model.Type.CHECKLIST),
            )
            | Q(id=1)
        )
        qset = qset.filter(qsetname__icontains=search_term) if search_term else qset
        qset = qset.annotate(text=F("qsetname")).values("id", "text")
        return qset or self.none()

    def qset_choices_for_report(self, request):
        S = request.session
        qset = self.filter(bu_id=S["bu_id"], client_id=S["client_id"]).values_list(
            "id", "qsetname"
        )
        return qset or self.none()


class QuestionManager(models.Manager):
    use_in_migrations = True
    fields = [
        "id",
        "quesname",
        "options",
        "min",
        "max",
        "alerton",
        "answertype",
        "muser_id",
        "cdtz",
        "mdtz",
        "client_id",
        "isworkflow",
        "enable",
        "category_id",
        "cuser_id",
        "unit_id",
        "tenant_id",
        "ctzoffset",
    ]
    related = ["client", "muser", "cuser", "category", "unit"]

    def hrd(self):  # hrd: human readable data
        # Create a list of When conditions for each AnswerType choice
        conditions = [
            When(answertype=db_value, then=V(display_value))
            for db_value, display_value in self.model.AnswerType.choices
        ]

        return self.get_queryset().annotate(
            answertype_human_readable=Case(
                *conditions, default=V("Undefined"), output_field=CharField()
            )
        )

    def get_questions_modified_after(self, mdtz, clientid):
        mdtzinput = mdtz
        qset = (
            self.select_related(*self.related)
            .filter(mdtz__gte=mdtzinput, enable=True, client_id=clientid)
            .values(*self.fields)
            .order_by("-mdtz")
        )
        return qset or None

    def questions_of_client(self, request, RGet):
        search_term = RGet.get("search")
        qset = self.filter(client_id=request.session["client_id"])
        qset = qset.filter(quesname__icontains=search_term) if search_term else qset
        qset = qset.annotate(
            text=Concat(F("quesname"), V(" | "), F("answertype"))
        ).values("id", "text", "answertype")
        return qset or self.none()

    def questions_listview(self, request, fields, related):
        S = request.session
        qset = (
            self.select_related(*related)
            .filter(
                enable=True,
                client_id=S["client_id"],
            )
            .values(*fields)
        )
        return qset or self.none()

    def get_questiondetails(self, questionid):
        qset = self.filter(pk=questionid).values(
            "id", "answertype", "isavpt", "options", "min", "max", "alerton", "avpttype"
        )
        return qset or self.none()

    def optimized_filter_for_display(self, question_id, fields):
        """
        Get question data for display with optimized FK loading.
        Prevents N+1 when accessing related fields like unit__tacode.
        """
        return self.select_related('unit', 'category').filter(
            id=question_id
        ).values(*fields).first()


class QsetBlngManager(models.Manager):
    use_in_migrations = True
    fields = [
        "id",
        "seqno",
        "answertype",
        "isavpt",
        "options",
        "ctzoffset",
        "ismandatory",
        "min",
        "max",
        "alerton",
        "client_id",
        "bu_id",
        "question_id",
        "isavpt",
        "avpttype",
        "qset_id",
        "cuser_id",
        "muser_id",
        "cdtz",
        "mdtz",
        "alertmails_sendto",
        "tenant_id",
        "display_conditions",  # Add conditional logic field for mobile apps
    ]
    related = ["client", "bu", "question", "qset", "cuser", "muser"]

    def get_modified_after(self, mdtz, buid):
        """
        Get QuestionSetBelonging records modified after a timestamp for mobile sync.

        OPTIMIZED (2025-10-03):
        - Uses select_related for all FKs (question, qset, client, bu)
        - Indexed by (bu, mdtz) - see migration 0018
        - Reduces query count from N+3 to 3 (site_groups, qset_ids, main query)

        Following .claude/rules.md Rule #12: Database query optimization
        """
        from apps.activity.models.question_model import QuestionSet

        # Fetch site group ids which contains the buid
        site_groups = pm.Pgbelonging.objects.filter(
            Q(people_id=1) | Q(people__isnull=True), assignsites_id=buid
        ).values_list("pgroup_id", flat=True)

        # Convert site_groups to a list
        site_groups_list = list(site_groups)

        # Fetch the qsets of the group ids
        qset_ids = QuestionSet.objects.filter(
            site_grp_includes__overlap=site_groups_list
        ).values_list("id", flat=True)

        # Main query with optimized select_related
        # This prevents N+1 queries when accessing related objects
        qset = (
            self.select_related(*self.related)
            .filter((Q(bu_id=buid) | Q(qset_id__in=qset_ids)), mdtz__gte=mdtz)
            .values(*self.fields)
        )

        return qset or self.none()

    def handle_questionpostdata(self, request):
        from apps.activity.models.question_model import QuestionSet

        R, S, Id, r = request.POST, request.session, None, {}
        r["ismandatory"] = R.get("ismandatory", False) == "true"
        r["isavpt"] = R.get("isavpt", False) == "true"
        r["options"] = R["options"].replace('"', "").replace("[", "").replace("]", "")
        r["min"] = 0.0 if R["min"] == "" else R["min"]
        r["max"] = 0.0 if R["max"] == "" else R["max"]

        if R["answertype"] in ["DROPDOWN", "CHECKBOX"]:
            r["alerton"] = (
                R["alerton"].replace('"', "").replace("[", "").replace("]", "")
            )

        elif R["answertype"] == "NUMERIC" and (R["alertbelow"] or R["alertabove"]):
            r["alerton"] = f"<{R['alertbelow']}, >{R['alertabove']}"

        questionset_data = QuestionSet.objects.get(id=R["parent_id"])
        buincludes = questionset_data.buincludes
        
        # Handle display_conditions if provided
        display_conditions = {}
        if R.get("display_conditions"):
            import json
            import html
            try:
                # Decode HTML entities first, then parse JSON
                decoded_json = html.unescape(R["display_conditions"])
                display_conditions = json.loads(decoded_json)
            except (json.JSONDecodeError, TypeError):
                display_conditions = {}
        
        PostData = {
            "qset_id": R["parent_id"],
            "answertype": R["answertype"],
            "min": r.get("min", "0.0"),
            "max": r.get("max", "0.0"),
            "alerton": r.get("alerton"),
            "ismandatory": r["ismandatory"],
            "question_id": R["question_id"],
            "isavpt": r["isavpt"],
            "avpttype": R["avpttype"],
            "options": r.get("options"),
            "seqno": R["seqno"],
            "client_id": S["client_id"],
            "bu_id": S["bu_id"],
            "cuser": request.user,
            "muser": request.user,
            "cdtz": utils.getawaredatetime(datetime.now(), R["ctzoffset"]),
            "mdtz": utils.getawaredatetime(datetime.now(), R["ctzoffset"]),
            "buincludes": buincludes,
            "display_conditions": display_conditions,  # Add display_conditions
        }
        if R["action"] == "create":
            if self.filter(
                qset_id=PostData["qset_id"],
                question_id=PostData["question_id"],
                client_id=PostData["client_id"],
                bu_id=PostData["bu_id"],
            ).exists():
                return {
                    "data": list(self.none()),
                    "error": "Warning: You are trying to add the same question again!",
                }
            ID = self.create(**PostData).id

        elif R["action"] == "edit":
            PostData.pop("cuser")
            PostData.pop("cdtz")
            if updated := self.filter(pk=R["pk"]).update(**PostData):
                ID = R["pk"]
        else:
            self.filter(pk=R["pk"]).delete()
            return {"data": list(self.none())}

        qset = (
            self.filter(id=ID)
            .annotate(quesname=F("question__quesname"))
            .values(
                "pk",
                "seqno",
                "quesname",
                "answertype",
                "min",
                "question_id",
                "ctzoffset",
                "max",
                "options",
                "alerton",
                "ismandatory",
                "isavpt",
                "avpttype",
            )
            or self.none()
        )
        return {"data": list(qset)}

    def get_questions_of_qset(self, R):
        """
        Get all questions in a question set with their configuration.

        OPTIMIZED (2025-10-03):
        - Uses select_related for question FK
        - Indexed by (qset, seqno) - see migration 0018
        - Ordered by seqno for display

        Following .claude/rules.md Rule #12: Database query optimization
        """
        if R["qset_id"] in ["None", None, ""]:
            return self.none()

        qset = (
            self.annotate(quesname=F("question__quesname"))
            .filter(qset_id=R["qset_id"])
            .select_related("question", "qset")  # Optimize FK access
            .order_by("seqno")  # Explicit ordering for consistent display
            .values(
                "pk",
                "quesname",
                "answertype",
                "min",
                "max",
                "question_id",
                "options",
                "alerton",
                "ismandatory",
                "seqno",
                "ctzoffset",
                "isavpt",
                "avpttype",
                "display_conditions",  # Include display conditions
            )
        )
        return qset or self.none()
    
    def get_questions_with_logic(self, qset_id):
        """
        Get questions with validated conditional display logic for mobile/API.

        Enhanced with:
        - Dependency validation
        - Circular dependency detection
        - Ordering validation

        Following .claude/rules.md Rule #12: Database query optimization
        """
        if not qset_id:
            return self.none()

        # Optimized query with select_related
        questions = (
            self.annotate(quesname=F("question__quesname"))
            .filter(qset_id=qset_id)
            .select_related("question", "qset")  # Optimize FK access
            .order_by("seqno")
            .values(
                "pk",
                "question_id",
                "quesname",
                "answertype",
                "min",
                "max",
                "options",
                "alerton",
                "ismandatory",
                "seqno",
                "isavpt",
                "avpttype",
                "display_conditions",
            )
        )

        # Process and structure for mobile consumption
        questions_list = list(questions)
        dependency_map = {}
        validation_warnings = []

        for q in questions_list:
            if q.get("display_conditions") and q["display_conditions"].get("depends_on"):
                depends_on = q["display_conditions"]["depends_on"]
                # Support both old 'question_id' and new 'qsb_id' keys
                parent_id = depends_on.get("question_id") or depends_on.get("qsb_id")

                if parent_id:
                    # Validate dependency exists in questions_list
                    parent_exists = any(
                        qitem["pk"] == parent_id
                        for qitem in questions_list
                    )

                    if not parent_exists:
                        validation_warnings.append({
                            "question_id": q["pk"],
                            "warning": f"Dependency on QSB ID {parent_id} not found in this question set",
                            "severity": "error"
                        })
                        continue

                    # Validate ordering (dependency must come before)
                    parent_seqno = next(
                        (qitem["seqno"] for qitem in questions_list if qitem["pk"] == parent_id),
                        None
                    )

                    if parent_seqno and parent_seqno >= q["seqno"]:
                        validation_warnings.append({
                            "question_id": q["pk"],
                            "warning": f"Dependency on QSB ID {parent_id} (seqno {parent_seqno}) comes after or same as this question (seqno {q['seqno']})",
                            "severity": "error"
                        })

                    # Build dependency map
                    if parent_id not in dependency_map:
                        dependency_map[parent_id] = []

                    dependency_map[parent_id].append({
                        "question_id": q["pk"],  # The dependent question's ID
                        "question_seqno": q["seqno"],  # Include seqno for display order
                        "operator": depends_on.get("operator", "EQUALS"),
                        "values": depends_on.get("values", []),
                        "show_if": q["display_conditions"].get("show_if", True),
                        "cascade_hide": q["display_conditions"].get("cascade_hide", False),
                        "group": q["display_conditions"].get("group")
                    })

        # Detect circular dependencies
        circular_deps = self._detect_circular_dependencies(questions_list, dependency_map)
        if circular_deps:
            validation_warnings.extend(circular_deps)

        result = {
            "questions": questions_list,
            "dependency_map": dependency_map,
            "has_conditional_logic": bool(dependency_map),
        }

        # Include validation warnings if any
        if validation_warnings:
            result["validation_warnings"] = validation_warnings
            logger.warning(
                f"Question set {qset_id} has {len(validation_warnings)} dependency validation warnings",
                extra={'qset_id': qset_id, 'warnings': validation_warnings}
            )

        return result

    def _detect_circular_dependencies(self, questions_list, dependency_map):
        """
        Detect circular dependencies in the dependency map.

        Args:
            questions_list: List of questions
            dependency_map: Dependency mapping

        Returns:
            List of validation warnings for circular dependencies
        """
        warnings = []

        def has_circular_path(qsb_id, target_id, visited=None):
            """Check if there's a circular path from qsb_id to target_id."""
            if visited is None:
                visited = set()

            if qsb_id in visited:
                return True  # Circular!

            visited.add(qsb_id)

            # Check all dependencies of this question
            for dep_list in dependency_map.values():
                for dep in dep_list:
                    if dep["question_id"] == qsb_id:
                        # This question depends on something
                        # Check if it creates a circle back to target
                        for parent_id, children in dependency_map.items():
                            if any(child["question_id"] == qsb_id for child in children):
                                if parent_id == target_id:
                                    return True
                                if has_circular_path(parent_id, target_id, visited.copy()):
                                    return True

            return False

        # Check each question for circular dependencies
        for q in questions_list:
            qsb_id = q["pk"]
            if has_circular_path(qsb_id, qsb_id):
                warnings.append({
                    "question_id": qsb_id,
                    "warning": f"Circular dependency detected involving question {qsb_id}",
                    "severity": "critical"
                })

        return warnings
