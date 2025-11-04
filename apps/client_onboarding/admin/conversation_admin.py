"""
Conversation Admin Module

Admin interfaces for AI-powered conversational onboarding sessions and LLM recommendations.

Migrated from apps/onboarding/admin.py
Date: 2025-09-30
"""
from .base import *


@admin.register(om.ConversationSession)
class ConversationSessionAdmin(admin.ModelAdmin):
    """Django admin for ConversationSession model with progress tracking and export functionality"""
    list_display = ('session_id', 'user', 'client', 'current_state', 'conversation_type', 'progress_percentage', 'cdtz', 'mdtz')
    list_filter = ('current_state', 'conversation_type', 'language', 'cdtz')
    search_fields = ('session_id', 'user__email', 'client__buname', 'client__bucode')
    readonly_fields = ('session_id', 'cdtz', 'mdtz', 'cuser', 'muser', 'pretty_context_data', 'pretty_collected_data')
    date_hierarchy = 'cdtz'
    actions = ['export_session_data', 'mark_as_completed', 'cancel_sessions']

    fieldsets = (
        ('Basic Information', {
            'fields': ('session_id', 'user', 'client', 'current_state', 'conversation_type', 'language')
        }),
        ('Data', {
            'fields': ('context_data', 'collected_data', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('cdtz', 'mdtz', 'cuser', 'muser'),
            'classes': ('collapse',)
        })
    )

    def progress_percentage(self, obj):
        """Calculate and display progress percentage"""
        import logging
        logger = logging.getLogger(__name__)

        try:
            from apps.onboarding_api.views import ConversationStatusView
            view = ConversationStatusView()
            return f"{view._calculate_progress(obj) * 100:.1f}%"
        except (ImportError, ModuleNotFoundError) as e:
            logger.warning(f"Cannot import ConversationStatusView for progress calculation: {e}")
            return "N/A"
        except AttributeError as e:
            logger.warning(f"Progress calculation method not available: {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error calculating progress for {obj}: {e}")
            return "N/A"
    progress_percentage.short_description = "Progress"

    def pretty_context_data(self, obj):
        """Pretty display of context data JSON"""
        import json
        import logging
        from django.utils.html import format_html

        logger = logging.getLogger(__name__)

        try:
            pretty_json = json.dumps(obj.context_data, indent=2)
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', pretty_json)
        except (TypeError, ValueError) as e:
            logger.info(f"JSON serialization failed for context data (obj={obj}): {e}")
            return str(obj.context_data)
        except AttributeError as e:
            logger.warning(f"Object missing context_data attribute (obj={obj}): {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error formatting context data for {obj}: {e}")
            return str(obj.context_data)
    pretty_context_data.short_description = "Context Data (Pretty)"

    def pretty_collected_data(self, obj):
        """Pretty display of collected data JSON"""
        import json
        import logging
        from django.utils.html import format_html

        logger = logging.getLogger(__name__)

        try:
            pretty_json = json.dumps(obj.collected_data, indent=2)
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', pretty_json)
        except (TypeError, ValueError) as e:
            logger.info(f"JSON serialization failed for collected data (obj={obj}): {e}")
            return str(obj.collected_data)
        except AttributeError as e:
            logger.warning(f"Object missing collected_data attribute (obj={obj}): {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error formatting collected data for {obj}: {e}")
            return str(obj.collected_data)
    pretty_collected_data.short_description = "Collected Data (Pretty)"

    def export_session_data(self, request, queryset):
        """Export session data to JSON"""
        import json
        from django.http import HttpResponse

        sessions_data = []
        for session in queryset:
            sessions_data.append({
                'session_id': str(session.session_id),
                'user': session.user.email,
                'client': session.client.buname,
                'state': session.current_state,
                'type': session.conversation_type,
                'context_data': session.context_data,
                'collected_data': session.collected_data,
                'created': session.cdtz.isoformat(),
                'modified': session.mdtz.isoformat()
            })

        response = HttpResponse(
            json.dumps(sessions_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="conversation_sessions.json"'
        return response
    export_session_data.short_description = "Export selected sessions to JSON"

    def mark_as_completed(self, request, queryset):
        """Mark sessions as completed"""
        updated = queryset.update(
            current_state=om.ConversationSession.StateChoices.COMPLETED
        )
        self.message_user(request, f"Marked {updated} session(s) as completed.")
    mark_as_completed.short_description = "Mark selected sessions as completed"

    def cancel_sessions(self, request, queryset):
        """Cancel selected sessions"""
        updated = queryset.update(
            current_state=om.ConversationSession.StateChoices.CANCELLED
        )
        self.message_user(request, f"Cancelled {updated} session(s).")
    cancel_sessions.short_description = "Cancel selected sessions"


@admin.register(om.LLMRecommendation)
class LLMRecommendationAdmin(admin.ModelAdmin):
    """Django admin for LLMRecommendation model with approval workflows and export functionality"""
    list_display = ('recommendation_id', 'session', 'status', 'user_decision', 'confidence_score', 'cdtz')
    list_filter = ('status', 'user_decision', 'confidence_score', 'cdtz')
    search_fields = ('recommendation_id', 'session__session_id', 'trace_id')
    readonly_fields = ('recommendation_id', 'cdtz', 'mdtz', 'cuser', 'muser', 'pretty_consensus', 'pretty_maker_output', 'pretty_checker_output')
    date_hierarchy = 'cdtz'
    actions = ['approve_recommendations', 'reject_recommendations', 'export_recommendations']

    fieldsets = (
        ('Basic Information', {
            'fields': ('recommendation_id', 'session', 'status', 'user_decision')
        }),
        ('AI Output', {
            'fields': ('maker_output', 'checker_output', 'consensus', 'confidence_score', 'authoritative_sources')
        }),
        ('Performance Metrics', {
            'fields': ('latency_ms', 'provider_cost_cents', 'eval_scores', 'trace_id')
        }),
        ('User Feedback', {
            'fields': ('rejection_reason', 'modifications')
        }),
        ('Timestamps', {
            'fields': ('cdtz', 'mdtz', 'cuser', 'muser'),
            'classes': ('collapse',)
        })
    )

    def pretty_consensus(self, obj):
        """Pretty display of consensus JSON"""
        import json
        import logging
        from django.utils.html import format_html

        logger = logging.getLogger(__name__)

        try:
            pretty_json = json.dumps(obj.consensus, indent=2)
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', pretty_json)
        except (TypeError, ValueError) as e:
            logger.info(f"JSON serialization failed for consensus (obj={obj}): {e}")
            return str(obj.consensus)
        except AttributeError as e:
            logger.warning(f"Object missing consensus attribute (obj={obj}): {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error formatting consensus for {obj}: {e}")
            return str(obj.consensus)
    pretty_consensus.short_description = "Consensus (Pretty)"

    def pretty_maker_output(self, obj):
        """Pretty display of maker output JSON"""
        import json
        import logging
        from django.utils.html import format_html

        logger = logging.getLogger(__name__)

        try:
            pretty_json = json.dumps(obj.maker_output, indent=2)
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', pretty_json)
        except (TypeError, ValueError) as e:
            logger.info(f"JSON serialization failed for maker output (obj={obj}): {e}")
            return str(obj.maker_output)
        except AttributeError as e:
            logger.warning(f"Object missing maker_output attribute (obj={obj}): {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error formatting maker output for {obj}: {e}")
            return str(obj.maker_output)
    pretty_maker_output.short_description = "Maker Output (Pretty)"

    def pretty_checker_output(self, obj):
        """Pretty display of checker output JSON"""
        import json
        import logging
        from django.utils.html import format_html

        logger = logging.getLogger(__name__)

        try:
            pretty_json = json.dumps(obj.checker_output, indent=2)
            return format_html('<pre style="white-space: pre-wrap;">{}</pre>', pretty_json)
        except (TypeError, ValueError) as e:
            logger.info(f"JSON serialization failed for checker output (obj={obj}): {e}")
            return str(obj.checker_output)
        except AttributeError as e:
            logger.warning(f"Object missing checker_output attribute (obj={obj}): {e}")
            return "N/A"
        except Exception as e:
            logger.exception(f"Unexpected error formatting checker output for {obj}: {e}")
            return str(obj.checker_output)
    pretty_checker_output.short_description = "Checker Output (Pretty)"

    def approve_recommendations(self, request, queryset):
        """Approve selected recommendations"""
        updated = queryset.update(
            user_decision=om.LLMRecommendation.UserDecisionChoices.APPROVED
        )
        self.message_user(request, f"Approved {updated} recommendation(s).")
    approve_recommendations.short_description = "Approve selected recommendations"

    def reject_recommendations(self, request, queryset):
        """Reject selected recommendations"""
        updated = queryset.update(
            user_decision=om.LLMRecommendation.UserDecisionChoices.REJECTED
        )
        self.message_user(request, f"Rejected {updated} recommendation(s).")
    reject_recommendations.short_description = "Reject selected recommendations"

    def export_recommendations(self, request, queryset):
        """Export recommendations to JSON"""
        import json
        from django.http import HttpResponse

        recommendations_data = []
        for rec in queryset:
            recommendations_data.append({
                'recommendation_id': str(rec.recommendation_id),
                'session_id': str(rec.session.session_id),
                'status': rec.status,
                'user_decision': rec.user_decision,
                'confidence_score': rec.confidence_score,
                'consensus': rec.consensus,
                'trace_id': rec.trace_id,
                'created': rec.cdtz.isoformat()
            })

        response = HttpResponse(
            json.dumps(recommendations_data, indent=2),
            content_type='application/json'
        )
        response['Content-Disposition'] = 'attachment; filename="llm_recommendations.json"'
        return response
    export_recommendations.short_description = "Export selected recommendations to JSON"
