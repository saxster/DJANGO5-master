import re
import hashlib
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class ChunkProcessor:
    """
    Post-processes document chunks for quality and metadata enhancement
    """

    def __init__(self, max_tokens: int = 512):
        self.max_tokens = max_tokens

    def post_process_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """Post-process chunks to ensure quality and token limits"""
        processed_chunks = []

        for i, chunk in enumerate(chunks):
            estimated_tokens = len(chunk['text']) // 4

            if estimated_tokens > self.max_tokens:
                sub_chunks = self.split_oversized_chunk(chunk)
                processed_chunks.extend(sub_chunks)
            else:
                chunk['chunk_index'] = i
                chunk['estimated_tokens'] = estimated_tokens
                chunk['chunk_checksum'] = hashlib.md5(chunk['text'].encode()).hexdigest()[:16]
                processed_chunks.append(chunk)

        return processed_chunks

    def split_oversized_chunk(self, chunk: Dict) -> List[Dict]:
        """Split a chunk that exceeds token limits"""
        text = chunk['text']
        max_chars = self.max_tokens * 4

        if len(text) <= max_chars:
            return [chunk]

        sentences = re.split(r'(?<=[.!?])\s+', text)
        sub_chunks = []
        current_text = ""

        for sentence in sentences:
            if len(current_text) + len(sentence) <= max_chars:
                current_text += sentence + " "
            else:
                if current_text.strip():
                    sub_chunk = chunk.copy()
                    sub_chunk['text'] = current_text.strip()
                    sub_chunk['estimated_tokens'] = len(current_text) // 4
                    sub_chunks.append(sub_chunk)
                current_text = sentence + " "

        if current_text.strip():
            sub_chunk = chunk.copy()
            sub_chunk['text'] = current_text.strip()
            sub_chunk['estimated_tokens'] = len(current_text) // 4
            sub_chunks.append(sub_chunk)

        return sub_chunks

    @staticmethod
    def create_chunk_tags(section: Dict, metadata: Optional[Dict] = None, start: int = 0, end: int = None) -> Dict:
        """Create comprehensive tags for a chunk"""
        tags = (metadata or {}).copy()

        if section.get('heading'):
            tags.update({
                'section_title': section['heading']['text'],
                'section_level': section['heading']['level'],
                'heading_source': section['heading']['source']
            })

        if section.get('page_start'):
            tags['page_start'] = section['page_start']
        if section.get('page_end'):
            tags['page_end'] = section['page_end']

        tags.update({
            'section_start': start,
            'section_end': end or len(section.get('content', '')),
            'has_heading': bool(section.get('heading'))
        })

        return tags