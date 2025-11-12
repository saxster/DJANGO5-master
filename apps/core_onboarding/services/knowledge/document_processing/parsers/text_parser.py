import json
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from ...exceptions import DocumentParseError

logger = logging.getLogger(__name__)


class TextParser:
    """Plain text, JSON, and XML document parser"""

    def __init__(self, max_text_length: int = 1_000_000):
        self.max_text_length = max_text_length

    def parse_plain_text(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse plain text document"""
        try:
            encoding_used = 'utf-8'
            for encoding in ['utf-8', 'utf-16', 'iso-8859-1', 'cp1252']:
                try:
                    text = content.decode(encoding)
                    encoding_used = encoding
                    break
                except UnicodeDecodeError:
                    continue
            else:
                text = content.decode('utf-8', errors='replace')

            if len(text) > self.max_text_length:
                text = text[:self.max_text_length]
                logger.warning("Text content truncated due to size limit")

            lines = text.split('\n')
            potential_headings = []

            for i, line in enumerate(lines[:100]):
                line = line.strip()
                if line and (line.isupper() or line.endswith(':') or len(line) < 80):
                    potential_headings.append({
                        'line_number': i,
                        'text': line
                    })

            return {
                'full_text': text,
                'line_count': len(lines),
                'potential_headings': potential_headings,
                'document_info': {},
                'parser_metadata': {
                    'parser': 'plain_text',
                    'encoding_used': encoding_used,
                    'total_chars': len(text),
                    'line_count': len(lines)
                }
            }

        except (ValueError, TypeError) as e:
            logger.error(f"Text parsing failed: {str(e)}")
            raise DocumentParseError(f"Text parsing error: {str(e)}")

    def parse_json(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse JSON document"""
        try:
            text_content = content.decode('utf-8', errors='ignore')
            data = json.loads(text_content)

            if isinstance(data, dict):
                full_text = self._json_to_text(data)
            elif isinstance(data, list):
                full_text = "\n".join(self._json_to_text(item) if isinstance(item, dict) else str(item) for item in data)
            else:
                full_text = str(data)

            return {
                'full_text': full_text[:self.max_text_length],
                'json_data': data,
                'document_info': {
                    'title': data.get('title') if isinstance(data, dict) else None,
                    'version': data.get('version') if isinstance(data, dict) else None
                },
                'parser_metadata': {
                    'parser': 'json',
                    'data_type': type(data).__name__,
                    'total_chars': len(full_text)
                }
            }

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {str(e)}")
            raise DocumentParseError(f"JSON parsing error: {str(e)}")
        except (ValueError, TypeError) as e:
            logger.error(f"JSON conversion failed: {str(e)}")
            raise DocumentParseError(f"JSON conversion error: {str(e)}")

    def parse_xml(self, content: bytes, metadata: Dict = None) -> Dict[str, any]:
        """Parse XML document"""
        try:
            text_content = content.decode('utf-8', errors='ignore')
            root = ET.fromstring(text_content)

            full_text = self._xml_to_text(root)

            title = root.find('.//title')
            version = root.find('.//version')

            return {
                'full_text': full_text[:self.max_text_length],
                'root_tag': root.tag,
                'document_info': {
                    'title': title.text if title is not None else None,
                    'version': version.text if version is not None else None
                },
                'parser_metadata': {
                    'parser': 'xml_etree',
                    'root_element': root.tag,
                    'total_chars': len(full_text)
                }
            }

        except ET.ParseError as e:
            logger.error(f"XML parsing failed: {str(e)}")
            raise DocumentParseError(f"XML parsing error: {str(e)}")
        except (ValueError, TypeError) as e:
            logger.error(f"XML conversion failed: {str(e)}")
            raise DocumentParseError(f"XML conversion error: {str(e)}")

    def _json_to_text(self, data: Dict, prefix: str = "") -> str:
        """Convert JSON dictionary to readable text"""
        lines = []
        for key, value in data.items():
            if isinstance(value, dict):
                lines.append(f"{prefix}{key}:")
                lines.append(self._json_to_text(value, prefix + "  "))
            elif isinstance(value, list):
                lines.append(f"{prefix}{key}: [{len(value)} items]")
                for i, item in enumerate(value[:5]):
                    if isinstance(item, dict):
                        lines.append(f"{prefix}  {i+1}:")
                        lines.append(self._json_to_text(item, prefix + "    "))
                    else:
                        lines.append(f"{prefix}  {i+1}: {str(item)}")
            else:
                lines.append(f"{prefix}{key}: {str(value)}")
        return "\n".join(lines)

    def _xml_to_text(self, element, level: int = 0) -> str:
        """Convert XML element to readable text"""
        lines = []
        indent = "  " * level

        if element.text and element.text.strip():
            lines.append(f"{indent}{element.tag}: {element.text.strip()}")
        else:
            lines.append(f"{indent}{element.tag}:")

        if element.attrib:
            for key, value in element.attrib.items():
                lines.append(f"{indent}  @{key}: {value}")

        for child in element:
            lines.append(self._xml_to_text(child, level + 1))

        return "\n".join(lines)