"""
Ticket Intent Classifier.

Classifies user intent for ticket-related conversations to route
appropriately and improve deflection rates.

Follows .claude/rules.md Rule #8 (methods < 30 lines).
"""

import logging
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from apps.ontology import ontology

logger = logging.getLogger('helpbot.ticket_intent')


@dataclass
class IntentClassification:
    """Intent classification result."""
    intent: str
    confidence: float
    priority: Optional[str] = None
    category: Optional[str] = None
    requires_ticket: bool = True
    ticket_number: Optional[str] = None


@ontology(
    domain="help",
    purpose="NLP-based ticket intent classification for intelligent routing and deflection",
    inputs=[
        {"name": "message", "type": "str", "description": "User message text"}
    ],
    outputs=[
        {"name": "classification", "type": "IntentClassification", "description": "Intent with confidence, priority, category, deflection score"}
    ],
    depends_on=[],
    tags=["help", "nlp", "intent-classification", "ticket-deflection", "routing"],
    criticality="high",
    business_value="Improves ticket deflection rates by identifying answerable questions vs. issues requiring tickets"
)
class TicketIntentClassifier:
    """
    Classify user intent for ticket-related conversations.

    Intents:
    - check_status: User wants to check ticket status
    - create_ticket: User wants to report an issue
    - find_tickets: User wants to see their tickets
    - escalate: User wants to escalate a ticket
    - general_question: User has a question (may be deflectable)
    - close_ticket: User wants to close a resolved ticket
    """

    # Intent keyword patterns
    INTENT_PATTERNS = {
        'check_status': [
            r'status of (ticket )?(#?T?\d+)',
            r'what.s (the )?status',
            r'check (on )?(my )?ticket',
            r'(ticket )?(#?T?\d+) status',
            r'where (is my|\'s) ticket',
            r'what happened (with|to) (ticket )?(#?T?\d+)',
        ],
        'create_ticket': [
            r'(create|open|submit|file) (a |an )?ticket',
            r'report (a |an )?(issue|problem|bug)',
            r'i (have|need|want) (a |an )?(issue|problem)',
            r'(something|this) (is )?(not working|broken|down)',
            r'need help (with|fixing)',
            r'(urgent|emergency)',
        ],
        'find_tickets': [
            r'(show|list|display|find) my tickets',
            r'what tickets (do i have|are open)',
            r'all (of )?my tickets',
            r'my (open|pending) tickets',
            r'tickets assigned to me',
        ],
        'escalate': [
            r'escalate (this |ticket |#?T?\d+)?',
            r'(urgent|asap|immediately|right now)',
            r'speak (to|with) (a )?(supervisor|manager)',
            r'this (is |has been )?(taking|waited) too long',
            r'i.m frustrated',
            r'not (getting|receiving) (help|response)',
        ],
        'general_question': [
            r'how (do|to|can) i',
            r'what (is|does|are)',
            r'(where|when|why) (is|do|does|can)',
            r'(explain|tell me about)',
            r'help (me )?(with|understanding)',
        ],
        'close_ticket': [
            r'close (ticket |#?T?\d+)',
            r'(resolved|fixed|solved|done)',
            r'(can|want to) close',
            r'mark (as )?(resolved|complete)',
            r'no longer (an issue|needed)',
        ],
    }

    # Priority detection keywords
    PRIORITY_KEYWORDS = {
        'HIGH': [
            'urgent', 'asap', 'immediately', 'critical', 'emergency',
            'down', 'not working', 'broken', 'failed', 'failure',
            'security', 'safety', 'danger', 'right now'
        ],
        'LOW': [
            'question', 'when available', 'whenever', 'future',
            'enhancement', 'nice to have', 'suggestion', 'if possible'
        ],
    }

    # Category detection keywords
    CATEGORY_KEYWORDS = {
        'Access': ['login', 'password', 'access', 'card', 'permission', 'unlock', 'locked'],
        'Equipment': ['laptop', 'phone', 'equipment', 'device', 'hardware', 'computer'],
        'Facility': ['ac', 'air conditioning', 'lights', 'door', 'room', 'building'],
        'IT Support': ['software', 'email', 'internet', 'network', 'system', 'app'],
        'Maintenance': ['repair', 'fix', 'broken', 'maintenance', 'service'],
        'HR': ['payroll', 'salary', 'leave', 'hr', 'benefits', 'resignation'],
    }

    # Deflectable questions (can be answered without ticket)
    DEFLECTABLE_PATTERNS = [
        r'how (do|to|can) i reset (my )?password',
        r'(where|how) (is|do i find) (the|my) settings',
        r'how (do|to) (access|use|find)',
        r'what (is|are|does)',
        r'(explain|tell me about)',
    ]

    def classify(self, message: str) -> IntentClassification:
        """
        Classify user intent from message.

        Args:
            message: User message text

        Returns:
            IntentClassification with intent and metadata
        """
        message_lower = message.lower()

        # First, check if message contains ticket number (strong signal for check_status)
        ticket_number = self._extract_ticket_number(message)

        # Match intent patterns
        intent, confidence = self._match_intent_patterns(message_lower)

        # If ticket number found and no other strong intent, assume check_status
        if ticket_number and confidence < 0.8:
            intent = 'check_status'
            confidence = 0.9

        # Detect priority
        priority = self._detect_priority(message_lower)

        # Detect category
        category = self._detect_category(message_lower)

        # Determine if ticket is required
        requires_ticket = self._requires_ticket(intent, message_lower)

        return IntentClassification(
            intent=intent,
            confidence=confidence,
            priority=priority,
            category=category,
            requires_ticket=requires_ticket,
            ticket_number=ticket_number,
        )

    def _match_intent_patterns(self, message: str) -> tuple[str, float]:
        """
        Match message against intent patterns.

        Returns:
            Tuple of (intent, confidence)
        """
        best_intent = 'general_question'
        best_confidence = 0.3

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, message, re.IGNORECASE):
                    # Pattern match gives high confidence
                    confidence = 0.85
                    if confidence > best_confidence:
                        best_intent = intent
                        best_confidence = confidence

        return best_intent, best_confidence

    def _extract_ticket_number(self, message: str) -> Optional[str]:
        """
        Extract ticket number from message.

        Accepts formats: T00123, #123, ticket 123, 123
        """
        patterns = [
            r'T\d{5}',  # T00123
            r'#(\d+)',  # #123
            r'ticket\s+(\d+)',  # ticket 123
            r'\b(\d{3,5})\b',  # 123 (standalone number 3-5 digits)
        ]

        for pattern in patterns:
            match = re.search(pattern, message, re.IGNORECASE)
            if match:
                if pattern.startswith('T'):
                    return match.group(0)
                else:
                    num = match.group(1) if '(' in pattern else match.group(0)
                    return f"T{int(num):05d}"

        return None

    def _detect_priority(self, message: str) -> str:
        """
        Detect priority from message keywords.

        Returns:
            Priority: HIGH, MEDIUM, or LOW
        """
        # Check HIGH priority keywords
        high_count = sum(1 for keyword in self.PRIORITY_KEYWORDS['HIGH']
                        if keyword in message)

        if high_count >= 1:
            return 'HIGH'

        # Check LOW priority keywords
        low_count = sum(1 for keyword in self.PRIORITY_KEYWORDS['LOW']
                       if keyword in message)

        if low_count >= 1:
            return 'LOW'

        # Default to MEDIUM
        return 'MEDIUM'

    def _detect_category(self, message: str) -> Optional[str]:
        """
        Detect ticket category from message keywords.

        Returns:
            Category name or None
        """
        category_scores = {}

        for category, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in message)
            if score > 0:
                category_scores[category] = score

        if category_scores:
            # Return category with highest score
            return max(category_scores, key=category_scores.get)

        return None

    def _requires_ticket(self, intent: str, message: str) -> bool:
        """
        Determine if user intent requires creating a ticket.

        Args:
            intent: Classified intent
            message: User message

        Returns:
            True if ticket is required, False if deflectable
        """
        # Some intents never require new tickets
        if intent in ['check_status', 'find_tickets', 'close_ticket']:
            return False

        # Escalation requires existing ticket
        if intent == 'escalate':
            return False

        # For general questions, check if deflectable
        if intent == 'general_question':
            # Check deflectable patterns
            for pattern in self.DEFLECTABLE_PATTERNS:
                if re.search(pattern, message, re.IGNORECASE):
                    return False  # Can be deflected

        # Create ticket intent always requires ticket
        if intent == 'create_ticket':
            return True

        # Default: requires ticket
        return True

    def get_suggested_response_type(self, classification: IntentClassification) -> str:
        """
        Get suggested response type based on classification.

        Args:
            classification: Intent classification result

        Returns:
            Response type: 'knowledge_base', 'create_ticket', 'check_status', etc.
        """
        if classification.intent == 'general_question' and not classification.requires_ticket:
            return 'knowledge_base'

        if classification.intent == 'create_ticket':
            # Try knowledge base first (deflection strategy)
            return 'knowledge_base_then_ticket'

        if classification.intent == 'check_status':
            return 'check_status'

        if classification.intent == 'find_tickets':
            return 'list_tickets'

        if classification.intent == 'escalate':
            return 'escalate'

        if classification.intent == 'close_ticket':
            return 'close_ticket'

        # Default
        return 'general_help'

    def get_deflection_score(self, classification: IntentClassification) -> float:
        """
        Calculate deflection score (0-1) for this intent.

        Higher score = higher deflection potential.

        Args:
            classification: Intent classification result

        Returns:
            Deflection score between 0.0 and 1.0
        """
        # General questions have highest deflection potential
        if classification.intent == 'general_question':
            return 0.9

        # Low priority tickets have medium deflection potential
        if classification.priority == 'LOW':
            return 0.6

        # Create ticket with medium priority
        if classification.intent == 'create_ticket' and classification.priority == 'MEDIUM':
            return 0.5

        # Status checks don't create new tickets
        if classification.intent in ['check_status', 'find_tickets']:
            return 0.8  # Not creating new work

        # High priority or escalations have low deflection potential
        if classification.priority == 'HIGH' or classification.intent == 'escalate':
            return 0.2

        # Default
        return 0.4
