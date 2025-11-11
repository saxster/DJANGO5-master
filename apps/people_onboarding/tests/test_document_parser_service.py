import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from apps.people_onboarding.models import (
    DocumentSubmission,
    DocumentType,
    OnboardingRequest,
)
from apps.people_onboarding.services.document_parser_service import DocumentParserService
from apps.people_onboarding.tasks import extract_document_data
from apps.tenants.models import Tenant


@override_settings(PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING=True)
class DocumentParserServiceTests(TestCase):
    def setUp(self):
        self.service = DocumentParserService()

    def test_parse_resume_extracts_contact_details(self):
        resume_content = b"""
        Jane Doe
        Email: jane.doe@example.com
        Phone: +1 555 123 4567

        Skills
        - Python, Django, REST APIs

        Experience
        Senior Engineer at Example Corp
        """
        uploaded = SimpleUploadedFile(
            "resume.txt",
            resume_content,
            content_type="text/plain",
        )

        result = self.service.parse_resume(uploaded)

        self.assertEqual(result["name"], "Jane Doe")
        self.assertIn("Python", result["skills"])
        self.assertTrue(result["success"])
        self.assertGreater(result["confidence"], 0.4)

    def test_extract_id_data_detects_identifiers(self):
        id_content = b"""
        Government of India
        Permanent Account Number: ABCDE1234F
        Name: John Citizen
        DOB: 01/01/1990
        """
        uploaded = SimpleUploadedFile(
            "pan.txt",
            id_content,
            content_type="text/plain",
        )

        result = self.service.extract_id_data(uploaded, DocumentType.PAN)

        self.assertEqual(result["document_identifier"], "ABCDE1234F")
        self.assertEqual(result["name"], "Government Of India")
        self.assertTrue(result["success"])


@override_settings(PEOPLE_ONBOARDING_ENABLE_AI_DOCUMENT_PARSING=True)
class DocumentParserTaskTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            tenantname="Parser Tenant",
            subdomain_prefix="parser-tenant",
        )
        self.request = OnboardingRequest.objects.create(
            tenant=self.tenant,
            request_number="ONB-TEST-0001",
            person_type=OnboardingRequest.PersonType.EMPLOYEE_FULLTIME,
            current_state=OnboardingRequest.WorkflowState.DRAFT,
        )

    def test_extract_document_data_task_updates_submission(self):
        temp_media = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, temp_media, ignore_errors=True)

        resume = SimpleUploadedFile(
            "candidate_resume.txt",
            b"Alice Candidate\nEmail: alice@example.com\nSkills\n- Leadership\n- Python",
            content_type="text/plain",
        )

        with override_settings(MEDIA_ROOT=temp_media):
            document = DocumentSubmission.objects.create(
                tenant=self.tenant,
                onboarding_request=self.request,
                document_type=DocumentType.RESUME,
                document_file=resume,
            )
            extract_document_data.run(document.id)

        document.refresh_from_db()
        self.assertTrue(document.extracted_data.get("success"))
        self.assertIn("Alice", document.extracted_data.get("name", ""))
