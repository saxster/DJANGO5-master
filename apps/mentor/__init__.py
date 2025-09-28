"""
AI Mentor System for Django Projects

An intelligent development assistant that provides automated impact analysis,
patch generation, and targeted testing for Django applications.

This app is designed to operate only in development/CI environments and should
never be enabled in production.
"""

default_app_config = 'apps.mentor.apps.MentorConfig'