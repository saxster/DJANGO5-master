"""
Integration adapter for mapping AI recommendations to actual system models
Safely applies approved recommendations to Bt/Shift/TypeAssist (Phase 1 MVP)
"""
import logging
import hashlib
import time
import random
from django.db import transaction, IntegrityError
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.onboarding.models import Bt, Shift, TypeAssist, LLMRecommendation
from apps.peoples.models import People

logger = logging.getLogger(__name__)


class IntegrationAdapter:
    """
    Safe write-through adapter for applying AI recommendations to system models
    Supports dry-run mode and idempotent operations
    """

    def __init__(self):
        self.supported_types = [
            'business_unit_setup',
            'shift_configuration',
            'type_assist_setup',
            'security_configuration'
        ]
        self.max_retries = 3
        self.base_delay = 0.1  # 100ms base delay for exponential backoff

    def _generate_idempotency_key(self, operation_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> str:
        """Generate an idempotency key for an operation"""
        # Create a deterministic hash from operation parameters
        key_data = {
            'operation_type': operation_type,
            'data': data,
            'context': context or {}
        }

        # Sort and serialize the data for consistent hashing
        serialized = str(sorted(key_data.items()))
        return hashlib.sha256(serialized.encode()).hexdigest()[:16]

    def _retry_with_exponential_backoff(self, operation, operation_name: str, max_retries: int = None):
        """Retry an operation with exponential backoff"""
        max_retries = max_retries or self.max_retries

        for attempt in range(max_retries + 1):
            try:
                return operation()
            except IntegrityError as e:
                if attempt == max_retries:
                    logger.error(f"Operation {operation_name} failed after {max_retries} retries: {str(e)}")
                    raise

                # Exponential backoff with jitter
                delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                logger.warning(f"Operation {operation_name} failed on attempt {attempt + 1}, retrying in {delay:.2f}s: {str(e)}")
                time.sleep(delay)
            except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValidationError, ValueError) as e:
                logger.error(f"Non-retryable error in operation {operation_name}: {str(e)}")
                raise

    def _check_operation_conflicts(self, operation_type: str, data: Dict[str, Any], client: Bt) -> List[Dict[str, Any]]:
        """Check for potential conflicts before applying an operation"""
        conflicts = []

        if operation_type == 'business_unit_setup':
            bu_code = data.get('bu_code', f"AUTO_{client.id}")
            existing_bu = Bt.objects.filter(bucode=bu_code, parent=client).first()
            if existing_bu:
                conflicts.append({
                    'type': 'duplicate_bu_code',
                    'message': f'Business unit with code {bu_code} already exists',
                    'existing_object': str(existing_bu.id),
                    'resolution': 'update_existing'
                })

        elif operation_type == 'shift_configuration':
            shift_name = data.get('shift_name', 'Default Shift')
            existing_shift = Shift.objects.filter(shiftname=shift_name, client=client).first()
            if existing_shift:
                conflicts.append({
                    'type': 'duplicate_shift_name',
                    'message': f'Shift with name {shift_name} already exists',
                    'existing_object': str(existing_shift.id),
                    'resolution': 'update_existing'
                })

        elif operation_type == 'type_assist_setup':
            ta_code = data.get('ta_code', 'AUTO_TYPE')
            existing_ta = TypeAssist.objects.filter(tacode=ta_code, client=client).first()
            if existing_ta:
                conflicts.append({
                    'type': 'duplicate_typeassist_code',
                    'message': f'TypeAssist with code {ta_code} already exists',
                    'existing_object': str(existing_ta.id),
                    'resolution': 'update_existing'
                })

        return conflicts

    def _create_with_idempotency(self, model_class, create_data: Dict, unique_fields: List[str], update_fields: List[str] = None):
        """Create or update an object with idempotency guarantees"""
        # Build lookup filter from unique fields
        lookup_filter = {field: create_data[field] for field in unique_fields if field in create_data}

        def _perform_operation():
            with transaction.atomic():
                # Try to get existing object
                existing_obj = model_class.objects.filter(**lookup_filter).first()

                if existing_obj:
                    if update_fields:
                        # Update existing object with new data
                        updated = False
                        for field in update_fields:
                            if field in create_data and getattr(existing_obj, field) != create_data[field]:
                                setattr(existing_obj, field, create_data[field])
                                updated = True

                        if updated:
                            existing_obj.save()
                            logger.info(f"Updated existing {model_class.__name__} with {lookup_filter}")

                    return existing_obj, False  # False indicates update, not create
                else:
                    # Create new object
                    new_obj = model_class.objects.create(**create_data)
                    logger.info(f"Created new {model_class.__name__} with {lookup_filter}")
                    return new_obj, True  # True indicates create

        return self._retry_with_exponential_backoff(
            _perform_operation,
            f"create_or_update_{model_class.__name__}"
        )

    def apply_recommendations(
        self,
        approved_items: List[str],
        rejected_items: List[str],
        reasons: Dict[str, str],
        modifications: Dict[str, Any],
        dry_run: bool = True,
        user: Optional[People] = None,
        changeset = None
    ) -> Dict[str, Any]:
        """
        Apply multiple approved recommendations

        Args:
            approved_items: List of recommendation UUIDs to approve
            rejected_items: List of recommendation UUIDs to reject
            reasons: Rejection reasons by recommendation ID
            modifications: User modifications by recommendation ID
            dry_run: Whether to perform dry run without actual changes
            user: User performing the approval
            changeset: AIChangeSet instance for tracking changes (optional)

        Returns:
            Dictionary with configuration summary and implementation plan
        """
        logger.info(f"Applying {len(approved_items)} recommendations (dry_run={dry_run})")

        results = {
            'configuration': {},
            'plan': [],
            'learning_applied': False,
            'dry_run': dry_run,
            'applied_items': [],
            'failed_items': [],
            'rejected_items': [],
        }

        # Process approved items
        for item_id in approved_items:
            try:
                recommendation = LLMRecommendation.objects.get(recommendation_id=item_id)

                # Apply user modifications if any
                modified_consensus = self._apply_user_modifications(
                    recommendation.consensus,
                    modifications.get(item_id, {})
                )

                # Apply single recommendation
                result = self.apply_single_recommendation(
                    recommendation,
                    user,
                    dry_run,
                    modified_consensus,
                    changeset  # Pass changeset for change tracking
                )

                if result['success']:
                    results['applied_items'].append({
                        'recommendation_id': item_id,
                        'changes': result['changes'],
                        'configuration': result.get('configuration', {})
                    })

                    # Merge configuration
                    self._merge_configuration(results['configuration'], result.get('configuration', {}))

                else:
                    results['failed_items'].append({
                        'recommendation_id': item_id,
                        'error': result['error']
                    })

            except LLMRecommendation.DoesNotExist:
                logger.error(f"Recommendation {item_id} not found")
                results['failed_items'].append({
                    'recommendation_id': item_id,
                    'error': 'Recommendation not found'
                })

        # Process rejected items
        for item_id in rejected_items:
            try:
                recommendation = LLMRecommendation.objects.get(recommendation_id=item_id)

                if not dry_run:
                    recommendation.user_decision = LLMRecommendation.UserDecisionChoices.REJECTED
                    recommendation.rejection_reason = reasons.get(item_id, '')
                    recommendation.save()

                results['rejected_items'].append({
                    'recommendation_id': item_id,
                    'reason': reasons.get(item_id, '')
                })

                # Learn from rejection for future improvements
                self._learn_from_rejection(recommendation, reasons.get(item_id, ''))

            except LLMRecommendation.DoesNotExist:
                logger.error(f"Recommendation {item_id} not found for rejection")

        # Generate implementation plan
        results['plan'] = self._generate_implementation_plan(results['applied_items'])

        # Apply learning from user feedback
        results['learning_applied'] = self._apply_learning_feedback(
            results['applied_items'],
            results['rejected_items']
        )

        return results

    def apply_single_recommendation(
        self,
        recommendation: LLMRecommendation,
        user: Optional[People] = None,
        dry_run: bool = True,
        consensus: Optional[Dict[str, Any]] = None,
        changeset = None
    ) -> Dict[str, Any]:
        """
        Apply a single recommendation to the system

        Args:
            recommendation: The recommendation to apply
            user: User performing the action
            dry_run: Whether to perform dry run
            consensus: Optional modified consensus data
            changeset: AIChangeSet instance for tracking changes

        Returns:
            Result dictionary with success status and details
        """
        result = {
            'success': False,
            'changes': [],
            'configuration': {},
            'error': None
        }

        try:
            consensus_data = consensus or recommendation.consensus
            recommendations = consensus_data.get('recommendations', {})

            with transaction.atomic():
                # Business Unit Configuration
                if 'business_unit_config' in recommendations:
                    bu_result = self._apply_business_unit_config(
                        recommendations['business_unit_config'],
                        recommendation.session.client,
                        dry_run,
                        changeset,
                        sequence_start=len(result['changes'])
                    )
                    result['changes'].extend(bu_result['changes'])
                    result['configuration'].update(bu_result['configuration'])

                # Shift Configuration
                if 'suggested_shifts' in recommendations:
                    shift_result = self._apply_shift_configuration(
                        recommendations['suggested_shifts'],
                        recommendation.session.client,
                        dry_run,
                        changeset,
                        sequence_start=len(result['changes'])
                    )
                    result['changes'].extend(shift_result['changes'])
                    result['configuration'].update(shift_result['configuration'])

                # TypeAssist Configuration
                if 'type_assist_configs' in recommendations:
                    ta_result = self._apply_typeassist_configuration(
                        recommendations['type_assist_configs'],
                        recommendation.session.client,
                        dry_run,
                        changeset,
                        sequence_start=len(result['changes'])
                    )
                    result['changes'].extend(ta_result['changes'])
                    result['configuration'].update(ta_result['configuration'])

                # Security Settings
                if 'security_settings' in recommendations:
                    security_result = self._apply_security_settings(
                        recommendations['security_settings'],
                        recommendation.session.client,
                        dry_run,
                        changeset,
                        sequence_start=len(result['changes'])
                    )
                    result['changes'].extend(security_result['changes'])
                    result['configuration'].update(security_result['configuration'])

                # Update recommendation status if not dry run
                if not dry_run:
                    recommendation.user_decision = LLMRecommendation.UserDecisionChoices.APPROVED
                    recommendation.save()

                result['success'] = True
                logger.info(f"Successfully applied recommendation {recommendation.recommendation_id}")

        except ValidationError as e:
            result['error'] = f"Validation error: {str(e)}"
            logger.error(f"Validation error applying recommendation: {str(e)}")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            result['error'] = f"Application error: {str(e)}"
            logger.error(f"Error applying recommendation: {str(e)}")

        return result

    def _apply_business_unit_config(
        self,
        bu_config: Dict[str, Any],
        client: Bt,
        dry_run: bool,
        changeset = None,
        sequence_start: int = 0
    ) -> Dict[str, Any]:
        """Apply business unit configuration"""
        result = {'changes': [], 'configuration': {}}

        try:
            # Find or create business unit
            bu_name = bu_config.get('bu_name', f"New BU {client.buname}")
            bu_code = bu_config.get('bu_code', f"AUTO_{client.id}")

            if dry_run:
                result['changes'].append({
                    'action': 'create_business_unit',
                    'model': 'Bt',
                    'data': {
                        'buname': bu_name,
                        'bucode': bu_code,
                        'parent': client.id,
                        'max_users': bu_config.get('max_users', 10)
                    },
                    'dry_run': True
                })
            else:
                # Generate idempotency key
                idempotency_key = self._generate_idempotency_key(
                    'business_unit_setup',
                    bu_config,
                    {'client_id': client.id}
                )

                # Check for conflicts before proceeding
                conflicts = self._check_operation_conflicts('business_unit_setup', bu_config, client)
                if conflicts:
                    logger.info(f"Detected conflicts for BU setup: {conflicts}")

                # Prepare data for create/update
                bu_data = {
                    'buname': bu_name,
                    'bucode': bu_code,
                    'parent': client,
                    'onboarding_context': {
                        'ai_configured': True,
                        'configuration_data': bu_config,
                        'configured_at': timezone.now().isoformat(),
                        'idempotency_key': idempotency_key
                    },
                    'setup_confidence_score': bu_config.get('confidence_score', 0.8)
                }

                # Use idempotent create/update
                bu_obj, was_created = self._create_with_idempotency(
                    model_class=Bt,
                    create_data=bu_data,
                    unique_fields=['bucode', 'parent'],
                    update_fields=['buname', 'onboarding_context', 'setup_confidence_score']
                )

                # Track change in changeset
                if changeset and not dry_run:
                    from apps.onboarding.models import AIChangeRecord
                    action = AIChangeRecord.ActionChoices.CREATE if was_created else AIChangeRecord.ActionChoices.UPDATE

                    # Get before state for updates
                    before_state = None
                    if not was_created:
                        # For updates, we need to reconstruct the before state
                        before_state = self._serialize_model_instance(bu_obj)

                    self.track_change(
                        changeset=changeset,
                        action=action,
                        model_instance=bu_obj,
                        before_state=before_state,
                        sequence_order=sequence_start + len(result['changes'])
                    )

                result['changes'].append({
                    'action': 'create_business_unit' if was_created else 'update_business_unit',
                    'model': 'Bt',
                    'id': bu_obj.id,
                    'idempotency_key': idempotency_key,
                    'data': {
                        'buname': bu_name,
                        'bucode': bu_code
                    },
                    'conflicts_resolved': len(conflicts) if conflicts else 0
                })

            result['configuration']['business_unit'] = {
                'name': bu_name,
                'code': bu_code,
                'max_users': bu_config.get('max_users', 10),
                'type': bu_config.get('bu_type', 'Office')
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error applying business unit config: {str(e)}")
            raise

        return result

    def _apply_shift_configuration(
        self,
        shift_configs: List[Dict[str, Any]],
        client: Bt,
        dry_run: bool,
        changeset = None,
        sequence_start: int = 0
    ) -> Dict[str, Any]:
        """Apply shift configurations"""
        result = {'changes': [], 'configuration': {}}

        try:
            created_shifts = []

            for shift_config in shift_configs:
                shift_name = shift_config.get('shift_name', 'Default Shift')

                if dry_run:
                    result['changes'].append({
                        'action': 'create_shift',
                        'model': 'Shift',
                        'data': {
                            'shiftname': shift_name,
                            'starttime': shift_config.get('start_time', '09:00'),
                            'endtime': shift_config.get('end_time', '17:00'),
                            'peoplecount': shift_config.get('people_count', 5),
                            'client': client.id
                        },
                        'dry_run': True
                    })
                else:
                    # Check if shift already exists
                    existing_shift = Shift.objects.filter(
                        shiftname=shift_name,
                        client=client
                    ).first()

                    # Generate idempotency key
                    idempotency_key = self._generate_idempotency_key(
                        'shift_configuration',
                        shift_config,
                        {'client_id': client.id}
                    )

                    # Check for conflicts
                    conflicts = self._check_operation_conflicts('shift_configuration', shift_config, client)

                    # Prepare shift data
                    shift_data = {
                        'shiftname': shift_name,
                        'starttime': shift_config.get('start_time', '09:00'),
                        'endtime': shift_config.get('end_time', '17:00'),
                        'peoplecount': shift_config.get('people_count', 5),
                        'client': client,
                        'bu': client,  # Associate with client BU
                        'enable': True,
                        'shift_data': {
                            'ai_configured': True,
                            'original_config': shift_config,
                            'idempotency_key': idempotency_key
                        }
                    }

                    # Use idempotent create/update
                    shift_obj, was_created = self._create_with_idempotency(
                        model_class=Shift,
                        create_data=shift_data,
                        unique_fields=['shiftname', 'client'],
                        update_fields=['starttime', 'endtime', 'peoplecount', 'shift_data']
                    )

                    # Track creation in changeset
                    if changeset and not dry_run:
                        from apps.onboarding.models import AIChangeRecord
                        action = AIChangeRecord.ActionChoices.CREATE if was_created else AIChangeRecord.ActionChoices.UPDATE

                        self.track_change(
                            changeset=changeset,
                            action=action,
                            model_instance=shift_obj,
                            sequence_order=sequence_start + len(result['changes'])
                        )

                    result['changes'].append({
                        'action': 'create_shift' if was_created else 'update_shift',
                        'model': 'Shift',
                        'id': shift_obj.id,
                        'idempotency_key': idempotency_key,
                        'data': {
                            'shiftname': shift_name,
                            'starttime': shift_config.get('start_time'),
                            'endtime': shift_config.get('end_time')
                        },
                        'conflicts_resolved': len(conflicts) if conflicts else 0
                    })

                    created_shifts.append({
                        'name': shift_name,
                        'start_time': shift_config.get('start_time'),
                            'end_time': shift_config.get('end_time'),
                            'people_count': shift_config.get('people_count', 5)
                        })

            result['configuration']['shifts'] = created_shifts

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error applying shift configuration: {str(e)}")
            raise

        return result

    def _apply_typeassist_configuration(
        self,
        ta_configs: List[Dict[str, Any]],
        client: Bt,
        dry_run: bool,
        changeset = None,
        sequence_start: int = 0
    ) -> Dict[str, Any]:
        """Apply TypeAssist configurations"""
        result = {'changes': [], 'configuration': {}}

        try:
            created_typeassists = []

            for ta_config in ta_configs:
                ta_code = ta_config.get('ta_code', 'AUTO_TYPE')
                ta_name = ta_config.get('ta_name', 'AI Generated Type')

                if dry_run:
                    result['changes'].append({
                        'action': 'create_typeassist',
                        'model': 'TypeAssist',
                        'data': {
                            'tacode': ta_code,
                            'taname': ta_name,
                            'client': client.id
                        },
                        'dry_run': True
                    })
                else:
                    # Check if TypeAssist already exists
                    existing_ta = TypeAssist.objects.filter(
                        tacode=ta_code,
                        client=client
                    ).first()

                    if not existing_ta:
                        # Create new TypeAssist
                        new_ta = TypeAssist.objects.create(
                            tacode=ta_code,
                            taname=ta_name,
                            client=client,
                            bu=client,
                            enable=True
                        )

                        # Track creation in changeset
                        if changeset and not dry_run:
                            from apps.onboarding.models import AIChangeRecord
                            self.track_change(
                                changeset=changeset,
                                action=AIChangeRecord.ActionChoices.CREATE,
                                model_instance=new_ta,
                                sequence_order=sequence_start + len(result['changes'])
                            )

                        result['changes'].append({
                            'action': 'create_typeassist',
                            'model': 'TypeAssist',
                            'id': new_ta.id,
                            'data': {
                                'tacode': ta_code,
                                'taname': ta_name
                            }
                        })

                        created_typeassists.append({
                            'code': ta_code,
                            'name': ta_name,
                            'description': ta_config.get('description', '')
                        })

            result['configuration']['type_assists'] = created_typeassists

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error applying TypeAssist configuration: {str(e)}")
            raise

        return result

    def _apply_security_settings(
        self,
        security_config: Dict[str, Any],
        client: Bt,
        dry_run: bool,
        changeset = None,
        sequence_start: int = 0
    ) -> Dict[str, Any]:
        """Apply security settings to business unit"""
        result = {'changes': [], 'configuration': {}}

        try:
            security_updates = {}

            # GPS settings
            if 'enable_gps' in security_config:
                security_updates['gpsenable'] = security_config['enable_gps']

            # Sleeping guard detection
            if 'enable_sleeping_guard' in security_config:
                security_updates['enablesleepingguard'] = security_config['enable_sleeping_guard']

            # Permissible distance
            if 'permissible_distance' in security_config:
                security_updates['pdist'] = float(security_config['permissible_distance'])

            if dry_run:
                result['changes'].append({
                    'action': 'update_security_settings',
                    'model': 'Bt',
                    'id': client.id,
                    'updates': security_updates,
                    'dry_run': True
                })
            else:
                if security_updates:
                    # Track before state for changeset
                    if changeset and not dry_run:
                        before_state = self._serialize_model_instance(client)

                    # Update client security settings
                    for field, value in security_updates.items():
                        setattr(client, field, value)

                    # Update onboarding context
                    client.onboarding_context.update({
                        'security_configured': True,
                        'security_settings': security_config
                    })

                    client.save()

                    # Track change in changeset
                    if changeset and not dry_run:
                        from apps.onboarding.models import AIChangeRecord
                        self.track_change(
                            changeset=changeset,
                            action=AIChangeRecord.ActionChoices.UPDATE,
                            model_instance=client,
                            before_state=before_state,
                            sequence_order=sequence_start + len(result['changes'])
                        )

                    result['changes'].append({
                        'action': 'update_security_settings',
                        'model': 'Bt',
                        'id': client.id,
                        'updates': list(security_updates.keys())
                    })

            result['configuration']['security'] = {
                'gps_enabled': security_config.get('enable_gps', False),
                'sleeping_guard_detection': security_config.get('enable_sleeping_guard', False),
                'permissible_distance': security_config.get('permissible_distance', 100)
            }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError) as e:
            logger.error(f"Error applying security settings: {str(e)}")
            raise

        return result

    def _apply_user_modifications(
        self,
        consensus: Dict[str, Any],
        modifications: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply user modifications to consensus data"""
        if not modifications:
            return consensus

        modified_consensus = consensus.copy()

        # Apply modifications recursively
        for key, value in modifications.items():
            if key in modified_consensus:
                if isinstance(value, dict) and isinstance(modified_consensus[key], dict):
                    modified_consensus[key].update(value)
                else:
                    modified_consensus[key] = value

        # Add modification metadata
        from django.utils import timezone
        modified_consensus['user_modifications'] = {
            'applied_at': timezone.now().isoformat(),
            'modifications': modifications
        }

        return modified_consensus

    def _merge_configuration(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge source configuration into target"""
        for key, value in source.items():
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], dict):
                    target[key].update(value)
                elif isinstance(value, list) and isinstance(target[key], list):
                    target[key].extend(value)
                else:
                    target[key] = value
            else:
                target[key] = value

    def _generate_implementation_plan(self, applied_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate implementation plan from applied items"""
        plan = []

        for item in applied_items:
            for change in item.get('changes', []):
                plan.append({
                    'step': len(plan) + 1,
                    'action': change['action'],
                    'model': change['model'],
                    'description': self._get_action_description(change),
                    'status': 'completed' if 'id' in change else 'planned'
                })

        return plan

    def _get_action_description(self, change: Dict[str, Any]) -> str:
        """Get human-readable description for an action"""
        action_descriptions = {
            'create_business_unit': 'Create new business unit with AI-recommended configuration',
            'update_business_unit': 'Update business unit with AI recommendations',
            'create_shift': 'Create shift schedule based on operating hours',
            'create_typeassist': 'Set up type assistance configuration',
            'update_security_settings': 'Apply recommended security settings'
        }
        return action_descriptions.get(change['action'], f"Perform {change['action']}")

    def _learn_from_rejection(self, recommendation: LLMRecommendation, reason: str):
        """Learn from rejected recommendations for future improvements"""
        # For MVP, simple logging - can be expanded to update ML models later
        logger.info(f"Learning from rejection: {recommendation.recommendation_id} - {reason}")

        # Update recommendation with learning data (placeholder for future ML integration)
        if not hasattr(recommendation, 'learning_data'):
            recommendation.learning_data = {}

        recommendation.learning_data['rejection_reason'] = reason
        from django.utils import timezone
        recommendation.learning_data['rejected_at'] = timezone.now().isoformat()

    def _apply_learning_feedback(
        self,
        applied_items: List[Dict[str, Any]],
        rejected_items: List[Dict[str, Any]]
    ) -> bool:
        """Apply learning from user feedback"""
        # For MVP, simple logging - placeholder for future ML integration
        logger.info(f"Learning feedback: {len(applied_items)} approved, {len(rejected_items)} rejected")
        return True  # Placeholder return value

    # =============================================================================
    # CHANGE TRACKING AND ROLLBACK FUNCTIONALITY
    # =============================================================================

    def _serialize_model_instance(self, instance):
        """Serialize a Django model instance to a dictionary for change tracking"""
        try:
            from django.core import serializers
            import json

            # Use Django's serializer to get the data
            serialized = serializers.serialize('json', [instance])
            data = json.loads(serialized)[0]

            # Return just the fields portion with pk included
            result = data['fields']
            result['pk'] = data['pk']
            result['model'] = data['model']

            return result
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error serializing model instance {instance}: {str(e)}")
            return {'error': f'serialization_failed: {str(e)}'}

    def create_changeset(self, conversation_session, approved_by, description="AI Recommendations Applied"):
        """Create a new changeset for tracking changes"""
        from apps.onboarding.models import AIChangeSet
        from django.utils import timezone

        changeset = AIChangeSet.objects.create(
            conversation_session=conversation_session,
            approved_by=approved_by,
            description=description,
            status=AIChangeSet.StatusChoices.PENDING,
            metadata={}
        )

        logger.info(f"Created changeset {changeset.changeset_id} for session {conversation_session.session_id}")
        return changeset

    def track_change(self, changeset, action, model_instance, before_state=None, after_state=None, sequence_order=0):
        """Track an individual change within a changeset"""
        from apps.onboarding.models import AIChangeRecord
        from django.core import serializers
        import json

        # Serialize model states
        if before_state is None and action != AIChangeRecord.ActionChoices.CREATE:
            before_state = self._serialize_model_instance(model_instance)

        if after_state is None and action != AIChangeRecord.ActionChoices.DELETE:
            after_state = self._serialize_model_instance(model_instance)

        # Create change record
        change_record = AIChangeRecord.objects.create(
            changeset=changeset,
            sequence_order=sequence_order,
            model_name=model_instance._meta.model_name,
            app_label=model_instance._meta.app_label,
            object_id=str(model_instance.pk),
            action=action,
            before_state=before_state,
            after_state=after_state,
            status=AIChangeRecord.StatusChoices.PENDING
        )

        logger.debug(f"Tracked change {change_record.record_id}: {action} {model_instance._meta.model_name}")
        return change_record

    def rollback_changeset(self, changeset, rollback_reason, rollback_user):
        """
        Rollback all changes in a changeset

        Args:
            changeset: AIChangeSet instance to rollback
            rollback_reason: Reason for rollback
            rollback_user: User performing the rollback

        Returns:
            dict: Rollback result summary
        """
        from apps.onboarding.models import AIChangeRecord
        from django.utils import timezone

        logger.info(f"Starting rollback of changeset {changeset.changeset_id}")

        rolled_back_count = 0
        failed_count = 0
        rollback_operations = []

        try:
            with transaction.atomic():
                # Get all change records in reverse order for rollback
                change_records = changeset.change_records.filter(
                    status=AIChangeRecord.StatusChoices.SUCCESS
                ).order_by('-sequence_order')

                for change_record in change_records:
                    try:
                        rollback_result = self._rollback_change_record(change_record)

                        if rollback_result.get('success', False):
                            change_record.status = AIChangeRecord.StatusChoices.ROLLED_BACK
                            change_record.rollback_attempted_at = timezone.now()
                            change_record.rollback_success = True
                            change_record.save()

                            rolled_back_count += 1
                            rollback_operations.append({
                                'record_id': str(change_record.record_id),
                                'model': change_record.model_name,
                                'action': 'rolled_back',
                                'success': True
                            })
                        else:
                            change_record.rollback_attempted_at = timezone.now()
                            change_record.rollback_success = False
                            change_record.rollback_error = rollback_result.get('error')
                            change_record.save()

                            failed_count += 1
                            rollback_operations.append({
                                'record_id': str(change_record.record_id),
                                'model': change_record.model_name,
                                'action': 'rollback_failed',
                                'error': rollback_result.get('error')
                            })

                    except (DatabaseError, IntegrityError) as e:
                        logger.error(f"Failed to rollback change record {change_record.record_id}: {e}")
                        change_record.rollback_attempted_at = timezone.now()
                        change_record.rollback_success = False
                        change_record.rollback_error = str(e)
                        change_record.save()
                        failed_count += 1

                # Update changeset status
                if failed_count == 0:
                    changeset.status = changeset.StatusChoices.ROLLED_BACK
                else:
                    changeset.status = changeset.StatusChoices.PARTIALLY_APPLIED

                changeset.rolled_back_by = rollback_user
                changeset.rolled_back_at = timezone.now()
                changeset.rollback_reason = rollback_reason
                changeset.save()

                logger.info(f"Rollback completed: {rolled_back_count} successful, {failed_count} failed")

                return {
                    'success': failed_count == 0,
                    'rolled_back_count': rolled_back_count,
                    'failed_count': failed_count,
                    'rollback_operations': rollback_operations,
                    'partial_success': rolled_back_count > 0 and failed_count > 0
                }

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Changeset rollback failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'rolled_back_count': rolled_back_count,
                'failed_count': failed_count + 1
            }

    def _rollback_change_record(self, change_record):
        """Rollback a single change record"""
        try:
            model_class = change_record.get_target_model()
            if not model_class:
                return {'success': False, 'error': f'Model {change_record.model_name} not found'}

            if change_record.action == change_record.ActionChoices.CREATE:
                # Delete the created object
                try:
                    obj = model_class.objects.get(pk=change_record.object_id)
                    obj.delete()
                    logger.debug(f"Deleted created object {change_record.model_name}({change_record.object_id})")
                    return {'success': True}
                except model_class.DoesNotExist:
                    return {'success': False, 'error': 'Object already deleted'}

            elif change_record.action == change_record.ActionChoices.UPDATE:
                # Restore previous state
                if not change_record.before_state:
                    return {'success': False, 'error': 'No before state available for rollback'}

                try:
                    obj = model_class.objects.get(pk=change_record.object_id)
                    self._restore_model_state(obj, change_record.before_state)
                    obj.save()
                    logger.debug(f"Restored object state {change_record.model_name}({change_record.object_id})")
                    return {'success': True}
                except model_class.DoesNotExist:
                    return {'success': False, 'error': 'Object no longer exists'}

            elif change_record.action == change_record.ActionChoices.DELETE:
                # Recreate the deleted object
                if not change_record.before_state:
                    return {'success': False, 'error': 'No state available to recreate object'}

                try:
                    # Create new instance with previous state
                    restored_obj = self._create_from_state(model_class, change_record.before_state)
                    restored_obj.save()
                    logger.debug(f"Recreated deleted object {change_record.model_name}({change_record.object_id})")
                    return {'success': True}
                except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                    return {'success': False, 'error': f'Failed to recreate object: {e}'}

            else:
                return {'success': False, 'error': f'Unknown action: {change_record.action}'}

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to rollback change record {change_record.record_id}: {e}")
            return {'success': False, 'error': str(e)}

    def _serialize_model_instance(self, instance):
        """Serialize model instance to JSON for state tracking"""
        from django.core import serializers
        from django.forms.models import model_to_dict

        try:
            # Use model_to_dict for better handling of complex fields
            data = model_to_dict(instance)

            # Convert non-serializable fields
            for key, value in data.items():
                if hasattr(value, 'pk'):  # Foreign key
                    data[key] = value.pk
                elif hasattr(value, '__iter__') and not isinstance(value, (str, bytes)):  # Many-to-many
                    try:
                        data[key] = [item.pk for item in value]
                    except:
                        data[key] = list(value)

            return data
        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to serialize {instance._meta.model_name}: {e}")
            return {}

    def _restore_model_state(self, instance, state_data):
        """Restore model instance from serialized state"""
        try:
            for field, value in state_data.items():
                if hasattr(instance, field):
                    field_obj = instance._meta.get_field(field)

                    # Handle foreign keys
                    if field_obj.many_to_one or field_obj.one_to_one:
                        if value:
                            related_model = field_obj.related_model
                            related_obj = related_model.objects.get(pk=value)
                            setattr(instance, field, related_obj)
                        else:
                            setattr(instance, field, None)
                    else:
                        setattr(instance, field, value)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to restore state for {instance._meta.model_name}: {e}")
            raise

    def _create_from_state(self, model_class, state_data):
        """Create model instance from serialized state"""
        try:
            # Remove auto fields and relations that can't be set during creation
            creation_data = state_data.copy()

            # Remove primary key if it's auto-generated
            if 'id' in creation_data and model_class._meta.pk.name == 'id':
                creation_data.pop('id')

            # Handle foreign keys and create instance
            instance = model_class(**creation_data)
            return instance

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Failed to create {model_class._meta.model_name} from state: {e}")
            raise