"""
Duplicate Ticket Detector Service.

Identifies duplicate/similar tickets using text similarity.
Helps reduce ticket volume and improve response efficiency.

Follows .claude/rules.md:
- Rule #7: Service < 150 lines
- Rule #8: Methods < 30 lines
- Rule #11: Specific exception handling

@ontology(
    domain="helpdesk",
    purpose="Detect duplicate tickets using similarity scoring",
    business_value="Reduced duplicate work, faster resolution",
    criticality="low",
    tags=["helpdesk", "deduplication", "similarity", "nlp"]
)
"""

import logging
from typing import List, Tuple
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS, PARSING_EXCEPTIONS

logger = logging.getLogger('y_helpdesk.duplicate_detector')

__all__ = ['DuplicateDetectorService']


class DuplicateDetectorService:
    """Detect duplicate tickets using text similarity."""
    
    SIMILARITY_THRESHOLD = 0.75
    LOOKBACK_DAYS = 30
    
    @classmethod
    def find_duplicates(cls, ticket, limit: int = 5) -> List[Tuple]:
        """
        Find potential duplicate tickets.
        
        Args:
            ticket: Ticket instance to check
            limit: Maximum duplicates to return
            
        Returns:
            List of (ticket, similarity_score) tuples
        """
        from apps.y_helpdesk.models import Ticket
        
        try:
            lookback = timezone.now() - timedelta(days=cls.LOOKBACK_DAYS)
            
            candidates = Ticket.objects.filter(
                bu=ticket.bu,
                cdtz__gte=lookback,
                status__in=['NEW', 'OPEN', 'RESOLVED', 'CLOSED']
            ).exclude(id=ticket.id).select_related('assignedtopeople')[:100]
            
            similarities = []
            
            for candidate in candidates:
                score = cls._calculate_similarity(ticket, candidate)
                
                if score >= cls.SIMILARITY_THRESHOLD:
                    similarities.append((candidate, score))
            
            similarities.sort(key=lambda x: x[1], reverse=True)
            
            return similarities[:limit]
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error in duplicate detection for ticket {ticket.id}: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id, 'bu': ticket.bu.id if ticket.bu else None}
            )
            return []
        except PARSING_EXCEPTIONS as e:
            logger.error(
                f"Data parsing error in duplicate detection: {e}",
                exc_info=True,
                extra={'ticket_id': ticket.id}
            )
            return []
    
    @classmethod
    def _calculate_similarity(cls, ticket1, ticket2) -> float:
        """
        Calculate similarity score between two tickets.
        
        Uses simple Jaccard similarity on word tokens.
        For production, consider using embeddings or TF-IDF.
        """
        text1 = cls._normalize_text(ticket1.ticketdesc)
        text2 = cls._normalize_text(ticket2.ticketdesc)
        
        tokens1 = set(text1.split())
        tokens2 = set(text2.split())
        
        if not tokens1 or not tokens2:
            return 0.0
        
        intersection = tokens1.intersection(tokens2)
        union = tokens1.union(tokens2)
        
        jaccard = len(intersection) / len(union)
        
        category_match = 1.0 if ticket1.ticketcategory_id == ticket2.ticketcategory_id else 0.0
        location_match = 1.0 if ticket1.location_id == ticket2.location_id else 0.0
        
        final_score = (jaccard * 0.7) + (category_match * 0.2) + (location_match * 0.1)
        
        return final_score
    
    @classmethod
    def _normalize_text(cls, text: str) -> str:
        """Normalize text for comparison."""
        if not text:
            return ""
        
        text = text.lower()
        
        text = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in text)
        
        stopwords = {'the', 'a', 'an', 'in', 'on', 'at', 'to', 'for', 'is', 'are', 'was', 'were'}
        tokens = [w for w in text.split() if w not in stopwords and len(w) > 2]
        
        return ' '.join(tokens)
    
    @classmethod
    def check_on_create(cls, ticket_desc: str, bu, category=None) -> List[dict]:
        """
        Check for duplicates before creating ticket.
        
        Args:
            ticket_desc: Ticket description text
            bu: Business unit
            category: Optional ticket category
            
        Returns:
            List of potential duplicate ticket dicts
        """
        from apps.y_helpdesk.models import Ticket
        
        try:
            lookback = timezone.now() - timedelta(days=cls.LOOKBACK_DAYS)
            
            query = Q(bu=bu, cdtz__gte=lookback, status__in=['NEW', 'OPEN'])
            
            if category:
                query &= Q(ticketcategory=category)
            
            candidates = Ticket.objects.filter(query)[:50]
            
            normalized_input = cls._normalize_text(ticket_desc)
            input_tokens = set(normalized_input.split())
            
            matches = []
            
            for candidate in candidates:
                candidate_text = cls._normalize_text(candidate.ticketdesc)
                candidate_tokens = set(candidate_text.split())
                
                if not candidate_tokens:
                    continue
                
                intersection = input_tokens.intersection(candidate_tokens)
                union = input_tokens.union(candidate_tokens)
                
                similarity = len(intersection) / len(union) if union else 0.0
                
                if similarity >= cls.SIMILARITY_THRESHOLD:
                    matches.append({
                        'ticket_id': candidate.id,
                        'ticket_no': candidate.ticketno,
                        'description': candidate.ticketdesc[:100],
                        'similarity': round(similarity, 2),
                        'status': candidate.status
                    })
            
            return sorted(matches, key=lambda x: x['similarity'], reverse=True)[:5]
            
        except DATABASE_EXCEPTIONS as e:
            logger.error(
                f"Database error in pre-create duplicate check: {e}",
                exc_info=True,
                extra={'bu': bu.id if bu else None, 'category': category}
            )
            return []
        except PARSING_EXCEPTIONS as e:
            logger.error(
                f"Data parsing error in duplicate check: {e}",
                exc_info=True,
                extra={'description_length': len(ticket_desc) if ticket_desc else 0}
            )
            return []
