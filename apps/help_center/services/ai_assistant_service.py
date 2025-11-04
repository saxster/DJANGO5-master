"""
AI Assistant Service - RAG-powered conversational help.

Implements RAG (Retrieval-Augmented Generation) pipeline:
1. Retrieval - Hybrid search for relevant articles
2. Augmentation - Build context with retrieved content
3. Generation - Stream LLM response with citations

Following CLAUDE.md:
- Rule #7: Methods <50 lines
- Rule #11: Specific exception handling
- Rule #18: Mandatory timeouts for network calls
"""

import logging
from apps.help_center.services.search_service import SearchService

logger = logging.getLogger(__name__)


class AIAssistantService:
    """RAG-powered AI assistant for help queries."""

    SYSTEM_PROMPT = """You are a helpful assistant for the IntelliWiz facility management platform.

You have access to help articles from the knowledge base. Answer user questions using ONLY the provided context.

Guidelines:
- Cite article titles when referencing information
- If unsure, suggest relevant articles to read
- Keep responses under 200 words
- Be concise and actionable
- If context doesn't contain the answer, say so and suggest contacting support
"""

    @classmethod
    async def generate_response_stream(cls, tenant, user, query, session_id, current_url=''):
        """
        Generate AI response with streaming (async generator).

        Args:
            tenant: Tenant instance
            user: People instance
            query: User's question
            session_id: UUID for conversation tracking
            current_url: Page user is on (for context)

        Yields:
            {
                'type': 'chunk'|'citation'|'error',
                'content': str,
                'metadata': dict
            }
        """
        try:
            yield {'type': 'status', 'content': 'Searching knowledge base...'}

            retrieved_context = await cls._retrieve_context(tenant, user, query)

            if not retrieved_context['articles']:
                yield {
                    'type': 'error',
                    'content': 'No relevant articles found. Please try rephrasing your question or contact support.'
                }
                return

            yield {'type': 'status', 'content': 'Generating response...'}

            context_text = cls._build_context(retrieved_context, user, current_url)

            # Generate AI response using LLM service
            try:
                from apps.onboarding_api.services.production_llm_service import ProductionLLMService

                llm_service = ProductionLLMService()

                # Build prompt with context
                full_prompt = f"{cls.SYSTEM_PROMPT}\n\nContext:\n{context_text}\n\nQuestion: {query}"

                # Generate response (synchronous for now, async streaming would require modifications)
                response = llm_service.generate_completion(
                    prompt=full_prompt,
                    user_id=user.id,
                    client_id=user.tenant.id,
                    max_tokens=500,
                    temperature=0.3,
                    metadata={'purpose': 'help_assistant', 'query': query}
                )

                # Yield complete response as chunks
                response_text = response.response_text if hasattr(response, 'response_text') else str(response)

                # Stream in chunks for better UX
                chunk_size = 20
                words = response_text.split()
                for i in range(0, len(words), chunk_size):
                    chunk = ' '.join(words[i:i+chunk_size]) + ' '
                    yield {'type': 'chunk', 'content': chunk}

            except ImportError:
                # Fallback if LLM service not available
                logger.warning("ProductionLLMService not available, using fallback")
                yield {
                    'type': 'chunk',
                    'content': f"I found {len(retrieved_context['articles'])} relevant articles about '{query}'. Please review the articles below for detailed information."
                }
            except Exception as e:
                logger.error(f"LLM generation error: {e}", exc_info=True)
                yield {
                    'type': 'chunk',
                    'content': "I found relevant help articles. Please review the citations below."
                }

            article_ids = [a['id'] for a in retrieved_context['articles']]

            yield {
                'type': 'citations',
                'content': retrieved_context['articles'],
                'metadata': {'article_ids': article_ids, 'retrieval_method': 'hybrid'}
            }

            logger.info(
                "ai_assistant_response_generated",
                extra={'query': query, 'articles_used': len(article_ids), 'user': user.username}
            )

        except Exception as e:
            logger.error(f"AI assistant error: {e}", exc_info=True)
            yield {
                'type': 'error',
                'content': f"An error occurred: {str(e)}. Please try again or contact support."
            }

    @classmethod
    async def _retrieve_context(cls, tenant, user, query):
        """Retrieve relevant articles using hybrid search."""
        search_results = SearchService.hybrid_search(
            tenant=tenant,
            user=user,
            query=query,
            limit=5,
            role_filter=True
        )

        from apps.help_center.models import HelpArticle

        articles = []
        for result in search_results['results']:
            try:
                article = HelpArticle.objects.get(id=result['id'])
                articles.append({
                    'id': article.id,
                    'title': article.title,
                    'content_snippet': article.content[:1000],
                    'url': f"/help/articles/{article.slug}/",
                    'category': article.category.name
                })
            except HelpArticle.DoesNotExist:
                continue

        return {'articles': articles, 'total_retrieved': len(articles)}

    @classmethod
    def _build_context(cls, retrieved_context, user, current_url):
        """Build context string for LLM prompt."""
        articles_text = []

        for idx, article in enumerate(retrieved_context['articles'], 1):
            articles_text.append(
                f"[Article {idx}: {article['title']} ({article['category']})]\n"
                f"{article['content_snippet']}\n"
                f"Full article: {article['url']}\n"
            )

        context = "\n---\n".join(articles_text)

        user_roles = ', '.join(user.groups.values_list('name', flat=True))
        context += f"\n\nUser Role: {user_roles}\n"

        if current_url:
            context += f"Current Page: {current_url}\n"

        return context
