"""
Y-Helpdesk Celery Tasks Package

Contains async tasks for:
- Sentiment analysis
- Ticket processing
- SLA monitoring
- Escalation handling
"""

from .sentiment_analysis_tasks import AnalyzeTicketSentimentTask

__all__ = [
    'AnalyzeTicketSentimentTask',
]
