"""
AI Services for Intelligent Report Generation

Core services:
- SocraticQuestioningService: AI-guided questioning using multiple frameworks
- QualityGateService: Report validation and quality scoring
- ContextAutoPopulationService: Auto-fill from system data
- ReportLearningService: Pattern recognition and continuous improvement
- NarrativeAnalysisService: Text quality and clarity analysis
"""

from apps.report_generation.services.socratic_questioning_service import SocraticQuestioningService
from apps.report_generation.services.quality_gate_service import QualityGateService
from apps.report_generation.services.context_auto_population_service import ContextAutoPopulationService
from apps.report_generation.services.report_learning_service import ReportLearningService
from apps.report_generation.services.narrative_analysis_service import NarrativeAnalysisService

__all__ = [
    'SocraticQuestioningService',
    'QualityGateService',
    'ContextAutoPopulationService',
    'ReportLearningService',
    'NarrativeAnalysisService',
]
