"""
Cost optimization and performance caching layer

This module provides comprehensive cost and performance optimization including:
- Token and response caching with intelligent cache keys
- Adaptive token budgeting based on user/tenant risk profiles
- Provider routing for cost-effective model selection
- Early exit and streaming capabilities
- Hot path precomputation for common scenarios
"""

import logging
import json
import hashlib
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from django.db import DatabaseError, IntegrityError
from django.core.exceptions import ObjectDoesNotExist, ValidationError

from apps.onboarding.models import Bt
from apps.peoples.models import People
from apps.onboarding_api.services.learning import PreferenceProfile
from apps.core.exceptions import LLMServiceException

logger = logging.getLogger(__name__)


class CacheKeyGenerator:
    """
    Generates intelligent cache keys for recommendation outputs
    """

    def __init__(self):
        self.version = getattr(settings, 'CACHE_VERSION', '1.0')

    def generate_maker_key(self, intent: str, kb_citations: List[str],
                          policy_version: str, context_hash: str) -> str:
        """Generate cache key for maker LLM output"""
        # Normalize intent
        normalized_intent = self._normalize_intent(intent)

        # Sort citations for consistent key
        sorted_citations = sorted(kb_citations) if kb_citations else []

        # Create cache key components
        key_components = [
            'maker',
            self.version,
            policy_version,
            normalized_intent,
            hashlib.sha256('|'.join(sorted_citations).encode()).hexdigest()[:16],
            context_hash[:16]
        ]

        cache_key = ':'.join(key_components)
        return cache_key[:250]  # Redis key length limit

    def generate_checker_key(self, maker_output_hash: str, context_hash: str,
                           policy_version: str) -> str:
        """Generate cache key for checker LLM output"""
        key_components = [
            'checker',
            self.version,
            policy_version,
            maker_output_hash[:16],
            context_hash[:16]
        ]

        cache_key = ':'.join(key_components)
        return cache_key[:250]

    def generate_consensus_key(self, maker_hash: str, checker_hash: str,
                             knowledge_hash: str, policy_version: str) -> str:
        """Generate cache key for consensus results"""
        key_components = [
            'consensus',
            self.version,
            policy_version,
            maker_hash[:16],
            checker_hash[:16],
            knowledge_hash[:16]
        ]

        cache_key = ':'.join(key_components)
        return cache_key[:250]

    def generate_context_hash(self, context_data: Dict[str, Any]) -> str:
        """Generate hash for context data"""
        # Extract relevant context fields for caching
        cache_context = {
            'conversation_type': context_data.get('conversation_type'),
            'language': context_data.get('language'),
            'business_unit_type': context_data.get('business_unit_type'),
            'security_level': context_data.get('security_level'),
            'expected_users': context_data.get('expected_users'),
            'user_experience_level': context_data.get('user_experience_level')
        }

        # Remove None values
        cache_context = {k: v for k, v in cache_context.items() if v is not None}

        # Generate hash
        context_json = json.dumps(cache_context, sort_keys=True)
        return hashlib.sha256(context_json.encode()).hexdigest()

    def _normalize_intent(self, intent: str) -> str:
        """Normalize user intent for consistent caching"""
        # Convert to lowercase
        normalized = intent.lower().strip()

        # Remove common variations
        replacements = {
            'setup': 'configure',
            'set up': 'configure',
            'create': 'configure',
            'help me': '',
            'i want to': '',
            'i need to': '',
            'how do i': '',
            'can you': ''
        }

        for old, new in replacements.items():
            normalized = normalized.replace(old, new)

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized[:100]  # Limit length


class TokenBudgetManager:
    """
    Manages adaptive token budgeting based on user risk and context complexity
    """

    def __init__(self):
        # Base token budgets for different operations
        self.base_budgets = {
            'maker_simple': getattr(settings, 'TOKEN_BUDGET_MAKER_SIMPLE', 500),
            'maker_complex': getattr(settings, 'TOKEN_BUDGET_MAKER_COMPLEX', 1500),
            'checker': getattr(settings, 'TOKEN_BUDGET_CHECKER', 800),
            'retrieval_k_simple': 3,
            'retrieval_k_complex': 7,
            'max_citations': getattr(settings, 'MAX_CITATIONS_PER_REC', 5)
        }

        # Risk-based multipliers
        self.risk_multipliers = {
            'low_risk': 0.7,      # Simple scenarios can use fewer tokens
            'medium_risk': 1.0,    # Standard budget
            'high_risk': 1.4,      # Complex scenarios need more tokens
            'critical': 1.8        # Critical scenarios get maximum resources
        }

    def calculate_token_budget(self, user: People, client, context: Dict[str, Any]) -> Dict[str, int]:
        """Calculate adaptive token budget for a request"""
        try:
            # Assess risk level
            risk_level = self._assess_risk_level(user, client, context)

            # Assess context complexity
            complexity_level = self._assess_complexity_level(context)

            # Select base budget
            if complexity_level in ['high', 'critical']:
                base_maker = self.base_budgets['maker_complex']
                base_retrieval_k = self.base_budgets['retrieval_k_complex']
            else:
                base_maker = self.base_budgets['maker_simple']
                base_retrieval_k = self.base_budgets['retrieval_k_simple']

            # Apply risk multiplier
            risk_multiplier = self.risk_multipliers.get(risk_level, 1.0)

            # Calculate final budgets
            budget = {
                'maker_tokens': int(base_maker * risk_multiplier),
                'checker_tokens': int(self.base_budgets['checker'] * risk_multiplier),
                'retrieval_k': min(10, int(base_retrieval_k * risk_multiplier)),
                'max_citations': min(8, int(self.base_budgets['max_citations'] * risk_multiplier)),
                'risk_level': risk_level,
                'complexity_level': complexity_level
            }

            # Apply user preference adjustments
            if user:
                budget = self._apply_user_preferences(budget, user, client)

            return budget

        except (ConnectionError, LLMServiceException, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error calculating token budget: {str(e)}")
            return self._get_default_budget()

    def _assess_risk_level(self, user: People, client, context: Dict[str, Any]) -> str:
        """Assess risk level for the request"""
        risk_score = 0.0

        # Context-based risk factors
        if context.get('security_level') in ['enhanced', 'high_security']:
            risk_score += 0.3

        if context.get('expected_users', 0) > 100:
            risk_score += 0.2

        if context.get('compliance_needed', False):
            risk_score += 0.3

        if context.get('setup_urgency') == 'today':
            risk_score += 0.2

        # User experience risk factor
        user_experience = context.get('user_experience_level', 'beginner')
        if user_experience == 'beginner':
            risk_score += 0.2
        elif user_experience == 'expert':
            risk_score -= 0.1

        # Client complexity
        if hasattr(client, 'children') and client.children.count() > 10:
            risk_score += 0.2

        # Determine risk level
        if risk_score >= 0.8:
            return 'critical'
        elif risk_score >= 0.5:
            return 'high_risk'
        elif risk_score >= 0.2:
            return 'medium_risk'
        else:
            return 'low_risk'

    def _assess_complexity_level(self, context: Dict[str, Any]) -> str:
        """Assess complexity level of the request"""
        complexity_score = 0.0

        # Business unit complexity
        bu_type = context.get('business_unit_type', 'office')
        if bu_type in ['manufacturing', 'healthcare']:
            complexity_score += 0.3
        elif bu_type in ['warehouse', 'retail']:
            complexity_score += 0.1

        # Scale complexity
        expected_users = context.get('expected_users', 0)
        if expected_users > 500:
            complexity_score += 0.4
        elif expected_users > 100:
            complexity_score += 0.2
        elif expected_users > 50:
            complexity_score += 0.1

        # Feature complexity
        if context.get('integration_requirements'):
            complexity_score += 0.2

        if context.get('custom_workflows'):
            complexity_score += 0.3

        # Determine complexity level
        if complexity_score >= 0.7:
            return 'critical'
        elif complexity_score >= 0.4:
            return 'high'
        elif complexity_score >= 0.2:
            return 'medium'
        else:
            return 'low'

    def _apply_user_preferences(self, budget: Dict[str, int], user: People, client) -> Dict[str, int]:
        """Apply user preference adjustments to budget"""
        try:
            profile = PreferenceProfile.objects.filter(user=user, client=client).first()
            if not profile or not profile.weights:
                return budget

            weights = profile.weights

            # Adjust based on detail preference
            detail_level = weights.get('detail_level', 0.5)
            if detail_level > 0.7:
                budget['maker_tokens'] = int(budget['maker_tokens'] * 1.2)
                budget['max_citations'] = min(8, budget['max_citations'] + 1)
            elif detail_level < 0.3:
                budget['maker_tokens'] = int(budget['maker_tokens'] * 0.8)
                budget['max_citations'] = max(2, budget['max_citations'] - 1)

            # Adjust based on cost sensitivity
            cost_sensitivity = weights.get('cost_sensitivity', 0.5)
            if cost_sensitivity > 0.7:
                # Cost-sensitive users get reduced budgets
                budget['maker_tokens'] = int(budget['maker_tokens'] * 0.8)
                budget['checker_tokens'] = int(budget['checker_tokens'] * 0.7)
                budget['retrieval_k'] = max(2, budget['retrieval_k'] - 1)

            return budget

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error applying user preferences: {str(e)}")
            return budget

    def _get_default_budget(self) -> Dict[str, int]:
        """Get default budget when calculation fails"""
        return {
            'maker_tokens': self.base_budgets['maker_simple'],
            'checker_tokens': self.base_budgets['checker'],
            'retrieval_k': self.base_budgets['retrieval_k_simple'],
            'max_citations': self.base_budgets['max_citations'],
            'risk_level': 'medium_risk',
            'complexity_level': 'medium'
        }


class ProviderRouter:
    """
    Routes requests to different LLM providers based on cost and complexity
    """

    def __init__(self):
        # Provider configurations
        self.providers = {
            'gpt-3.5-turbo': {
                'cost_per_token': 0.0000015,  # $1.50 per 1M tokens
                'max_tokens': 4096,
                'latency_p95': 2000,  # ms
                'suitable_for': ['low_risk', 'medium_risk'],
                'quality_score': 0.8
            },
            'gpt-4': {
                'cost_per_token': 0.00003,    # $30 per 1M tokens
                'max_tokens': 8192,
                'latency_p95': 5000,  # ms
                'suitable_for': ['high_risk', 'critical'],
                'quality_score': 0.95
            },
            'claude-instant': {
                'cost_per_token': 0.000008,   # $8 per 1M tokens
                'max_tokens': 9000,
                'latency_p95': 1500,  # ms
                'suitable_for': ['low_risk', 'medium_risk'],
                'quality_score': 0.85
            }
        }

        # Default fallback
        self.default_provider = getattr(settings, 'DEFAULT_LLM_PROVIDER', 'gpt-3.5-turbo')

    def select_provider(self, budget: Dict[str, Any], context: Dict[str, Any],
                       prefer_speed: bool = False) -> str:
        """Select optimal provider based on budget and requirements"""
        try:
            risk_level = budget.get('risk_level', 'medium_risk')
            token_budget = budget.get('maker_tokens', 1000)

            # Filter providers suitable for risk level
            suitable_providers = []
            for provider, config in self.providers.items():
                if risk_level in config['suitable_for']:
                    suitable_providers.append((provider, config))

            if not suitable_providers:
                return self.default_provider

            # Select based on optimization criteria
            if prefer_speed:
                # Choose fastest provider
                best_provider = min(suitable_providers, key=lambda x: x[1]['latency_p95'])
            else:
                # Choose most cost-effective provider
                best_provider = min(suitable_providers,
                                  key=lambda x: x[1]['cost_per_token'] * token_budget)

            return best_provider[0]

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error selecting provider: {str(e)}")
            return self.default_provider

    def estimate_cost(self, provider: str, token_count: int) -> float:
        """Estimate cost for provider and token count"""
        if provider in self.providers:
            return self.providers[provider]['cost_per_token'] * token_count
        return 0.001 * token_count  # Default estimate


class ResponseCache:
    """
    Intelligent caching for LLM responses with TTL and invalidation
    """

    def __init__(self):
        self.key_generator = CacheKeyGenerator()
        self.default_ttl = getattr(settings, 'LLM_CACHE_TTL', 3600)  # 1 hour
        self.max_cache_size = getattr(settings, 'LLM_MAX_CACHE_SIZE', 10000)

    def get_cached_maker_response(self, intent: str, kb_citations: List[str],
                                policy_version: str, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Get cached maker response if available"""
        try:
            context_hash = self.key_generator.generate_context_hash(context)
            cache_key = self.key_generator.generate_maker_key(
                intent, kb_citations, policy_version, context_hash
            )

            cached_response = cache.get(cache_key)
            if cached_response:
                # Add cache metadata
                cached_response['cache_hit'] = True
                cached_response['cache_key'] = cache_key
                logger.debug(f"Cache hit for maker response: {cache_key}")
                return cached_response

            return None

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving cached maker response: {str(e)}")
            return None

    def cache_maker_response(self, intent: str, kb_citations: List[str],
                           policy_version: str, context: Dict[str, Any],
                           response: Dict[str, Any], ttl: Optional[int] = None):
        """Cache maker response"""
        try:
            context_hash = self.key_generator.generate_context_hash(context)
            cache_key = self.key_generator.generate_maker_key(
                intent, kb_citations, policy_version, context_hash
            )

            # Add cache metadata
            cached_response = response.copy()
            cached_response['cached_at'] = timezone.now().isoformat()
            cached_response['cache_key'] = cache_key

            # Cache with TTL
            cache_ttl = ttl or self._calculate_dynamic_ttl(response)
            cache.set(cache_key, cached_response, cache_ttl)

            logger.debug(f"Cached maker response: {cache_key} (TTL: {cache_ttl}s)")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error caching maker response: {str(e)}")

    def get_cached_checker_response(self, maker_output: Dict[str, Any],
                                  context: Dict[str, Any], policy_version: str) -> Optional[Dict[str, Any]]:
        """Get cached checker response if available"""
        try:
            maker_hash = hashlib.sha256(json.dumps(maker_output, sort_keys=True).encode()).hexdigest()
            context_hash = self.key_generator.generate_context_hash(context)
            cache_key = self.key_generator.generate_checker_key(maker_hash, context_hash, policy_version)

            cached_response = cache.get(cache_key)
            if cached_response:
                cached_response['cache_hit'] = True
                cached_response['cache_key'] = cache_key
                logger.debug(f"Cache hit for checker response: {cache_key}")
                return cached_response

            return None

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving cached checker response: {str(e)}")
            return None

    def cache_checker_response(self, maker_output: Dict[str, Any], context: Dict[str, Any],
                             policy_version: str, response: Dict[str, Any], ttl: Optional[int] = None):
        """Cache checker response"""
        try:
            maker_hash = hashlib.sha256(json.dumps(maker_output, sort_keys=True).encode()).hexdigest()
            context_hash = self.key_generator.generate_context_hash(context)
            cache_key = self.key_generator.generate_checker_key(maker_hash, context_hash, policy_version)

            # Add cache metadata
            cached_response = response.copy()
            cached_response['cached_at'] = timezone.now().isoformat()
            cached_response['cache_key'] = cache_key

            # Cache with TTL
            cache_ttl = ttl or self._calculate_dynamic_ttl(response)
            cache.set(cache_key, cached_response, cache_ttl)

            logger.debug(f"Cached checker response: {cache_key} (TTL: {cache_ttl}s)")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error caching checker response: {str(e)}")

    def invalidate_policy_cache(self, policy_version: str):
        """Invalidate all cached responses for a policy version"""
        try:
            # This would typically use Redis pattern matching or cache tagging
            # For Django cache, we'll implement a simple version tracking
            cache.set(f'policy_invalidated_{policy_version}', timezone.now().isoformat(), 86400)
            logger.info(f"Invalidated cache for policy version: {policy_version}")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error invalidating policy cache: {str(e)}")

    def invalidate_knowledge_cache(self, knowledge_ids: List[str]):
        """Invalidate cached responses that use specific knowledge"""
        try:
            # Mark knowledge as updated for cache invalidation
            for knowledge_id in knowledge_ids:
                cache.set(f'knowledge_updated_{knowledge_id}', timezone.now().isoformat(), 86400)

            logger.info(f"Invalidated cache for knowledge: {knowledge_ids}")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error invalidating knowledge cache: {str(e)}")

    def _calculate_dynamic_ttl(self, response: Dict[str, Any]) -> int:
        """Calculate dynamic TTL based on response characteristics"""
        base_ttl = self.default_ttl

        # High confidence responses can be cached longer
        confidence = response.get('confidence_score', 0.5)
        if confidence > 0.9:
            return int(base_ttl * 2)
        elif confidence < 0.5:
            return int(base_ttl * 0.5)

        # Responses with many citations are more stable
        citations = response.get('citations', [])
        if len(citations) > 3:
            return int(base_ttl * 1.5)

        return base_ttl


class HotPathManager:
    """
    Precomputes and caches common recommendation patterns
    """

    def __init__(self):
        self.cache_prefix = 'hotpath'
        self.precompute_ttl = 86400  # 24 hours

    def precompute_industry_starter_packs(self):
        """Precompute starter packs for common industry scenarios"""
        try:
            industries = ['healthcare', 'finance', 'manufacturing', 'retail', 'education']
            business_types = ['office', 'warehouse', 'retail_store']

            for industry in industries:
                for bu_type in business_types:
                    self._precompute_starter_pack(industry, bu_type)

            logger.info("Completed industry starter pack precomputation")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error precomputing starter packs: {str(e)}")

    def get_starter_pack(self, industry: str, bu_type: str,
                        user_size: str = 'medium') -> Optional[Dict[str, Any]]:
        """Get precomputed starter pack for industry/type combination"""
        try:
            cache_key = f"{self.cache_prefix}:starter:{industry}:{bu_type}:{user_size}"
            return cache.get(cache_key)

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving starter pack: {str(e)}")
            return None

    def _precompute_starter_pack(self, industry: str, bu_type: str):
        """Precompute starter pack for specific industry/business type"""
        try:
            # Generate common scenarios for this industry/type
            scenarios = self._generate_common_scenarios(industry, bu_type)

            for scenario in scenarios:
                user_size = scenario['user_size']
                cache_key = f"{self.cache_prefix}:starter:{industry}:{bu_type}:{user_size}"

                # Generate recommendations for this scenario
                starter_pack = self._generate_starter_pack_recommendations(scenario)

                # Cache the starter pack
                cache.set(cache_key, starter_pack, self.precompute_ttl)

                logger.debug(f"Precomputed starter pack: {cache_key}")

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error precomputing starter pack for {industry}/{bu_type}: {str(e)}")

    def _generate_common_scenarios(self, industry: str, bu_type: str) -> List[Dict[str, Any]]:
        """Generate common scenarios for industry/business type"""
        base_scenarios = [
            {
                'industry': industry,
                'bu_type': bu_type,
                'user_size': 'small',
                'expected_users': 15,
                'security_level': 'basic',
                'setup_urgency': 'no_deadline'
            },
            {
                'industry': industry,
                'bu_type': bu_type,
                'user_size': 'medium',
                'expected_users': 75,
                'security_level': 'enhanced',
                'setup_urgency': 'within_week'
            },
            {
                'industry': industry,
                'bu_type': bu_type,
                'user_size': 'large',
                'expected_users': 200,
                'security_level': 'high_security',
                'setup_urgency': 'within_month'
            }
        ]

        # Add industry-specific variations
        if industry == 'healthcare':
            for scenario in base_scenarios:
                scenario['compliance_needed'] = True
                scenario['security_level'] = 'high_security'

        elif industry == 'finance':
            for scenario in base_scenarios:
                scenario['compliance_needed'] = True
                scenario['audit_requirements'] = True

        return base_scenarios

    def _generate_starter_pack_recommendations(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Generate recommendations for a scenario"""
        # This would typically call the LLM service with the scenario
        # For now, we'll return a template-based response

        recommendations = {
            'business_unit_config': {
                'bu_type': scenario['bu_type'],
                'max_users': scenario['expected_users'],
                'security_level': scenario['security_level'],
                'industry': scenario['industry']
            },
            'suggested_shifts': self._generate_industry_shifts(scenario),
            'security_settings': self._generate_security_settings(scenario),
            'compliance_requirements': self._generate_compliance_requirements(scenario)
        }

        return {
            'recommendations': recommendations,
            'confidence_score': 0.8,  # Precomputed recommendations have good confidence
            'precomputed': True,
            'scenario': scenario,
            'generated_at': timezone.now().isoformat()
        }

    def _generate_industry_shifts(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate industry-appropriate shift configurations"""
        industry = scenario['industry']
        bu_type = scenario['bu_type']

        if industry == 'healthcare' and bu_type == 'office':
            return [
                {
                    'shift_name': 'Day Shift',
                    'start_time': '07:00',
                    'end_time': '19:00',
                    'people_count': min(scenario['expected_users'] // 2, 20)
                },
                {
                    'shift_name': 'Night Shift',
                    'start_time': '19:00',
                    'end_time': '07:00',
                    'people_count': min(scenario['expected_users'] // 4, 10)
                }
            ]
        elif industry == 'retail':
            return [
                {
                    'shift_name': 'Opening Shift',
                    'start_time': '08:00',
                    'end_time': '16:00',
                    'people_count': min(scenario['expected_users'] // 3, 15)
                },
                {
                    'shift_name': 'Closing Shift',
                    'start_time': '14:00',
                    'end_time': '22:00',
                    'people_count': min(scenario['expected_users'] // 3, 15)
                }
            ]
        else:
            # Standard business hours
            return [
                {
                    'shift_name': 'Business Hours',
                    'start_time': '09:00',
                    'end_time': '17:00',
                    'people_count': min(scenario['expected_users'], 30)
                }
            ]

    def _generate_security_settings(self, scenario: Dict[str, Any]) -> Dict[str, Any]:
        """Generate industry-appropriate security settings"""
        security_level = scenario['security_level']
        industry = scenario['industry']

        settings = {
            'enable_gps': security_level in ['enhanced', 'high_security'],
            'enable_sleeping_guard': security_level == 'high_security',
            'permissible_distance': 50 if security_level == 'high_security' else 100
        }

        # Industry-specific adjustments
        if industry in ['healthcare', 'finance']:
            settings['enable_gps'] = True
            settings['permissible_distance'] = 25  # Stricter for regulated industries

        return settings

    def _generate_compliance_requirements(self, scenario: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate compliance requirements based on industry"""
        industry = scenario['industry']
        requirements = []

        if industry == 'healthcare':
            requirements.extend([
                {
                    'type': 'HIPAA',
                    'description': 'Health Insurance Portability and Accountability Act compliance',
                    'required': True
                },
                {
                    'type': 'data_encryption',
                    'description': 'All patient data must be encrypted at rest and in transit',
                    'required': True
                }
            ])

        elif industry == 'finance':
            requirements.extend([
                {
                    'type': 'SOX',
                    'description': 'Sarbanes-Oxley Act compliance for financial reporting',
                    'required': True
                },
                {
                    'type': 'audit_trail',
                    'description': 'Complete audit trail for all financial transactions',
                    'required': True
                }
            ])

        return requirements


class OptimizationService:
    """
    Main optimization service that coordinates all optimization components
    """

    def __init__(self):
        self.token_manager = TokenBudgetManager()
        self.provider_router = ProviderRouter()
        self.response_cache = ResponseCache()
        self.hotpath_manager = HotPathManager()

        # Performance tracking
        self.performance_metrics = {}

    def optimize_request(self, user: People, client, intent: str, context: Dict[str, Any],
                        policy_version: str = 'v1.0') -> Dict[str, Any]:
        """
        Comprehensive request optimization

        Returns optimization configuration including:
        - Token budgets
        - Provider selection
        - Caching strategy
        - Early exit conditions
        """
        try:
            # Calculate token budget
            token_budget = self.token_manager.calculate_token_budget(user, client, context)

            # Check for hot path starter pack
            starter_pack = None
            if context.get('conversation_type') == 'initial_setup':
                industry = context.get('industry', 'general')
                bu_type = context.get('business_unit_type', 'office')
                user_size = self._determine_user_size(context.get('expected_users', 10))

                starter_pack = self.hotpath_manager.get_starter_pack(industry, bu_type, user_size)

            # Check cache for existing response
            kb_citations = context.get('kb_citations', [])
            cached_response = self.response_cache.get_cached_maker_response(
                intent, kb_citations, policy_version, context
            )

            # Select provider
            prefer_speed = context.get('setup_urgency') == 'today'
            selected_provider = self.provider_router.select_provider(
                token_budget, context, prefer_speed
            )

            # Determine early exit strategy
            early_exit_config = self._determine_early_exit_strategy(token_budget, context)

            optimization_config = {
                'token_budget': token_budget,
                'selected_provider': selected_provider,
                'estimated_cost': self.provider_router.estimate_cost(
                    selected_provider, token_budget['maker_tokens']
                ),
                'cached_response': cached_response,
                'starter_pack': starter_pack,
                'early_exit_config': early_exit_config,
                'should_use_checker': self._should_use_checker(token_budget, context),
                'streaming_enabled': self._should_enable_streaming(context),
                'optimization_applied': True
            }

            return optimization_config

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error optimizing request: {str(e)}")
            return self._get_default_optimization()

    def track_performance(self, optimization_config: Dict[str, Any], actual_cost: float,
                         latency_ms: int, success: bool):
        """Track optimization performance for continuous improvement"""
        try:
            provider = optimization_config.get('selected_provider')
            risk_level = optimization_config.get('token_budget', {}).get('risk_level')

            # Store performance metrics
            metric_key = f"{provider}_{risk_level}"
            if metric_key not in self.performance_metrics:
                self.performance_metrics[metric_key] = {
                    'requests': 0,
                    'total_cost': 0.0,
                    'total_latency': 0,
                    'successes': 0
                }

            metrics = self.performance_metrics[metric_key]
            metrics['requests'] += 1
            metrics['total_cost'] += actual_cost
            metrics['total_latency'] += latency_ms
            if success:
                metrics['successes'] += 1

            # Calculate averages
            metrics['avg_cost'] = metrics['total_cost'] / metrics['requests']
            metrics['avg_latency'] = metrics['total_latency'] / metrics['requests']
            metrics['success_rate'] = metrics['successes'] / metrics['requests']

        except (ConnectionError, DatabaseError, IntegrityError, LLMServiceException, ObjectDoesNotExist, TimeoutError, TypeError, ValidationError, ValueError, json.JSONDecodeError) as e:
            logger.error(f"Error tracking performance: {str(e)}")

    def _determine_user_size(self, expected_users: int) -> str:
        """Determine user size category"""
        if expected_users <= 25:
            return 'small'
        elif expected_users <= 100:
            return 'medium'
        else:
            return 'large'

    def _determine_early_exit_strategy(self, token_budget: Dict[str, Any],
                                     context: Dict[str, Any]) -> Dict[str, Any]:
        """Determine early exit strategy based on budget and context"""
        strategy = {
            'enabled': False,
            'confidence_threshold': 0.8,
            'max_wait_time_ms': 5000,
            'return_partial_results': False
        }

        # Enable early exit for cost-sensitive scenarios
        if token_budget.get('risk_level') in ['low_risk', 'medium_risk']:
            strategy['enabled'] = True
            strategy['confidence_threshold'] = 0.7

        # Enable for urgent requests
        if context.get('setup_urgency') == 'today':
            strategy['enabled'] = True
            strategy['max_wait_time_ms'] = 3000
            strategy['return_partial_results'] = True

        return strategy

    def _should_use_checker(self, token_budget: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Determine if checker should be used"""
        risk_level = token_budget.get('risk_level')

        # Always use checker for high-risk scenarios
        if risk_level in ['high_risk', 'critical']:
            return True

        # Use checker for compliance-required scenarios
        if context.get('compliance_needed', False):
            return True

        # Skip checker for simple, low-risk scenarios to save costs
        if risk_level == 'low_risk' and context.get('expected_users', 0) < 25:
            return False

        return True  # Default to using checker

    def _should_enable_streaming(self, context: Dict[str, Any]) -> bool:
        """Determine if streaming should be enabled"""
        # Enable streaming for urgent requests
        if context.get('setup_urgency') == 'today':
            return True

        # Enable for complex scenarios that might take time
        if context.get('expected_users', 0) > 100:
            return True

        return False

    def _get_default_optimization(self) -> Dict[str, Any]:
        """Get default optimization when calculation fails"""
        return {
            'token_budget': self.token_manager._get_default_budget(),
            'selected_provider': self.provider_router.default_provider,
            'estimated_cost': 0.01,  # $0.01 default estimate
            'cached_response': None,
            'starter_pack': None,
            'early_exit_config': {'enabled': False},
            'should_use_checker': True,
            'streaming_enabled': False,
            'optimization_applied': False
        }


# Factory function
def get_optimization_service() -> OptimizationService:
    """Get the optimization service"""
    return OptimizationService()