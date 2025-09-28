"""
Embeddings-based semantic indexer for AI Mentor system.

This module provides:
- Vector embeddings for code and documentation
- Semantic similarity search
- RAG-enhanced context retrieval
- Code understanding beyond syntactic analysis
"""

import numpy as np
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from django.core.cache import cache

from apps.mentor.models import IndexedFile, CodeSymbol


@dataclass
class EmbeddingVector:
    """Vector embedding with metadata."""
    content_id: str  # Unique identifier for the content
    content_type: str  # 'file', 'symbol', 'docstring', 'comment'
    content_text: str  # Original text content
    embedding: List[float]  # Vector embedding
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    content_hash: str = ""

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(self.content_text.encode()).hexdigest()


@dataclass
class SimilarityMatch:
    """Result of similarity search."""
    content_id: str
    content_type: str
    content_text: str
    similarity_score: float
    metadata: Dict[str, Any]


@dataclass
class SemanticContext:
    """Semantic context for RAG enhancement."""
    query: str
    relevant_files: List[str]
    relevant_symbols: List[str]
    context_snippets: List[str]
    similarity_threshold: float
    total_context_length: int


class EmbeddingsIndexer:
    """Semantic embeddings indexer for code and documentation."""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize embeddings indexer.

        Args:
            model_name: Name of the sentence transformer model to use
        """
        self.model_name = model_name
        self.model = None
        self.cache_prefix = "mentor_embeddings"
        self.vector_dim = 384  # Default for all-MiniLM-L6-v2

        # Initialize model lazily
        self._init_model()

    def _init_model(self):
        """Initialize the sentence transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(self.model_name)
            self.vector_dim = self.model.get_sentence_embedding_dimension()
            print(f"Initialized embeddings model: {self.model_name} (dim: {self.vector_dim})")
        except ImportError:
            print("Warning: sentence-transformers not available. Using mock embeddings.")
            self.model = None
        except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
            print(f"Error initializing embeddings model: {e}")
            self.model = None

    def index_file(self, file_path: str) -> List[EmbeddingVector]:
        """Create embeddings for a file and its components."""
        embeddings = []

        try:
            # Get file from database
            indexed_file = IndexedFile.objects.get(path=file_path)

            # Index entire file content
            file_content = self._get_file_content_for_embedding(indexed_file)
            if file_content:
                file_embedding = self._generate_embedding(file_content)
                if file_embedding:
                    embeddings.append(EmbeddingVector(
                        content_id=f"file:{file_path}",
                        content_type="file",
                        content_text=file_content,
                        embedding=file_embedding,
                        metadata={
                            'file_path': file_path,
                            'file_type': indexed_file.language,
                            'file_size': len(file_content)
                        }
                    ))

            # Index individual symbols
            for symbol in indexed_file.symbols.all():
                symbol_content = self._get_symbol_content_for_embedding(symbol)
                if symbol_content:
                    symbol_embedding = self._generate_embedding(symbol_content)
                    if symbol_embedding:
                        embeddings.append(EmbeddingVector(
                            content_id=f"symbol:{file_path}::{symbol.name}",
                            content_type="symbol",
                            content_text=symbol_content,
                            embedding=symbol_embedding,
                            metadata={
                                'file_path': file_path,
                                'symbol_name': symbol.name,
                                'symbol_type': symbol.kind,
                                'line_start': symbol.line_start,
                                'line_end': symbol.line_end
                            }
                        ))

            # Index docstrings separately
            docstrings = self._extract_docstrings(indexed_file)
            for docstring_info in docstrings:
                docstring_embedding = self._generate_embedding(docstring_info['content'])
                if docstring_embedding:
                    embeddings.append(EmbeddingVector(
                        content_id=f"docstring:{file_path}::{docstring_info['symbol']}",
                        content_type="docstring",
                        content_text=docstring_info['content'],
                        embedding=docstring_embedding,
                        metadata={
                            'file_path': file_path,
                            'symbol_name': docstring_info['symbol'],
                            'docstring_type': docstring_info['type']
                        }
                    ))

            # Store embeddings
            for embedding in embeddings:
                self._store_embedding(embedding)

        except IndexedFile.DoesNotExist:
            print(f"File not found in index: {file_path}")
        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError) as e:
            print(f"Error indexing file {file_path}: {e}")

        return embeddings

    def _get_file_content_for_embedding(self, indexed_file: IndexedFile) -> str:
        """Get file content optimized for embedding generation."""
        try:
            content = Path(indexed_file.path).read_text(encoding='utf-8')

            # Truncate very long files to manageable size
            max_chars = 8000  # Reasonable limit for embeddings
            if len(content) > max_chars:
                # Try to keep the most important parts (functions, classes)
                lines = content.split('\n')
                important_lines = []
                current_length = 0

                for line in lines:
                    # Prioritize lines with function/class definitions
                    if any(keyword in line for keyword in ['def ', 'class ', 'async def ']):
                        important_lines.append(line)
                        current_length += len(line) + 1
                    elif current_length < max_chars * 0.7:  # Include regular lines until 70% full
                        important_lines.append(line)
                        current_length += len(line) + 1

                    if current_length >= max_chars:
                        break

                content = '\n'.join(important_lines)

            return content

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            print(f"Error reading file content: {e}")
            return ""

    def _get_symbol_content_for_embedding(self, symbol: CodeSymbol) -> str:
        """Get symbol content optimized for embedding."""
        content_parts = []

        # Add symbol signature
        if symbol.signature:
            content_parts.append(f"{symbol.kind} {symbol.name}{symbol.signature}")

        # Add docstring if available
        if symbol.docstring:
            content_parts.append(symbol.docstring)

        # Add decorators context
        if symbol.decorators:
            content_parts.append(f"Decorators: {', '.join(symbol.decorators)}")

        # Add type hints context
        if symbol.return_type:
            content_parts.append(f"Returns: {symbol.return_type}")

        return '\n'.join(content_parts)

    def _extract_docstrings(self, indexed_file: IndexedFile) -> List[Dict[str, str]]:
        """Extract docstrings from file for separate indexing."""
        docstrings = []

        for symbol in indexed_file.symbols.filter(docstring__isnull=False):
            if symbol.docstring and len(symbol.docstring.strip()) > 20:
                docstrings.append({
                    'symbol': symbol.name,
                    'content': symbol.docstring,
                    'type': symbol.kind
                })

        return docstrings

    def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding vector for text."""
        if not text or not text.strip():
            return None

        if self.model is None:
            # Mock embedding for testing when model is not available
            import random
            random.seed(hash(text) % (2**32))
            return [random.random() for _ in range(self.vector_dim)]

        try:
            # Generate embedding using sentence transformer
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            print(f"Error generating embedding: {e}")
            return None

    def _store_embedding(self, embedding: EmbeddingVector):
        """Store embedding in cache."""
        cache_key = f"{self.cache_prefix}_{embedding.content_id}"
        embedding_data = {
            'content_id': embedding.content_id,
            'content_type': embedding.content_type,
            'content_text': embedding.content_text,
            'embedding': embedding.embedding,
            'metadata': embedding.metadata,
            'content_hash': embedding.content_hash
        }

        # Store with long timeout
        cache.set(cache_key, embedding_data, timeout=7 * 24 * 3600)  # 7 days

    def semantic_search(self, query: str, content_types: Optional[List[str]] = None,
                       max_results: int = 10, similarity_threshold: float = 0.5) -> List[SimilarityMatch]:
        """Perform semantic search across indexed content."""
        query_embedding = self._generate_embedding(query)
        if not query_embedding:
            return []

        # Get all stored embeddings
        all_embeddings = self._get_all_embeddings(content_types)

        # Calculate similarities
        similarities = []
        for stored_embedding in all_embeddings:
            similarity = self._cosine_similarity(query_embedding, stored_embedding.embedding)
            if similarity >= similarity_threshold:
                similarities.append(SimilarityMatch(
                    content_id=stored_embedding.content_id,
                    content_type=stored_embedding.content_type,
                    content_text=stored_embedding.content_text,
                    similarity_score=similarity,
                    metadata=stored_embedding.metadata
                ))

        # Sort by similarity and return top results
        similarities.sort(key=lambda x: x.similarity_score, reverse=True)
        return similarities[:max_results]

    def get_semantic_context(self, query: str, max_context_length: int = 4000) -> SemanticContext:
        """Get semantic context for RAG-enhanced LLM prompts."""
        # Search for relevant content
        matches = self.semantic_search(query, max_results=20, similarity_threshold=0.3)

        relevant_files = set()
        relevant_symbols = set()
        context_snippets = []
        current_length = 0

        for match in matches:
            # Add file to relevant files
            if 'file_path' in match.metadata:
                relevant_files.add(match.metadata['file_path'])

            # Add symbol to relevant symbols
            if 'symbol_name' in match.metadata:
                relevant_symbols.add(f"{match.metadata['file_path']}::{match.metadata['symbol_name']}")

            # Add content snippet if we have space
            snippet = match.content_text[:500]  # Limit snippet size
            if current_length + len(snippet) <= max_context_length:
                context_snippets.append(f"[{match.similarity_score:.2f}] {snippet}")
                current_length += len(snippet)
            else:
                break

        return SemanticContext(
            query=query,
            relevant_files=list(relevant_files),
            relevant_symbols=list(relevant_symbols),
            context_snippets=context_snippets,
            similarity_threshold=0.3,
            total_context_length=current_length
        )

    def _get_all_embeddings(self, content_types: Optional[List[str]] = None) -> List[EmbeddingVector]:
        """Get all stored embeddings."""
        embeddings = []

        # This is a simplified implementation using cache.keys()
        # In production, you'd use a proper vector database
        cache_keys = cache.keys(f"{self.cache_prefix}_*")

        for cache_key in cache_keys:
            embedding_data = cache.get(cache_key)
            if embedding_data:
                # Filter by content type if specified
                if content_types and embedding_data['content_type'] not in content_types:
                    continue

                embeddings.append(EmbeddingVector(
                    content_id=embedding_data['content_id'],
                    content_type=embedding_data['content_type'],
                    content_text=embedding_data['content_text'],
                    embedding=embedding_data['embedding'],
                    metadata=embedding_data['metadata'],
                    content_hash=embedding_data['content_hash']
                ))

        return embeddings

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            # Convert to numpy arrays
            a = np.array(vec1)
            b = np.array(vec2)

            # Calculate cosine similarity
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)

            if norm_a == 0 or norm_b == 0:
                return 0.0

            similarity = dot_product / (norm_a * norm_b)
            return float(similarity)

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            print(f"Error calculating similarity: {e}")
            return 0.0

    def index_all_files(self, max_files: int = 100) -> Dict[str, Any]:
        """Index embeddings for all files in the project."""
        indexed_files = IndexedFile.objects.all()[:max_files]
        results = {
            'total_files': indexed_files.count(),
            'successfully_indexed': 0,
            'failed_files': [],
            'total_embeddings': 0
        }

        for indexed_file in indexed_files:
            try:
                embeddings = self.index_file(indexed_file.path)
                results['successfully_indexed'] += 1
                results['total_embeddings'] += len(embeddings)

            except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
                results['failed_files'].append({
                    'file': indexed_file.path,
                    'error': str(e)
                })

        return results

    def update_embeddings_for_changed_files(self, changed_files: List[str]) -> int:
        """Update embeddings for files that have changed."""
        updated_count = 0

        for file_path in changed_files:
            try:
                # Check if file content has changed
                if self._file_content_changed(file_path):
                    # Remove old embeddings
                    self._remove_file_embeddings(file_path)

                    # Generate new embeddings
                    self.index_file(file_path)
                    updated_count += 1

            except (AttributeError, ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError) as e:
                print(f"Error updating embeddings for {file_path}: {e}")

        return updated_count

    def _file_content_changed(self, file_path: str) -> bool:
        """Check if file content has changed since last embedding."""
        try:
            current_content = Path(file_path).read_text(encoding='utf-8')
            current_hash = hashlib.sha256(current_content.encode()).hexdigest()

            # Get stored hash
            file_cache_key = f"{self.cache_prefix}_file:{file_path}"
            stored_data = cache.get(file_cache_key)

            if stored_data and stored_data.get('content_hash') == current_hash:
                return False  # Content hasn't changed

            return True

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError):
            return True  # Assume changed if we can't determine

    def _remove_file_embeddings(self, file_path: str):
        """Remove all embeddings for a file."""
        # Find and remove all embeddings for this file
        cache_keys = cache.keys(f"{self.cache_prefix}_*")

        for cache_key in cache_keys:
            embedding_data = cache.get(cache_key)
            if (embedding_data and
                embedding_data.get('metadata', {}).get('file_path') == file_path):
                cache.delete(cache_key)

    def get_index_statistics(self) -> Dict[str, Any]:
        """Get statistics about the embeddings index."""
        all_embeddings = self._get_all_embeddings()

        # Group by content type
        type_counts = {}
        file_counts = {}

        for embedding in all_embeddings:
            content_type = embedding.content_type
            type_counts[content_type] = type_counts.get(content_type, 0) + 1

            if 'file_path' in embedding.metadata:
                file_path = embedding.metadata['file_path']
                file_counts[file_path] = file_counts.get(file_path, 0) + 1

        return {
            'total_embeddings': len(all_embeddings),
            'embeddings_by_type': type_counts,
            'files_with_embeddings': len(file_counts),
            'average_embeddings_per_file': len(all_embeddings) / len(file_counts) if file_counts else 0,
            'vector_dimension': self.vector_dim,
            'model_name': self.model_name
        }


class RAGEnhancedContextBuilder:
    """RAG (Retrieval-Augmented Generation) context builder."""

    def __init__(self, embeddings_indexer: EmbeddingsIndexer):
        self.embeddings_indexer = embeddings_indexer

    def build_context_for_plan_generation(self, request: str, scope: Optional[List[str]] = None) -> str:
        """Build enhanced context for plan generation."""
        # Get semantic context
        semantic_context = self.embeddings_indexer.get_semantic_context(request)

        context_parts = [
            f"Request: {request}",
            "",
            "SEMANTIC CONTEXT:",
            f"Found {len(semantic_context.relevant_files)} relevant files and {len(semantic_context.relevant_symbols)} symbols"
        ]

        if semantic_context.relevant_files:
            context_parts.append("")
            context_parts.append("Relevant files:")
            for file_path in semantic_context.relevant_files[:5]:
                context_parts.append(f"- {file_path}")

        if semantic_context.relevant_symbols:
            context_parts.append("")
            context_parts.append("Relevant symbols:")
            for symbol in semantic_context.relevant_symbols[:10]:
                context_parts.append(f"- {symbol}")

        if semantic_context.context_snippets:
            context_parts.append("")
            context_parts.append("Code context snippets:")
            for snippet in semantic_context.context_snippets[:3]:
                context_parts.append(f"```\n{snippet}\n```")

        return '\n'.join(context_parts)

    def build_context_for_patch_generation(self, request: str, target_files: List[str]) -> str:
        """Build enhanced context for patch generation."""
        # Search for similar patches or implementations
        semantic_context = self.embeddings_indexer.get_semantic_context(
            f"patch fix implement {request}"
        )

        context_parts = [
            f"Patch request: {request}",
            f"Target files: {', '.join(target_files)}",
            "",
            "SEMANTIC CONTEXT FROM SIMILAR IMPLEMENTATIONS:"
        ]

        # Filter context to be most relevant to target files
        relevant_snippets = []
        for snippet in semantic_context.context_snippets:
            if any(target_file.split('/')[-1] in snippet for target_file in target_files):
                relevant_snippets.append(snippet)

        if not relevant_snippets:
            relevant_snippets = semantic_context.context_snippets[:2]

        for snippet in relevant_snippets:
            context_parts.append(f"```\n{snippet}\n```")

        return '\n'.join(context_parts)

    def build_context_for_explanation(self, target: str, target_type: str) -> str:
        """Build enhanced context for code explanation."""
        # Search for documentation and related code
        search_query = f"{target_type} {target} documentation usage examples"
        semantic_context = self.embeddings_indexer.get_semantic_context(search_query)

        context_parts = [
            f"Explaining {target_type}: {target}",
            "",
            "RELATED DOCUMENTATION AND CODE:"
        ]

        # Prioritize docstrings and comments
        docstring_matches = self.embeddings_indexer.semantic_search(
            search_query,
            content_types=['docstring'],
            max_results=5
        )

        if docstring_matches:
            context_parts.append("")
            context_parts.append("Related documentation:")
            for match in docstring_matches:
                context_parts.append(f"- {match.metadata.get('symbol_name', 'Unknown')}: {match.content_text[:200]}...")

        # Add code examples
        if semantic_context.context_snippets:
            context_parts.append("")
            context_parts.append("Usage examples:")
            for snippet in semantic_context.context_snippets[:3]:
                context_parts.append(f"```\n{snippet[:300]}...\n```")

        return '\n'.join(context_parts)


class EmbeddingsHealthChecker:
    """Health checker for embeddings system."""

    def __init__(self, embeddings_indexer: EmbeddingsIndexer):
        self.embeddings_indexer = embeddings_indexer

    def run_health_check(self) -> Dict[str, Any]:
        """Run comprehensive health check on embeddings system."""
        health_results = {
            'overall_health': 'healthy',
            'checks': [],
            'recommendations': []
        }

        # Check model availability
        model_check = self._check_model_availability()
        health_results['checks'].append(model_check)

        # Check index completeness
        index_check = self._check_index_completeness()
        health_results['checks'].append(index_check)

        # Check search functionality
        search_check = self._check_search_functionality()
        health_results['checks'].append(search_check)

        # Check performance
        performance_check = self._check_performance()
        health_results['checks'].append(performance_check)

        # Determine overall health
        failed_checks = [c for c in health_results['checks'] if c['status'] != 'healthy']
        if failed_checks:
            if any(c['status'] == 'critical' for c in failed_checks):
                health_results['overall_health'] = 'critical'
            else:
                health_results['overall_health'] = 'degraded'

        # Generate recommendations
        health_results['recommendations'] = self._generate_health_recommendations(health_results['checks'])

        return health_results

    def _check_model_availability(self) -> Dict[str, Any]:
        """Check if embeddings model is available and working."""
        try:
            test_embedding = self.embeddings_indexer._generate_embedding("test text")
            if test_embedding and len(test_embedding) == self.embeddings_indexer.vector_dim:
                return {
                    'component': 'Embeddings Model',
                    'status': 'healthy',
                    'message': f'Model {self.embeddings_indexer.model_name} is working correctly',
                    'details': {
                        'model_name': self.embeddings_indexer.model_name,
                        'vector_dimension': len(test_embedding)
                    }
                }
            else:
                return {
                    'component': 'Embeddings Model',
                    'status': 'degraded',
                    'message': 'Model is using fallback implementation',
                    'details': {'using_mock_embeddings': True}
                }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            return {
                'component': 'Embeddings Model',
                'status': 'critical',
                'message': f'Model initialization failed: {str(e)}',
                'details': {'error': str(e)}
            }

    def _check_index_completeness(self) -> Dict[str, Any]:
        """Check completeness of embeddings index."""
        try:
            stats = self.embeddings_indexer.get_index_statistics()
            total_files = IndexedFile.objects.count()
            files_with_embeddings = stats['files_with_embeddings']

            coverage_ratio = files_with_embeddings / total_files if total_files > 0 else 0

            if coverage_ratio >= 0.8:
                status = 'healthy'
                message = f'Good coverage: {files_with_embeddings}/{total_files} files indexed'
            elif coverage_ratio >= 0.5:
                status = 'degraded'
                message = f'Partial coverage: {files_with_embeddings}/{total_files} files indexed'
            else:
                status = 'critical'
                message = f'Low coverage: {files_with_embeddings}/{total_files} files indexed'

            return {
                'component': 'Index Completeness',
                'status': status,
                'message': message,
                'details': {
                    'total_files': total_files,
                    'files_with_embeddings': files_with_embeddings,
                    'coverage_ratio': coverage_ratio,
                    'total_embeddings': stats['total_embeddings']
                }
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            return {
                'component': 'Index Completeness',
                'status': 'critical',
                'message': f'Failed to check index: {str(e)}',
                'details': {'error': str(e)}
            }

    def _check_search_functionality(self) -> Dict[str, Any]:
        """Check if semantic search is working."""
        try:
            # Run a test search
            results = self.embeddings_indexer.semantic_search("user authentication login", max_results=5)

            if results:
                avg_similarity = sum(r.similarity_score for r in results) / len(results)
                return {
                    'component': 'Search Functionality',
                    'status': 'healthy',
                    'message': f'Search working: {len(results)} results, avg similarity {avg_similarity:.2f}',
                    'details': {
                        'test_results_count': len(results),
                        'average_similarity': avg_similarity
                    }
                }
            else:
                return {
                    'component': 'Search Functionality',
                    'status': 'degraded',
                    'message': 'Search returning no results',
                    'details': {'test_results_count': 0}
                }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            return {
                'component': 'Search Functionality',
                'status': 'critical',
                'message': f'Search failed: {str(e)}',
                'details': {'error': str(e)}
            }

    def _check_performance(self) -> Dict[str, Any]:
        """Check performance of embeddings operations."""
        try:
            # Time a search operation
            start_time = time.time()
            results = self.embeddings_indexer.semantic_search("test query", max_results=10)
            search_time = time.time() - start_time

            if search_time < 0.5:  # Under 500ms
                status = 'healthy'
                message = f'Good performance: search in {search_time:.2f}s'
            elif search_time < 2.0:  # Under 2s
                status = 'degraded'
                message = f'Acceptable performance: search in {search_time:.2f}s'
            else:
                status = 'critical'
                message = f'Poor performance: search in {search_time:.2f}s'

            return {
                'component': 'Search Performance',
                'status': status,
                'message': message,
                'details': {
                    'search_time_seconds': search_time,
                    'results_count': len(results)
                }
            }

        except (AttributeError, ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, asyncio.CancelledError) as e:
            return {
                'component': 'Search Performance',
                'status': 'critical',
                'message': f'Performance check failed: {str(e)}',
                'details': {'error': str(e)}
            }

    def _generate_health_recommendations(self, checks: List[Dict[str, Any]]) -> List[str]:
        """Generate recommendations based on health check results."""
        recommendations = []

        for check in checks:
            if check['status'] == 'critical':
                if check['component'] == 'Embeddings Model':
                    recommendations.append("Install sentence-transformers: pip install sentence-transformers")
                elif check['component'] == 'Index Completeness':
                    recommendations.append("Run full reindexing: python manage.py mentor index --embeddings --full")

            elif check['status'] == 'degraded':
                if check['component'] == 'Index Completeness':
                    recommendations.append("Update embeddings for changed files: python manage.py mentor index --embeddings --incremental")
                elif check['component'] == 'Search Performance':
                    recommendations.append("Consider using a dedicated vector database for better performance")

        return recommendations


# Global instance
_embeddings_indexer = None

def get_embeddings_indexer() -> EmbeddingsIndexer:
    """Get global embeddings indexer instance."""
    global _embeddings_indexer
    if _embeddings_indexer is None:
        _embeddings_indexer = EmbeddingsIndexer()
    return _embeddings_indexer


def get_rag_context_builder() -> RAGEnhancedContextBuilder:
    """Get RAG context builder."""
    return RAGEnhancedContextBuilder(get_embeddings_indexer())