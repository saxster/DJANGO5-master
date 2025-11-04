"""
Comprehensive test suite for production-grade knowledge base system
Covers unit, integration, regression, and security tests
"""
import uuid
import hashlib
from django.test import TestCase, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from apps.onboarding.models import (
    AuthoritativeKnowledge,
    AuthoritativeKnowledgeChunk,
    KnowledgeReview,
)
from apps.core_onboarding.services.knowledge.vector_stores.postgres_array import PostgresArrayBackend
from apps.core_onboarding.services.knowledge.vector_stores.pgvector_base import PgVectorBackend
from apps.core_onboarding.services.knowledge.vector_stores.chroma import ChromaBackend
from apps.core_onboarding.services.knowledge.exceptions import (
    SecurityError,
    DocumentFetchError,
    DocumentParseError,
)
from apps.core_onboarding.services.llm import CitationAwareMakerLLM, CitationAwareCheckerLLM
from apps.core_onboarding.services.security import (
    PIIRedactor, SecurityGuardian, ContentDeduplicator, LicenseValidator
)

User = get_user_model()


# =============================================================================
# UNIT TESTS
# =============================================================================


class DocumentParserUnitTests(TestCase):
    """Unit tests for document parsers with mocked dependencies"""

    def setUp(self):
        self.parser = DocumentParser()

    @patch('PyPDF2.PdfReader')
    def test_pdf_parser_with_mock(self, mock_pdf_reader):
        """Test PDF parser with mocked PyPDF2"""
        # Mock PDF reader
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Test PDF content page 1"

        mock_reader_instance = MagicMock()
        mock_reader_instance.pages = [mock_page]
        mock_reader_instance.metadata = {'/Title': 'Test Document'}

        mock_pdf_reader.return_value = mock_reader_instance

        # Test parsing
        content = b"fake_pdf_content"
        result = self.parser._parse_pdf(content)

        self.assertIn('full_text', result)
        self.assertEqual(result['page_count'], 1)
        self.assertEqual(result['document_info']['title'], 'Test Document')
        self.assertIn('parser', result['parser_metadata'])

    def test_html_parser_with_mock(self):
        """Test HTML parser with mocked BeautifulSoup"""
        html_content = b"""
        <html>
            <head><title>Test Document</title></head>
            <body>
                <h1>Main Heading</h1>
                <p>Test content</p>
                <script>alert('test')</script>
            </body>
        </html>
        """

        with patch('bs4.BeautifulSoup') as mock_soup:
            mock_soup_instance = MagicMock()
            mock_soup_instance.find.return_value.get_text.return_value = "Test Document"
            mock_soup_instance.get_text.return_value = "Main Heading\nTest content"
            mock_soup_instance.find_all.return_value = [
                MagicMock(name='h1', get_text=lambda: 'Main Heading')
            ]
            mock_soup.return_value = mock_soup_instance

            result = self.parser._parse_html(html_content)

            self.assertIn('full_text', result)
            self.assertIn('title', result)
            self.assertIn('headings', result)

    def test_text_parser_encoding_detection(self):
        """Test text parser with different encodings"""
        # Test UTF-8
        content_utf8 = "Test content with üñíčódé".encode('utf-8')
        result = self.parser._parse_text(content_utf8)
        self.assertIn('Test content', result['full_text'])

        # Test with potential headings
        content_with_headings = b"SECTION 1: INTRODUCTION\n\nThis is content.\n\n2. Another Section\n\nMore content."
        result = self.parser._parse_text(content_with_headings)
        self.assertGreater(len(result['potential_headings']), 0)


class DocumentChunkerUnitTests(TestCase):
    """Unit tests for document chunker with boundary detection"""

    def setUp(self):
        self.chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)

    def test_chunk_boundaries_respect_sentences(self):
        """Test that chunker respects sentence boundaries"""
        text = "This is sentence one. This is sentence two. " * 10
        chunks = self.chunker.chunk_text(text)

        # Check that chunks end at sentence boundaries when possible
        for chunk in chunks[:-1]:  # Exclude last chunk
            chunk_text = chunk['text']
            self.assertTrue(
                chunk_text.endswith('.') or chunk_text.endswith('!') or chunk_text.endswith('?'),
                f"Chunk doesn't end at sentence boundary: '{chunk_text[-10:]}'"
            )

    def test_structured_chunking_with_headings(self):
        """Test chunker with heading detection"""
        text = """
        # Main Heading

        This is content under main heading.

        ## Sub Heading

        This is content under sub heading.

        ### Sub Sub Heading

        Final content here.
        """

        parsed_data = {
            'headings': [
                {'level': 'h1', 'text': 'Main Heading'},
                {'level': 'h2', 'text': 'Sub Heading'},
                {'level': 'h3', 'text': 'Sub Sub Heading'}
            ]
        }

        chunks = self.chunker.chunk_with_structure(text, {}, parsed_data)

        # Check that sections are properly identified
        self.assertGreater(len(chunks), 1)

        # Check that chunks contain section information
        for chunk in chunks:
            if chunk.get('section_heading'):
                self.assertIn('heading', chunk['tags'])

    def test_token_budget_enforcement(self):
        """Test that chunks respect token limits"""
        # Create oversized content
        long_text = "This is a very long sentence that should exceed token limits. " * 100

        chunker_with_limits = DocumentChunker(chunk_size=100, max_tokens=50)
        chunks = chunker_with_limits.chunk_text(long_text)

        # Check that no chunk exceeds token limit
        for chunk in chunks:
            estimated_tokens = chunk.get('estimated_tokens', len(chunk['text']) // 4)
            self.assertLessEqual(estimated_tokens, 50, "Chunk exceeds token limit")


class VectorStoreUnitTests(TestCase):
    """Unit tests for vector store backends"""

    def setUp(self):
        self.user = User.objects.create_user(
            loginid='testuser',
            email='test@example.com'
        )
        self.test_knowledge = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Document',
            authority_level='medium',
            content_summary='Test content for vector storage',
            publication_date=datetime.now()
        )

    def test_postgres_array_backend(self):
        """Test PostgreSQL array backend operations"""
        backend = PostgresArrayBackend()

        # Test vector storage
        test_vector = [0.1, 0.2, 0.3, 0.4]
        success = backend.store_embedding(str(self.test_knowledge.knowledge_id), test_vector, {})
        self.assertTrue(success)

        # Verify vector was stored
        self.test_knowledge.refresh_from_db()
        self.assertEqual(self.test_knowledge.content_vector, test_vector)

        # Test similarity search
        search_vector = [0.1, 0.2, 0.3, 0.5]  # Slightly different
        results = backend.search_similar(search_vector, top_k=5, threshold=0.5)

        # Should find our stored vector
        self.assertGreater(len(results), 0)
        found_result = next((r for r in results if r['knowledge_id'] == str(self.test_knowledge.knowledge_id)), None)
        self.assertIsNotNone(found_result)
        self.assertGreater(found_result['similarity'], 0.5)

    @patch('django.db.connection.cursor')
    def test_pgvector_backend_fallback(self, mock_cursor):
        """Test pgvector backend with fallback to array backend"""
        # Mock pgvector extension not available
        mock_cursor_instance = MagicMock()
        mock_cursor_instance.fetchone.return_value = None  # No pgvector extension
        mock_cursor.return_value.__enter__.return_value = mock_cursor_instance

        backend = PgVectorBackend()
        self.assertFalse(backend._pgvector_available)

        # Should fall back to array operations
        test_vector = [0.1, 0.2, 0.3]
        with patch.object(backend, '_store_as_array') as mock_store:
            mock_store.return_value = True
            result = backend.store_embedding(str(self.test_knowledge.knowledge_id), test_vector, {})
            mock_store.assert_called_once()

    @patch('chromadb.HttpClient')
    def test_chroma_backend_initialization(self, mock_client):
        """Test ChromaDB backend initialization"""
        mock_collection = MagicMock()
        mock_client_instance = MagicMock()
        mock_client_instance.get_or_create_collection.return_value = mock_collection
        mock_client.return_value = mock_client_instance

        backend = ChromaBackend()
        self.assertIsNotNone(backend._collection)
        mock_client.assert_called_once()

    def test_vector_backend_selection(self):
        """Test vector backend factory selection"""
        from apps.core_onboarding.services.knowledge import get_vector_store

        # Test default (postgres_array)
        with override_settings(ONBOARDING_VECTOR_BACKEND='postgres_array'):
            store = get_vector_store()
            self.assertIsInstance(store, PostgresArrayBackend)

        # Test unknown backend falls back to default
        with override_settings(ONBOARDING_VECTOR_BACKEND='unknown_backend'):
            with patch('apps.onboarding_api.services.knowledge.logger') as mock_logger:
                store = get_vector_store()
                self.assertIsInstance(store, PostgresArrayBackend)
                mock_logger.warning.assert_called()


class SecurityUnitTests(TestCase):
    """Unit tests for security features"""

    def setUp(self):
        self.pii_redactor = PIIRedactor()
        self.content_deduplicator = ContentDeduplicator()
        self.license_validator = LicenseValidator()

    def test_pii_redaction_patterns(self):
        """Test PII redaction for various patterns"""
        test_cases = [
            ("Contact john.doe@example.com for details", "[REDACTED_EMAIL]"),
            ("Call me at 555-123-4567", "[REDACTED_PHONE]"),
            ("SSN: 123-45-6789", "[REDACTED_SSN]"),
            ("Credit card: 4532 1234 5678 9012", "[REDACTED_CC]")
        ]

        for original, expected_pattern in test_cases:
            redacted, metadata = self.pii_redactor.redact_text(original)
            self.assertNotEqual(redacted, original)
            self.assertGreater(len(metadata['redactions']), 0)

    def test_content_deduplication(self):
        """Test content deduplication with versioning"""
        # Create test document
        test_content = "This is test content for deduplication"
        content_hash = hashlib.sha256(test_content.encode()).hexdigest()

        existing_doc = AuthoritativeKnowledge.objects.create(
            source_organization='Test Org',
            document_title='Test Document',
            document_version='1.0',
            authority_level='medium',
            content_summary=test_content,
            publication_date=datetime.now(),
            doc_checksum=content_hash
        )

        # Test exact duplicate detection
        result = self.content_deduplicator.check_duplicate_with_versioning(
            content_hash,
            {'source_organization': 'Test Org', 'document_version': '1.0'}
        )
        self.assertTrue(result['is_duplicate'])

        # Test version update allowance
        result = self.content_deduplicator.check_duplicate_with_versioning(
            content_hash,
            {'source_organization': 'Test Org', 'document_version': '2.0'}
        )
        self.assertTrue(result['allow_duplicate'])

    def test_license_validation(self):
        """Test license validation patterns"""
        test_cases = [
            ("All rights reserved. Proprietary content.", False),
            ("Creative Commons Attribution license", True),
            ("This is a government work in the public domain", True),
            ("Confidential internal use only", False)
        ]

        for content, should_allow_redistribution in test_cases:
            result = self.license_validator.validate_document_license(content)
            self.assertEqual(
                result['redistribution_allowed'],
                should_allow_redistribution,
                f"License validation failed for: {content}"
            )

    def test_security_guardian_rbac(self):
        """Test RBAC permission checking"""
        guardian = SecurityGuardian()

        # Test user with curator role
        curator_user = User.objects.create_user(
            loginid='curator',
            email='curator@example.com',
            capabilities={'knowledge_curator': True}
        )

        # Test user without permissions
        regular_user = User.objects.create_user(
            loginid='regular',
            email='regular@example.com'
        )

        # Curator should be able to ingest
        curator_permission = guardian.check_rbac_permissions(curator_user, 'ingest')
        self.assertTrue(curator_permission['allowed'])

        # Regular user should not be able to ingest
        regular_permission = guardian.check_rbac_permissions(regular_user, 'ingest')
        self.assertFalse(regular_permission['allowed'])


class DocumentFetcherUnitTests(TestCase):
    """Unit tests for document fetcher with mocked HTTP requests"""

    def setUp(self):
        self.fetcher = DocumentFetcher()
        self.test_source = KnowledgeSource.objects.create(
            name='Test Source',
            source_type='external',
            base_url='https://example.com'
        )

    @patch('requests.get')
    def test_successful_document_fetch(self, mock_get):
        """Test successful document fetching"""
        # Mock successful response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {
            'content-type': 'text/plain',
            'content-length': '100'
        }
        mock_response.iter_content.return_value = [b"Test content"]
        mock_response.url = 'https://example.com/doc.txt'
        mock_get.return_value = mock_response

        result = self.fetcher.fetch_document('https://example.com/doc.txt', self.test_source)

        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['content'], b"Test content")
        self.assertIn('content_hash', result)

    def test_security_validation_blocked_domain(self):
        """Test that non-allowlisted domains are blocked"""
        with self.assertRaises(SecurityError):
            self.fetcher._validate_url_security('https://malicious.com/doc.pdf')

    def test_security_validation_suspicious_patterns(self):
        """Test that suspicious URL patterns are blocked"""
        suspicious_urls = [
            'https://example.com/malware.exe',
            'javascript:alert(1)',
            'data:text/html,<script>alert(1)</script>'
        ]

        for url in suspicious_urls:
            with self.assertRaises(SecurityError):
                self.fetcher._validate_url_security(url)

    @patch('requests.get')
    def test_content_size_limit_enforcement(self, mock_get):
        """Test that content size limits are enforced"""
        # Mock oversized response
        mock_response = MagicMock()
        mock_response.headers = {
            'content-type': 'text/plain',
            'content-length': str(self.fetcher.max_file_size + 1000)
        }
        mock_get.return_value = mock_response

        with self.assertRaises(SecurityError):
            self.fetcher._validate_response(mock_response, 'https://example.com/huge.txt')


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class KnowledgeIngestionIntegrationTests(APITestCase):
    """Integration tests for end-to-end ingestion pipeline"""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            loginid='staff',
            email='staff@example.com',
            is_staff=True,
            capabilities={'knowledge_curator': True}
        )
        self.client.force_authenticate(user=self.staff_user)

        self.test_source = KnowledgeSource.objects.create(
            name='Test Integration Source',
            source_type='external',
            base_url='https://example.com',
            is_active=True
        )

    @patch('apps.onboarding_api.services.knowledge.requests.get')
    def test_end_to_end_ingestion_pipeline(self, mock_get):
        """Test complete ingestion pipeline from API to storage"""
        # Mock HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.headers = {'content-type': 'text/plain'}
        mock_response.iter_content.return_value = [b"Test document content for ingestion pipeline testing."]
        mock_response.url = 'https://example.com/test.txt'
        mock_get.return_value = mock_response

        # Start ingestion via API
        url = reverse('onboarding_api:knowledge-ingestions-list')
        data = {
            'source_id': str(self.test_source.source_id),
            'source_url': 'https://example.com/test.txt'
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 201)

        # Verify job was created
        job_data = response.json()
        self.assertIn('job', job_data)
        self.assertEqual(job_data['status'], 'queued')

        # Verify ingestion job exists
        job_id = job_data['job']['job_id']
        job = KnowledgeIngestionJob.objects.get(job_id=job_id)
        self.assertEqual(job.source, self.test_source)
        self.assertEqual(job.created_by, self.staff_user)

    def test_citation_aware_conversation_flow(self):
        """Test conversation flow with citation-aware LLM"""
        with patch('apps.onboarding_api.services.llm.CitationAwareMakerLLM') as mock_maker:
            # Mock maker LLM response with citations
            mock_maker_instance = MagicMock()
            mock_maker_instance.process_conversation_step.return_value = {
                'recommendations': {'business_unit_config': {'bu_type': 'Office'}},
                'citations': [
                    {
                        'doc_id': str(uuid.uuid4()),
                        'chunk_index': 0,
                        'quote': 'Office setup requires basic security configuration',
                        'relevance': 'supporting',
                        'authority_level': 'high'
                    }
                ],
                'confidence_score': 0.85
            }
            mock_maker.return_value = mock_maker_instance

            # Create conversation session
            session = ConversationSession.objects.create(
                user=self.staff_user,
                client=Bt.objects.create(buname='Test Client', bucode='TEST'),
                language='en'
            )

            # Test conversation processing
            url = reverse('onboarding_api:conversation-process', kwargs={'conversation_id': session.session_id})
            data = {
                'user_input': 'I want to set up an office',
                'context': {}
            }

            # Mock the background task
            with patch('background_tasks.onboarding_tasks.process_conversation_step.delay') as mock_task:
                mock_task.return_value.id = 'mock-task-id'
                response = self.client.post(url, data, format='json')

                self.assertEqual(response.status_code, 200)
                mock_task.assert_called_once()


class KnowledgeSearchIntegrationTests(APITestCase):
    """Integration tests for knowledge search with filtering"""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            loginid='search_user',
            email='search@example.com',
            is_staff=True
        )
        self.client.force_authenticate(user=self.staff_user)

        # Create test knowledge documents
        self.doc1 = AuthoritativeKnowledge.objects.create(
            source_organization='NIST',
            document_title='Security Framework',
            authority_level='official',
            content_summary='Security framework for enterprise environments',
            publication_date=datetime.now(),
            jurisdiction='US',
            industry='security',
            language='en'
        )

        self.doc2 = AuthoritativeKnowledge.objects.create(
            source_organization='ISO',
            document_title='Quality Management',
            authority_level='high',
            content_summary='Quality management systems and processes',
            publication_date=datetime.now(),
            jurisdiction='Global',
            industry='manufacturing',
            language='en'
        )

    def test_advanced_knowledge_search_api(self):
        """Test advanced search API with filters"""
        url = reverse('onboarding_api:knowledge-search-advanced')

        # Test search with filters
        params = {
            'q': 'security',
            'authority_level': 'official,high',
            'jurisdiction': 'US',
            'max_results': 10,
            'mode': 'text'
        }

        response = self.client.get(url, params)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('results', data)
        self.assertIn('search_metadata', data)

        # Should find relevant documents
        results = data['results']
        self.assertGreater(len(results), 0)

        # Check that filters were applied
        security_doc = next((r for r in results if 'security' in r.get('document_title', '').lower()), None)
        self.assertIsNotNone(security_doc)


# =============================================================================
# REGRESSION TESTS
# =============================================================================


class RetrievalQualityRegressionTests(TestCase):
    """Regression tests for retrieval quality with gold standard dataset"""

    def setUp(self):
        # Create gold standard test dataset
        self.gold_questions = [
            {
                'question': 'What are the security requirements for office setup?',
                'expected_sources': ['NIST Security Framework', 'ISO 27001'],
                'expected_authority': ['high', 'official'],
                'min_recall_at_5': 0.8
            },
            {
                'question': 'How many users can be configured for a warehouse?',
                'expected_sources': ['Capacity Planning Guide'],
                'expected_authority': ['medium', 'high'],
                'min_recall_at_5': 0.6
            }
        ]

        # Create corresponding knowledge documents
        self.security_doc = AuthoritativeKnowledge.objects.create(
            source_organization='NIST',
            document_title='NIST Security Framework',
            authority_level='official',
            content_summary='Comprehensive security requirements for enterprise systems including office setups',
            publication_date=datetime.now()
        )

        self.capacity_doc = AuthoritativeKnowledge.objects.create(
            source_organization='Internal',
            document_title='Capacity Planning Guide',
            authority_level='medium',
            content_summary='User capacity limits and configuration guidelines for different facility types',
            publication_date=datetime.now()
        )

    def test_retrieval_recall_at_k(self):
        """Test recall@k metrics for knowledge retrieval"""
        from apps.core_onboarding.services.knowledge import get_knowledge_service

        knowledge_service = get_knowledge_service()

        total_recall = 0
        total_questions = len(self.gold_questions)

        for gold_question in self.gold_questions:
            query = gold_question['question']
            expected_sources = gold_question['expected_sources']
            min_recall = gold_question['min_recall_at_5']

            # Perform search
            results = knowledge_service.search_knowledge(
                query=query,
                top_k=5,
                authority_filter=gold_question['expected_authority']
            )

            # Calculate recall@5
            found_sources = [r['document_title'] for r in results]
            matches = sum(1 for expected in expected_sources if any(expected in found for found in found_sources))
            recall_at_5 = matches / len(expected_sources) if expected_sources else 0

            total_recall += recall_at_5

            # Assert minimum recall threshold
            self.assertGreaterEqual(
                recall_at_5,
                min_recall,
                f"Recall@5 {recall_at_5:.2f} below threshold {min_recall} for question: {query}"
            )

        # Overall recall should be reasonable
        avg_recall = total_recall / total_questions
        self.assertGreaterEqual(avg_recall, 0.6, f"Average recall {avg_recall:.2f} below 60%")

    def test_citation_validity_rate(self):
        """Test citation validity in LLM responses"""
        citation_aware_maker = CitationAwareMakerLLM()

        # Test question that should produce citations
        test_input = "What security settings should I use?"
        test_context = {}

        # Mock knowledge retrieval
        with patch.object(citation_aware_maker, '_retrieve_knowledge_context') as mock_retrieve:
            mock_retrieve.return_value = [
                {
                    'knowledge_id': str(self.security_doc.knowledge_id),
                    'content': 'Security framework requires multi-factor authentication',
                    'authority_level': 'official',
                    'metadata': {'page_start': 1, 'page_end': 1}
                }
            ]

            # Generate recommendations
            mock_session = MagicMock()
            mock_session.collected_data = {}
            mock_session.save = MagicMock()

            result = citation_aware_maker.process_conversation_step(mock_session, test_input, test_context)

            # Validate citations
            citations = result.get('citations', [])
            self.assertGreater(len(citations), 0, "No citations generated")

            # Check citation validity
            for citation in citations:
                self.assertIn('doc_id', citation)
                self.assertIn('chunk_index', citation)
                self.assertIn('quote', citation)
                self.assertIn('relevance', citation)
                self.assertIn(citation['relevance'], ['supporting', 'contradicting', 'contextual'])


# =============================================================================
# SECURITY TESTS
# =============================================================================


class SecurityComplianceTests(APITestCase):
    """Security compliance and penetration testing"""

    def setUp(self):
        self.staff_user = User.objects.create_user(
            loginid='security_tester',
            email='security@example.com',
            is_staff=True,
            capabilities={'knowledge_curator': True}
        )
        self.regular_user = User.objects.create_user(
            loginid='regular',
            email='regular@example.com'
        )

    def test_allowlist_enforcement(self):
        """Test that allowlist is properly enforced"""
        self.client.force_authenticate(user=self.staff_user)

        # Try to create source with non-allowlisted domain
        url = reverse('onboarding_api:knowledge-sources-list')
        data = {
            'name': 'Malicious Source',
            'source_type': 'external',
            'base_url': 'https://malicious-domain.com'
        }

        response = self.client.post(url, data, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertIn('allowlist', response.json()['error'].lower())

    def test_rbac_enforcement_on_endpoints(self):
        """Test RBAC enforcement on knowledge management endpoints"""
        # Test with regular user (should be denied)
        self.client.force_authenticate(user=self.regular_user)

        url = reverse('onboarding_api:knowledge-sources-list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

        # Test with staff user (should be allowed)
        self.client.force_authenticate(user=self.staff_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_pii_scanner_quarantine(self):
        """Test that documents with PII are properly quarantined"""
        guardian = SecurityGuardian()

        # Content with high-sensitivity PII
        pii_content = """
        Employee John Doe (SSN: 123-45-6789) can be reached at john.doe@company.com.
        His phone number is 555-123-4567 and credit card ending in 9012.
        """

        document_info = {
            'title': 'Employee Information',
            'source_organization': 'Internal HR'
        }

        security_result = guardian.validate_document_security(pii_content, document_info)

        # Should be quarantined due to PII
        self.assertTrue(security_result['quarantine_required'])
        self.assertEqual(security_result['overall_risk'], 'high')
        self.assertFalse(security_result['security_passed'])

    def test_license_compliance_blocking(self):
        """Test that restricted licenses block redistribution"""
        guardian = SecurityGuardian()

        # Content with restricted license
        restricted_content = """
        PROPRIETARY AND CONFIDENTIAL

        All rights reserved. This document is proprietary to Company XYZ.
        Internal use only. Redistribution is strictly prohibited.
        """

        document_info = {'title': 'Proprietary Document'}
        security_result = guardian.validate_document_security(restricted_content, document_info)

        # Should block redistribution
        license_validation = security_result['license_validation']
        self.assertFalse(license_validation['redistribution_allowed'])
        self.assertEqual(security_result['overall_risk'], 'high')

    @patch('apps.onboarding_api.services.security.RateLimiter.check_rate_limit')
    def test_rate_limiting_enforcement(self, mock_rate_check):
        """Test rate limiting enforcement"""
        # Mock rate limit exceeded
        mock_rate_check.return_value = (False, {
            'allowed': False,
            'current_usage': 100,
            'limit': 50,
            'window': 'hourly'
        })

        guardian = SecurityGuardian()

        with self.assertRaises(RateLimitExceeded):
            guardian.sanitize_prompt("Test prompt", "user123", "prompt")


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class PerformanceTests(TestCase):
    """Performance tests for knowledge base operations"""

    def setUp(self):
        # Create test dataset
        self.test_docs = []
        for i in range(10):
            doc = AuthoritativeKnowledge.objects.create(
                source_organization=f'Test Org {i}',
                document_title=f'Test Document {i}',
                authority_level='medium',
                content_summary=f'Test content {i} with various keywords and topics',
                publication_date=datetime.now()
            )
            self.test_docs.append(doc)

    def test_search_performance_with_large_dataset(self):
        """Test search performance with larger dataset"""
        from apps.core_onboarding.services.knowledge import get_knowledge_service
        import time

        knowledge_service = get_knowledge_service()

        # Measure search time
        start_time = time.time()
        results = knowledge_service.search_knowledge('test', top_k=10)
        search_time = (time.time() - start_time) * 1000  # Convert to ms

        # Performance assertion (should be under 300ms for small dataset)
        self.assertLess(search_time, 300, f"Search took {search_time:.1f}ms, expected <300ms")

        # Should return results
        self.assertGreater(len(results), 0)

    def test_chunking_performance(self):
        """Test chunking performance for large documents"""
        import time

        chunker = DocumentChunker()

        # Generate large document
        large_content = "This is test content. " * 1000  # ~21KB of text

        start_time = time.time()
        chunks = chunker.chunk_text(large_content)
        chunking_time = (time.time() - start_time) * 1000

        # Performance and quality assertions
        self.assertLess(chunking_time, 1000, f"Chunking took {chunking_time:.1f}ms, expected <1000ms")
        self.assertGreater(len(chunks), 0)
        self.assertLess(len(chunks), 100, "Too many chunks generated")


# =============================================================================
# ERROR HANDLING TESTS
# =============================================================================


class ErrorHandlingTests(TestCase):
    """Tests for error handling and recovery"""

    def test_parser_graceful_degradation(self):
        """Test that parsers gracefully handle corrupted content"""
        parser = DocumentParser()

        # Test with corrupted PDF
        corrupted_pdf = b"Not a real PDF content"
        with patch('PyPDF2.PdfReader', side_effect=Exception("Corrupted PDF")):
            result = parser._parse_pdf(corrupted_pdf)

            # Should fall back gracefully
            self.assertIn('fallback', result['parser_metadata'].get('parser', ''))

        # Test with malformed HTML
        malformed_html = b"<html><head><title>Test</title><body><p>Unclosed paragraph"
        try:
            result = parser._parse_html(malformed_html)
            # Should not raise exception
            self.assertIsNotNone(result)
        except Exception as e:
            self.fail(f"Parser should handle malformed HTML gracefully: {str(e)}")

    def test_vector_store_error_recovery(self):
        """Test vector store error recovery"""
        backend = PostgresArrayBackend()

        # Test with non-existent knowledge ID
        result = backend.store_embedding('non-existent-id', [0.1, 0.2], {})
        self.assertFalse(result, "Should return False for non-existent document")

        # Test with malformed vector
        test_doc = AuthoritativeKnowledge.objects.create(
            source_organization='Test',
            document_title='Test',
            authority_level='medium',
            content_summary='Test',
            publication_date=datetime.now()
        )

        # Should handle empty/None vectors gracefully
        result = backend.store_embedding(str(test_doc.knowledge_id), None, {})
        self.assertFalse(result)

    def test_citation_validation_edge_cases(self):
        """Test citation validation with edge cases"""
        checker = CitationAwareCheckerLLM()

        # Test with malformed citations
        malformed_citations = [
            {'doc_id': 'test'},  # Missing required fields
            {'doc_id': 'test', 'chunk_index': 'not_a_number', 'quote': '', 'relevance': 'invalid'},
            {}  # Empty citation
        ]

        validation = checker._validate_citations_comprehensive(malformed_citations, {}, {})

        self.assertEqual(validation['valid_citations'], 0)
        self.assertGreater(validation['invalid_citations'], 0)
        self.assertGreater(len(validation['issues']), 0)


# =============================================================================
# TEST UTILITIES
# =============================================================================


class KnowledgeBaseTestUtils:
    """Utility functions for knowledge base testing"""

    @staticmethod
    def create_test_knowledge_document(**kwargs):
        """Create test knowledge document with default values"""
        defaults = {
            'source_organization': 'Test Organization',
            'document_title': 'Test Document',
            'authority_level': 'medium',
            'content_summary': 'Test content summary for knowledge base testing',
            'publication_date': datetime.now(),
            'jurisdiction': 'Global',
            'industry': 'testing',
            'language': 'en'
        }
        defaults.update(kwargs)
        return AuthoritativeKnowledge.objects.create(**defaults)

    @staticmethod
    def create_test_ingestion_job(source, user, **kwargs):
        """Create test ingestion job"""
        defaults = {
            'source': source,
            'source_url': 'https://example.com/test.txt',
            'created_by': user,
            'status': KnowledgeIngestionJob.StatusChoices.QUEUED
        }
        defaults.update(kwargs)
        return KnowledgeIngestionJob.objects.create(**defaults)

    @staticmethod
    def assert_citation_format(test_case, citations):
        """Assert that citations follow the required format"""
        for citation in citations:
            test_case.assertIn('doc_id', citation)
            test_case.assertIn('chunk_index', citation)
            test_case.assertIn('quote', citation)
            test_case.assertIn('relevance', citation)
            test_case.assertIn(citation['relevance'], ['supporting', 'contradicting', 'contextual'])
            test_case.assertIsInstance(citation['chunk_index'], int)
            test_case.assertGreaterEqual(citation['chunk_index'], 0)
