import pytest
from unittest.mock import Mock, MagicMock, patch

from apps.onboarding_api.services.knowledge import (
    VectorStore,
    PostgresArrayBackend,
    KnowledgeService,
    EnhancedKnowledgeService,
    DummyEmbeddingGenerator,
    EnhancedEmbeddingGenerator,
    DocumentChunker,
    DocumentFetcher,
    DocumentParser,
    SecurityError,
    DocumentFetchError,
    DocumentParseError,
    get_vector_store,
    get_knowledge_service,
    get_embedding_generator,
)


class TestBackwardCompatibility:
    """Test that refactored module maintains backward compatibility"""

    def test_all_classes_importable(self):
        """Verify all refactored classes can be imported"""
        from apps.onboarding_api.services.knowledge import (
            VectorStore,
            PostgresArrayBackend,
            PgVectorBackend,
            EnhancedPgVectorBackend,
            ChromaBackend,
            KnowledgeService,
            EnhancedKnowledgeService,
            DummyEmbeddingGenerator,
            EnhancedEmbeddingGenerator,
            DocumentChunker,
            DocumentFetcher,
            DocumentParser,
        )

        assert VectorStore is not None
        assert PostgresArrayBackend is not None
        assert KnowledgeService is not None

    def test_factory_functions_available(self):
        """Verify all factory functions are importable"""
        from apps.onboarding_api.services.knowledge import (
            get_vector_store,
            get_knowledge_service,
            get_embedding_generator,
            get_document_chunker,
            get_document_fetcher,
            get_document_parser,
        )

        assert callable(get_vector_store)
        assert callable(get_knowledge_service)
        assert callable(get_embedding_generator)

    def test_exceptions_importable(self):
        """Verify all custom exceptions are importable"""
        from apps.onboarding_api.services.knowledge import (
            SecurityError,
            DocumentFetchError,
            DocumentParseError,
            UnsupportedFormatError,
        )

        assert issubclass(SecurityError, Exception)
        assert issubclass(DocumentFetchError, Exception)


class TestDummyEmbeddingGenerator:
    """Test embedding generator functionality"""

    def test_generate_embedding_deterministic(self):
        """Test that same input produces same embedding"""
        text = "Test document content"

        embedding1 = DummyEmbeddingGenerator.generate_embedding(text)
        embedding2 = DummyEmbeddingGenerator.generate_embedding(text)

        assert embedding1 == embedding2
        assert len(embedding1) == 384

    def test_generate_embedding_different_inputs(self):
        """Test that different inputs produce different embeddings"""
        embedding1 = DummyEmbeddingGenerator.generate_embedding("Text A")
        embedding2 = DummyEmbeddingGenerator.generate_embedding("Text B")

        assert embedding1 != embedding2


class TestDocumentChunker:
    """Test document chunking functionality"""

    def test_chunk_small_text(self):
        """Test chunking of small text that fits in one chunk"""
        chunker = DocumentChunker(chunk_size=1000, chunk_overlap=200)
        text = "This is a small test document."

        chunks = chunker.chunk_text(text)

        assert len(chunks) >= 1
        assert chunks[0]['text'] == text

    def test_chunk_with_overlap(self):
        """Test that overlapping chunks are created correctly"""
        chunker = DocumentChunker(chunk_size=100, chunk_overlap=20)
        text = "A" * 300

        chunks = chunker.chunk_text(text)

        assert len(chunks) > 1

    def test_chunk_structure_detection(self):
        """Test structure detection in documents"""
        chunker = DocumentChunker()
        structured_text = """
# Main Heading

Some content here.

## Subheading

More content.
        """

        chunks = chunker.chunk_text(structured_text)

        assert len(chunks) >= 1


class TestURLValidator:
    """Test URL validation security"""

    def test_validate_allowed_domain(self):
        """Test validation of allowed domains"""
        from apps.onboarding_api.services.knowledge.security import URLValidator

        validator = URLValidator(['nist.gov', 'iso.org'])

        try:
            validator.validate_url_security('https://nist.gov/document.pdf')
        except SecurityError:
            pytest.fail("Should not raise SecurityError for allowed domain")

    def test_reject_disallowed_domain(self):
        """Test rejection of disallowed domains"""
        from apps.onboarding_api.services.knowledge.security import URLValidator

        validator = URLValidator(['nist.gov'])

        with pytest.raises(SecurityError):
            validator.validate_url_security('https://malicious-site.com/document.pdf')

    def test_reject_suspicious_patterns(self):
        """Test rejection of suspicious URL patterns"""
        from apps.onboarding_api.services.knowledge.security import URLValidator

        validator = URLValidator(['example.com'])

        with pytest.raises(SecurityError):
            validator.validate_url_security('https://example.com/malware.exe')


class TestRateLimiter:
    """Test rate limiting functionality"""

    def test_rate_limiter_enforces_delay(self):
        """Test that rate limiter enforces delays"""
        from apps.onboarding_api.services.knowledge.security import RateLimiter
        import time

        limiter = RateLimiter(delay_seconds=0.1)

        start_time = time.time()
        limiter.enforce_rate_limit('https://example.com/doc1')
        limiter.enforce_rate_limit('https://example.com/doc2')
        elapsed_time = time.time() - start_time

        assert elapsed_time >= 0.1


@pytest.mark.django_db
class TestKnowledgeServiceIntegration:
    """Integration tests for knowledge service"""

    @patch('apps.onboarding_api.services.knowledge.knowledge.service.AuthoritativeKnowledge')
    def test_add_knowledge(self, mock_model):
        """Test adding knowledge item"""
        mock_instance = Mock()
        mock_instance.knowledge_id = '12345'
        mock_model.objects.create.return_value = mock_instance

        vector_store = Mock(spec=VectorStore)
        service = KnowledgeService(vector_store)

        result = service.add_knowledge(
            source_org="NIST",
            title="Security Standard",
            content_summary="Test content"
        )

        assert result == '12345'
        mock_model.objects.create.assert_called_once()


class TestRefactoringCompliance:
    """Test compliance with .claude/rules.md Rule 7"""

    def test_all_files_under_300_lines(self):
        """Verify no file exceeds 300 lines (with some tolerance)"""
        import os
        import glob

        knowledge_path = '/Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge'
        py_files = glob.glob(f"{knowledge_path}/**/*.py", recursive=True)

        violations = []
        for file_path in py_files:
            if '__pycache__' in file_path:
                continue

            with open(file_path, 'r') as f:
                line_count = len(f.readlines())

            if line_count > 300:
                violations.append((file_path, line_count))

        assert len(violations) == 0, f"Files exceeding 300 lines: {violations}"

    def test_no_generic_exception_handlers(self):
        """Verify no generic 'except Exception:' patterns (Rule 11)"""
        import os
        import glob
        import re

        knowledge_path = '/Users/amar/Desktop/MyCode/DJANGO5-master/apps/onboarding_api/services/knowledge'
        py_files = glob.glob(f"{knowledge_path}/**/*.py", recursive=True)

        violations = []
        for file_path in py_files:
            if '__pycache__' in file_path or '__init__' in file_path:
                continue

            with open(file_path, 'r') as f:
                content = f.read()

            generic_exceptions = re.findall(r'except Exception[ :]', content)
            if generic_exceptions:
                violations.append((os.path.basename(file_path), len(generic_exceptions)))

        assert len(violations) == 0, f"Files with generic exception handlers: {violations}"