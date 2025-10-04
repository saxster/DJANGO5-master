# Mobile SDK WebSocket Integration Guide

> **Complete guide for integrating WebSocket JWT authentication in iOS, Android, and React Native apps**

## Table of Contents

- [Prerequisites](#prerequisites)
- [iOS/Swift Integration](#iosswift-integration)
- [Android/Kotlin Integration](#androidkotlin-integration)
- [React Native Integration](#react-native-integration)
- [Connection Lifecycle](#connection-lifecycle)
- [Error Handling](#error-handling)
- [Best Practices](#best-practices)

---

## Prerequisites

### 1. Obtain JWT Access Token

Before connecting to WebSocket, obtain a valid JWT access token via REST API:

```http
POST /api/auth/token/
Content-Type: application/json

{
    "username": "user@example.com",
    "password": "password123"
}
```

**Response:**

```json
{
    "access": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 3600
}
```

### 2. Get Device Identifier

Each platform provides a unique device identifier:

- **iOS:** `UIDevice.current.identifierForVendor`
- **Android:** `UUID.randomUUID()` or `Settings.Secure.ANDROID_ID`
- **React Native:** `react-native-device-info`

---

## iOS/Swift Integration

### Dependencies

Add to your `Podfile` or `Package.swift`:

```swift
// Native URLSessionWebSocketTask (iOS 13+)
// No additional dependencies required

// OR using Starscream (3rd party)
pod 'Starscream', '~> 4.0'
```

### WebSocket Manager (URLSession)

```swift
import Foundation
import UIKit

class WebSocketManager: NSObject, URLSessionWebSocketDelegate {

    // MARK: - Properties

    private var webSocketTask: URLSessionWebSocketTask?
    private var session: URLSession?
    private let baseURL: String
    private var accessToken: String
    private let deviceId: String

    // Callbacks
    var onConnected: (() -> Void)?
    var onMessage: ((Data) -> Void)?
    var onError: ((Error) -> Void)?
    var onDisconnected: ((URLSessionWebSocketTask.CloseCode, String?) -> Void)?

    // Reconnection
    private var reconnectAttempts = 0
    private let maxReconnectAttempts = 5
    private var reconnectTimer: Timer?

    // MARK: - Initialization

    init(baseURL: String, accessToken: String) {
        self.baseURL = baseURL
        self.accessToken = accessToken
        self.deviceId = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString

        super.init()

        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 30
        configuration.timeoutIntervalForResource = 60

        self.session = URLSession(
            configuration: configuration,
            delegate: self,
            delegateQueue: OperationQueue()
        )
    }

    // MARK: - Connection Management

    func connect() {
        guard webSocketTask == nil else {
            print("WebSocket already connected")
            return
        }

        // Build WebSocket URL with JWT token and device_id
        let wsURL = "\(baseURL)?token=\(accessToken)&device_id=\(deviceId)"
        guard let url = URL(string: wsURL) else {
            print("Invalid WebSocket URL")
            return
        }

        webSocketTask = session?.webSocketTask(with: url)
        webSocketTask?.resume()

        // Start receiving messages
        receiveMessage()

        print("WebSocket connecting to: \(baseURL)")
    }

    func disconnect(closeCode: URLSessionWebSocketTask.CloseCode = .normalClosure) {
        reconnectTimer?.invalidate()
        reconnectTimer = nil

        webSocketTask?.cancel(with: closeCode, reason: nil)
        webSocketTask = nil

        print("WebSocket disconnected")
    }

    // MARK: - Send/Receive

    func send(message: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: message, options: []) else {
            print("Failed to serialize message")
            return
        }

        let message = URLSessionWebSocketTask.Message.data(data)
        webSocketTask?.send(message) { error in
            if let error = error {
                print("WebSocket send error: \(error)")
                self.onError?(error)
            }
        }
    }

    private func receiveMessage() {
        webSocketTask?.receive { [weak self] result in
            switch result {
            case .success(let message):
                switch message {
                case .data(let data):
                    self?.handleMessage(data: data)
                case .string(let string):
                    if let data = string.data(using: .utf8) {
                        self?.handleMessage(data: data)
                    }
                @unknown default:
                    print("Unknown WebSocket message type")
                }

                // Continue receiving
                self?.receiveMessage()

            case .failure(let error):
                print("WebSocket receive error: \(error)")
                self?.onError?(error)
                self?.scheduleReconnect()
            }
        }
    }

    private func handleMessage(data: Data) {
        // Parse message
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let messageType = json["type"] as? String else {
            print("Invalid message format")
            return
        }

        switch messageType {
        case "connection_established":
            reconnectAttempts = 0
            onConnected?()
            print("WebSocket connection established")

        case "error":
            if let errorMessage = json["message"] as? String,
               let errorCode = json["error_code"] as? String {
                print("WebSocket error: [\(errorCode)] \(errorMessage)")
            }

        default:
            // Delegate to callback
            onMessage?(data)
        }
    }

    // MARK: - Token Refresh

    func updateToken(_ newToken: String) {
        self.accessToken = newToken

        // Reconnect with new token
        disconnect()
        connect()
    }

    // MARK: - Reconnection Logic

    private func scheduleReconnect() {
        guard reconnectAttempts < maxReconnectAttempts else {
            print("Max reconnect attempts reached")
            return
        }

        let delay = pow(2.0, Double(reconnectAttempts))
        reconnectAttempts += 1

        print("Reconnecting in \(delay) seconds (attempt \(reconnectAttempts)/\(maxReconnectAttempts))")

        reconnectTimer = Timer.scheduledTimer(withTimeInterval: delay, repeats: false) { [weak self] _ in
            self?.connect()
        }
    }

    // MARK: - URLSessionWebSocketDelegate

    func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didOpenWithProtocol protocol: String?
    ) {
        print("WebSocket did open")
    }

    func urlSession(
        _ session: URLSession,
        webSocketTask: URLSessionWebSocketTask,
        didCloseWith closeCode: URLSessionWebSocketTask.CloseCode,
        reason: Data?
    ) {
        let reasonString = reason != nil ? String(data: reason!, encoding: .utf8) : nil
        print("WebSocket did close: \(closeCode.rawValue) - \(reasonString ?? "")")

        onDisconnected?(closeCode, reasonString)

        // Auto-reconnect on abnormal closure
        if closeCode != .normalClosure {
            scheduleReconnect()
        }
    }
}
```

### Usage Example

```swift
// Initialize
let wsManager = WebSocketManager(
    baseURL: "wss://api.youtility.com/ws/mobile/sync/",
    accessToken: AuthService.shared.accessToken
)

// Set callbacks
wsManager.onConnected = {
    print("Connected to WebSocket!")

    // Send sync request
    wsManager.send(message: [
        "type": "start_sync",
        "sync_id": UUID().uuidString,
        "data_types": ["voice", "behavioral", "metrics"]
    ])
}

wsManager.onMessage = { data in
    if let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
        print("Received: \(json)")
    }
}

wsManager.onError = { error in
    print("WebSocket error: \(error)")
}

// Connect
wsManager.connect()

// Later: disconnect
wsManager.disconnect()
```

---

## Android/Kotlin Integration

### Dependencies

Add to your `build.gradle`:

```gradle
dependencies {
    // OkHttp WebSocket
    implementation 'com.squareup.okhttp3:okhttp:4.12.0'

    // Gson for JSON
    implementation 'com.google.code.gson:gson:2.10.1'

    // Coroutines
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
}
```

### WebSocket Manager

```kotlin
import android.util.Log
import okhttp3.*
import okio.ByteString
import java.util.*
import java.util.concurrent.TimeUnit
import kotlin.math.pow

class WebSocketManager(
    private val baseUrl: String,
    private var accessToken: String
) {
    companion object {
        private const val TAG = "WebSocketManager"
        private const val MAX_RECONNECT_ATTEMPTS = 5
    }

    private var webSocket: WebSocket? = null
    private val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .pingInterval(30, TimeUnit.SECONDS)
            .build()
    }

    private val deviceId: String = UUID.randomUUID().toString()
    private var reconnectAttempts = 0

    // Callbacks
    var onConnected: (() -> Unit)? = null
    var onMessage: ((String) -> Unit)? = null
    var onError: ((Throwable) -> Unit)? = null
    var onClosed: ((Int, String) -> Unit)? = null

    // MARK: - Connection Management

    fun connect() {
        if (webSocket != null) {
            Log.w(TAG, "WebSocket already connected")
            return
        }

        val wsUrl = "$baseUrl?token=$accessToken&device_id=$deviceId"

        val request = Request.Builder()
            .url(wsUrl)
            .build()

        webSocket = client.newWebSocket(request, webSocketListener)
        Log.d(TAG, "WebSocket connecting to: $baseUrl")
    }

    fun disconnect() {
        webSocket?.close(1000, "Normal closure")
        webSocket = null
        reconnectAttempts = 0
    }

    // MARK: - Send Messages

    fun send(message: Map<String, Any>) {
        val json = com.google.gson.Gson().toJson(message)
        webSocket?.send(json) ?: run {
            Log.w(TAG, "WebSocket not connected, cannot send message")
        }
    }

    // MARK: - Token Refresh

    fun updateToken(newToken: String) {
        accessToken = newToken
        disconnect()
        connect()
    }

    // MARK: - WebSocket Listener

    private val webSocketListener = object : WebSocketListener() {
        override fun onOpen(webSocket: WebSocket, response: Response) {
            Log.d(TAG, "WebSocket opened")
        }

        override fun onMessage(webSocket: WebSocket, text: String) {
            handleMessage(text)
        }

        override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
            handleMessage(bytes.utf8())
        }

        override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
            Log.d(TAG, "WebSocket closing: $code - $reason")
        }

        override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
            Log.d(TAG, "WebSocket closed: $code - $reason")
            this@WebSocketManager.webSocket = null
            onClosed?.invoke(code, reason)

            // Auto-reconnect on abnormal closure
            if (code != 1000) {
                scheduleReconnect()
            }
        }

        override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
            Log.e(TAG, "WebSocket failure", t)
            this@WebSocketManager.webSocket = null
            onError?.invoke(t)
            scheduleReconnect()
        }
    }

    // MARK: - Message Handling

    private fun handleMessage(text: String) {
        try {
            val gson = com.google.gson.Gson()
            val message = gson.fromJson(text, Map::class.java) as? Map<String, Any>

            when (message?.get("type")) {
                "connection_established" -> {
                    reconnectAttempts = 0
                    onConnected?.invoke()
                    Log.d(TAG, "Connection established")
                }
                "error" -> {
                    val errorMsg = message["message"] as? String
                    val errorCode = message["error_code"] as? String
                    Log.e(TAG, "WebSocket error: [$errorCode] $errorMsg")
                }
                else -> {
                    onMessage?.invoke(text)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Error parsing message", e)
        }
    }

    // MARK: - Reconnection Logic

    private fun scheduleReconnect() {
        if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
            Log.e(TAG, "Max reconnect attempts reached")
            return
        }

        val delay = (2.0.pow(reconnectAttempts) * 1000).toLong()
        reconnectAttempts++

        Log.d(TAG, "Reconnecting in ${delay}ms (attempt $reconnectAttempts/$MAX_RECONNECT_ATTEMPTS)")

        android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
            connect()
        }, delay)
    }
}
```

### Usage Example

```kotlin
// Initialize
val wsManager = WebSocketManager(
    baseUrl = "wss://api.youtility.com/ws/mobile/sync/",
    accessToken = authService.getAccessToken()
)

// Set callbacks
wsManager.onConnected = {
    Log.d("App", "Connected to WebSocket!")

    // Send sync request
    wsManager.send(mapOf(
        "type" to "start_sync",
        "sync_id" to UUID.randomUUID().toString(),
        "data_types" to listOf("voice", "behavioral", "metrics")
    ))
}

wsManager.onMessage = { message ->
    Log.d("App", "Received: $message")
}

wsManager.onError = { error ->
    Log.e("App", "WebSocket error", error)
}

// Connect
wsManager.connect()

// Later: disconnect
override fun onDestroy() {
    super.onDestroy()
    wsManager.disconnect()
}
```

---

## React Native Integration

### Dependencies

```bash
npm install @react-native-async-storage/async-storage react-native-device-info
```

### WebSocket Hook

```javascript
import { useEffect, useRef, useState, useCallback } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import DeviceInfo from 'react-native-device-info';

export const useWebSocket = (baseUrl) => {
    const [isConnected, setIsConnected] = useState(false);
    const [message, setMessage] = useState(null);
    const wsRef = useRef(null);
    const reconnectAttemptsRef = useRef(0);
    const maxReconnectAttempts = 5;

    const connect = useCallback(async () => {
        try {
            // Get token and device ID
            const token = await AsyncStorage.getItem('access_token');
            const deviceId = await DeviceInfo.getUniqueId();

            if (!token) {
                console.error('No access token found');
                return;
            }

            // Build WebSocket URL
            const wsUrl = `${baseUrl}?token=${token}&device_id=${deviceId}`;

            // Create WebSocket
            const ws = new WebSocket(wsUrl);

            ws.onopen = () => {
                console.log('WebSocket connected');
                setIsConnected(true);
                reconnectAttemptsRef.current = 0;
            };

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    if (data.type === 'connection_established') {
                        console.log('Connection established');
                    } else if (data.type === 'error') {
                        console.error(`WebSocket error: [${data.error_code}] ${data.message}`);
                    } else {
                        setMessage(data);
                    }
                } catch (error) {
                    console.error('Error parsing message:', error);
                }
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
            };

            ws.onclose = (event) => {
                console.log(`WebSocket closed: ${event.code} - ${event.reason}`);
                setIsConnected(false);
                wsRef.current = null;

                // Auto-reconnect on abnormal closure
                if (event.code !== 1000) {
                    scheduleReconnect();
                }
            };

            wsRef.current = ws;

        } catch (error) {
            console.error('Error connecting to WebSocket:', error);
        }
    }, [baseUrl]);

    const disconnect = useCallback(() => {
        if (wsRef.current) {
            wsRef.current.close(1000, 'Normal closure');
            wsRef.current = null;
        }
    }, []);

    const send = useCallback((data) => {
        if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data));
        } else {
            console.warn('WebSocket not connected');
        }
    }, []);

    const updateToken = useCallback(async (newToken) => {
        await AsyncStorage.setItem('access_token', newToken);
        disconnect();
        connect();
    }, [connect, disconnect]);

    const scheduleReconnect = useCallback(() => {
        if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
            console.error('Max reconnect attempts reached');
            return;
        }

        const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000;
        reconnectAttemptsRef.current++;

        console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${maxReconnectAttempts})`);

        setTimeout(() => {
            connect();
        }, delay);
    }, [connect]);

    // Auto-connect on mount
    useEffect(() => {
        connect();

        return () => {
            disconnect();
        };
    }, [connect, disconnect]);

    return {
        isConnected,
        message,
        send,
        connect,
        disconnect,
        updateToken,
    };
};
```

### Usage Example

```javascript
import React, { useEffect } from 'react';
import { View, Text, Button } from 'react-native';
import { useWebSocket } from './hooks/useWebSocket';

const SyncScreen = () => {
    const { isConnected, message, send, disconnect } = useWebSocket(
        'wss://api.youtility.com/ws/mobile/sync/'
    );

    useEffect(() => {
        if (isConnected) {
            // Send sync request
            send({
                type: 'start_sync',
                sync_id: Date.now().toString(),
                data_types: ['voice', 'behavioral', 'metrics'],
            });
        }
    }, [isConnected]);

    useEffect(() => {
        if (message) {
            console.log('Received message:', message);

            // Handle different message types
            switch (message.type) {
                case 'sync_progress':
                    console.log(`Sync progress: ${message.progress.synced_items}/${message.progress.total_items}`);
                    break;

                case 'server_data_response':
                    console.log('Received server data:', message.data);
                    break;
            }
        }
    }, [message]);

    return (
        <View>
            <Text>WebSocket Status: {isConnected ? 'Connected' : 'Disconnected'}</Text>
            <Button title="Disconnect" onPress={disconnect} />
        </View>
    );
};

export default SyncScreen;
```

---

## Best Practices

### 1. Implement Proper Lifecycle Management

**iOS:**
```swift
override func viewDidAppear(_ animated: Bool) {
    super.viewDidAppear(animated)
    wsManager.connect()
}

override func viewDidDisappear(_ animated: Bool) {
    super.viewDidDisappear(animated)
    wsManager.disconnect()
}
```

**Android:**
```kotlin
override fun onResume() {
    super.onResume()
    wsManager.connect()
}

override fun onPause() {
    super.onPause()
    wsManager.disconnect()
}
```

### 2. Handle Background/Foreground Transitions

**iOS:**
```swift
NotificationCenter.default.addObserver(
    forName: UIApplication.willResignActiveNotification,
    object: nil,
    queue: nil
) { _ in
    wsManager.disconnect()
}

NotificationCenter.default.addObserver(
    forName: UIApplication.didBecomeActiveNotification,
    object: nil,
    queue: nil
) { _ in
    wsManager.connect()
}
```

### 3. Store Device ID Persistently

**iOS:**
```swift
class DeviceIDManager {
    static func getDeviceID() -> String {
        if let stored = UserDefaults.standard.string(forKey: "device_id") {
            return stored
        }

        let newID = UIDevice.current.identifierForVendor?.uuidString ?? UUID().uuidString
        UserDefaults.standard.set(newID, forKey: "device_id")
        return newID
    }
}
```

**Android:**
```kotlin
object DeviceIDManager {
    fun getDeviceID(context: Context): String {
        val prefs = context.getSharedPreferences("app_prefs", Context.MODE_PRIVATE)
        return prefs.getString("device_id", null) ?: run {
            val newID = UUID.randomUUID().toString()
            prefs.edit().putString("device_id", newID).apply()
            newID
        }
    }
}
```

---

## Support

**Issues:** https://github.com/anthropics/youtility/issues
**API Documentation:** [`WEBSOCKET_JWT_AUTHENTICATION.md`](../WEBSOCKET_JWT_AUTHENTICATION.md)
**Security:** security@youtility.com

---

**Last Updated:** 2025-10-01
**Version:** 1.0.0
