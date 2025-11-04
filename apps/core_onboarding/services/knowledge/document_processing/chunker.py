import logging
from typing import List, Dict, Optional
from django.conf import settings

from .structure_detector import StructureDetector
from .chunk_processor import ChunkProcessor

logger = logging.getLogger(__name__)


class DocumentChunker:
    """
    Production-grade chunker service with heading/page awareness and token budgeting
    """

    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, max_tokens: int = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.max_tokens = max_tokens or getattr(settings, 'KB_MAX_CHUNK_TOKENS', 512)

        self.structure_detector = StructureDetector()
        self.chunk_processor = ChunkProcessor(self.max_tokens)

    def chunk_text(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Basic text chunking with boundary detection"""
        if not text:
            return []

        if self.structure_detector.has_structure(text):
            return self.chunk_with_structure(text, metadata)

        return self._chunk_simple_overlap(text, metadata)

    def chunk_with_structure(self, text: str, metadata: Optional[Dict] = None, parsed_data: Dict = None) -> List[Dict]:
        """Chunk text with heading and page awareness"""
        if not text:
            return []

        chunks = []

        headings = self.structure_detector.extract_headings(text, parsed_data)
        page_breaks = self.structure_detector.extract_page_breaks(text, parsed_data)

        sections = self.structure_detector.create_sections(text, headings, page_breaks)

        for section in sections:
            section_chunks = self._chunk_section(section, metadata)
            chunks.extend(section_chunks)

        processed_chunks = self.chunk_processor.post_process_chunks(chunks)

        logger.info(f"Created {len(processed_chunks)} chunks from {len(sections)} sections")
        return processed_chunks

    def chunk_document(self, document_content: str, document_metadata: Dict, parsed_data: Dict = None) -> List[Dict]:
        """Chunk a full document with enhanced metadata and structure awareness"""
        base_chunks = self.chunk_with_structure(document_content, document_metadata, parsed_data)

        enhanced_chunks = []
        for i, chunk in enumerate(base_chunks):
            enhanced_chunk = chunk.copy()
            enhanced_chunk['tags'].update({
                'document_title': document_metadata.get('title', ''),
                'source_org': document_metadata.get('organization', ''),
                'authority': document_metadata.get('authority_level', 'medium'),
                'chunk_position': f"{i+1}/{len(base_chunks)}",
                'is_first_chunk': i == 0,
                'is_last_chunk': i == len(base_chunks) - 1,
                'total_chunks': len(base_chunks)
            })
            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks

    def _chunk_section(self, section: Dict, metadata: Optional[Dict] = None) -> List[Dict]:
        """Chunk a single section with respect for boundaries"""
        content = section['content']
        if not content or len(content.strip()) == 0:
            return []

        chunks = []

        if len(content) <= self.chunk_size:
            chunk = {
                'text': content.strip(),
                'start_idx': section['start'],
                'end_idx': section['end'],
                'section_heading': section.get('heading', {}).get('text', ''),
                'page_start': section.get('page_start'),
                'page_end': section.get('page_end', section.get('page_start')),
                'tags': ChunkProcessor.create_chunk_tags(section, metadata)
            }
            chunks.append(chunk)
            return chunks

        start = 0
        content_length = len(content)

        while start < content_length:
            end = min(start + self.chunk_size, content_length)

            if end < content_length:
                sentence_end = content.rfind('.', start, end)
                if sentence_end > start + self.chunk_size * 0.7:
                    end = sentence_end + 1
                else:
                    para_end = content.rfind('\n\n', start, end)
                    if para_end > start + self.chunk_size * 0.6:
                        end = para_end
                    else:
                        word_end = content.rfind(' ', start, end)
                        if word_end > start + self.chunk_size * 0.8:
                            end = word_end

            chunk_text = content[start:end].strip()
            if chunk_text:
                chunk = {
                    'text': chunk_text,
                    'start_idx': section['start'] + start,
                    'end_idx': section['start'] + end,
                    'section_heading': section.get('heading', {}).get('text', ''),
                    'page_start': section.get('page_start'),
                    'page_end': section.get('page_end', section.get('page_start')),
                    'tags': ChunkProcessor.create_chunk_tags(section, metadata, start, end)
                }
                chunks.append(chunk)

            start = max(start + 1, end - self.chunk_overlap)

        return chunks

    def _chunk_simple_overlap(self, text: str, metadata: Optional[Dict] = None) -> List[Dict]:
        """Fallback simple overlapping chunks"""
        chunks = []
        text_length = len(text)

        if text_length <= self.chunk_size:
            return [{
                'text': text,
                'start_idx': 0,
                'end_idx': text_length,
                'tags': metadata or {}
            }]

        start = 0
        chunk_index = 0

        while start < text_length:
            end = min(start + self.chunk_size, text_length)

            if end < text_length:
                sentence_end = text.rfind('.', start, end)
                if sentence_end > start + self.chunk_size * 0.7:
                    end = sentence_end + 1
                else:
                    word_end = text.rfind(' ', start, end)
                    if word_end > start + self.chunk_size * 0.8:
                        end = word_end

            chunk_text = text[start:end].strip()
            if chunk_text:
                chunk_tags = (metadata or {}).copy()
                chunk_tags.update({
                    'chunk_start': start,
                    'chunk_end': end,
                    'chunk_length': len(chunk_text)
                })

                chunks.append({
                    'text': chunk_text,
                    'start_idx': start,
                    'end_idx': end,
                    'tags': chunk_tags
                })

            start = max(start + 1, end - self.chunk_overlap)
            chunk_index += 1

            if chunk_index > 1000:
                logger.warning("Breaking chunking loop after 1000 chunks")
                break

        return chunks