"""
HelpBot Knowledge Service

Integrates with existing txtai infrastructure for semantic search and RAG.
Handles knowledge indexing, retrieval, and content processing.
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from django.conf import settings
from django.db import transaction
from django.core.cache import cache
from django.utils import timezone
from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank

from apps.helpbot.models import HelpBotKnowledge, HelpBotAnalytics

logger = logging.getLogger(__name__)


class HelpBotKnowledgeService:
    """
    Core knowledge management service for HelpBot.
    Integrates with existing txtai engine and semantic search infrastructure.
    """

    def __init__(self):
        self.cache_prefix = 'helpbot_knowledge'
        self.cache_timeout = getattr(settings, 'HELPBOT_CACHE_TIMEOUT', 3600)

        # Initialize txtai integration if available
        self._init_txtai_integration()

        # Documentation paths based on codebase analysis
        self.doc_paths = [
            settings.BASE_DIR / 'docs',
            settings.BASE_DIR / 'CLAUDE.md',
            settings.BASE_DIR / 'README.md',
        ]

    def _init_txtai_integration(self):
        """Initialize integration with existing txtai engine."""
        try:
            # Try to import and initialize txtai engine components
            # Based on the templates I found, there's already txtai infrastructure
            self.txtai_enabled = getattr(settings, 'TXTAI_ENABLED', False)
            if self.txtai_enabled:
                logger.info("txtai integration enabled for HelpBot")
            else:
                logger.info("txtai integration not enabled, using basic search")
        except ImportError as e:
            logger.warning(f"Could not initialize txtai integration: {e}")
            self.txtai_enabled = False

    def initialize_index(self) -> bool:
        """
        Initialize the knowledge index from existing documentation.
        Returns True if successful, False otherwise.
        """
        try:
            logger.info("Initializing HelpBot knowledge index...")

            # Process documentation files
            processed_count = self._process_documentation_files()

            # Process API documentation
            api_count = self._process_api_documentation()

            # Process model documentation
            model_count = self._process_model_documentation()

            # Build search index
            if self.txtai_enabled:
                self._build_txtai_index()

            total_count = processed_count + api_count + model_count
            logger.info(f"HelpBot knowledge index initialized with {total_count} entries")

            # Update analytics
            self._record_analytics('knowledge_index_update', total_count)

            return True

        except Exception as e:
            logger.error(f"Error initializing HelpBot knowledge index: {e}")
            return False

    def _process_documentation_files(self) -> int:
        """Process markdown documentation files."""
        processed_count = 0

        for doc_path in self.doc_paths:
            if doc_path.is_file():
                processed_count += self._process_single_file(doc_path)
            elif doc_path.is_dir():
                for md_file in doc_path.rglob('*.md'):
                    processed_count += self._process_single_file(md_file)

        return processed_count

    def _process_single_file(self, file_path: Path) -> int:
        """Process a single markdown file into knowledge entries."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            if not content.strip():
                return 0

            # Generate file hash for change detection
            file_hash = hashlib.md5(content.encode()).hexdigest()

            # Check if file has changed
            cache_key = f"{self.cache_prefix}_file_{file_path.name}_{file_hash}"
            if cache.get(cache_key):
                return 0  # Already processed

            # Determine knowledge type and category from path and content
            knowledge_type, category = self._classify_document(file_path, content)

            # Extract title from content or filename
            title = self._extract_title(content, file_path.name)

            # Extract search keywords
            keywords = self._extract_keywords(content, title)

            # Create or update knowledge entry
            knowledge, created = HelpBotKnowledge.objects.update_or_create(
                source_file=str(file_path),
                defaults={
                    'title': title,
                    'content': content,
                    'knowledge_type': knowledge_type,
                    'category': category,
                    'search_keywords': keywords,
                    'tags': self._extract_tags(content),
                    'related_urls': self._extract_urls(content),
                    'is_active': True,
                }
            )

            # Cache that we've processed this version
            cache.set(cache_key, True, self.cache_timeout)

            logger.debug(f"{'Created' if created else 'Updated'} knowledge: {title}")
            return 1 if created else 0

        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}")
            return 0

    def _classify_document(self, file_path: Path, content: str) -> Tuple[str, str]:
        """Classify document type and category based on path and content."""
        path_str = str(file_path).lower()
        content_lower = content.lower()

        # Determine knowledge type
        if 'api' in path_str or 'openapi' in content_lower:
            knowledge_type = HelpBotKnowledge.KnowledgeTypeChoices.API_REFERENCE
        elif 'faq' in path_str or 'frequently asked' in content_lower:
            knowledge_type = HelpBotKnowledge.KnowledgeTypeChoices.FAQ
        elif 'tutorial' in path_str or 'guide' in path_str:
            knowledge_type = HelpBotKnowledge.KnowledgeTypeChoices.TUTORIAL
        elif 'troubleshoot' in path_str or 'error' in path_str:
            knowledge_type = HelpBotKnowledge.KnowledgeTypeChoices.TROUBLESHOOTING
        else:
            knowledge_type = HelpBotKnowledge.KnowledgeTypeChoices.DOCUMENTATION

        # Determine category based on path and content
        if any(term in path_str for term in ['operation', 'task', 'tour', 'schedule']):
            category = HelpBotKnowledge.CategoryChoices.OPERATIONS
        elif any(term in path_str for term in ['asset', 'inventory', 'maintenance']):
            category = HelpBotKnowledge.CategoryChoices.ASSETS
        elif any(term in path_str for term in ['people', 'user', 'attendance']):
            category = HelpBotKnowledge.CategoryChoices.PEOPLE
        elif any(term in path_str for term in ['helpdesk', 'ticket', 'support']):
            category = HelpBotKnowledge.CategoryChoices.HELPDESK
        elif any(term in path_str for term in ['report', 'analytics', 'dashboard']):
            category = HelpBotKnowledge.CategoryChoices.REPORTS
        elif any(term in path_str for term in ['admin', 'settings', 'config']):
            category = HelpBotKnowledge.CategoryChoices.ADMINISTRATION
        elif any(term in path_str for term in ['api', 'technical', 'development']):
            category = HelpBotKnowledge.CategoryChoices.TECHNICAL
        else:
            category = HelpBotKnowledge.CategoryChoices.GENERAL

        return knowledge_type, category

    def _extract_title(self, content: str, filename: str) -> str:
        """Extract title from content or generate from filename."""
        lines = content.split('\n')

        # Look for markdown H1
        for line in lines[:10]:  # Check first 10 lines
            line = line.strip()
            if line.startswith('# '):
                return line[2:].strip()

        # Look for HTML title or other patterns
        for line in lines[:20]:  # Check first 20 lines
            line = line.strip()
            if line.startswith('title:') or line.startswith('Title:'):
                return line.split(':', 1)[1].strip()

        # Generate from filename
        title = filename.replace('.md', '').replace('_', ' ').replace('-', ' ')
        return title.title()

    def _extract_keywords(self, content: str, title: str) -> List[str]:
        """Extract search keywords from content."""
        keywords = []

        # Add title words
        keywords.extend(title.lower().split())

        # Extract from headers
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                header = line.lstrip('#').strip()
                keywords.extend(header.lower().split())

        # Extract important terms
        important_terms = [
            'api', 'endpoint', 'authentication', 'authorization', 'error', 'troubleshoot',
            'configuration', 'setup', 'installation', 'deployment', 'security',
            'performance', 'optimization', 'monitoring', 'logging', 'testing'
        ]

        content_lower = content.lower()
        for term in important_terms:
            if term in content_lower:
                keywords.append(term)

        # Remove duplicates and short words
        keywords = list(set([k for k in keywords if len(k) > 2]))

        return keywords[:20]  # Limit to 20 keywords

    def _extract_tags(self, content: str) -> List[str]:
        """Extract tags from content."""
        tags = []
        content_lower = content.lower()

        # Technology tags (graphql=legacy, removed Oct 2025)
        tech_tags = ['django', 'postgresql', 'redis', 'api', 'rest', 'graphql', 'websocket']
        for tag in tech_tags:
            if tag in content_lower:
                tags.append(tag)

        # Feature tags
        feature_tags = ['authentication', 'security', 'monitoring', 'testing', 'deployment']
        for tag in feature_tags:
            if tag in content_lower:
                tags.append(tag)

        return list(set(tags))

    def _extract_urls(self, content: str) -> List[str]:
        """Extract URLs from content."""
        import re

        # Extract markdown links
        markdown_links = re.findall(r'\[.*?\]\((.*?)\)', content)

        # Extract plain URLs
        url_pattern = r'https?://[^\s<>"\'(){}[\]|`~]*'
        plain_urls = re.findall(url_pattern, content)

        urls = markdown_links + plain_urls

        # Filter and clean URLs
        cleaned_urls = []
        for url in urls:
            if url.startswith(('http://', 'https://', '/')):
                if len(url) < 500:  # Reasonable URL length
                    cleaned_urls.append(url)

        return list(set(cleaned_urls))[:10]  # Limit to 10 URLs

    def _process_api_documentation(self) -> int:
        """Process API documentation from existing OpenAPI schemas."""
        try:
            # Look for OpenAPI/Swagger documentation
            # Based on codebase analysis, there might be existing API docs
            api_docs_paths = [
                settings.BASE_DIR / 'docs' / 'api',
                settings.BASE_DIR / 'apps' / 'api',
            ]

            processed_count = 0
            for path in api_docs_paths:
                if path.exists():
                    for api_file in path.rglob('*.json'):
                        processed_count += self._process_api_file(api_file)
                    for api_file in path.rglob('*.yaml'):
                        processed_count += self._process_api_file(api_file)

            return processed_count

        except Exception as e:
            logger.error(f"Error processing API documentation: {e}")
            return 0

    def _process_api_file(self, file_path: Path) -> int:
        """Process a single API documentation file."""
        try:
            # This would process OpenAPI/Swagger files
            # For now, just treat as regular documentation
            return self._process_single_file(file_path)
        except Exception as e:
            logger.error(f"Error processing API file {file_path}: {e}")
            return 0

    def _process_model_documentation(self) -> int:
        """Generate documentation from Django models."""
        try:
            from django.apps import apps

            processed_count = 0

            # Get all models from the applications
            for app_config in apps.get_app_configs():
                if not app_config.name.startswith('django.'):
                    for model in app_config.get_models():
                        processed_count += self._process_model(model)

            return processed_count

        except Exception as e:
            logger.error(f"Error processing model documentation: {e}")
            return 0

    def _process_model(self, model) -> int:
        """Process a single Django model into knowledge."""
        try:
            model_name = model.__name__
            app_label = model._meta.app_label

            # Generate documentation content
            content = self._generate_model_documentation(model)

            # Create knowledge entry
            title = f"{model_name} Model - {app_label.title()} App"

            knowledge, created = HelpBotKnowledge.objects.update_or_create(
                source_file=f"model:{app_label}.{model_name}",
                defaults={
                    'title': title,
                    'content': content,
                    'knowledge_type': HelpBotKnowledge.KnowledgeTypeChoices.API_REFERENCE,
                    'category': self._categorize_model(app_label),
                    'search_keywords': [model_name.lower(), app_label] + self._extract_model_keywords(model),
                    'tags': [app_label, 'model', 'database'],
                    'is_active': True,
                }
            )

            return 1 if created else 0

        except Exception as e:
            logger.error(f"Error processing model {model}: {e}")
            return 0

    def _generate_model_documentation(self, model) -> str:
        """Generate markdown documentation for a Django model."""
        lines = [
            f"# {model.__name__} Model",
            "",
            f"**App:** {model._meta.app_label}",
            f"**Table:** {model._meta.db_table}",
            "",
        ]

        if model.__doc__:
            lines.extend([
                "## Description",
                "",
                model.__doc__.strip(),
                "",
            ])

        lines.extend([
            "## Fields",
            "",
        ])

        # Document fields
        for field in model._meta.get_fields():
            field_info = self._get_field_documentation(field)
            if field_info:
                lines.append(field_info)

        # Document methods
        public_methods = [method for method in dir(model)
                         if not method.startswith('_') and callable(getattr(model, method))]

        if public_methods:
            lines.extend([
                "",
                "## Methods",
                "",
            ])
            for method in public_methods[:10]:  # Limit to avoid too much content
                lines.append(f"- `{method}()`")

        return "\n".join(lines)

    def _get_field_documentation(self, field) -> str:
        """Generate documentation for a single model field."""
        try:
            field_type = field.__class__.__name__
            field_name = field.name if hasattr(field, 'name') else 'unknown'

            # Get field properties
            properties = []
            if hasattr(field, 'null') and field.null:
                properties.append("nullable")
            if hasattr(field, 'blank') and field.blank:
                properties.append("optional")
            if hasattr(field, 'unique') and field.unique:
                properties.append("unique")
            if hasattr(field, 'primary_key') and field.primary_key:
                properties.append("primary key")

            prop_str = f" ({', '.join(properties)})" if properties else ""

            # Get help text
            help_text = ""
            if hasattr(field, 'help_text') and field.help_text:
                help_text = f" - {field.help_text}"

            return f"- **{field_name}**: {field_type}{prop_str}{help_text}"

        except Exception:
            return ""

    def _categorize_model(self, app_label: str) -> str:
        """Categorize model based on app label."""
        category_mapping = {
            'activity': HelpBotKnowledge.CategoryChoices.OPERATIONS,
            'assets': HelpBotKnowledge.CategoryChoices.ASSETS,
            'peoples': HelpBotKnowledge.CategoryChoices.PEOPLE,
            'attendance': HelpBotKnowledge.CategoryChoices.PEOPLE,
            'y_helpdesk': HelpBotKnowledge.CategoryChoices.HELPDESK,
            'reports': HelpBotKnowledge.CategoryChoices.REPORTS,
            'onboarding': HelpBotKnowledge.CategoryChoices.ADMINISTRATION,
            'core': HelpBotKnowledge.CategoryChoices.TECHNICAL,
            'api': HelpBotKnowledge.CategoryChoices.TECHNICAL,
        }

        return category_mapping.get(app_label, HelpBotKnowledge.CategoryChoices.GENERAL)

    def _extract_model_keywords(self, model) -> List[str]:
        """Extract keywords from a Django model."""
        keywords = []

        # Add field names
        for field in model._meta.get_fields():
            if hasattr(field, 'name'):
                keywords.append(field.name.lower())

        # Add verbose names
        if hasattr(model._meta, 'verbose_name'):
            keywords.extend(model._meta.verbose_name.lower().split())

        return list(set(keywords))

    def _build_txtai_index(self):
        """Build txtai search index if enabled."""
        if not self.txtai_enabled:
            return

        try:
            # This would integrate with existing txtai engine
            # For now, just log that we would build the index
            logger.info("Building txtai index for HelpBot knowledge...")

            # Get all active knowledge
            knowledge_entries = HelpBotKnowledge.objects.filter(is_active=True)

            # Prepare documents for indexing
            documents = []
            for knowledge in knowledge_entries:
                document = {
                    'id': str(knowledge.knowledge_id),
                    'text': f"{knowledge.title}\n\n{knowledge.content}",
                    'metadata': {
                        'title': knowledge.title,
                        'category': knowledge.category,
                        'knowledge_type': knowledge.knowledge_type,
                        'tags': knowledge.tags,
                        'keywords': knowledge.search_keywords,
                    }
                }
                documents.append(document)

            logger.info(f"Prepared {len(documents)} documents for txtai indexing")

            # Here you would actually build the txtai index
            # This requires the txtai configuration from the existing system

        except Exception as e:
            logger.error(f"Error building txtai index: {e}")

    def search_knowledge(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Search knowledge base using semantic search.
        Returns list of relevant knowledge entries.
        """
        try:
            # First try txtai semantic search if available
            if self.txtai_enabled:
                results = self._txtai_search(query, category, limit)
                if results:
                    return results

            # Fallback to database search
            return self._database_search(query, category, limit)

        except Exception as e:
            logger.error(f"Error searching knowledge: {e}")
            return []

    def _txtai_search(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Search using txtai semantic search."""
        try:
            # This would integrate with existing txtai search
            # For now, return empty list
            logger.debug(f"txtai search for: {query}")
            return []

        except Exception as e:
            logger.error(f"Error in txtai search: {e}")
            return []

    def _database_search(self, query: str, category: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Fallback database search using PostgreSQL full-text search."""
        try:
            from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
            from django.db.models import Q

            # Build base query
            knowledge_qs = HelpBotKnowledge.objects.filter(is_active=True)

            if category:
                knowledge_qs = knowledge_qs.filter(category=category)

            # Use PostgreSQL full-text search
            search_vector = SearchVector('title', weight='A') + SearchVector('content', weight='B') + SearchVector('search_keywords', weight='C')
            search_query = SearchQuery(query)

            results = (
                knowledge_qs
                .annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query)
                )
                .filter(search=search_query)
                .order_by('-rank', '-usage_count', '-effectiveness_score')
                [:limit]
            )

            # Convert to list of dicts
            search_results = []
            for knowledge in results:
                result = {
                    'id': str(knowledge.knowledge_id),
                    'title': knowledge.title,
                    'content': knowledge.content[:500] + '...' if len(knowledge.content) > 500 else knowledge.content,
                    'category': knowledge.category,
                    'knowledge_type': knowledge.knowledge_type,
                    'tags': knowledge.tags,
                    'effectiveness_score': knowledge.effectiveness_score,
                    'usage_count': knowledge.usage_count,
                }
                search_results.append(result)

            # Update usage count
            from django.db import models
            knowledge_ids = [result['id'] for result in search_results]
            HelpBotKnowledge.objects.filter(knowledge_id__in=knowledge_ids).update(
                usage_count=models.F('usage_count') + 1
            )

            return search_results

        except Exception as e:
            logger.error(f"Error in database search: {e}")
            return []

    def get_knowledge_by_id(self, knowledge_id: str) -> Optional[Dict[str, Any]]:
        """Get specific knowledge entry by ID."""
        try:
            knowledge = HelpBotKnowledge.objects.get(knowledge_id=knowledge_id, is_active=True)

            # Increment usage count
            knowledge.usage_count += 1
            knowledge.save(update_fields=['usage_count'])

            return {
                'id': str(knowledge.knowledge_id),
                'title': knowledge.title,
                'content': knowledge.content,
                'category': knowledge.category,
                'knowledge_type': knowledge.knowledge_type,
                'tags': knowledge.tags,
                'related_urls': knowledge.related_urls,
                'effectiveness_score': knowledge.effectiveness_score,
                'last_updated': knowledge.last_updated.isoformat(),
            }

        except HelpBotKnowledge.DoesNotExist:
            return None
        except Exception as e:
            logger.error(f"Error getting knowledge by ID {knowledge_id}: {e}")
            return None

    def update_knowledge_effectiveness(self, knowledge_id: str, feedback_score: float):
        """Update knowledge effectiveness based on user feedback."""
        try:
            knowledge = HelpBotKnowledge.objects.get(knowledge_id=knowledge_id)

            # Update effectiveness score using exponential moving average
            current_score = knowledge.effectiveness_score
            alpha = 0.1  # Learning rate
            new_score = (1 - alpha) * current_score + alpha * feedback_score

            knowledge.effectiveness_score = new_score
            knowledge.save(update_fields=['effectiveness_score'])

            logger.debug(f"Updated effectiveness score for {knowledge_id}: {current_score} -> {new_score}")

        except HelpBotKnowledge.DoesNotExist:
            logger.warning(f"Knowledge {knowledge_id} not found for effectiveness update")
        except Exception as e:
            logger.error(f"Error updating knowledge effectiveness: {e}")

    def _record_analytics(self, metric_type: str, value: float, dimension_data: Dict = None):
        """Record analytics metrics."""
        try:
            from apps.helpbot.models import HelpBotAnalytics

            HelpBotAnalytics.objects.create(
                metric_type=metric_type,
                value=value,
                dimension_data=dimension_data or {},
                date=timezone.now().date(),
                hour=timezone.now().hour,
            )

        except Exception as e:
            logger.error(f"Error recording analytics: {e}")