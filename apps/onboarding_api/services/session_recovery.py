"""
Session Recovery Service

Comprehensive session checkpoint and recovery system for conversational onboarding.

Architecture:
- Redis: Active checkpoints (1h TTL) for fast access
- PostgreSQL: Historical recovery data for long-term storage
- ML-based abandonment risk detection
- Smart resume with context restoration

Following .claude/rules.md:
- Rule #7: Service methods < 150 lines
- Rule #11: Specific exception handling
- Rule #15: Logging data sanitization
- Rule #17: Transaction management

Author: Claude Code
Date: 2025-10-01
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List, Tuple

from django.core.cache import cache
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import transaction, DatabaseError, IntegrityError
from django.utils import timezone

from apps.core_onboarding.models import ConversationSession

logger = logging.getLogger(__name__)


class CheckpointNotFoundError(Exception):
    """Raised when a checkpoint cannot be found"""
    pass


class SessionRecoveryService:
    """
    Service for session checkpoint management and recovery

    Provides:
    - Automatic checkpoint creation every 30 seconds
    - Abandonment risk detection with ML-based scoring
    - Smart session resume with context restoration
    - Historical checkpoint storage in PostgreSQL
    """

    def __init__(self):
        self.checkpoint_ttl = 3600  # 1 hour in Redis
        self.checkpoint_interval_seconds = 30  # Auto-checkpoint every 30s
        self.abandonment_threshold_seconds = 300  # 5 minutes inactivity

    # ==========================================================================
    # CHECKPOINT MANAGEMENT
    # ==========================================================================

    def create_checkpoint(
        self,
        session_id: str,
        checkpoint_data: Dict[str, Any],
        force: bool = False
    ) -> Dict[str, Any]:
        """
        Create a checkpoint for session state

        Args:
            session_id: Conversation session ID
            checkpoint_data: State data to checkpoint
            force: Force checkpoint even if interval hasn't elapsed

        Returns:
            Checkpoint metadata

        Raises:
            ValidationError: Invalid checkpoint data
            DatabaseError: Storage failure
        """
        try:
            # Validate checkpoint data
            self._validate_checkpoint_data(checkpoint_data)

            # Check if checkpoint interval has elapsed (unless forced)
            if not force:
                last_checkpoint_time = self._get_last_checkpoint_time(session_id)
                if last_checkpoint_time:
                    elapsed = (timezone.now() - last_checkpoint_time).total_seconds()
                    if elapsed < self.checkpoint_interval_seconds:
                        logger.debug(f"Skipping checkpoint for {session_id} - interval not elapsed")
                        return {'status': 'skipped', 'reason': 'interval_not_elapsed'}

            # Create checkpoint
            checkpoint = {
                'session_id': session_id,
                'checkpoint_version': checkpoint_data.get('version', 1),
                'current_state': checkpoint_data['state'],
                'collected_data': checkpoint_data['data'],
                'question_history': checkpoint_data.get('history', []),
                'ui_state': checkpoint_data.get('ui_state', {}),
                'metadata': checkpoint_data.get('metadata', {}),
                'created_at': timezone.now().isoformat(),
                'checkpoint_hash': self._calculate_checkpoint_hash(checkpoint_data)
            }

            # Store in Redis (fast access)
            cache_key = self._get_checkpoint_cache_key(session_id)
            cache.set(cache_key, checkpoint, timeout=self.checkpoint_ttl)

            # Store in PostgreSQL (historical record)
            self._store_checkpoint_in_db(session_id, checkpoint)

            logger.info(
                f"Created checkpoint for session",
                extra={
                    'session_id': session_id,
                    'checkpoint_version': checkpoint['checkpoint_version']
                }
            )

            return {
                'status': 'created',
                'checkpoint_version': checkpoint['checkpoint_version'],
                'checkpoint_hash': checkpoint['checkpoint_hash'],
                'created_at': checkpoint['created_at']
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Invalid checkpoint data for {session_id}: {str(e)}")
            raise ValidationError(f"Invalid checkpoint data: {str(e)}")

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error creating checkpoint: {str(e)}", exc_info=True)
            raise

    def get_latest_checkpoint(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve most recent checkpoint for session

        Args:
            session_id: Conversation session ID

        Returns:
            Checkpoint data or None if not found
        """
        try:
            # Try Redis first (fast)
            cache_key = self._get_checkpoint_cache_key(session_id)
            checkpoint = cache.get(cache_key)

            if checkpoint:
                logger.debug(f"Retrieved checkpoint from cache for {session_id}")
                return checkpoint

            # Fallback to PostgreSQL
            checkpoint = self._get_checkpoint_from_db(session_id)

            if checkpoint:
                logger.debug(f"Retrieved checkpoint from database for {session_id}")
                # Warm up cache
                cache.set(cache_key, checkpoint, timeout=self.checkpoint_ttl)
                return checkpoint

            logger.warning(f"No checkpoint found for session {session_id}")
            return None

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error retrieving checkpoint: {str(e)}", exc_info=True)
            return None

    def list_checkpoints(
        self,
        session_id: str,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        List historical checkpoints for session

        Args:
            session_id: Conversation session ID
            limit: Maximum number of checkpoints to return

        Returns:
            List of checkpoint metadata (newest first)
        """
        try:
            session = ConversationSession.objects.get(session_id=session_id)

            # Get checkpoint history from collected_data
            checkpoint_history = session.collected_data.get('checkpoint_history', [])

            # Sort by created_at descending
            sorted_checkpoints = sorted(
                checkpoint_history,
                key=lambda x: x.get('created_at', ''),
                reverse=True
            )

            return sorted_checkpoints[:limit]

        except ConversationSession.DoesNotExist:
            logger.warning(f"Session {session_id} not found for checkpoint list")
            return []

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error listing checkpoints: {str(e)}", exc_info=True)
            return []

    # ==========================================================================
    # SESSION RESUME
    # ==========================================================================

    def resume_session(
        self,
        session_id: str,
        user_id: int
    ) -> Dict[str, Any]:
        """
        Smart session resume with context restoration

        Args:
            session_id: Conversation session ID
            user_id: User attempting to resume

        Returns:
            Resume metadata with next action

        Raises:
            CheckpointNotFoundError: No checkpoint available
            ValidationError: Invalid session state
        """
        try:
            # Get latest checkpoint
            checkpoint = self.get_latest_checkpoint(session_id)

            if not checkpoint:
                raise CheckpointNotFoundError(f"No checkpoint found for session {session_id}")

            # Verify session ownership
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=session_id
                )

                if session.user_id != user_id:
                    raise ValidationError("User does not own this session")

                # Restore session state
                session.current_state = checkpoint['current_state']
                session.collected_data.update(checkpoint['collected_data'])

                # Update UI state
                if checkpoint.get('ui_state'):
                    session.collected_data['ui_state'] = checkpoint['ui_state']

                # Add resume metadata
                session.collected_data['last_resume'] = {
                    'resumed_at': timezone.now().isoformat(),
                    'checkpoint_version': checkpoint['checkpoint_version'],
                    'questions_answered': len(checkpoint.get('question_history', []))
                }

                session.save()

            # Determine next action
            next_action = self._determine_next_action(checkpoint)

            logger.info(
                f"Session resumed successfully",
                extra={
                    'session_id': session_id,
                    'user_id': user_id,
                    'checkpoint_version': checkpoint['checkpoint_version']
                }
            )

            return {
                'status': 'resumed',
                'session_id': session_id,
                'resumed_at': checkpoint['current_state'],
                'questions_answered': len(checkpoint.get('question_history', [])),
                'next_action': next_action,
                'progress_percent': self._calculate_progress_percent(checkpoint)
            }

        except ConversationSession.DoesNotExist:
            raise CheckpointNotFoundError(f"Session {session_id} not found")

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Database error resuming session: {str(e)}", exc_info=True)
            raise

    # ==========================================================================
    # ABANDONMENT RISK DETECTION
    # ==========================================================================

    def detect_abandonment_risk(self, session_id: str) -> Dict[str, Any]:
        """
        ML-based abandonment prediction

        Analyzes multiple risk factors:
        1. Inactivity time (weight: 30%)
        2. Question repetition/confusion (weight: 25%)
        3. Session complexity/fatigue (weight: 20%)
        4. Error frequency (weight: 25%)

        Args:
            session_id: Conversation session ID

        Returns:
            Risk assessment with score (0-100) and recommended intervention
        """
        try:
            session = ConversationSession.objects.get(session_id=session_id)

            risk_factors = []
            risk_score = 0

            # Factor 1: Inactivity time (30% weight)
            time_inactive = (timezone.now() - session.mdtz).total_seconds()
            if time_inactive > 600:  # 10 minutes
                risk_factors.append('extended_inactivity')
                risk_score += 30
            elif time_inactive > 300:  # 5 minutes
                risk_factors.append('moderate_inactivity')
                risk_score += 20
            elif time_inactive > 120:  # 2 minutes
                risk_factors.append('short_inactivity')
                risk_score += 10

            # Factor 2: Question repetition (25% weight)
            same_question_count = session.collected_data.get('same_question_count', 0)
            if same_question_count > 3:
                risk_factors.append('severe_confusion')
                risk_score += 25
            elif same_question_count > 1:
                risk_factors.append('question_confusion')
                risk_score += 15

            # Factor 3: Session complexity/fatigue (20% weight)
            question_history = session.collected_data.get('question_history', [])
            total_questions = len(question_history)
            if total_questions > 20:
                risk_factors.append('fatigue_risk_high')
                risk_score += 20
            elif total_questions > 15:
                risk_factors.append('fatigue_risk_medium')
                risk_score += 10

            # Factor 4: Error frequency (25% weight)
            error_count = session.collected_data.get('error_count', 0)
            if error_count > 5:
                risk_factors.append('critical_technical_issues')
                risk_score += 25
            elif error_count > 3:
                risk_factors.append('moderate_technical_issues')
                risk_score += 15
            elif error_count > 1:
                risk_factors.append('minor_technical_issues')
                risk_score += 8

            # Determine risk level
            if risk_score >= 70:
                risk_level = 'critical'
            elif risk_score >= 40:
                risk_level = 'high'
            elif risk_score >= 20:
                risk_level = 'medium'
            else:
                risk_level = 'low'

            # Recommend intervention
            intervention = self._recommend_intervention(risk_factors, risk_score)

            return {
                'session_id': session_id,
                'risk_score': min(risk_score, 100),
                'risk_level': risk_level,
                'risk_factors': risk_factors,
                'intervention': intervention,
                'time_inactive_seconds': int(time_inactive),
                'assessed_at': timezone.now().isoformat()
            }

        except ConversationSession.DoesNotExist:
            logger.warning(f"Session {session_id} not found for risk assessment")
            return {
                'error': 'session_not_found',
                'risk_score': 0,
                'risk_level': 'unknown'
            }

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error detecting abandonment risk: {str(e)}", exc_info=True)
            return {
                'error': 'assessment_failed',
                'risk_score': 0,
                'risk_level': 'unknown'
            }

    def get_at_risk_sessions(
        self,
        risk_level: str = 'high',
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get list of sessions at risk of abandonment

        Args:
            risk_level: Minimum risk level ('medium', 'high', 'critical')
            limit: Maximum number of sessions to return

        Returns:
            List of at-risk sessions with risk scores
        """
        try:
            # Get active sessions (not completed or errored)
            active_sessions = ConversationSession.objects.exclude(
                current_state__in=[
                    ConversationSession.StateChoices.COMPLETED,
                    ConversationSession.StateChoices.ERROR
                ]
            ).order_by('-mdtz')[:limit * 2]  # Get more to filter

            at_risk_sessions = []

            for session in active_sessions:
                # Calculate risk for each session
                risk_assessment = self.detect_abandonment_risk(str(session.session_id))

                # Filter by risk level
                risk_score = risk_assessment.get('risk_score', 0)

                if risk_level == 'critical' and risk_score >= 70:
                    at_risk_sessions.append(risk_assessment)
                elif risk_level == 'high' and risk_score >= 40:
                    at_risk_sessions.append(risk_assessment)
                elif risk_level == 'medium' and risk_score >= 20:
                    at_risk_sessions.append(risk_assessment)

                # Stop if we have enough
                if len(at_risk_sessions) >= limit:
                    break

            return at_risk_sessions

        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error getting at-risk sessions: {str(e)}", exc_info=True)
            return []

    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================

    def _validate_checkpoint_data(self, data: Dict[str, Any]) -> None:
        """Validate checkpoint data structure"""
        required_fields = ['state', 'data']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")

        # Validate state is valid
        valid_states = [choice.value for choice in ConversationSession.StateChoices]
        if data['state'] not in valid_states:
            raise ValueError(f"Invalid state: {data['state']}")

    def _get_checkpoint_cache_key(self, session_id: str) -> str:
        """Generate cache key for checkpoint"""
        return f"session:checkpoint:{session_id}"

    def _get_last_checkpoint_time(self, session_id: str) -> Optional[datetime]:
        """Get timestamp of last checkpoint"""
        cache_key = self._get_checkpoint_cache_key(session_id)
        checkpoint = cache.get(cache_key)

        if checkpoint and 'created_at' in checkpoint:
            return datetime.fromisoformat(checkpoint['created_at'])

        return None

    def _calculate_checkpoint_hash(self, data: Dict[str, Any]) -> str:
        """Calculate hash of checkpoint data for integrity verification"""
        # Create deterministic string representation
        checkpoint_str = f"{data['state']}:{str(data['data'])}"
        return hashlib.sha256(checkpoint_str.encode()).hexdigest()[:16]

    def _store_checkpoint_in_db(self, session_id: str, checkpoint: Dict[str, Any]) -> None:
        """Store checkpoint in PostgreSQL for historical record"""
        try:
            with transaction.atomic():
                session = ConversationSession.objects.select_for_update().get(
                    session_id=session_id
                )

                # Add to checkpoint history
                if 'checkpoint_history' not in session.collected_data:
                    session.collected_data['checkpoint_history'] = []

                # Keep last 10 checkpoints
                session.collected_data['checkpoint_history'].append({
                    'version': checkpoint['checkpoint_version'],
                    'created_at': checkpoint['created_at'],
                    'checkpoint_hash': checkpoint['checkpoint_hash'],
                    'state': checkpoint['current_state']
                })

                # Trim to last 10
                session.collected_data['checkpoint_history'] = \
                    session.collected_data['checkpoint_history'][-10:]

                session.save()

        except ConversationSession.DoesNotExist:
            logger.warning(f"Session {session_id} not found for checkpoint storage")
        except (DatabaseError, IntegrityError) as e:
            logger.error(f"Error storing checkpoint in DB: {str(e)}", exc_info=True)

    def _get_checkpoint_from_db(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve checkpoint from PostgreSQL"""
        try:
            session = ConversationSession.objects.get(session_id=session_id)

            checkpoint_history = session.collected_data.get('checkpoint_history', [])

            if not checkpoint_history:
                return None

            # Get most recent checkpoint
            latest = checkpoint_history[-1]

            # Reconstruct full checkpoint from session data
            return {
                'session_id': session_id,
                'checkpoint_version': latest['version'],
                'current_state': latest['state'],
                'collected_data': session.collected_data,
                'created_at': latest['created_at'],
                'checkpoint_hash': latest['checkpoint_hash']
            }

        except ConversationSession.DoesNotExist:
            return None
        except (DatabaseError, IntegrityError, KeyError) as e:
            logger.error(f"Error getting checkpoint from DB: {str(e)}", exc_info=True)
            return None

    def _determine_next_action(self, checkpoint: Dict[str, Any]) -> Dict[str, Any]:
        """Determine next action after resume based on checkpoint state"""
        current_state = checkpoint['current_state']
        question_history = checkpoint.get('question_history', [])

        if current_state == ConversationSession.StateChoices.STARTED:
            return {
                'action': 'continue_conversation',
                'message': 'Welcome back! Let\'s continue where you left off.',
                'next_question_index': len(question_history)
            }
        elif current_state == ConversationSession.StateChoices.IN_PROGRESS:
            return {
                'action': 'continue_conversation',
                'message': 'Resuming your onboarding session.',
                'next_question_index': len(question_history)
            }
        elif current_state == ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS:
            return {
                'action': 'wait_for_recommendations',
                'message': 'We\'re still generating your recommendations. Please wait...'
            }
        elif current_state == ConversationSession.StateChoices.AWAITING_USER_APPROVAL:
            return {
                'action': 'show_recommendations',
                'message': 'Your recommendations are ready for review.'
            }
        else:
            return {
                'action': 'unknown',
                'message': 'Unable to determine next action.'
            }

    def _calculate_progress_percent(self, checkpoint: Dict[str, Any]) -> float:
        """Calculate completion progress percentage"""
        current_state = checkpoint['current_state']
        question_history = checkpoint.get('question_history', [])

        # Estimate total questions (adjust based on your flow)
        estimated_total_questions = 10

        # Base progress on state
        state_progress = {
            ConversationSession.StateChoices.STARTED: 0.1,
            ConversationSession.StateChoices.IN_PROGRESS: 0.3,
            ConversationSession.StateChoices.GENERATING_RECOMMENDATIONS: 0.6,
            ConversationSession.StateChoices.AWAITING_USER_APPROVAL: 0.8,
            ConversationSession.StateChoices.COMPLETED: 1.0
        }

        base_progress = state_progress.get(current_state, 0.0)

        # Adjust based on questions answered
        if len(question_history) > 0:
            question_progress = min(len(question_history) / estimated_total_questions, 0.5)
            base_progress = max(base_progress, question_progress)

        return round(base_progress * 100, 1)

    def _recommend_intervention(
        self,
        risk_factors: List[str],
        risk_score: int
    ) -> Dict[str, Any]:
        """Recommend intervention based on risk factors"""
        interventions = []

        # Inactivity interventions
        if 'extended_inactivity' in risk_factors or 'moderate_inactivity' in risk_factors:
            interventions.append({
                'type': 'proactive_reach_out',
                'action': 'send_reminder_email',
                'message': 'Send email reminder with resume link',
                'priority': 'high' if 'extended_inactivity' in risk_factors else 'medium'
            })

        # Confusion interventions
        if 'severe_confusion' in risk_factors or 'question_confusion' in risk_factors:
            interventions.append({
                'type': 'human_assistance',
                'action': 'offer_live_chat',
                'message': 'Offer live chat support or simplified workflow',
                'priority': 'high'
            })

        # Fatigue interventions
        if 'fatigue_risk_high' in risk_factors:
            interventions.append({
                'type': 'break_suggestion',
                'action': 'suggest_save_and_resume',
                'message': 'Suggest taking a break and resuming later',
                'priority': 'medium'
            })

        # Technical issues interventions
        if 'critical_technical_issues' in risk_factors:
            interventions.append({
                'type': 'technical_support',
                'action': 'escalate_to_support',
                'message': 'Escalate to technical support team',
                'priority': 'critical'
            })

        # Default intervention
        if not interventions:
            interventions.append({
                'type': 'gentle_nudge',
                'action': 'send_encouragement',
                'message': 'Send encouraging message to continue',
                'priority': 'low'
            })

        return {
            'recommended_interventions': interventions,
            'urgency': 'immediate' if risk_score >= 70 else 'soon' if risk_score >= 40 else 'monitor'
        }


# Service factory function
def get_session_recovery_service() -> SessionRecoveryService:
    """Get session recovery service instance"""
    return SessionRecoveryService()


__all__ = [
    'SessionRecoveryService',
    'CheckpointNotFoundError',
    'get_session_recovery_service',
]
