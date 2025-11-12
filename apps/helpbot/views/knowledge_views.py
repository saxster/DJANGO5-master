"""
HelpBot Knowledge Views

Handles knowledge base queries and article retrieval.
"""

import logging

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.helpbot.services import HelpBotKnowledgeService
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS

logger = logging.getLogger(__name__)


class HelpBotKnowledgeView(APIView):
    """Access HelpBot knowledge base."""

    permission_classes = [IsAuthenticated]

    def __init__(self):
        super().__init__()
        self.knowledge_service = HelpBotKnowledgeService()

    def get(self, request):
        """Search knowledge base or get specific article."""
        try:
            knowledge_id = request.query_params.get('id')

            if knowledge_id:
                return self._get_article(knowledge_id)
            else:
                return self._search_knowledge(request.query_params)

        except (DATABASE_EXCEPTIONS, BUSINESS_LOGIC_EXCEPTIONS) as e:
            logger.error(f"Error in HelpBot knowledge view: {e}", exc_info=True)
            return Response(
                {'error': 'Could not process knowledge request'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def _get_article(self, knowledge_id):
        """Get specific knowledge article by ID."""
        article = self.knowledge_service.get_knowledge_by_id(knowledge_id)

        if not article:
            return Response(
                {'error': 'Article not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        return Response({'article': article})

    def _search_knowledge(self, query_params):
        """Search knowledge base."""
        query = query_params.get('q', '').strip()

        if not query:
            return Response(
                {'error': 'Query parameter "q" is required for search'},
                status=status.HTTP_400_BAD_REQUEST
            )

        category = query_params.get('category')
        limit = min(int(query_params.get('limit', 10)), 50)

        results = self.knowledge_service.search_knowledge(
            query=query,
            category=category,
            limit=limit
        )

        return Response({
            'query': query,
            'category': category,
            'results': results,
            'total': len(results)
        })
