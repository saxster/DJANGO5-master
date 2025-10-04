"""
Push Subscription Models

Manages per-device push subscriptions for selective notifications.

Follows .claude/rules.md:
- Rule #7: Model < 150 lines
"""

from django.db import models
from django.utils import timezone


class PushSubscription(models.Model):
    """
    Per-device push subscription configuration.

    Tracks which domains each device wants to receive push notifications for.
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        related_name='push_subscriptions'
    )

    device_id = models.CharField(
        max_length=255,
        db_index=True,
        help_text="Unique device identifier"
    )

    domain = models.CharField(
        max_length=50,
        choices=[
            ('journal', 'Journal Entries'),
            ('attendance', 'Attendance Records'),
            ('task', 'Tasks'),
            ('ticket', 'Help Desk Tickets'),
            ('work_order', 'Work Orders'),
            ('all', 'All Domains'),
        ],
        help_text="Data domain for subscription"
    )

    active = models.BooleanField(
        default=True,
        help_text="Subscription active status"
    )

    battery_saver_mode = models.BooleanField(
        default=False,
        help_text="Reduce push frequency for battery saving"
    )

    priority_filter = models.CharField(
        max_length=20,
        choices=[
            ('all', 'All Priorities'),
            ('high', 'High Priority Only'),
            ('critical', 'Critical Only'),
        ],
        default='all',
        help_text="Priority level filter"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'push_subscription'
        unique_together = [('user', 'device_id', 'domain')]
        indexes = [
            models.Index(fields=['user', 'device_id']),
            models.Index(fields=['active']),
        ]
        verbose_name = 'Push Subscription'
        verbose_name_plural = 'Push Subscriptions'

    def __str__(self):
        return f"{self.device_id} - {self.domain} ({'active' if self.active else 'inactive'})"


class PushDeliveryLog(models.Model):
    """
    Log of push notification deliveries for monitoring.

    Tracks success/failure of push notifications.
    """

    user = models.ForeignKey(
        'peoples.People',
        on_delete=models.CASCADE,
        null=True,
        related_name='push_delivery_logs'
    )

    device_id = models.CharField(max_length=255, db_index=True)

    push_type = models.CharField(
        max_length=50,
        choices=[
            ('data_update', 'Data Update'),
            ('sync_trigger', 'Sync Trigger'),
            ('conflict_alert', 'Conflict Alert'),
            ('system_notification', 'System Notification'),
        ]
    )

    domain = models.CharField(max_length=50, null=True, blank=True)

    delivered = models.BooleanField(default=False)

    delivery_latency_ms = models.IntegerField(
        null=True,
        blank=True,
        help_text="Time to deliver in milliseconds"
    )

    error_message = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'push_delivery_log'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['device_id', 'created_at']),
            models.Index(fields=['delivered']),
        ]
        verbose_name = 'Push Delivery Log'
        verbose_name_plural = 'Push Delivery Logs'

    def __str__(self):
        status = 'delivered' if self.delivered else 'failed'
        return f"{self.device_id} - {self.push_type} ({status})"