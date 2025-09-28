import re
import logging
from typing import Dict

from ...exceptions import DocumentParseError

logger = logging.getLogger(__name__)


class HTMLParser:
    """HTML document parser using BeautifulSoup"""

    def __init__(self, max_text_length: int = 1_000_000):
        self.max_text_length = max_text_length

    def parse(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse HTML document"""
        try:
            from bs4 import BeautifulSoup

            text_content = content.decode('utf-8', errors='ignore')
            soup = BeautifulSoup(text_content, 'html.parser')

            for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
                element.decompose()

            title = soup.find('title')
            title_text = title.get_text().strip() if title else ""

            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content')
            if main_content:
                full_text = main_content.get_text(separator='\n', strip=True)
            else:
                full_text = soup.get_text(separator='\n', strip=True)

            if len(full_text) > self.max_text_length:
                full_text = full_text[:self.max_text_length]
                logger.warning("HTML text truncated due to size limit")

            headings = []
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                headings.append({
                    'level': heading.name,
                    'text': heading.get_text().strip()
                })

            return {
                'full_text': full_text,
                'title': title_text,
                'headings': headings,
                'document_info': {
                    'title': title_text,
                    'language': soup.get('lang'),
                    'description': self._extract_meta_content(soup, 'description'),
                    'keywords': self._extract_meta_content(soup, 'keywords'),
                    'author': self._extract_meta_content(soup, 'author')
                },
                'parser_metadata': {
                    'parser': 'BeautifulSoup',
                    'total_chars': len(full_text),
                    'headings_count': len(headings)
                }
            }

        except ImportError:
            logger.warning("BeautifulSoup not installed, using basic HTML parsing")
            text = content.decode('utf-8', errors='ignore')
            clean_text = re.sub(r'<[^>]+>', '', text)
            clean_text = re.sub(r'\s+', ' ', clean_text).strip()

            return {
                'full_text': clean_text[:self.max_text_length],
                'title': "",
                'headings': [],
                'document_info': {},
                'parser_metadata': {'parser': 'regex_fallback', 'fallback': True}
            }
        except (ValueError, TypeError) as e:
            logger.error(f"HTML parsing failed: {str(e)}")
            raise DocumentParseError(f"HTML parsing error: {str(e)}")

    @staticmethod
    def _extract_meta_content(soup, name: str) -> str:
        """Extract content from meta tags"""
        meta = soup.find('meta', attrs={'name': name}) or soup.find('meta', attrs={'property': f'og:{name}'})
        return meta.get('content', '') if meta else ''