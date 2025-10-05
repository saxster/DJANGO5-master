#!/usr/bin/env python
"""
Generate JSON Schema for WebSocket Messages

Creates JSON Schema from Pydantic models for Kotlin/Swift codegen.
Output: docs/api-contracts/websocket-messages.json

Usage:
    python scripts/generate_websocket_schema.py

For Kotlin codegen:
    Use kotlinx-serialization or Moshi with the generated schema
"""

import json
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'intelliwiz_config.settings.development')
import django
django.setup()

from apps.api.websocket_messages import (
    ConnectionEstablishedMessage,
    HeartbeatMessage,
    SyncStartMessage,
    SyncDataMessage,
    SyncCompleteMessage,
    ServerDataRequestMessage,
    ServerDataMessage,
    ConflictNotificationMessage,
    ConflictResolutionMessage,
    SyncStatusMessage,
    ErrorMessage,
)


def generate_json_schema():
    """Generate comprehensive JSON Schema for all WebSocket messages."""

    # All message types
    message_types = [
        ('ConnectionEstablished', ConnectionEstablishedMessage),
        ('Heartbeat', HeartbeatMessage),
        ('SyncStart', SyncStartMessage),
        ('SyncData', SyncDataMessage),
        ('SyncComplete', SyncCompleteMessage),
        ('ServerDataRequest', ServerDataRequestMessage),
        ('ServerData', ServerDataMessage),
        ('ConflictNotification', ConflictNotificationMessage),
        ('ConflictResolution', ConflictResolutionMessage),
        ('SyncStatus', SyncStatusMessage),
        ('Error', ErrorMessage),
    ]

    # Generate schema for each message type
    schemas = {}
    definitions = {}

    for name, model_class in message_types:
        schema = model_class.model_json_schema()
        schemas[name] = schema

        # Extract definitions if they exist
        if '$defs' in schema:
            definitions.update(schema['$defs'])
            del schema['$defs']

    # Create master schema with oneOf pattern (for discriminated union)
    master_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "WebSocketMessages",
        "description": "Type-safe WebSocket message contracts for mobile SDK synchronization",
        "version": "1.0.0",
        "oneOf": [
            {"$ref": f"#/definitions/{name}"}
            for name, _ in message_types
        ],
        "definitions": {}
    }

    # Add individual message schemas to definitions
    for name, _ in message_types:
        master_schema["definitions"][name] = schemas[name]

    # Add nested definitions
    master_schema["definitions"].update(definitions)

    # Add metadata for Kotlin codegen
    master_schema["x-kotlin-package"] = "com.youtility.api.websocket"
    master_schema["x-kotlin-sealed-class"] = "WebSocketMessage"
    master_schema["x-discriminator"] = {
        "propertyName": "type",
        "mapping": {
            "connection_established": "ConnectionEstablished",
            "heartbeat": "Heartbeat",
            "start_sync": "SyncStart",
            "sync_data": "SyncData",
            "sync_complete": "SyncComplete",
            "server_data_request": "ServerDataRequest",
            "server_data": "ServerData",
            "conflict_notification": "ConflictNotification",
            "conflict_resolution": "ConflictResolution",
            "sync_status": "SyncStatus",
            "error": "Error",
        }
    }

    return master_schema


def save_schema(schema: dict, output_path: Path):
    """Save JSON Schema to file with pretty formatting."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(schema, f, indent=2, sort_keys=False)

    print(f"✅ JSON Schema generated: {output_path}")
    print(f"   Size: {output_path.stat().st_size:,} bytes")
    print(f"   Message types: {len(schema['definitions'])}")


def generate_kotlin_example(schema: dict, output_path: Path):
    """Generate Kotlin sealed class example."""

    kotlin_code = '''
/**
 * WebSocket Message Types
 * Auto-generated from JSON Schema
 *
 * DO NOT EDIT MANUALLY
 * Generated: {timestamp}
 */

package com.youtility.api.websocket

import kotlinx.serialization.Serializable
import kotlinx.serialization.SerialName
import kotlinx.serialization.json.JsonObject
import java.time.Instant

@Serializable
sealed class WebSocketMessage {{
    abstract val type: String

    @Serializable
    @SerialName("connection_established")
    data class ConnectionEstablished(
        override val type: String = "connection_established",
        @SerialName("user_id") val userId: String,
        @SerialName("device_id") val deviceId: String,
        @SerialName("server_time") val serverTime: Instant,
        val features: Map<String, Boolean>
    ) : WebSocketMessage()

    @Serializable
    @SerialName("heartbeat")
    data class Heartbeat(
        override val type: String = "heartbeat",
        val timestamp: Instant
    ) : WebSocketMessage()

    @Serializable
    @SerialName("start_sync")
    data class SyncStart(
        override val type: String = "start_sync",
        val domain: SyncDomain,
        @SerialName("since_timestamp") val sinceTimestamp: Instant? = null,
        @SerialName("full_sync") val fullSync: Boolean = false,
        @SerialName("device_id") val deviceId: String
    ) : WebSocketMessage()

    @Serializable
    @SerialName("sync_data")
    data class SyncData(
        override val type: String = "sync_data",
        val payload: JsonObject,
        @SerialName("idempotency_key") val idempotencyKey: String,
        val domain: String,
        @SerialName("client_timestamp") val clientTimestamp: Instant
    ) : WebSocketMessage()

    @Serializable
    @SerialName("sync_complete")
    data class SyncComplete(
        override val type: String = "sync_complete",
        val domain: String,
        @SerialName("item_count") val itemCount: Int
    ) : WebSocketMessage()

    @Serializable
    @SerialName("server_data")
    data class ServerData(
        override val type: String = "server_data",
        val domain: String,
        val data: List<JsonObject>,
        @SerialName("next_sync_token") val nextSyncToken: String? = null,
        @SerialName("server_timestamp") val serverTimestamp: Instant
    ) : WebSocketMessage()

    @Serializable
    @SerialName("error")
    data class Error(
        override val type: String = "error",
        @SerialName("error_code") val errorCode: String,
        val message: String,
        val retryable: Boolean = true,
        val details: Map<String, Any>? = null
    ) : WebSocketMessage()

    // Add other message types as needed...
}}

@Serializable
enum class SyncDomain {{
    @SerialName("voice") VOICE,
    @SerialName("attendance") ATTENDANCE,
    @SerialName("task") TASK,
    @SerialName("journal") JOURNAL,
    @SerialName("ticket") TICKET
}}
'''

    from datetime import datetime
    kotlin_code = kotlin_code.replace('{timestamp}', datetime.now().isoformat())

    example_path = output_path.parent / 'WebSocketMessage.kt.example'
    with open(example_path, 'w') as f:
        f.write(kotlin_code)

    print(f"✅ Kotlin example generated: {example_path}")


if __name__ == '__main__':
    print("Generating WebSocket Message JSON Schema...")
    print("-" * 60)

    schema = generate_json_schema()
    output_path = project_root / 'docs' / 'api-contracts' / 'websocket-messages.json'

    save_schema(schema, output_path)
    generate_kotlin_example(schema, output_path)

    print("-" * 60)
    print("\n✨ Schema generation complete!")
    print("\nNext steps for Kotlin team:")
    print("  1. Review: docs/api-contracts/websocket-messages.json")
    print("  2. Reference: docs/api-contracts/WebSocketMessage.kt.example")
    print("  3. Codegen: Use kotlinx-serialization or your preferred tool")
    print()
