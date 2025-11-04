"""
WebSocket Consumer for Help Center AI Chat.

Provides real-time AI assistant chat with streaming responses.

WebSocket Route:
- /ws/help-center/chat/<session_id>/

Features:
- Async WebSocket handling
- Stream AIAssistantService responses in real-time
- Session management with conversation history
- Error handling with graceful degradation

Following CLAUDE.md:
- Rule #11: Specific exception handling
- Async best practices with Channels
"""

import json
import uuid
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.core.exceptions import ObjectDoesNotExist
from apps.help_center.services.ai_assistant_service import AIAssistantService

logger = logging.getLogger(__name__)


class HelpChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for AI-powered help chat.

    Connection URL: /ws/help-center/chat/<session_id>/

    Messages:
    - Client → Server: {"query": "How do I create a work order?", "current_url": "/work-orders/"}
    - Server → Client: {"type": "chunk", "content": "...", "metadata": {...}}
    """

    async def connect(self):
        """Accept WebSocket connection and initialize session."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.user = self.scope['user']

        if not self.user.is_authenticated:
            await self.close(code=4001)
            return

        await self.accept()

        logger.info(
            "help_chat_connected",
            extra={'session_id': str(self.session_id), 'user': self.user.username}
        )

        await self.send(text_data=json.dumps({
            'type': 'connection',
            'content': 'Connected to help assistant',
            'session_id': str(self.session_id)
        }))

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        logger.info(
            "help_chat_disconnected",
            extra={'session_id': str(self.session_id), 'close_code': close_code}
        )

    async def receive(self, text_data):
        """
        Receive message from client and stream AI response.

        Client message format:
        {
            "query": "How do I approve a work order?",
            "current_url": "/work-orders/123/"
        }
        """
        try:
            data = json.loads(text_data)
            query = data.get('query', '').strip()
            current_url = data.get('current_url', '')

            if not query:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'content': 'Query cannot be empty'
                }))
                return

            if len(query) < 2:
                await self.send(text_data=json.dumps({
                    'type': 'error',
                    'content': 'Query must be at least 2 characters'
                }))
                return

            tenant = await database_sync_to_async(lambda: self.user.tenant)()

            async for response_chunk in AIAssistantService.generate_response_stream(
                tenant=tenant,
                user=self.user,
                query=query,
                session_id=uuid.UUID(self.session_id),
                current_url=current_url
            ):
                await self.send(text_data=json.dumps(response_chunk))

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON received: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'content': 'Invalid message format'
            }))

        except ValueError as e:
            logger.error(f"Invalid session_id: {e}")
            await self.send(text_data=json.dumps({
                'type': 'error',
                'content': 'Invalid session ID'
            }))

        except Exception as e:
            logger.error(f"Help chat error: {e}", exc_info=True)
            await self.send(text_data=json.dumps({
                'type': 'error',
                'content': 'An error occurred. Please try again or contact support.'
            }))
