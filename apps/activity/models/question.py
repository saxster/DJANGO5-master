"""
Question Model Shim
===================

Phase 6 split the original god file into ``question_model.py`` but many legacy
imports still reference ``apps.activity.models.question``. This module simply
re-exports the real models to keep both paths working.
"""

from .question_model import Question, QuestionSet, QuestionSetBelonging

__all__ = ['Question', 'QuestionSet', 'QuestionSetBelonging']
