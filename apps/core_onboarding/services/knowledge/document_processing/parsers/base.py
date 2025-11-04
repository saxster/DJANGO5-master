import logging
from typing import Dict
from django.conf import settings

from ...exceptions import UnsupportedFormatError, DocumentParseError
from .pdf_parser import PDFParser
from .html_parser import HTMLParser
from .text_parser import TextParser

logger = logging.getLogger(__name__)


class DocumentParser:
    """
    Multi-format document parser supporting PDF, HTML, and text formats
    """

    def __init__(self):
        self.max_text_length = getattr(settings, 'KB_MAX_TEXT_LENGTH', 1_000_000)
        self.preserve_formatting = getattr(settings, 'KB_PRESERVE_FORMATTING', True)

        self.pdf_parser = PDFParser(self.max_text_length)
        self.html_parser = HTMLParser(self.max_text_length)
        self.text_parser = TextParser(self.max_text_length)

    def parse_document(self, content: bytes, content_type: str, metadata: Dict = None) -> Dict[str, any]:
        """Parse document content based on content type"""
        logger.info(f"Parsing document of type {content_type} ({len(content)} bytes)")

        try:
            if content_type.startswith('application/pdf'):
                return self.pdf_parser.parse(content, metadata)
            elif content_type.startswith('text/html'):
                return self.html_parser.parse(content, metadata)
            elif content_type.startswith('text/plain'):
                return self.text_parser.parse_plain_text(content, metadata)
            elif content_type.startswith('application/json'):
                return self.text_parser.parse_json(content, metadata)
            elif content_type.startswith(('application/xml', 'text/xml')):
                return self.text_parser.parse_xml(content, metadata)
            else:
                raise UnsupportedFormatError(f"Unsupported content type: {content_type}")

        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing document: {str(e)}")
            raise DocumentParseError(f"Failed to parse document: {str(e)}")