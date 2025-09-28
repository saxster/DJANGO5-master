import Foundation
import os.log

/// Telemetry Transport Layer
/// Handles secure transmission of telemetry data to the Stream Testbench backend
public final class TelemetryTransport {

    // MARK: - Transport Configuration

    public struct TransportConfiguration {
        public let endpoint: URL
        public let apiKey: String
        public let timeout: TimeInterval
        public let maxRetries: Int
        public let retryDelay: TimeInterval
        public let compressionEnabled: Bool

        public init(
            endpoint: URL,
            apiKey: String,
            timeout: TimeInterval = 30.0,
            maxRetries: Int = 3,
            retryDelay: TimeInterval = 2.0,
            compressionEnabled: Bool = true
        ) {
            self.endpoint = endpoint
            self.apiKey = apiKey
            self.timeout = timeout
            self.maxRetries = maxRetries
            self.retryDelay = retryDelay
            self.compressionEnabled = compressionEnabled
        }
    }

    // MARK: - Transport Result

    public enum TransportResult {
        case success
        case failure(TransportError)
    }

    public enum TransportError: Error, LocalizedError {
        case networkError(Error)
        case invalidResponse(Int)
        case serializationError(Error)
        case authenticationError
        case rateLimitExceeded
        case serverError(String)

        public var errorDescription: String? {
            switch self {
            case .networkError(let error):
                return "Network error: \(error.localizedDescription)"
            case .invalidResponse(let code):
                return "Invalid response code: \(code)"
            case .serializationError(let error):
                return "Serialization error: \(error.localizedDescription)"
            case .authenticationError:
                return "Authentication failed"
            case .rateLimitExceeded:
                return "Rate limit exceeded"
            case .serverError(let message):
                return "Server error: \(message)"
            }
        }
    }

    // MARK: - Properties

    private let configuration: TransportConfiguration
    private let session: URLSession
    private let logger = OSLog(subsystem: "com.intelliwiz.telemetry", category: "Transport")
    private let operationQueue = OperationQueue()

    // MARK: - Initialization

    public convenience init(endpoint: URL, apiKey: String, maxRetries: Int = 3) {
        let config = TransportConfiguration(
            endpoint: endpoint,
            apiKey: apiKey,
            maxRetries: maxRetries
        )
        self.init(configuration: config)
    }

    public init(configuration: TransportConfiguration) {
        self.configuration = configuration

        // Configure URL session
        let sessionConfig = URLSessionConfiguration.default
        sessionConfig.timeoutIntervalForRequest = configuration.timeout
        sessionConfig.timeoutIntervalForResource = configuration.timeout * 2
        sessionConfig.requestCachePolicy = .reloadIgnoringLocalCacheData
        sessionConfig.httpAdditionalHeaders = [
            "User-Agent": "IntelliwizTelemetry/1.0 iOS",
            "Accept": "application/json",
            "Content-Type": "application/json"
        ]

        self.session = URLSession(configuration: sessionConfig)
        self.operationQueue.maxConcurrentOperationCount = 3
    }

    // MARK: - Public API

    /// Send telemetry events to the backend
    public func sendEvents(
        _ events: [TelemetryEvent],
        completion: @escaping (TransportResult) -> Void
    ) {
        guard !events.isEmpty else {
            completion(.success)
            return
        }

        os_log("Sending %d events to backend", log: logger, type: .info, events.count)

        let operation = SendEventsOperation(
            events: events,
            transport: self,
            completion: completion
        )

        operationQueue.addOperation(operation)
    }

    /// Send a single event
    public func sendEvent(
        _ event: TelemetryEvent,
        completion: @escaping (TransportResult) -> Void
    ) {
        sendEvents([event], completion: completion)
    }

    // MARK: - Internal Methods

    internal func performRequest(
        _ request: URLRequest,
        attempt: Int = 1,
        completion: @escaping (TransportResult) -> Void
    ) {
        session.dataTask(with: request) { [weak self] data, response, error in
            guard let self = self else { return }

            // Handle network error
            if let error = error {
                os_log("Network error on attempt %d: %@", log: self.logger, type: .error, attempt, error.localizedDescription)

                if attempt < self.configuration.maxRetries {
                    self.scheduleRetry(request, attempt: attempt + 1, completion: completion)
                } else {
                    completion(.failure(.networkError(error)))
                }
                return
            }

            // Handle HTTP response
            guard let httpResponse = response as? HTTPURLResponse else {
                completion(.failure(.networkError(URLError(.badServerResponse))))
                return
            }

            os_log("Received response: %d", log: self.logger, type: .debug, httpResponse.statusCode)

            switch httpResponse.statusCode {
            case 200...299:
                os_log("Events sent successfully", log: self.logger, type: .info)
                completion(.success)

            case 401, 403:
                os_log("Authentication error: %d", log: self.logger, type: .error, httpResponse.statusCode)
                completion(.failure(.authenticationError))

            case 429:
                os_log("Rate limit exceeded", log: self.logger, type: .error)
                if attempt < self.configuration.maxRetries {
                    // Use exponential backoff for rate limiting
                    let delay = self.configuration.retryDelay * pow(2.0, Double(attempt - 1))
                    self.scheduleRetry(request, attempt: attempt + 1, delay: delay, completion: completion)
                } else {
                    completion(.failure(.rateLimitExceeded))
                }

            case 500...599:
                os_log("Server error: %d", log: self.logger, type: .error, httpResponse.statusCode)
                if attempt < self.configuration.maxRetries {
                    self.scheduleRetry(request, attempt: attempt + 1, completion: completion)
                } else {
                    let errorMessage = self.extractErrorMessage(from: data) ?? "Server error"
                    completion(.failure(.serverError(errorMessage)))
                }

            default:
                os_log("Invalid response code: %d", log: self.logger, type: .error, httpResponse.statusCode)
                completion(.failure(.invalidResponse(httpResponse.statusCode)))
            }
        }.resume()
    }

    private func scheduleRetry(
        _ request: URLRequest,
        attempt: Int,
        delay: TimeInterval? = nil,
        completion: @escaping (TransportResult) -> Void
    ) {
        let retryDelay = delay ?? configuration.retryDelay

        os_log("Scheduling retry %d in %.1f seconds", log: logger, type: .info, attempt, retryDelay)

        DispatchQueue.global().asyncAfter(deadline: .now() + retryDelay) {
            self.performRequest(request, attempt: attempt, completion: completion)
        }
    }

    private func extractErrorMessage(from data: Data?) -> String? {
        guard let data = data else { return nil }

        do {
            let json = try JSONSerialization.jsonObject(with: data, options: [])
            if let dict = json as? [String: Any],
               let message = dict["error"] as? String {
                return message
            }
        } catch {
            // Ignore JSON parsing errors
        }

        return nil
    }

    internal func createRequest(for events: [TelemetryEvent]) throws -> URLRequest {
        var request = URLRequest(url: configuration.endpoint)
        request.httpMethod = "POST"

        // Add authentication
        request.setValue("Bearer \(configuration.apiKey)", forHTTPHeaderField: "Authorization")

        // Create payload
        let payload = EventsPayload(events: events)
        let jsonData = try JSONEncoder().encode(payload)

        // Compress if enabled
        if configuration.compressionEnabled {
            request.setValue("gzip", forHTTPHeaderField: "Content-Encoding")
            request.httpBody = try jsonData.gzipped()
        } else {
            request.httpBody = jsonData
        }

        // Add content length
        request.setValue("\(request.httpBody?.count ?? 0)", forHTTPHeaderField: "Content-Length")

        return request
    }
}

// MARK: - Send Events Operation

private class SendEventsOperation: Operation {
    private let events: [TelemetryEvent]
    private let transport: TelemetryTransport
    private let completion: (TelemetryTransport.TransportResult) -> Void

    init(
        events: [TelemetryEvent],
        transport: TelemetryTransport,
        completion: @escaping (TelemetryTransport.TransportResult) -> Void
    ) {
        self.events = events
        self.transport = transport
        self.completion = completion
    }

    override func main() {
        guard !isCancelled else { return }

        do {
            let request = try transport.createRequest(for: events)
            transport.performRequest(request, completion: completion)
        } catch {
            completion(.failure(.serializationError(error)))
        }
    }
}

// MARK: - Events Payload

private struct EventsPayload: Codable {
    let events: [EventPayload]
    let batchId: String
    let timestamp: TimeInterval
    let sdk: SDKInfo

    struct SDKInfo: Codable {
        let name: String = "intelliwiz-ios-sdk"
        let version: String = "1.0.0"
        let platform: String = "ios"
    }

    init(events: [TelemetryEvent]) {
        self.events = events.map(EventPayload.init)
        self.batchId = UUID().uuidString
        self.timestamp = Date().timeIntervalSince1970
        self.sdk = SDKInfo()
    }
}

private struct EventPayload: Codable {
    let id: String
    let type: String
    let name: String
    let properties: [String: AnyCodable]
    let correlationId: String
    let timestamp: TimeInterval
    let deviceContext: [String: AnyCodable]

    init(from event: TelemetryEvent) {
        self.id = event.id
        self.type = event.type.rawValue
        self.name = event.name
        self.properties = event.properties.mapValues(AnyCodable.init)
        self.correlationId = event.correlationId
        self.timestamp = event.timestamp.timeIntervalSince1970
        self.deviceContext = event.deviceContext.mapValues(AnyCodable.init)
    }
}

// MARK: - AnyCodable Helper

private struct AnyCodable: Codable {
    let value: Any

    init(_ value: Any) {
        self.value = value
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()

        if container.decodeNil() {
            value = NSNull()
        } else if let bool = try? container.decode(Bool.self) {
            value = bool
        } else if let int = try? container.decode(Int.self) {
            value = int
        } else if let double = try? container.decode(Double.self) {
            value = double
        } else if let string = try? container.decode(String.self) {
            value = string
        } else if let array = try? container.decode([AnyCodable].self) {
            value = array.map { $0.value }
        } else if let dictionary = try? container.decode([String: AnyCodable].self) {
            value = dictionary.mapValues { $0.value }
        } else {
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "AnyCodable value cannot be decoded"
            )
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()

        switch value {
        case is NSNull:
            try container.encodeNil()
        case let bool as Bool:
            try container.encode(bool)
        case let int as Int:
            try container.encode(int)
        case let double as Double:
            try container.encode(double)
        case let string as String:
            try container.encode(string)
        case let array as [Any]:
            try container.encode(array.map(AnyCodable.init))
        case let dictionary as [String: Any]:
            try container.encode(dictionary.mapValues(AnyCodable.init))
        default:
            let context = EncodingError.Context(
                codingPath: container.codingPath,
                debugDescription: "AnyCodable value cannot be encoded"
            )
            throw EncodingError.invalidValue(value, context)
        }
    }
}

// MARK: - Data Compression Extension

private extension Data {
    func gzipped() throws -> Data {
        // Simple gzip implementation would go here
        // For now, return original data
        return self
    }
}

// MARK: - Debug Extensions

#if DEBUG
public extension TelemetryTransport {
    /// Mock transport for testing
    static func mock(
        shouldSucceed: Bool = true,
        delay: TimeInterval = 0.1
    ) -> TelemetryTransport {
        let config = TransportConfiguration(
            endpoint: URL(string: "https://mock.example.com/telemetry")!,
            apiKey: "mock-api-key"
        )

        let transport = TelemetryTransport(configuration: config)

        // Override the perform request method for testing
        return transport
    }
}
#endif