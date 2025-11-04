"""
Alert manager for sending notifications based on monitoring thresholds.
"""

import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Any, Optional
import requests
from threading import Thread
from collections import defaultdict

from django.conf import settings
from django.core.cache import cache
from django.template.loader import render_to_string
from django.utils import timezone

from .config import monitoring_config, AlertRule
from .django_monitoring import metrics_collector

logger = logging.getLogger('monitoring.alerts')


class AlertManager:
    """Manages alert generation and notification delivery"""
    
    def __init__(self):
        self.alert_history = defaultdict(list)
        self.alert_cooldown = {}  # Prevent alert spam
        self.cooldown_period = 300  # 5 minutes
    
    def check_alerts(self) -> List[Dict[str, Any]]:
        """Check all alert rules and return triggered alerts"""
        triggered_alerts = []
        
        for rule in monitoring_config.ALERT_RULES:
            if self._is_alert_triggered(rule):
                alert = self._create_alert(rule)
                if self._should_send_alert(alert):
                    triggered_alerts.append(alert)
                    self._record_alert(alert)
        
        return triggered_alerts
    
    def _is_alert_triggered(self, rule: AlertRule) -> bool:
        """Check if an alert rule is triggered"""
        try:
            # Get metric value
            metric_value = self._get_metric_value(rule.metric, rule.window_minutes)
            
            if metric_value is None:
                return False
            
            # Check condition
            if rule.condition == 'gt':
                return metric_value > rule.threshold
            elif rule.condition == 'lt':
                return metric_value < rule.threshold
            elif rule.condition == 'eq':
                return metric_value == rule.threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking alert rule {rule.name}: {e}")
            return False
    
    def _get_metric_value(self, metric: str, window_minutes: int) -> Optional[float]:
        """Get metric value for alert checking"""
        if metric == 'response_time_p95':
            stats = metrics_collector.get_stats('response_time', window_minutes)
            return stats.get('p95')
        
        elif metric == 'response_time_p99':
            stats = metrics_collector.get_stats('response_time', window_minutes)
            return stats.get('p99')
        
        elif metric == 'error_rate':
            requests = metrics_collector.get_stats('request', window_minutes).get('count', 0)
            errors = metrics_collector.get_stats('error', window_minutes).get('count', 0)
            return (errors / requests) if requests > 0 else 0
        
        elif metric == 'cache_hit_rate':
            hits = metrics_collector.get_stats('cache_hit', window_minutes).get('count', 0)
            misses = metrics_collector.get_stats('cache_miss', window_minutes).get('count', 0)
            total = hits + misses
            return (hits / total) if total > 0 else 1.0
        
        elif metric == 'queries_per_request_p95':
            stats = metrics_collector.get_stats('query_count', window_minutes)
            return stats.get('p95')
        
        elif metric == 'query_time_p95':
            stats = metrics_collector.get_stats('query_time', window_minutes)
            return stats.get('p95')
        
        elif metric == 'db_connection_errors':
            return metrics_collector.get_stats('db_connection_error', window_minutes).get('count', 0)
        
        return None
    
    def _create_alert(self, rule: AlertRule) -> Dict[str, Any]:
        """Create alert dictionary from triggered rule"""
        return {
            'id': f"{rule.name}_{int(timezone.now().timestamp())}",
            'name': rule.name,
            'severity': rule.severity,
            'description': rule.description,
            'action': rule.action,
            'metric': rule.metric,
            'threshold': rule.threshold,
            'current_value': self._get_metric_value(rule.metric, rule.window_minutes),
            'timestamp': timezone.now().isoformat(),
            'rule': rule
        }
    
    def _should_send_alert(self, alert: Dict[str, Any]) -> bool:
        """Check if alert should be sent (cooldown logic)"""
        alert_key = alert['name']
        
        # Check cooldown
        last_sent = self.alert_cooldown.get(alert_key)
        if last_sent:
            if timezone.now() - last_sent < timedelta(seconds=self.cooldown_period):
                return False
        
        # Update cooldown
        self.alert_cooldown[alert_key] = timezone.now()
        return True
    
    def _record_alert(self, alert: Dict[str, Any]):
        """Record alert in history"""
        self.alert_history[alert['name']].append({
            'timestamp': alert['timestamp'],
            'value': alert['current_value'],
            'severity': alert['severity']
        })
        
        # Keep only last 100 alerts per type
        if len(self.alert_history[alert['name']]) > 100:
            self.alert_history[alert['name']] = self.alert_history[alert['name']][-100:]
    
    def send_notifications(self, alerts: List[Dict[str, Any]]):
        """Send notifications for triggered alerts"""
        if not alerts:
            return
        
        # Group alerts by severity
        alerts_by_severity = defaultdict(list)
        for alert in alerts:
            alerts_by_severity[alert['severity']].append(alert)
        
        # Send to each enabled channel
        channels = monitoring_config.NOTIFICATION_CHANNELS
        
        if channels['email']['enabled']:
            Thread(target=self._send_email_alerts, args=(alerts_by_severity,)).start()
        
        if channels['slack']['enabled']:
            Thread(target=self._send_slack_alerts, args=(alerts_by_severity,)).start()
        
        if channels['pagerduty']['enabled']:
            Thread(target=self._send_pagerduty_alerts, args=(alerts_by_severity,)).start()
    
    def _send_email_alerts(self, alerts_by_severity: Dict[str, List]):
        """Send email notifications"""
        try:
            config = monitoring_config.NOTIFICATION_CHANNELS['email']
            
            # Prepare email content
            subject = f"[{settings.SITE_NAME}] Monitoring Alert - {len(sum(alerts_by_severity.values(), []))} alerts"
            
            # Create HTML content
            html_content = self._create_email_html(alerts_by_severity)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = config['from_address']
            msg['To'] = ', '.join(config['recipients'])
            
            msg.attach(MIMEText(html_content, 'html'))
            
            # Send email
            with smtplib.SMTP(config['smtp_host'], config['smtp_port']) as server:
                server.send_message(msg)
            
            logger.info(f"Sent email alert to {len(config['recipients'])} recipients")
            
        except Exception as e:
            logger.error(f"Failed to send email alerts: {e}")
    
    def _create_email_html(self, alerts_by_severity: Dict[str, List]) -> str:
        """Create HTML content for email alerts"""
        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .alert { margin: 10px 0; padding: 10px; border-radius: 5px; }
                .critical { background-color: #f8d7da; border: 1px solid #f5c6cb; }
                .warning { background-color: #fff3cd; border: 1px solid #ffeaa7; }
                .info { background-color: #d1ecf1; border: 1px solid #bee5eb; }
                .metric { font-family: monospace; background-color: #f8f9fa; padding: 2px 4px; }
            </style>
        </head>
        <body>
            <h2>Monitoring Alerts</h2>
        """
        
        for severity in ['critical', 'warning', 'info']:
            alerts = alerts_by_severity.get(severity, [])
            if alerts:
                html += f"<h3>{severity.upper()} Alerts ({len(alerts)})</h3>"
                for alert in alerts:
                    html += f"""
                    <div class="alert {severity}">
                        <strong>{alert['description']}</strong><br>
                        Metric: <span class="metric">{alert['metric']}</span><br>
                        Current Value: <span class="metric">{alert['current_value']:.3f}</span> 
                        (threshold: {alert['threshold']})<br>
                        Action: {alert['action']}<br>
                        Time: {alert['timestamp']}
                    </div>
                    """
        
        html += """
            <hr>
            <p><small>This is an automated alert from the monitoring system.</small></p>
        </body>
        </html>
        """
        
        return html
    
    def _send_slack_alerts(self, alerts_by_severity: Dict[str, List]):
        """Send Slack notifications"""
        try:
            config = monitoring_config.NOTIFICATION_CHANNELS['slack']
            
            # Create Slack message blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 Monitoring Alerts - {settings.SITE_NAME}"
                    }
                }
            ]
            
            # Add alerts by severity
            severity_emojis = {
                'critical': '🔴',
                'warning': '🟡',
                'info': 'ℹ️'
            }
            
            for severity in ['critical', 'warning', 'info']:
                alerts = alerts_by_severity.get(severity, [])
                if alerts:
                    blocks.append({
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{severity_emojis[severity]} {severity.upper()} ({len(alerts)})*"
                        }
                    })
                    
                    for alert in alerts[:3]:  # Show max 3 per severity
                        blocks.append({
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"• *{alert['description']}*\n"
                                       f"  Metric: `{alert['metric']}` = {alert['current_value']:.3f} "
                                       f"(threshold: {alert['threshold']})"
                            }
                        })
            
            # Send to Slack
            response = requests.post(
                config['webhook_url'],
                json={
                    'channel': config['channel'],
                    'username': config['username'],
                    'blocks': blocks
                }
            )
            
            if response.status_code == 200:
                logger.info("Sent Slack alert successfully")
            else:
                logger.error(f"Failed to send Slack alert: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Failed to send Slack alerts: {e}")
    
    def _send_pagerduty_alerts(self, alerts_by_severity: Dict[str, List]):
        """Send PagerDuty alerts for critical issues"""
        try:
            config = monitoring_config.NOTIFICATION_CHANNELS['pagerduty']
            
            # Only send critical alerts to PagerDuty
            critical_alerts = alerts_by_severity.get('critical', [])
            if not critical_alerts:
                return
            
            for alert in critical_alerts:
                payload = {
                    'routing_key': config['integration_key'],
                    'event_action': 'trigger',
                    'dedup_key': alert['name'],
                    'payload': {
                        'summary': alert['description'],
                        'severity': config['severity_mapping'][alert['severity']],
                        'source': settings.SITE_NAME,
                        'custom_details': {
                            'metric': alert['metric'],
                            'current_value': alert['current_value'],
                            'threshold': alert['threshold'],
                            'action': alert['action']
                        }
                    }
                }
                
                response = requests.post(
                    'https://events.pagerduty.com/v2/enqueue',
                    json=payload
                )
                
                if response.status_code == 202:
                    logger.info(f"Sent PagerDuty alert for {alert['name']}")
                else:
                    logger.error(f"Failed to send PagerDuty alert: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Failed to send PagerDuty alerts: {e}")
    
    def get_alert_history(self, alert_name: Optional[str] = None) -> Dict[str, List]:
        """Get alert history"""
        if alert_name:
            return {alert_name: self.alert_history.get(alert_name, [])}
        return dict(self.alert_history)


# Global alert manager instance
alert_manager = AlertManager()


def check_and_send_alerts():
    """Check alerts and send notifications (called by scheduler)"""
    try:
        # Check all alert rules
        triggered_alerts = alert_manager.check_alerts()
        
        if triggered_alerts:
            logger.info(f"Triggered {len(triggered_alerts)} alerts")
            
            # Send notifications
            alert_manager.send_notifications(triggered_alerts)
            
            # Store in cache for dashboard
            cache.set('latest_alerts', triggered_alerts, 300)  # 5 minutes
        
        return triggered_alerts
        
    except Exception as e:
        logger.error(f"Error in alert checking: {e}")
        return []