from apps.tenants.managers import TenantAwareManager
from apps.peoples.models import People
import logging

logger = logging.getLogger("django")


class WorkOrderReportWPManager(TenantAwareManager):
    """
    Custom manager for Work Permit report data extraction and transformations.

    Tenant Isolation:
    - All queries automatically filtered by current tenant
    - Cross-tenant queries require explicit cross_tenant_query() call
    """
    use_in_migrations = True

    def get_empty_rwp_section(self):
        return {
            "section": "THIS SECTION TO BE COMPLETED ON RETURN OF PERMIT",
            "questions": [
                {
                    "question__quesname": "Permit Returned at",
                    "answer": "",
                },
                {
                    "question__quesname": "Work Checked at",
                    "answer": "",
                },
                {
                    "question__quesname": "Name of Requester",
                    "answer": "",
                },
            ],
        }

    def wp_data_for_report(self, id):
        site = self.filter(id=id).first().bu
        wp_answers = self.get_wp_answers(id)
        wp_info = wp_answers[0]
        wp_answers.pop(0)
        rwp_section = wp_answers.pop(-1)
        if rwp_section["section"] == "EMAIL":
            rwp_section = self.get_empty_rwp_section()
        wp_sections = wp_answers
        return wp_info, wp_sections, rwp_section, site.buname

    def convert_the_queryset_to_list(self, workpermit_sections):
        questions = workpermit_sections.get("questions")
        questions_in_list = list(questions.values("question__quesname", "answer"))
        workpermit_sections.pop("questions")
        workpermit_sections["questions"] = questions_in_list
        return workpermit_sections

    def extract_question_from_general_details(
        self, new_general_details, id, approval_status
    ):
        permit_initiated_by = ""
        permit_authorized_by = ""
        workpermit = ""
        permit_valid_upto = ""
        permit_valid_from = ""
        for question in new_general_details["questions"]:
            quesname = question[
                "question__quesname"
            ].lower()  # Convert to lowercase for case-insensitive comparison
            if quesname == "permit initiated by":
                permit_initiated_by = question["answer"]
            elif quesname == "permit authorized by":
                permit_authorized_by = question["answer"].split(",")
            elif quesname == "type of permit":
                workpermit = question["answer"]
            elif quesname == "permit valid from":
                permit_valid_from = question["answer"]
            elif quesname == "permit valid upto":
                permit_valid_upto = question["answer"]
        from apps.work_order_management.models import Wom

        approvers = []
        wom = Wom.objects.get(id=id)
        permit_authorized_by = wom.approvers
        for code in permit_authorized_by:
            people = People.objects.get(peoplecode=code)
            approvers.append(people.peoplename)

        data = {
            "permit_initiated_by": permit_initiated_by,
            "permit_authorized_by": approvers if approval_status == "APPROVED" else "",
            "workpermit": workpermit,
            "permit_valid_from": permit_valid_from,
            "permit_valid_upto": permit_valid_upto,
        }
        return data

    def extract_questions_from_section_five(self, new_section_details_five):
        permit_returned_at = ""
        work_checked_at = ""
        name_of_requester = ""

        for question in new_section_details_five["questions"]:
            if question["question__quesname"] == "PERMIT RETURNED AT":
                permit_returned_at = question["answer"]
            elif question["question__quesname"] == "WORK CHECKED AT":
                work_checked_at = question["answer"]
            elif question["question__quesname"] == "Name Of Requester":
                name_of_requester = question["answer"]

        section_data = {
            "permit_returned_at": permit_returned_at,
            "work_checked_at": work_checked_at,
            "name_of_requester": name_of_requester,
        }
        return section_data

    def extract_questions_from_section_one(self, new_section_details_one):
        """Extract work permit questions from section one."""
        field_mapping = {
            "Name of the Supervisors/Incharge": "name_of_supervisor",
            "Name of the persons involved": "name_of_persons_involved",
            "Debris are Cleared and kept at": "debris_cleared",
            "Any Other or additional control measures if required": "other_control_measures",
            "Department": "department",
            "Area/Building": "area_building",
            "Location": "location",
            "Job Description": "job_description",
            "Name of the Employees/Contractor's": "employees_contractors",
            "Workmen Fitness": "workmen_fitness",
        }

        section_data = {field: "" for field in field_mapping.values()}

        for question in new_section_details_one["questions"]:
            question_name = question["question__quesname"]
            if question_name in field_mapping:
                field_key = field_mapping[question_name]
                section_data[field_key] = question["answer"]

        return section_data

    def _build_work_permit_data(self, general_details_data, section_one_data,
                                 section_details_two, section_details_three):
        """Build core work permit data from extracted details."""
        return {
            "department": section_one_data["department"],
            "area_building": section_one_data["area_building"],
            "location": section_one_data["location"],
            "job_description": section_one_data["job_description"],
            "employees_contractors": section_one_data["employees_contractors"],
            "workmen_fitness": section_one_data["workmen_fitness"],
            "permit_authorized_by": general_details_data["permit_authorized_by"],
            "permit_initiated_by": general_details_data["permit_initiated_by"],
            "name_of_supervisor": section_one_data["name_of_supervisor"],
            "name_of_persons_involved": section_one_data["name_of_persons_involved"],
            "other_control_measures": section_one_data["other_control_measures"],
            "debris_cleared": section_one_data["debris_cleared"],
            "new_section_details_two": section_details_two["questions"],
            "new_section_details_three": section_details_three["questions"],
            "workpermit": general_details_data["workpermit"],
            "permit_valid_from": general_details_data["permit_valid_from"],
            "permit_valid_upto": general_details_data["permit_valid_upto"],
            "permit_returned_at": "",
            "work_checked_at": "",
            "name_of_requester": "",
        }

    def _add_section_five_data(self, data, section_five_data):
        """Add section five data to work permit data if present."""
        data["permit_returned_at"] = section_five_data["permit_returned_at"]
        data["work_checked_at"] = section_five_data["work_checked_at"]
        data["name_of_requester"] = section_five_data["name_of_requester"]
        return data

    def get_wp_sections_answers(self, wp_answers, id, approval_status):
        """Get work permit sections answers."""
        general_details = wp_answers[0]
        section_details_one = wp_answers[1]
        section_details_two = wp_answers[2]
        section_details_three = wp_answers[3]

        # Converting the queryset to list
        new_general_details = self.convert_the_queryset_to_list(general_details)
        new_section_details_one = self.convert_the_queryset_to_list(section_details_one)
        new_section_details_two = self.convert_the_queryset_to_list(section_details_two)
        new_section_details_three = self.convert_the_queryset_to_list(
            section_details_three
        )

        # Extracting the questions from the queryset
        general_details_data = self.extract_question_from_general_details(
            new_general_details, id, approval_status
        )
        section_one_data = self.extract_questions_from_section_one(
            new_section_details_one
        )

        # Build core work permit data
        data = self._build_work_permit_data(
            general_details_data,
            section_one_data,
            new_section_details_two,
            new_section_details_three,
        )

        # Add section five data if present
        if len(wp_answers) == 6:
            section_details_five = wp_answers[5]
            new_section_details_five = self.convert_the_queryset_to_list(
                section_details_five
            )
            section_five_data = self.extract_questions_from_section_five(
                new_section_details_five
            )
            data = self._add_section_five_data(data, section_five_data)

        return data
