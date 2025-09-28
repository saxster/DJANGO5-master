"""
Elasticsearch Integration for Advanced Journal Search

Privacy-filtered full-text search with:
- Real-time indexing of journal entries
- Privacy scope enforcement at search level
- Advanced faceting and aggregations
- Highlighting and suggestion generation
- Multi-tenant search isolation
- Performance optimization for large datasets
"""

from django.conf import settings
from django.utils import timezone
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
from datetime import timedelta
import logging

from .models import JournalEntry, JournalPrivacySettings
from .privacy import JournalPrivacyManager

logger = logging.getLogger(__name__)


class JournalElasticsearchService:
    """
    Comprehensive Elasticsearch service for journal search

    Features:
    - Privacy-aware indexing and searching
    - Real-time index updates via signals
    - Advanced search with faceting
    - Search analytics and personalization
    - Multi-tenant index isolation
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.es_client = self._get_elasticsearch_client()
        self.privacy_manager = JournalPrivacyManager()

    def _get_elasticsearch_client(self):
        """Get configured Elasticsearch client"""
        try:
            # Use Django settings for Elasticsearch configuration
            es_config = getattr(settings, 'ELASTICSEARCH_DSL', {
                'default': {
                    'hosts': ['localhost:9200']
                }
            })

            host_config = es_config.get('default', {}).get('hosts', ['localhost:9200'])
            return Elasticsearch(host_config)

        except (ValueError, TypeError) as e:
            self.logger.error(f"Failed to connect to Elasticsearch: {e}")
            return None

    def create_journal_index(self, tenant_id):
        """
        Create optimized Elasticsearch index for journal entries

        Args:
            tenant_id: Tenant ID for index isolation

        Returns:
            bool: Success status
        """

        if not self.es_client:
            self.logger.error("Elasticsearch client not available")
            return False

        index_name = f"journal_entries_{tenant_id}"

        try:
            # Define index mapping with privacy-aware fields
            mapping = {
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1,
                    "analysis": {
                        "analyzer": {
                            "journal_analyzer": {
                                "type": "custom",
                                "tokenizer": "standard",
                                "filter": [
                                    "lowercase",
                                    "stop",
                                    "snowball"
                                ]
                            }
                        }
                    }
                },
                "mappings": {
                    "properties": {
                        # Core fields
                        "id": {"type": "keyword"},
                        "user_id": {"type": "keyword"},
                        "tenant_id": {"type": "keyword"},
                        "title": {
                            "type": "text",
                            "analyzer": "journal_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "content": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },
                        "subtitle": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },

                        # Entry metadata
                        "entry_type": {"type": "keyword"},
                        "timestamp": {"type": "date"},
                        "privacy_scope": {"type": "keyword"},

                        # Wellbeing metrics
                        "mood_rating": {"type": "integer"},
                        "stress_level": {"type": "integer"},
                        "energy_level": {"type": "integer"},
                        "mood_description": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },

                        # Location and context
                        "location_site_name": {
                            "type": "text",
                            "analyzer": "journal_analyzer",
                            "fields": {
                                "keyword": {"type": "keyword"}
                            }
                        },
                        "location_coordinates": {"type": "geo_point"},

                        # Categorization
                        "tags": {"type": "keyword"},
                        "priority": {"type": "keyword"},
                        "severity": {"type": "keyword"},

                        # Performance metrics
                        "completion_rate": {"type": "float"},
                        "efficiency_score": {"type": "float"},
                        "quality_score": {"type": "float"},

                        # Positive psychology (for searchable insights)
                        "gratitude_items": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },
                        "achievements": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },
                        "learnings": {
                            "type": "text",
                            "analyzer": "journal_analyzer"
                        },

                        # Entry state
                        "is_bookmarked": {"type": "boolean"},
                        "is_draft": {"type": "boolean"},
                        "is_deleted": {"type": "boolean"},

                        # Audit fields
                        "created_at": {"type": "date"},
                        "updated_at": {"type": "date"},

                        # Privacy enforcement
                        "searchable_by": {"type": "keyword"},  # User IDs who can search this entry
                        "privacy_level": {"type": "integer"}   # Numeric privacy level for filtering
                    }
                }
            }

            # Create index
            if self.es_client.indices.exists(index=index_name):
                self.logger.info(f"Index {index_name} already exists")
                return True

            response = self.es_client.indices.create(index=index_name, body=mapping)
            self.logger.info(f"Created Elasticsearch index: {index_name}")

            return response.get('acknowledged', False)

        except (ValueError, TypeError) as e:
            self.logger.error(f"Failed to create Elasticsearch index {index_name}: {e}")
            return False

    def index_journal_entry(self, journal_entry):
        """
        Index journal entry with privacy controls

        Args:
            journal_entry: JournalEntry object to index

        Returns:
            bool: Success status
        """

        if not self.es_client:
            return False

        try:
            # Check if entry should be indexed based on privacy settings
            if not self._should_index_entry(journal_entry):
                self.logger.debug(f"Skipping indexing for private entry {journal_entry.id}")
                return True

            index_name = f"journal_entries_{journal_entry.tenant.id}"

            # Prepare document with privacy filtering
            doc = self._prepare_search_document(journal_entry)

            # Index document
            response = self.es_client.index(
                index=index_name,
                id=str(journal_entry.id),
                body=doc
            )

            self.logger.debug(f"Indexed journal entry {journal_entry.id} in {index_name}")
            return response.get('result') in ['created', 'updated']

        except (ValueError, TypeError) as e:
            self.logger.error(f"Failed to index journal entry {journal_entry.id}: {e}")
            return False

    def search_journal_entries(self, user, search_params):
        """
        Execute privacy-filtered search with advanced features

        Args:
            user: User performing search
            search_params: Search parameters dict

        Returns:
            dict: Search results with privacy filtering applied
        """

        if not self.es_client:
            # Fallback to database search
            return self._fallback_database_search(user, search_params)

        try:
            index_name = f"journal_entries_{user.tenant.id}"

            # Build Elasticsearch query with privacy filtering
            es_query = self._build_elasticsearch_query(user, search_params)

            # Execute search
            response = self.es_client.search(
                index=index_name,
                body=es_query
            )

            # Post-process results for privacy compliance
            filtered_results = self._apply_privacy_filtering(response, user)

            # Generate search suggestions
            suggestions = self._generate_search_suggestions(
                search_params.get('query', ''),
                user
            )

            # Track search for personalization
            self._track_search_interaction(user, search_params)

            return {
                'results': filtered_results,
                'total_results': response['hits']['total']['value'],
                'facets': response.get('aggregations', {}),
                'search_suggestions': suggestions,
                'search_time_ms': response['took'],
                'elasticsearch_used': True
            }

        except (ValueError, TypeError) as e:
            self.logger.error(f"Elasticsearch search failed for user {user.id}: {e}")
            # Fallback to database search
            return self._fallback_database_search(user, search_params)

    def _should_index_entry(self, journal_entry):
        """Check if entry should be indexed based on privacy settings"""
        # Private wellbeing entries are never indexed for search
        if (journal_entry.is_wellbeing_entry and
            journal_entry.privacy_scope == 'private'):
            return False

        # Check user's consent for search indexing
        try:
            privacy_settings = journal_entry.user.journal_privacy_settings
            if not privacy_settings.analytics_consent:
                return False
        except JournalPrivacySettings.DoesNotExist:
            return False

        return True

    def _prepare_search_document(self, journal_entry):
        """Prepare journal entry document for Elasticsearch indexing"""
        # Determine who can search this entry
        searchable_by = [str(journal_entry.user.id)]

        if journal_entry.privacy_scope == 'shared':
            searchable_by.extend([str(uid) for uid in journal_entry.sharing_permissions])
        elif journal_entry.privacy_scope == 'team':
            # TODO: Add team member IDs
            pass
        elif journal_entry.privacy_scope == 'manager':
            # TODO: Add manager ID
            pass

        # Privacy level for filtering (lower = more private)
        privacy_levels = {
            'private': 1,
            'manager': 2,
            'team': 3,
            'shared': 4,
            'aggregate_only': 5
        }

        doc = {
            # Core fields
            'id': str(journal_entry.id),
            'user_id': str(journal_entry.user.id),
            'tenant_id': str(journal_entry.tenant.id),
            'title': journal_entry.title,
            'content': journal_entry.content if not journal_entry.is_wellbeing_entry else '',  # Exclude wellbeing content from search
            'subtitle': journal_entry.subtitle,

            # Entry metadata
            'entry_type': journal_entry.entry_type,
            'timestamp': journal_entry.timestamp.isoformat(),
            'privacy_scope': journal_entry.privacy_scope,

            # Location (if not private)
            'location_site_name': journal_entry.location_site_name if journal_entry.privacy_scope != 'private' else '',
            'location_coordinates': journal_entry.location_coordinates if journal_entry.privacy_scope != 'private' else None,

            # Categorization
            'tags': journal_entry.tags,
            'priority': journal_entry.priority,
            'severity': journal_entry.severity,

            # Entry state
            'is_bookmarked': journal_entry.is_bookmarked,
            'is_draft': journal_entry.is_draft,
            'is_deleted': journal_entry.is_deleted,

            # Audit fields
            'created_at': journal_entry.created_at.isoformat(),
            'updated_at': journal_entry.updated_at.isoformat(),

            # Privacy enforcement
            'searchable_by': searchable_by,
            'privacy_level': privacy_levels.get(journal_entry.privacy_scope, 1)
        }

        # Add wellbeing metrics only if user consented to analytics
        try:
            privacy_settings = journal_entry.user.journal_privacy_settings
            if privacy_settings.analytics_consent:
                doc.update({
                    'mood_rating': journal_entry.mood_rating,
                    'stress_level': journal_entry.stress_level,
                    'energy_level': journal_entry.energy_level,
                    'mood_description': journal_entry.mood_description
                })
        except JournalPrivacySettings.DoesNotExist:
            pass

        # Add non-sensitive positive psychology content
        if not journal_entry.is_wellbeing_entry:
            doc.update({
                'achievements': ' '.join(journal_entry.achievements or []),
                'learnings': ' '.join(journal_entry.learnings or [])
            })

        return doc

    def _build_elasticsearch_query(self, user, search_params):
        """Build comprehensive Elasticsearch query with privacy filtering"""
        query_text = search_params.get('query', '')

        # Base privacy filter - user can only search their own entries or entries shared with them
        privacy_filter = {
            "bool": {
                "should": [
                    {"term": {"user_id": str(user.id)}},  # Own entries
                    {"terms": {"searchable_by": [str(user.id)]}}  # Shared entries
                ],
                "minimum_should_match": 1
            }
        }

        # Main search query
        if query_text:
            main_query = {
                "bool": {
                    "must": [
                        {
                            "multi_match": {
                                "query": query_text,
                                "fields": [
                                    "title^3",      # Title gets highest weight
                                    "content^2",    # Content gets medium weight
                                    "subtitle^1.5", # Subtitle gets some boost
                                    "achievements",
                                    "learnings",
                                    "location_site_name"
                                ],
                                "type": "best_fields",
                                "fuzziness": "AUTO"
                            }
                        },
                        privacy_filter  # Always apply privacy filter
                    ]
                }
            }
        else:
            # No text query - just privacy filter with match_all
            main_query = {
                "bool": {
                    "must": [
                        {"match_all": {}},
                        privacy_filter
                    ]
                }
            }

        # Apply additional filters
        filters = []

        # Tenant isolation
        filters.append({"term": {"tenant_id": str(user.tenant.id)}})

        # Entry type filter
        entry_types = search_params.get('entry_types', [])
        if entry_types:
            filters.append({"terms": {"entry_type": entry_types}})

        # Date range filter
        date_from = search_params.get('date_from')
        date_to = search_params.get('date_to')
        if date_from and date_to:
            filters.append({
                "range": {
                    "timestamp": {
                        "gte": date_from,
                        "lte": date_to
                    }
                }
            })

        # Wellbeing metric filters (only if user consented to analytics)
        try:
            privacy_settings = user.journal_privacy_settings
            if privacy_settings.analytics_consent:
                # Mood filter
                mood_min = search_params.get('mood_min')
                mood_max = search_params.get('mood_max')
                if mood_min and mood_max:
                    filters.append({
                        "range": {
                            "mood_rating": {
                                "gte": mood_min,
                                "lte": mood_max
                            }
                        }
                    })

                # Stress filter
                stress_min = search_params.get('stress_min')
                stress_max = search_params.get('stress_max')
                if stress_min and stress_max:
                    filters.append({
                        "range": {
                            "stress_level": {
                                "gte": stress_min,
                                "lte": stress_max
                            }
                        }
                    })

        except JournalPrivacySettings.DoesNotExist:
            pass

        # Location filter
        location = search_params.get('location')
        if location:
            filters.append({
                "wildcard": {
                    "location_site_name": f"*{location.lower()}*"
                }
            })

        # Tag filters
        tags = search_params.get('tags', [])
        if tags:
            filters.append({"terms": {"tags": tags}})

        # Exclude deleted and draft entries
        filters.extend([
            {"term": {"is_deleted": False}},
            {"term": {"is_draft": False}}
        ])

        # Add filters to query
        if filters:
            main_query["bool"]["filter"] = filters

        # Build complete query with aggregations
        sort_by = search_params.get('sort_by', 'relevance')
        sort_config = self._get_sort_configuration(sort_by)

        es_query = {
            "query": main_query,
            "sort": sort_config,
            "highlight": {
                "fields": {
                    "title": {"number_of_fragments": 1},
                    "content": {"number_of_fragments": 2},
                    "achievements": {"number_of_fragments": 1}
                },
                "pre_tags": ["<mark>"],
                "post_tags": ["</mark>"]
            },
            "aggs": {
                "entry_types": {
                    "terms": {"field": "entry_type", "size": 10}
                },
                "mood_ranges": {
                    "range": {
                        "field": "mood_rating",
                        "ranges": [
                            {"key": "1-3", "from": 1, "to": 4},
                            {"key": "4-6", "from": 4, "to": 7},
                            {"key": "7-10", "from": 7, "to": 11}
                        ]
                    }
                },
                "stress_levels": {
                    "terms": {"field": "stress_level", "size": 5}
                },
                "locations": {
                    "terms": {"field": "location_site_name.keyword", "size": 10}
                },
                "tags": {
                    "terms": {"field": "tags", "size": 15}
                }
            },
            "size": 50,  # Limit results
            "from": search_params.get('offset', 0)
        }

        return es_query

    def _get_sort_configuration(self, sort_by):
        """Get Elasticsearch sort configuration"""
        sort_configs = {
            'relevance': ["_score"],
            'timestamp': [{"timestamp": {"order": "desc"}}],
            '-timestamp': [{"timestamp": {"order": "asc"}}],
            'mood_rating': [{"mood_rating": {"order": "desc"}}],
            'stress_level': [{"stress_level": {"order": "asc"}}]
        }

        return sort_configs.get(sort_by, ["_score"])

    def _apply_privacy_filtering(self, es_response, user):
        """Apply additional privacy filtering to search results"""
        filtered_hits = []

        for hit in es_response['hits']['hits']:
            try:
                # Get journal entry from database for privacy check
                entry_id = hit['_source']['id']
                journal_entry = JournalEntry.objects.get(id=entry_id)

                # Double-check privacy permissions
                permission_result = self.privacy_manager.check_data_access_permission(
                    user, journal_entry, 'read'
                )

                if permission_result['allowed']:
                    # Sanitize sensitive data based on privacy scope
                    sanitized_hit = self._sanitize_search_hit(hit, journal_entry, user)
                    filtered_hits.append(sanitized_hit)

            except JournalEntry.DoesNotExist:
                self.logger.warning(f"Journal entry {hit['_source']['id']} not found in database")
                continue
            except PermissionDenied:
                # User doesn't have access - skip this result
                continue
            except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
                self.logger.error(f"Error filtering search hit: {e}")
                continue

        return filtered_hits

    def _sanitize_search_hit(self, hit, journal_entry, user):
        """Sanitize search hit based on privacy requirements"""
        source = hit['_source'].copy()

        # Remove sensitive data if user is not the owner
        if journal_entry.user != user:
            # Remove or mask sensitive fields for non-owners
            if journal_entry.is_wellbeing_entry:
                source['content'] = "[Wellbeing content - access restricted]"
                source.pop('mood_rating', None)
                source.pop('stress_level', None)
                source.pop('energy_level', None)

            # Remove personal location data
            if journal_entry.privacy_scope == 'aggregate_only':
                source['location_site_name'] = "[Location aggregated]"
                source.pop('location_coordinates', None)

        # Add metadata about access level
        source['access_level'] = 'owner' if journal_entry.user == user else journal_entry.privacy_scope

        hit['_source'] = source
        return hit

    def _generate_search_suggestions(self, query, user):
        """Generate search suggestions based on user's search history and content"""
        suggestions = []

        try:
            # Get user's recent tags for suggestions
            recent_entries = JournalEntry.objects.filter(
                user=user,
                timestamp__gte=timezone.now() - timedelta(days=30)
            )

            # Extract common tags
            all_tags = []
            for entry in recent_entries:
                all_tags.extend(entry.tags or [])

            from collections import Counter
            common_tags = Counter(all_tags).most_common(5)

            # Generate tag-based suggestions
            for tag, count in common_tags:
                if query.lower() not in tag.lower():  # Don't suggest current query
                    suggestions.append({
                        'suggestion': tag,
                        'type': 'tag',
                        'reason': f'Used in {count} recent entries'
                    })

            # Generate entry type suggestions
            common_types = Counter([entry.entry_type for entry in recent_entries]).most_common(3)
            for entry_type, count in common_types:
                type_display = dict(JournalEntry.JournalEntryType.choices).get(entry_type, entry_type)
                suggestions.append({
                    'suggestion': type_display,
                    'type': 'entry_type',
                    'reason': f'Your most common entry type'
                })

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to generate search suggestions: {e}")

        return suggestions[:10]  # Limit suggestions

    def _track_search_interaction(self, user, search_params):
        """Track search interaction for analytics and personalization"""
        try:
            # TODO: Implement search analytics tracking
            # This could include:
            # - Search query patterns
            # - Result click-through rates
            # - Search refinement patterns
            # - Popular search terms by user/tenant

            self.logger.debug(f"Search tracked for user {user.id}: {search_params.get('query', '')}")

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to track search interaction: {e}")

    def _fallback_database_search(self, user, search_params):
        """Fallback to database search when Elasticsearch is unavailable"""
        self.logger.warning("Using database fallback for search")

        from django.db.models import Q

        query_text = search_params.get('query', '')

        # Base queryset with privacy filtering
        queryset = JournalEntry.objects.filter(
            user=user,
            tenant=user.tenant,
            is_deleted=False,
            is_draft=False
        )

        # Text search
        if query_text:
            queryset = queryset.filter(
                Q(title__icontains=query_text) |
                Q(content__icontains=query_text) |
                Q(subtitle__icontains=query_text)
            )

        # Apply other filters (similar to API view implementation)
        # ... (implementation details)

        # Serialize results
        from .serializers import JournalEntryListSerializer
        results = JournalEntryListSerializer(
            queryset[:50],
            many=True,
            context={'request': None}
        ).data

        return {
            'results': results,
            'total_results': queryset.count(),
            'search_time_ms': 0,
            'facets': {},
            'search_suggestions': [],
            'elasticsearch_used': False
        }

    def bulk_index_entries(self, tenant_id, entries=None):
        """
        Bulk index journal entries for initial setup or reindexing

        Args:
            tenant_id: Tenant to index entries for
            entries: Specific entries to index (if None, indexes all)

        Returns:
            dict: Bulk indexing results
        """

        if not self.es_client:
            return {'success': False, 'error': 'Elasticsearch not available'}

        try:
            index_name = f"journal_entries_{tenant_id}"

            # Create index if it doesn't exist
            self.create_journal_index(tenant_id)

            # Get entries to index
            if entries is None:
                entries = JournalEntry.objects.filter(
                    tenant_id=tenant_id,
                    is_deleted=False
                )

            # Filter entries that should be indexed
            indexable_entries = [entry for entry in entries if self._should_index_entry(entry)]

            # Prepare bulk indexing operations
            actions = []
            for entry in indexable_entries:
                doc = self._prepare_search_document(entry)

                action = {
                    "_index": index_name,
                    "_id": str(entry.id),
                    "_source": doc
                }
                actions.append(action)

            # Execute bulk indexing
            if actions:
                success_count, errors = bulk(self.es_client, actions, chunk_size=100)

                self.logger.info(f"Bulk indexed {success_count} entries for tenant {tenant_id}")

                return {
                    'success': True,
                    'indexed_count': success_count,
                    'error_count': len(errors) if errors else 0,
                    'errors': errors[:5] if errors else []  # Return first 5 errors
                }
            else:
                return {
                    'success': True,
                    'indexed_count': 0,
                    'message': 'No entries to index'
                }

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Bulk indexing failed for tenant {tenant_id}: {e}")
            return {
                'success': False,
                'error': str(e)
            }

    def delete_from_index(self, journal_entry):
        """Remove journal entry from search index"""
        if not self.es_client:
            return False

        try:
            index_name = f"journal_entries_{journal_entry.tenant.id}"

            response = self.es_client.delete(
                index=index_name,
                id=str(journal_entry.id),
                ignore=[404]  # Ignore if document doesn't exist
            )

            self.logger.debug(f"Removed entry {journal_entry.id} from search index")
            return True

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to remove entry {journal_entry.id} from index: {e}")
            return False

    def reindex_for_privacy_change(self, user):
        """Reindex user's entries when privacy settings change"""
        self.logger.info(f"Reindexing entries for privacy change - user {user.id}")

        try:
            user_entries = JournalEntry.objects.filter(user=user, is_deleted=False)

            for entry in user_entries:
                if self._should_index_entry(entry):
                    self.index_journal_entry(entry)
                else:
                    self.delete_from_index(entry)

            return True

        except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
            self.logger.error(f"Failed to reindex for privacy change: {e}")
            return False


# Signal handlers for real-time indexing
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

es_service = JournalElasticsearchService()

@receiver(post_save, sender=JournalEntry)
def update_search_index_on_save(sender, instance, created, **kwargs):
    """Update search index when journal entry is saved"""
    try:
        if created or not instance.is_deleted:
            es_service.index_journal_entry(instance)
        else:
            es_service.delete_from_index(instance)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to update search index for entry {instance.id}: {e}")

@receiver(post_delete, sender=JournalEntry)
def remove_from_search_index_on_delete(sender, instance, **kwargs):
    """Remove from search index when journal entry is deleted"""
    try:
        es_service.delete_from_index(instance)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to remove entry {instance.id} from search index: {e}")

@receiver(post_save, sender=JournalPrivacySettings)
def reindex_on_privacy_change(sender, instance, **kwargs):
    """Reindex user's entries when privacy settings change"""
    try:
        es_service.reindex_for_privacy_change(instance.user)
    except (DatabaseError, IntegrityError, ObjectDoesNotExist) as e:
        logger.error(f"Failed to reindex for privacy change: {e}")


# Management command helpers
def setup_elasticsearch_for_tenant(tenant_id):
    """Setup Elasticsearch for a specific tenant"""
    es_service = JournalElasticsearchService()

    # Create index
    index_created = es_service.create_journal_index(tenant_id)

    if index_created:
        # Bulk index existing entries
        bulk_result = es_service.bulk_index_entries(tenant_id)
        return {
            'index_created': True,
            'bulk_index_result': bulk_result
        }

    return {'index_created': False}


def reindex_all_tenants():
    """Reindex all tenants' journal entries"""
    results = {}

    for tenant in Tenant.objects.all():
        try:
            result = setup_elasticsearch_for_tenant(tenant.id)
            results[tenant.tenantname] = result
        except (ValueError, TypeError) as e:
            results[tenant.tenantname] = {'error': str(e)}

    return results