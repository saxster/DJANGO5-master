# WebSocket Client SDK Documentation

Complete guide for integrating with Django 5 WebSocket infrastructure.

## 🎯 **Quick Start**

### **JavaScript/TypeScript**

```javascript
// 1. Install dependencies (none required - uses native WebSocket)

// 2. Create WebSocket client
class NOCWebSocketClient {
    constructor(token) {
        this.token = token;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.baseReconnectDelay = 1000; // 1 second
    }

    connect(endpoint = '/ws/noc/presence/') {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}${endpoint}?token=${this.token}`;

        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log('✅ WebSocket connected');
            this.reconnectAttempts = 0;
            this.startHeartbeat();
        };

        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleMessage(data);
        };

        this.ws.onerror = (error) => {
            console.error('❌ WebSocket error:', error);
        };

        this.ws.onclose = (event) => {
            console.log(`🔌 WebSocket closed: ${event.code}`);
            this.stopHeartbeat();
            this.attemptReconnect();
        };
    }

    handleMessage(data) {
        switch (data.type) {
            case 'connection_established':
                console.log(`Heartbeat interval: ${data.heartbeat_interval}s`);
                break;
            case 'heartbeat_ack':
                console.log(`Latency: ${data.latency_ms}ms, Uptime: ${data.uptime_seconds}s`);
                break;
            case 'error':
                console.error('Server error:', data.message);
                break;
        }
    }

    startHeartbeat() {
        this.heartbeatInterval = setInterval(() => {
            this.sendHeartbeat();
        }, 30000); // 30 seconds
    }

    stopHeartbeat() {
        if (this.heartbeatInterval) {
            clearInterval(this.heartbeatInterval);
        }
    }

    sendHeartbeat() {
        this.send({
            type: 'heartbeat',
            timestamp: new Date().toISOString()
        });
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    attemptReconnect() {
        if (this.reconnectAttempts >= this.maxReconnectAttempts) {
            console.error('❌ Max reconnection attempts reached');
            return;
        }

        const delay = this.baseReconnectDelay * Math.pow(2, this.reconnectAttempts);
        console.log(`🔄 Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1}/${this.maxReconnectAttempts})`);

        setTimeout(() => {
            this.reconnectAttempts++;
            this.connect();
        }, delay);
    }

    disconnect() {
        this.stopHeartbeat();
        if (this.ws) {
            this.ws.close();
        }
    }
}

// 3. Usage
const client = new NOCWebSocketClient('YOUR_JWT_TOKEN');
client.connect();
```

---

## 📡 **Endpoints**

| Endpoint | Purpose | Authentication | Consumer |
|----------|---------|----------------|----------|
| `/ws/noc/dashboard/` | NOC dashboard updates | JWT + noc:view | NOCDashboardConsumer |
| `/ws/noc/presence/` | Connection health monitoring | JWT | PresenceMonitorConsumer |
| `/ws/mobile/sync/` | Mobile app sync | JWT | MobileSyncConsumer |

---

## 🔐 **Authentication**

### **Method 1: Query Parameter (Recommended for Web)**
```javascript
const url = `wss://app.example.com/ws/noc/presence/?token=${jwt_token}`;
```

### **Method 2: Authorization Header**
```javascript
const ws = new WebSocket('wss://app.example.com/ws/noc/presence/');
ws.onopen = () => {
    // Note: Can't set headers on WebSocket constructor
    // Must use query param or cookie
};
```

### **Method 3: Cookie (Recommended for Browser)**
```javascript
// Server sets: ws_token=JWT_TOKEN; HttpOnly; Secure
const ws = new WebSocket('wss://app.example.com/ws/noc/presence/');
```

---

## 💓 **Heartbeat Protocol**

### **Client → Server**
```json
{
    "type": "heartbeat",
    "timestamp": "2025-10-01T12:00:00.000Z"
}
```

### **Server → Client**
```json
{
    "type": "heartbeat_ack",
    "server_time": "2025-10-01T12:00:00.100Z",
    "latency_ms": 45,
    "uptime_seconds": 120
}
```

### **Intervals**
- **Client heartbeat**: Every 30 seconds
- **Server timeout**: 5 minutes without heartbeat → auto-disconnect
- **Auto-reconnect**: Exponential backoff (1s, 2s, 4s, 8s, 16s)

---

## 📊 **Message Types**

### **Presence Monitor**

| Type | Direction | Purpose |
|------|-----------|---------|
| `connection_established` | Server → Client | Initial connection confirmation |
| `heartbeat` | Bidirectional | Keep-alive |
| `heartbeat_ack` | Server → Client | Heartbeat acknowledgment |
| `ping` | Client → Server | Simple keep-alive |
| `pong` | Server → Client | Ping response |
| `get_stats` | Client → Server | Request connection stats |
| `stats` | Server → Client | Connection statistics |

### **NOC Dashboard**

| Type | Direction | Purpose |
|------|-----------|---------|
| `connected` | Server → Client | Dashboard connection |
| `subscribe_client` | Client → Server | Subscribe to client alerts |
| `subscribed` | Server → Client | Subscription confirmation |
| `acknowledge_alert` | Client → Server | Acknowledge alert |
| `alert_acknowledged` | Server → Client | Acknowledgment confirmation |
| `alert_new` | Server → Client | New alert broadcast |

---

## 🔄 **Reconnection Strategy**

### **Exponential Backoff**
```javascript
function calculateReconnectDelay(attemptNumber) {
    const baseDelay = 1000; // 1 second
    const maxAttempts = 5;

    if (attemptNumber >= maxAttempts) {
        return null; // Stop trying
    }

    return baseDelay * Math.pow(2, attemptNumber);
}

// Delays: 1s, 2s, 4s, 8s, 16s
```

### **Connection States**
```javascript
const ConnectionState = {
    CONNECTING: 'connecting',
    CONNECTED: 'connected',
    RECONNECTING: 'reconnecting',
    FAILED: 'failed',
    DISCONNECTED: 'disconnected'
};
```

---

## 🎨 **React Hook Example**

```typescript
import { useEffect, useState, useCallback } from 'react';

interface WebSocketHookOptions {
    endpoint: string;
    token: string;
    autoReconnect?: boolean;
}

export function useWebSocket({ endpoint, token, autoReconnect = true }: WebSocketHookOptions) {
    const [isConnected, setIsConnected] = useState(false);
    const [lastMessage, setLastMessage] = useState<any>(null);
    const [ws, setWs] = useState<WebSocket | null>(null);

    useEffect(() => {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const url = `${protocol}//${host}${endpoint}?token=${token}`;

        const websocket = new WebSocket(url);

        websocket.onopen = () => {
            console.log('✅ Connected');
            setIsConnected(true);
        };

        websocket.onmessage = (event) => {
            const data = JSON.parse(event.data);
            setLastMessage(data);
        };

        websocket.onclose = () => {
            console.log('🔌 Disconnected');
            setIsConnected(false);
        };

        setWs(websocket);

        return () => {
            websocket.close();
        };
    }, [endpoint, token]);

    const sendMessage = useCallback((data: any) => {
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify(data));
        }
    }, [ws]);

    return { isConnected, lastMessage, sendMessage };
}

// Usage
function NOCDashboard() {
    const { isConnected, lastMessage, sendMessage } = useWebSocket({
        endpoint: '/ws/noc/dashboard/',
        token: 'YOUR_JWT_TOKEN'
    });

    return (
        <div>
            <p>Status: {isConnected ? '🟢 Connected' : '🔴 Disconnected'}</p>
            {lastMessage && <pre>{JSON.stringify(lastMessage, null, 2)}</pre>}
        </div>
    );
}
```

---

## 🐍 **Python Client Example**

```python
import asyncio
import websockets
import json
from datetime import datetime, timezone

class NOCWebSocketClient:
    def __init__(self, url: str, token: str):
        self.url = f"{url}?token={token}"
        self.ws = None

    async def connect(self):
        async with websockets.connect(self.url) as websocket:
            self.ws = websocket
            print("✅ Connected")

            # Receive connection_established
            message = await websocket.recv()
            data = json.loads(message)
            print(f"Server: {data}")

            # Start heartbeat
            await self.heartbeat_loop()

    async def heartbeat_loop(self):
        while True:
            await asyncio.sleep(30)
            await self.send_heartbeat()

    async def send_heartbeat(self):
        await self.ws.send(json.dumps({
            'type': 'heartbeat',
            'timestamp': datetime.now(timezone.utc).isoformat()
        }))

        response = await self.ws.recv()
        data = json.loads(response)
        print(f"Heartbeat ACK: Latency={data['latency_ms']}ms")

# Usage
async def main():
    client = NOCWebSocketClient('ws://localhost:8000/ws/noc/presence/', 'YOUR_JWT_TOKEN')
    await client.connect()

asyncio.run(main())
```

---

## 🚨 **Error Codes**

| Code | Meaning | Action |
|------|---------|--------|
| 4401 | Unauthorized | Invalid or missing JWT |
| 4403 | Forbidden | Invalid origin or insufficient permissions |
| 4408 | Request Timeout | Stale connection (no heartbeat) |
| 4429 | Too Many Connections | Throttle limit exceeded |

---

## 🎯 **Best Practices**

1. **Always implement reconnection** with exponential backoff
2. **Send heartbeats** every 30 seconds
3. **Handle all message types** gracefully
4. **Use JWT authentication** for security
5. **Monitor connection state** in UI
6. **Log errors** for debugging
7. **Test with network interruptions** (airplane mode)
8. **Implement message queue** for offline support

---

## 📈 **Performance Tips**

- **Batch messages** when possible (reduce roundtrips)
- **Use binary frames** for large data (not implemented yet)
- **Compress payloads** for large messages
- **Monitor latency** (target <50ms P95)
- **Limit concurrent connections** per user

---

## 🔧 **Troubleshooting**

### **Connection Fails Immediately**
- Check JWT token validity
- Verify endpoint URL
- Check CORS/origin whitelist

### **Connection Drops After 5 Minutes**
- Not sending heartbeats
- Check `WEBSOCKET_PRESENCE_TIMEOUT` setting

### **High Latency**
- Check network conditions
- Monitor server load
- Review middleware stack

---

**Need Help?** Contact: support@example.com
