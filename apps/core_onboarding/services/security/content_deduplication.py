"""
Content Deduplication Service with Version Awareness
Prevents duplicate document ingestion with intelligent version handling
"""
import hashlib
import logging
from typing import Dict, Any, List
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime
from apps.core.exceptions.patterns import DATABASE_EXCEPTIONS

from apps.core.exceptions.patterns import ENCRYPTION_EXCEPTIONS


logger = logging.getLogger(__name__)


class ContentDeduplicator:
    """
    Content deduplication with hash-based detection and version management
    Merges functionality from both original implementations
    """

    def check_duplicate_content(self, content: str, content_hash: str = None) -> Dict[str, Any]:
        """Check if content already exists in knowledge base"""
        if not content:
            return {'is_duplicate': False, 'duplicate_info': None}

        if not content_hash:
            content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()

        try:
            from apps.core_onboarding.models import AuthoritativeKnowledge

            existing_docs = AuthoritativeKnowledge.objects.filter(
                doc_checksum=content_hash,
                is_current=True
            )

            if existing_docs.exists():
                existing_doc = existing_docs.first()
                return {
                    'is_duplicate': True,
                    'duplicate_info': {
                        'existing_doc_id': str(existing_doc.knowledge_id),
                        'existing_title': existing_doc.document_title,
                        'existing_version': existing_doc.document_version,
                        'hash_match': 'exact',
                        'should_reject': True,
                        'recommendation': 'Content already exists. Consider version update instead.'
                    }
                }

            similar_docs = self._find_similar_content(content, content_hash)
            if similar_docs:
                return {
                    'is_duplicate': False,
                    'similar_content': similar_docs,
                    'recommendation': 'Similar content found. Review for potential duplication.'
                }

            return {'is_duplicate': False, 'duplicate_info': None, 'content_hash': content_hash}

        except ENCRYPTION_EXCEPTIONS as e:
            logger.error(f"Error checking duplicate content: {str(e)}")
            return {'is_duplicate': False, 'duplicate_info': None, 'error': str(e)}

    def check_duplicate_with_versioning(self, content_hash: str, document_info: Dict[str, Any]) -> Dict[str, Any]:
        """Check for duplicates considering version bumps"""
        try:
            from apps.core_onboarding.models import AuthoritativeKnowledge

            dedup_result = {
                'is_duplicate': False,
                'allow_duplicate': False,
                'existing_documents': [],
                'version_conflict': False,
                'recommendations': []
            }

            exact_matches = AuthoritativeKnowledge.objects.filter(
                doc_checksum=content_hash,
                is_current=True
            )

            if not exact_matches.exists():
                return dedup_result

            for existing_doc in exact_matches:
                match_info = {
                    'doc_id': str(existing_doc.knowledge_id),
                    'title': existing_doc.document_title,
                    'version': existing_doc.document_version,
                    'source_org': existing_doc.source_organization,
                    'jurisdiction': existing_doc.jurisdiction,
                    'industry': existing_doc.industry
                }

                dedup_result['existing_documents'].append(match_info)

                if self._is_version_update(existing_doc, document_info):
                    dedup_result['allow_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Version update: {existing_doc.document_version} → {document_info.get('version', 'unknown')}"
                    )
                elif self._is_different_context(existing_doc, document_info):
                    dedup_result['allow_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Different context: {existing_doc.jurisdiction}/{existing_doc.industry}"
                    )
                else:
                    dedup_result['is_duplicate'] = True
                    dedup_result['recommendations'].append(
                        f"Exact duplicate: {existing_doc.document_title}"
                    )

            return dedup_result

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error checking duplicates: {str(e)}")
            return {'is_duplicate': False, 'error': str(e)}

    def should_allow_duplicate(self, existing_doc_info: Dict, new_doc_info: Dict) -> bool:
        """Determine if duplicate content should be allowed"""
        existing_version = existing_doc_info.get('existing_version', '')
        new_version = new_doc_info.get('document_version', '')

        if existing_version != new_version and new_version:
            return True

        existing_org = existing_doc_info.get('source_organization', '')
        new_org = new_doc_info.get('source_organization', '')

        if existing_org != new_org:
            return True

        existing_jurisdiction = existing_doc_info.get('jurisdiction', '')
        new_jurisdiction = new_doc_info.get('jurisdiction', '')

        if existing_jurisdiction != new_jurisdiction and new_jurisdiction:
            return True

        return False

    def retire_superseded_versions(self, document_info: Dict[str, Any]) -> List[str]:
        """Retire superseded versions when a new version is ingested"""
        try:
            from apps.core_onboarding.models import AuthoritativeKnowledge

            older_versions = AuthoritativeKnowledge.objects.filter(
                source_organization=document_info.get('source_organization'),
                document_title__iexact=document_info.get('document_title', ''),
                is_current=True
            ).exclude(
                document_version=document_info.get('document_version', '')
            )

            retired_ids = []
            for old_doc in older_versions:
                old_doc.is_current = False
                old_doc.tags['superseded_by'] = document_info.get('knowledge_id', '')
                old_doc.tags['superseded_at'] = datetime.now().isoformat()
                old_doc.save()
                retired_ids.append(str(old_doc.knowledge_id))

            if retired_ids:
                logger.info(f"Retired {len(retired_ids)} superseded document versions")

            return retired_ids

        except DATABASE_EXCEPTIONS as e:
            logger.error(f"Error retiring superseded versions: {str(e)}")
            return []

    def _find_similar_content(self, content: str, content_hash: str) -> List[Dict[str, Any]]:
        """Find similar content using fuzzy matching"""
        try:
            from apps.core_onboarding.models import AuthoritativeKnowledge

            similar_candidates = AuthoritativeKnowledge.objects.filter(
                is_current=True
            ).exclude(doc_checksum=content_hash)

            similar_docs = []
            for doc in similar_candidates[:50]:  # Limit candidates
                similarity_score = self._calculate_similarity_score(content, doc.content_summary or '')
                if similarity_score > 0.7:
                    similar_docs.append({
                        'doc_id': str(doc.knowledge_id),
                        'title': doc.document_title,
                        'similarity_score': similarity_score,
                        'reason': 'high_content_similarity'
                    })

            return similar_docs[:5]

        except DATABASE_EXCEPTIONS as e:
            logger.warning(f"Error finding similar content: {str(e)}")
            return []

    def _calculate_similarity_score(self, content1: str, content2: str) -> float:
        """Calculate Jaccard similarity between two texts"""
        if not content1 or not content2:
            return 0.0

        words1 = set(content1.lower().split())
        words2 = set(content2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0

    def _is_version_update(self, existing_doc, new_doc_info: Dict[str, Any]) -> bool:
        """Check if this is a legitimate version update"""
        existing_version = existing_doc.document_version
        new_version = new_doc_info.get('document_version', '')
        existing_org = existing_doc.source_organization
        new_org = new_doc_info.get('source_organization', '')

        return existing_org == new_org and existing_version != new_version and new_version

    def _is_different_context(self, existing_doc, new_doc_info: Dict[str, Any]) -> bool:
        """Check if document has different jurisdiction/industry context"""
        existing_jurisdiction = existing_doc.jurisdiction
        new_jurisdiction = new_doc_info.get('jurisdiction', '')
        existing_industry = existing_doc.industry
        new_industry = new_doc_info.get('industry', '')

        return ((existing_jurisdiction != new_jurisdiction and new_jurisdiction) or
                (existing_industry != new_industry and new_industry))


def get_content_deduplicator() -> ContentDeduplicator:
    """Factory function to get content deduplicator"""
    return ContentDeduplicator()
