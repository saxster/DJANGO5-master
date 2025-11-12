from apps.tenants.managers import TenantAwareManager
import logging

logger = logging.getLogger("django")


class WorkOrderReportSLAManager(TenantAwareManager):
    """
    Custom manager for SLA report data extraction and scoring.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_sla_answers(self, slaid):
        child_slarecords = self.filter(parent_id=slaid).order_by("seqno")
        # work_permit_no = childwoms[0].other_data['wp_seqno']
        sla_details = []
        overall_score = []
        all_questions = []
        all_answers = []
        all_average_score = []
        remarks = []
        for child_sla in child_slarecords:
            section_weight = child_sla.other_data["section_weightage"]
            ans = []
            answers = child_sla.womdetails_set.values("answer")
            for answer in answers:
                if answer["answer"].isdigit():
                    if int(answer["answer"]) <= 10:
                        all_answers.append(int(answer["answer"]))
                        ans.append(int(answer["answer"]))
                else:
                    remarks.append(answer["answer"])
            questions = child_sla.womdetails_set.values("question__quesname")
            for que in questions:
                all_questions.append(que["question__quesname"])
            if sum(ans) == 0 or len(ans) == 0:
                average_score = 0
            else:
                average_score = sum(ans) / len(ans)
            all_average_score.append(round(average_score, 1))
            score = average_score * section_weight
            overall_score.append(score)
            sq = {
                "section": child_sla.description,
                "sectionID": child_sla.seqno,
                "section_weightage": child_sla.other_data["section_weightage"],
            }

            sla_details.append(sq)
        overall_score = sum(overall_score)
        question_ans = dict(zip(all_questions, all_answers))
        final_overall_score = overall_score * 10
        rounded_overall_score = round(final_overall_score, 2)
        wom_ele = self.model.objects.get(id=slaid)
        wom_ele.other_data["overall_score"] = rounded_overall_score
        remarks = remarks[-1] if len(remarks) > 0 else ""
        wom_ele.other_data["remarks"] = remarks
        wom_ele.save()
        return (
            sla_details,
            rounded_overall_score,
            question_ans,
            all_average_score,
            remarks or self.none(),
        )

    def sla_data_for_report(self, id):
        (
            sla_answers,
            overall_score,
            question_ans,
            all_average_score,
            remarks,
        ) = self.get_sla_answers(id)
        return sla_answers, overall_score, question_ans, all_average_score, remarks
