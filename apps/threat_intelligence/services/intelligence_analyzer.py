from typing import Dict, List, Tuple
from django.contrib.gis.geos import Point, Polygon
from apps.threat_intelligence.models import ThreatEvent
import logging

logger = logging.getLogger(__name__)


class IntelligenceAnalyzer:
    """NLP and ML analysis of raw intelligence data."""
    
    SEVERITY_KEYWORDS = {
        'CRITICAL': ['emergency', 'evacuation', 'imminent', 'severe', 'catastrophic', 'immediate threat'],
        'HIGH': ['warning', 'dangerous', 'significant', 'major', 'urgent'],
        'MEDIUM': ['caution', 'moderate', 'watch', 'advisory'],
        'LOW': ['minor', 'low', 'isolated', 'limited'],
    }
    
    CATEGORY_KEYWORDS = {
        'POLITICAL': ['protest', 'demonstration', 'unrest', 'riot', 'political', 'strike'],
        'WEATHER': ['storm', 'hurricane', 'tornado', 'flood', 'snow', 'ice', 'weather'],
        'CYBER': ['breach', 'hack', 'ransomware', 'cyber attack', 'phishing', 'malware'],
        'TERRORISM': ['terrorism', 'attack', 'bombing', 'threat', 'suspicious package'],
        'CRIME': ['robbery', 'theft', 'burglary', 'crime wave', 'shooting'],
        'INFRASTRUCTURE': ['power outage', 'gas leak', 'water main', 'road closure'],
        'HEALTH': ['outbreak', 'pandemic', 'epidemic', 'health emergency', 'quarantine'],
    }
    
    @classmethod
    def classify_event(cls, title: str, description: str, raw_content: str) -> Tuple[str, str, float]:
        """
        Classify threat category and severity from text.
        
        Returns:
            (category, severity, confidence_score)
        """
        text = f"{title} {description} {raw_content}".lower()
        
        category = cls._classify_category(text)
        severity = cls._classify_severity(text)
        confidence = cls._calculate_confidence(text, category, severity)
        
        return category, severity, confidence
    
    @classmethod
    def _classify_category(cls, text: str) -> str:
        """Classify threat category using keyword matching."""
        scores = {}
        for category, keywords in cls.CATEGORY_KEYWORDS.items():
            score = sum(1 for keyword in keywords if keyword in text)
            scores[category] = score
        
        if max(scores.values()) == 0:
            return 'OTHER'
        
        return max(scores, key=scores.get)
    
    @classmethod
    def _classify_severity(cls, text: str) -> str:
        """Classify severity using keyword matching."""
        for severity, keywords in cls.SEVERITY_KEYWORDS.items():
            if any(keyword in text for keyword in keywords):
                return severity
        
        return 'INFO'
    
    @classmethod
    def _calculate_confidence(cls, text: str, category: str, severity: str) -> float:
        """Calculate confidence score based on keyword matches."""
        category_matches = sum(
            1 for keyword in cls.CATEGORY_KEYWORDS.get(category, [])
            if keyword in text
        )
        severity_matches = sum(
            1 for keyword in cls.SEVERITY_KEYWORDS.get(severity, [])
            if keyword in text
        )
        
        total_matches = category_matches + severity_matches
        max_possible = 5
        
        return min(0.3 + (total_matches / max_possible) * 0.7, 1.0)
    
    @classmethod
    def extract_entities(cls, text: str) -> Dict[str, List[str]]:
        """
        Extract named entities (locations, organizations, people).
        
        FUTURE: Replace with spaCy or transformer-based NER.
        """
        return {
            'locations': [],
            'organizations': [],
            'people': [],
        }
    
    @classmethod
    def extract_keywords(cls, text: str) -> List[str]:
        """
        Extract relevant keywords/tags.
        
        FUTURE: Replace with TF-IDF or BERT-based extraction.
        """
        words = text.lower().split()
        stopwords = {'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for'}
        keywords = [w for w in words if w not in stopwords and len(w) > 3]
        return list(set(keywords))[:20]
    
    @classmethod
    def calculate_impact_radius(cls, category: str, severity: str) -> float:
        """
        Estimate impact radius in kilometers.
        
        FUTURE: ML model based on historical event data.
        """
        base_radius = {
            'POLITICAL': 2.0,
            'WEATHER': 50.0,
            'CYBER': 0.0,
            'TERRORISM': 5.0,
            'CRIME': 1.0,
            'INFRASTRUCTURE': 10.0,
            'HEALTH': 20.0,
            'OTHER': 5.0,
        }
        
        severity_multiplier = {
            'CRITICAL': 3.0,
            'HIGH': 2.0,
            'MEDIUM': 1.5,
            'LOW': 1.0,
            'INFO': 0.5,
        }
        
        return base_radius[category] * severity_multiplier.get(severity, 1.0)
