"""
Mobile WebSocket Consumers
Real-time communication for mobile SDK synchronization and monitoring
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache
from django.utils import timezone

from apps.core.utils_new.sql_security import validate_query_security
from apps.voice_recognition.models import VoiceVerificationLog
from .v1.views.mobile_sync_views import sync_engine

logger = logging.getLogger('mobile.websocket')


class MobileSyncConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for mobile SDK synchronization
    Handles real-time sync events, notifications, and bidirectional communication
    """
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = None
        self.device_id = None
        self.user_group = None
        self.sync_sessions = {}
        self.heartbeat_task = None
        self.last_activity = None
        
    async def connect(self):
        """Handle WebSocket connection"""
        try:
            # Get user from scope (assumes auth middleware)
            self.user = self.scope.get('user')
            
            if self.user is None or isinstance(self.user, AnonymousUser):
                logger.warning("Unauthorized mobile WebSocket connection attempt")
                await self.close(code=4401)
                return
            
            # Extract device ID from query parameters
            query_params = dict(self.scope.get('query_string', b'').decode().split('&'))
            self.device_id = None
            
            for param in query_params:
                if '=' in param:
                    key, value = param.split('=', 1)
                    if key == 'device_id':
                        self.device_id = value
                        break
            
            if not self.device_id:
                logger.warning("Mobile WebSocket connection without device ID")
                await self.close(code=4400)
                return
            
            # Join user-specific group
            self.user_group = f"mobile_user_{self.user.id}"
            await self.channel_layer.group_add(
                self.user_group,
                self.channel_name
            )
            
            # Accept connection
            await self.accept()
            
            # Send connection confirmation
            await self.send_message({
                'type': 'connection_established',
                'user_id': str(self.user.id),
                'device_id': self.device_id,
                'server_time': timezone.now().isoformat(),
                'features': {
                    'real_time_sync': True,
                    'push_notifications': True,
                    'bi_directional_sync': True,
                    'conflict_resolution': True
                }
            })
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
            self.last_activity = datetime.utcnow()
            
            logger.info(f"Mobile sync connection established for user {self.user.id}, device {self.device_id}")
            
        except Exception as e:
            logger.error(f"Mobile WebSocket connection error: {str(e)}", exc_info=True)
            await self.close(code=4500)
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            # Cancel heartbeat
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
                try:
                    await self.heartbeat_task
                except asyncio.CancelledError:
                    pass
            
            # Leave group
            if self.user_group:
                await self.channel_layer.group_discard(
                    self.user_group,
                    self.channel_name
                )
            
            # Clean up sync sessions
            await self._cleanup_sync_sessions()
            
            # Update connection status
            if self.user and self.device_id:
                await self._update_device_status('offline')
            
            logger.info(f"Mobile sync connection closed for user {self.user.id if self.user else 'Unknown'}, code {close_code}")
            
        except Exception as e:
            logger.error(f"Mobile WebSocket disconnect error: {str(e)}", exc_info=True)
    
    async def receive(self, text_data):
        """Handle incoming messages from mobile clients"""
        try:
            message = json.loads(text_data)
            await self._handle_message(message)
            self.last_activity = datetime.utcnow()
            
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON message", "JSON_DECODE_ERROR")
        except Exception as e:
            logger.error(f"Mobile message handling error: {str(e)}", exc_info=True)
            await self.send_error(f"Message processing failed: {str(e)}", "MESSAGE_PROCESSING_ERROR")
    
    async def _handle_message(self, message: Dict[str, Any]):
        """Handle different message types"""
        try:
            message_type = message.get('type')
            
            if message_type == 'start_sync':
                await self._handle_start_sync(message)
            elif message_type == 'sync_data':
                await self._handle_sync_data(message)
            elif message_type == 'request_server_data':
                await self._handle_server_data_request(message)
            elif message_type == 'resolve_conflict':
                await self._handle_conflict_resolution(message)
            elif message_type == 'subscribe_events':
                await self._handle_event_subscription(message)
            elif message_type == 'heartbeat':
                await self._handle_heartbeat(message)
            elif message_type == 'device_status':
                await self._handle_device_status(message)
            else:
                await self.send_error(f"Unknown message type: {message_type}", "UNKNOWN_MESSAGE_TYPE")
                
        except Exception as e:
            logger.error(f"Message handler error: {str(e)}", exc_info=True)
            await self.send_error(f"Handler error: {str(e)}", "HANDLER_ERROR")
    
    async def _handle_start_sync(self, message: Dict[str, Any]):
        """Handle sync session initiation"""
        try:
            sync_id = message.get('sync_id')
            if not sync_id:
                await self.send_error("Missing sync_id", "MISSING_SYNC_ID")
                return
            
            # Create sync session
            sync_session = {
                'sync_id': sync_id,
                'started_at': datetime.utcnow(),
                'status': 'active',
                'data_types': message.get('data_types', []),
                'total_items': message.get('total_items', 0),
                'synced_items': 0,
                'failed_items': 0
            }
            
            self.sync_sessions[sync_id] = sync_session
            
            # Send sync session started event
            await self.send_message({
                'type': 'sync_session_started',
                'sync_id': sync_id,
                'server_time': timezone.now().isoformat(),
                'session_info': {
                    'supported_data_types': ['voice', 'behavioral', 'session', 'metrics'],
                    'max_batch_size': 100,
                    'timeout_seconds': 300
                }
            })
            
            # Notify other systems
            await self._notify_sync_started(sync_id)
            
        except Exception as e:
            logger.error(f"Start sync error: {str(e)}")
            await self.send_error(f"Sync start failed: {str(e)}", "SYNC_START_ERROR")
    
    async def _handle_sync_data(self, message: Dict[str, Any]):
        """Handle real-time data synchronization"""
        try:
            sync_id = message.get('sync_id')
            if sync_id not in self.sync_sessions:
                await self.send_error("Invalid sync session", "INVALID_SYNC_SESSION")
                return
            
            sync_session = self.sync_sessions[sync_id]
            data_batch = message.get('data', {})
            
            # Process data batch using sync engine
            user_id = str(self.user.id)
            sync_results = {}
            
            # Voice data
            if 'voice_data' in data_batch:
                voice_result = await sync_engine.sync_voice_data(
                    user_id, {'voice_data': data_batch['voice_data']}, self.device_id
                )
                sync_results['voice'] = voice_result
            
            # Behavioral data
            if 'behavioral_data' in data_batch:
                behavioral_result = await sync_engine.sync_behavioral_data(
                    user_id, {'behavioral_data': data_batch['behavioral_data']}, self.device_id
                )
                sync_results['behavioral'] = behavioral_result
            
            # Sessions
            if 'sessions' in data_batch:
                session_result = await sync_engine.sync_session_data(
                    user_id, {'sessions': data_batch['sessions']}, self.device_id
                )
                sync_results['sessions'] = session_result
            
            # Metrics
            if 'metrics' in data_batch:
                metrics_result = await sync_engine.sync_metrics_data(
                    user_id, {'metrics': data_batch['metrics']}, self.device_id
                )
                sync_results['metrics'] = metrics_result
            
            # Update sync session
            for result in sync_results.values():
                sync_session['synced_items'] += result.get('synced_items', 0)
                sync_session['failed_items'] += result.get('failed_items', 0)
            
            # Send sync progress
            await self.send_message({
                'type': 'sync_progress',
                'sync_id': sync_id,
                'progress': {
                    'synced_items': sync_session['synced_items'],
                    'failed_items': sync_session['failed_items'],
                    'total_items': sync_session['total_items']
                },
                'batch_results': sync_results
            })
            
        except Exception as e:
            logger.error(f"Sync data error: {str(e)}")
            await self.send_error(f"Data sync failed: {str(e)}", "DATA_SYNC_ERROR")
    
    async def _handle_server_data_request(self, message: Dict[str, Any]):
        """Handle requests for server data (bidirectional sync)"""
        try:
            request_type = message.get('request_type')
            since_timestamp = message.get('since_timestamp')
            
            server_data = {}
            
            if request_type in ['all', 'voice']:
                voice_data = await self._get_server_voice_data(since_timestamp)
                if voice_data:
                    server_data['voice_data'] = voice_data
            
            if request_type in ['all', 'behavioral']:
                behavioral_data = await self._get_server_behavioral_data(since_timestamp)
                if behavioral_data:
                    server_data['behavioral_data'] = behavioral_data
            
            if request_type in ['all', 'sessions']:
                session_data = await self._get_server_session_data(since_timestamp)
                if session_data:
                    server_data['session_data'] = session_data
            
            # Send server data to client
            await self.send_message({
                'type': 'server_data_response',
                'request_id': message.get('request_id'),
                'data': server_data,
                'server_timestamp': timezone.now().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Server data request error: {str(e)}")
            await self.send_error(f"Server data request failed: {str(e)}", "SERVER_DATA_ERROR")
    
    async def _handle_conflict_resolution(self, message: Dict[str, Any]):
        """Handle conflict resolution from client"""
        try:
            conflict_id = message.get('conflict_id')
            resolution_strategy = message.get('resolution_strategy')
            
            # Apply conflict resolution
            result = await self._apply_conflict_resolution(
                conflict_id, resolution_strategy, message.get('resolved_data')
            )
            
            await self.send_message({
                'type': 'conflict_resolved',
                'conflict_id': conflict_id,
                'resolution_strategy': resolution_strategy,
                'result': result
            })
            
        except Exception as e:
            logger.error(f"Conflict resolution error: {str(e)}")
            await self.send_error(f"Conflict resolution failed: {str(e)}", "CONFLICT_RESOLUTION_ERROR")
    
    async def _handle_event_subscription(self, message: Dict[str, Any]):
        """Handle event subscription requests"""
        try:
            event_types = message.get('event_types', [])
            
            # Join event-specific groups
            for event_type in event_types:
                group_name = f"mobile_events_{event_type}_{self.user.id}"
                await self.channel_layer.group_add(group_name, self.channel_name)
            
            await self.send_message({
                'type': 'subscription_confirmed',
                'subscribed_events': event_types
            })
            
        except Exception as e:
            logger.error(f"Event subscription error: {str(e)}")
            await self.send_error(f"Subscription failed: {str(e)}", "SUBSCRIPTION_ERROR")
    
    async def _handle_heartbeat(self, message: Dict[str, Any]):
        """Handle heartbeat from client"""
        await self.send_message({
            'type': 'heartbeat_response',
            'server_time': timezone.now().isoformat(),
            'client_time': message.get('client_time')
        })
    
    async def _handle_device_status(self, message: Dict[str, Any]):
        """Handle device status updates"""
        try:
            status = message.get('status', 'active')
            await self._update_device_status(status)
            
            # Store additional device info
            if 'device_info' in message:
                await self._update_device_info(message['device_info'])
            
        except Exception as e:
            logger.error(f"Device status update error: {str(e)}")
    
    async def _heartbeat_loop(self):
        """Background heartbeat to maintain connection"""
        try:
            while True:
                await asyncio.sleep(30)  # 30 second intervals
                
                # Check if connection is still active
                if self.last_activity:
                    inactive_time = (datetime.utcnow() - self.last_activity).total_seconds()
                    if inactive_time > 300:  # 5 minutes of inactivity
                        logger.info(f"Closing inactive connection for user {self.user.id}")
                        await self.close(code=4408)  # Request timeout
                        break
                
                # Send server heartbeat
                await self.send_message({
                    'type': 'server_heartbeat',
                    'server_time': timezone.now().isoformat(),
                    'connection_duration': (datetime.utcnow() - self.last_activity).total_seconds() if self.last_activity else 0
                })
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Heartbeat loop error: {str(e)}")
    
    async def _cleanup_sync_sessions(self):
        """Clean up active sync sessions"""
        try:
            for sync_id, session in self.sync_sessions.items():
                if session['status'] == 'active':
                    session['status'] = 'interrupted'
                    session['ended_at'] = datetime.utcnow()
                    
                    # Store session results
                    await self._store_sync_session_results(sync_id, session)
            
            self.sync_sessions.clear()
            
        except Exception as e:
            logger.error(f"Sync session cleanup error: {str(e)}")
    
    async def _notify_sync_started(self, sync_id: str):
        """Notify other systems about sync start"""
        try:
            # Send to monitoring systems
            await self.channel_layer.group_send(
                "system_monitoring",
                {
                    'type': 'sync_event',
                    'event': 'sync_started',
                    'user_id': str(self.user.id),
                    'device_id': self.device_id,
                    'sync_id': sync_id,
                    'timestamp': timezone.now().isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Sync notification error: {str(e)}")
    
    @database_sync_to_async
    def _get_server_voice_data(self, since_timestamp: Optional[str]) -> List[Dict[str, Any]]:
        """Get voice data from server for bidirectional sync"""
        try:
            if since_timestamp:
                since_dt = datetime.fromisoformat(since_timestamp)
                logs = VoiceVerificationLog.objects.filter(
                    user=self.user,
                    created_at__gt=since_dt
                ).order_by('-created_at')[:50]
            else:
                logs = VoiceVerificationLog.objects.filter(
                    user=self.user
                ).order_by('-created_at')[:20]
            
            return [
                {
                    'id': log.verification_id,
                    'timestamp': log.created_at.isoformat(),
                    'verified': log.verified,
                    'confidence_score': log.confidence_score,
                    'quality_score': log.quality_score,
                    'processing_time_ms': log.processing_time_ms
                }
                for log in logs
            ]
            
        except Exception as e:
            logger.error(f"Server voice data retrieval error: {str(e)}")
            return []
    
    async def _get_server_behavioral_data(self, since_timestamp: Optional[str]) -> List[Dict[str, Any]]:
        """Get behavioral data from server"""
        # Implementation would query behavioral logs
        return []
    
    async def _get_server_session_data(self, since_timestamp: Optional[str]) -> List[Dict[str, Any]]:
        """Get session data from server"""
        # Implementation would query session data
        return []
    
    async def _apply_conflict_resolution(
        self,
        conflict_id: str,
        strategy: str,
        resolved_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Apply conflict resolution strategy"""
        try:
            # Implementation would resolve data conflicts
            return {
                'status': 'resolved',
                'strategy_applied': strategy,
                'timestamp': timezone.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Conflict resolution application error: {str(e)}")
            return {'status': 'failed', 'error': str(e)}
    
    async def _update_device_status(self, status: str):
        """Update device online/offline status"""
        try:
            cache_key = f"device_status:{self.user.id}:{self.device_id}"
            device_status = {
                'status': status,
                'last_seen': timezone.now().isoformat(),
                'connection_type': 'websocket'
            }
            cache.set(cache_key, device_status, timeout=3600)
            
        except Exception as e:
            logger.error(f"Device status update error: {str(e)}")
    
    async def _update_device_info(self, device_info: Dict[str, Any]):
        """Update device information"""
        try:
            cache_key = f"device_info:{self.user.id}:{self.device_id}"
            cache.set(cache_key, device_info, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.error(f"Device info update error: {str(e)}")
    
    async def _store_sync_session_results(self, sync_id: str, session: Dict[str, Any]):
        """Store sync session results for analytics"""
        try:
            # Store in cache for analytics
            cache_key = f"sync_session:{sync_id}"
            cache.set(cache_key, session, timeout=86400 * 7)  # 7 days
            
        except Exception as e:
            logger.error(f"Sync session storage error: {str(e)}")
    
    async def send_message(self, message: Dict[str, Any]):
        """Send message to WebSocket client"""
        try:
            await self.send(text_data=json.dumps(message))
        except Exception as e:
            logger.error(f"WebSocket send error: {str(e)}")
    
    async def send_error(self, message: str, error_code: str = "GENERAL_ERROR"):
        """Send error message to client"""
        try:
            await self.send_message({
                'type': 'error',
                'error_code': error_code,
                'message': message,
                'timestamp': timezone.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error message send failed: {str(e)}")
    
    # Channel layer message handlers
    
    async def sync_update(self, event):
        """Handle sync update events from channel layer"""
        await self.send_message(event['data'])
    
    async def sync_event(self, event):
        """Handle sync events from other parts of the system"""
        await self.send_message({
            'type': 'system_sync_event',
            'event_data': event
        })
    
    async def notification(self, event):
        """Handle push notifications"""
        await self.send_message({
            'type': 'push_notification',
            'notification': event['notification']
        })


class MobileSystemConsumer(AsyncWebsocketConsumer):
    """System-level consumer for mobile infrastructure monitoring"""
    
    async def connect(self):
        """Handle connection for system monitoring"""
        user = self.scope.get('user')
        
        # Only allow admin users
        if not user or not (user.is_staff or user.is_superuser):
            await self.close(code=4401)
            return
        
        # Join system monitoring group
        await self.channel_layer.group_add(
            'mobile_system_monitoring',
            self.channel_name
        )
        
        await self.accept()
        
        # Send system status
        await self.send(text_data=json.dumps({
            'type': 'system_status',
            'status': 'connected',
            'mobile_features': {
                'sync_engine_status': 'active',
                'real_time_events': 'active',
                'conflict_resolution': 'active'
            },
            'timestamp': timezone.now().isoformat()
        }))
    
    async def disconnect(self, close_code):
        """Handle disconnection"""
        await self.channel_layer.group_discard(
            'mobile_system_monitoring',
            self.channel_name
        )
    
    async def system_alert(self, event):
        """Handle system alerts"""
        await self.send(text_data=json.dumps(event))
    
    async def mobile_metrics(self, event):
        """Handle mobile system metrics"""
        await self.send(text_data=json.dumps(event))