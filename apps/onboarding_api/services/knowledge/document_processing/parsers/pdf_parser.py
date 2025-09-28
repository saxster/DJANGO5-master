import logging
from typing import Dict
from io import BytesIO

from ...exceptions import DocumentParseError

logger = logging.getLogger(__name__)


class PDFParser:
    """PDF document parser using PyPDF2"""

    def __init__(self, max_text_length: int = 1_000_000):
        self.max_text_length = max_text_length

    def parse(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse PDF document"""
        try:
            import PyPDF2

            pdf_reader = PyPDF2.PdfReader(BytesIO(content))

            full_text = ""
            page_texts = []

            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                page_texts.append(page_text)
                full_text += page_text + "\n\n"

                if len(full_text) > self.max_text_length:
                    logger.warning(f"PDF text exceeds limit, truncating at page {page_num}")
                    break

            pdf_info = pdf_reader.metadata or {}

            return {
                'full_text': full_text.strip(),
                'page_texts': page_texts,
                'page_count': len(pdf_reader.pages),
                'document_info': {
                    'title': pdf_info.get('/Title'),
                    'author': pdf_info.get('/Author'),
                    'subject': pdf_info.get('/Subject'),
                    'creator': pdf_info.get('/Creator'),
                    'creation_date': pdf_info.get('/CreationDate'),
                    'modification_date': pdf_info.get('/ModDate')
                },
                'parser_metadata': {
                    'parser': 'PyPDF2',
                    'pages_processed': len(page_texts),
                    'total_chars': len(full_text)
                }
            }

        except ImportError:
            logger.warning("PyPDF2 not installed, falling back to basic text extraction")
            text = content.decode('utf-8', errors='ignore')
            return {
                'full_text': text[:self.max_text_length],
                'page_texts': [text],
                'page_count': 1,
                'document_info': {},
                'parser_metadata': {'parser': 'fallback_binary', 'fallback': True}
            }
        except (ValueError, TypeError, IOError) as e:
            logger.error(f"PDF parsing failed: {str(e)}")
            raise DocumentParseError(f"PDF parsing error: {str(e)}")