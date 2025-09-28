import re
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class StructureDetector:
    """
    Detects document structure (headings, page breaks, sections)
    """

    def __init__(self):
        self.heading_patterns = [
            r'^#+\s+(.+)$',
            r'^(.+)\n={3,}$',
            r'^(.+)\n-{3,}$',
            r'^\d+\.\s+(.+)$',
            r'^([A-Z][A-Z\s]{2,})\s*$',
            r'^\s*([A-Z][a-z\s]+):\s*$',
        ]

        self.page_break_patterns = [
            r'^\s*page\s+\d+\s*$',
            r'^\s*-+\s*page\s+\d+\s*-+\s*$',
            r'\f',
            r'^\s*\[page\s+\d+\]\s*$',
        ]

    def has_structure(self, text: str) -> bool:
        """Check if text has detectable structure"""
        lines = text.split('\n')[:50]

        structure_indicators = 0
        for line in lines:
            if any(re.match(pattern, line.strip(), re.IGNORECASE) for pattern in self.heading_patterns):
                structure_indicators += 1
            if structure_indicators >= 3:
                return True

        return False

    def extract_headings(self, text: str, parsed_data: Optional[Dict] = None) -> List[Dict]:
        """Extract headings from text and parsed data"""
        headings = []

        if parsed_data and 'headings' in parsed_data:
            for heading in parsed_data['headings']:
                heading_text = heading.get('text', '').strip()
                if heading_text:
                    pos = text.find(heading_text)
                    if pos != -1:
                        headings.append({
                            'text': heading_text,
                            'level': self.normalize_heading_level(heading.get('level', 'h2')),
                            'position': pos,
                            'source': 'parsed'
                        })

        lines = text.split('\n')
        current_pos = 0

        for line in lines:
            line_stripped = line.strip()
            if line_stripped:
                for i, pattern in enumerate(self.heading_patterns):
                    match = re.match(pattern, line_stripped, re.IGNORECASE)
                    if match:
                        heading_text = match.group(1).strip()
                        headings.append({
                            'text': heading_text,
                            'level': i + 1,
                            'position': current_pos + text[current_pos:].find(line_stripped),
                            'source': 'pattern'
                        })
                        break
            current_pos += len(line) + 1

        headings = sorted(headings, key=lambda x: x['position'])
        unique_headings = []
        seen_positions = set()

        for heading in headings:
            if heading['position'] not in seen_positions:
                unique_headings.append(heading)
                seen_positions.add(heading['position'])

        return unique_headings

    def extract_page_breaks(self, text: str, parsed_data: Optional[Dict] = None) -> List[Dict]:
        """Extract page break positions"""
        page_breaks = []

        if parsed_data and 'page_texts' in parsed_data:
            current_pos = 0
            for i, page_text in enumerate(parsed_data['page_texts']):
                if i > 0:
                    page_breaks.append({
                        'position': current_pos,
                        'page_number': i + 1,
                        'source': 'parsed'
                    })
                current_pos += len(page_text) + 2

        for pattern in self.page_break_patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
                page_breaks.append({
                    'position': match.start(),
                    'page_number': None,
                    'source': 'pattern'
                })

        return sorted(page_breaks, key=lambda x: x['position'])

    def create_sections(self, text: str, headings: List[Dict], page_breaks: List[Dict]) -> List[Dict]:
        """Create logical sections based on headings and page breaks"""
        sections = []
        boundaries = []

        for heading in headings:
            boundaries.append({
                'position': heading['position'],
                'type': 'heading',
                'data': heading
            })

        for page_break in page_breaks:
            boundaries.append({
                'position': page_break['position'],
                'type': 'page_break',
                'data': page_break
            })

        boundaries = sorted(boundaries, key=lambda x: x['position'])

        current_section = {
            'start': 0,
            'heading': None,
            'page_start': 1,
            'content_start': 0
        }

        for boundary in boundaries:
            if boundary['type'] == 'heading':
                if current_section['start'] < boundary['position']:
                    current_section['end'] = boundary['position']
                    current_section['content'] = text[current_section['content_start']:boundary['position']].strip()
                    if current_section['content']:
                        sections.append(current_section)

                current_section = {
                    'start': boundary['position'],
                    'heading': boundary['data'],
                    'page_start': self.infer_page_number(boundary['position'], page_breaks),
                    'content_start': boundary['position']
                }

            elif boundary['type'] == 'page_break':
                current_section['page_end'] = boundary['data'].get('page_number',
                    self.infer_page_number(boundary['position'], page_breaks))

        current_section['end'] = len(text)
        current_section['content'] = text[current_section['content_start']:].strip()
        if current_section['content']:
            sections.append(current_section)

        if not sections:
            sections.append({
                'start': 0,
                'end': len(text),
                'content': text,
                'heading': None,
                'page_start': 1,
                'page_end': 1
            })

        return sections

    @staticmethod
    def normalize_heading_level(level: str) -> int:
        """Convert heading level to numeric"""
        if isinstance(level, int):
            return level
        if level.startswith('h'):
            try:
                return int(level[1:])
            except (ValueError, IndexError):
                return 2
        return 2

    @staticmethod
    def infer_page_number(position: int, page_breaks: List[Dict]) -> int:
        """Infer page number for a given text position"""
        page_num = 1
        for page_break in page_breaks:
            if page_break['position'] <= position:
                if page_break.get('page_number'):
                    page_num = page_break['page_number']
                else:
                    page_num += 1
            else:
                break
        return page_num