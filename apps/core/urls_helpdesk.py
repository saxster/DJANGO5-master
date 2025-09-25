"""
Consolidated URL configuration for Help Desk domain
Combines y_helpdesk app functionality
"""
from django.urls import path
from apps.y_helpdesk import views as helpdesk_views

app_name = 'help_desk'  # Changed to avoid namespace conflict

urlpatterns = [
    # ========== TICKETS ==========
    path('tickets/', helpdesk_views.TicketView.as_view(), name='tickets_list'),
    path('ticket/', helpdesk_views.TicketView.as_view(), name='ticket'),  # Legacy singular form
    
    # ========== ESCALATIONS ==========
    path('escalations/', helpdesk_views.EscalationMatrixView.as_view(), name='escalations_list'),
    path('escalationmatrix/', helpdesk_views.EscalationMatrixView.as_view(), name='escalationmatrix'),  # Legacy name
    
    # ========== POSTING ORDERS ==========
    path('posting-orders/', helpdesk_views.PostingOrderView.as_view(), name='posting_orders_list'),
    path('postingorder/', helpdesk_views.PostingOrderView.as_view(), name='postingorder'),  # Legacy name
    
    # ========== UNIFORMS ==========
    path('uniforms/', helpdesk_views.UniformView.as_view(), name='uniforms_list'),
    path('uniform/', helpdesk_views.UniformView.as_view(), name='uniform'),  # Legacy name
]