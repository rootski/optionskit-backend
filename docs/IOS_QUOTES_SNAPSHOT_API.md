# Quotes Snapshot API - iOS Client Guide

## Overview

The Quotes Snapshot API provides real-time market quotes for all optionable underlyings. The backend automatically refreshes quotes every 61 seconds, so you can fetch the latest data efficiently without making individual API calls for each symbol.

**Key Features:**
- Single API call to get quotes for all symbols or filter by specific symbols
- Lightweight endpoint to check snapshot freshness
- Data is refreshed automatically every 61 seconds
- Available within 5 seconds of server startup

---

## Endpoints

### 1. Get Quotes Snapshot

**Endpoint:** `GET /v1/markets/quotes/snapshot`

**Description:** Returns the current quotes snapshot. Can optionally filter by specific symbols.

**Query Parameters:**
- `symbols` (optional): Comma-separated list of symbols to filter by (e.g., "AAPL,MSFT,GOOGL")
  - If omitted, returns quotes for all optionable underlyings
  - Symbols are case-insensitive (automatically converted to uppercase)

**Response Format:**
```json
{
  "last_update": "2024-01-15T10:30:45.123456",
  "count": 150,
  "results": [
    {
      "symbol": "AAPL",
      "description": "Apple Inc.",
      "last": 150.25,
      "bid": 150.20,
      "ask": 150.30,
      "volume": 50000000
    },
    {
      "symbol": "MSFT",
      "description": "Microsoft Corporation",
      "last": 380.50,
      "bid": 380.45,
      "ask": 380.55,
      "volume": 30000000
    }
    // ... more quotes
  ]
}
```

**Response Fields:**
- `last_update`: ISO 8601 timestamp of when the snapshot was last refreshed
- `count`: Number of quotes in the results array
- `results`: Array of quote objects, each containing:
  - `symbol`: Stock symbol (uppercase)
  - `description`: Company name/description
  - `last`: Last traded price
  - `bid`: Current bid price
  - `ask`: Current ask price
  - `volume`: Trading volume

**Examples:**

```swift
// Get all quotes
GET https://your-api-domain.com/v1/markets/quotes/snapshot

// Get quotes for specific symbols
GET https://your-api-domain.com/v1/markets/quotes/snapshot?symbols=AAPL,MSFT,GOOGL

// Get quote for single symbol
GET https://your-api-domain.com/v1/markets/quotes/snapshot?symbols=AAPL
```

---

### 2. Get Last Update Info

**Endpoint:** `GET /v1/markets/quotes/last_update`

**Description:** Lightweight endpoint to check snapshot freshness without fetching all quote data. Useful for polling to detect when new data is available.

**Response Format:**
```json
{
  "last_update": "2024-01-15T10:30:45.123456",
  "count": 150
}
```

**Response Fields:**
- `last_update`: ISO 8601 timestamp of when the snapshot was last refreshed
- `count`: Total number of quotes in the snapshot

**Example:**

```swift
GET https://your-api-domain.com/v1/markets/quotes/last_update
```

---

## Swift Implementation Examples

### Model Structures

```swift
import Foundation

struct QuotesSnapshotResponse: Codable {
    let lastUpdate: String
    let count: Int
    let results: [Quote]
    
    enum CodingKeys: String, CodingKey {
        case lastUpdate = "last_update"
        case count
        case results
    }
}

struct Quote: Codable {
    let symbol: String
    let description: String
    let last: Double
    let bid: Double
    let ask: Double
    let volume: Int
}

struct LastUpdateResponse: Codable {
    let lastUpdate: String
    let count: Int
    
    enum CodingKeys: String, CodingKey {
        case lastUpdate = "last_update"
        case count
    }
}
```

### API Service Class

```swift
import Foundation

class QuotesSnapshotService {
    private let baseURL: String
    
    init(baseURL: String) {
        self.baseURL = baseURL
    }
    
    // MARK: - Get All Quotes
    
    func getAllQuotes() async throws -> QuotesSnapshotResponse {
        let url = URL(string: "\(baseURL)/v1/markets/quotes/snapshot")!
        return try await fetchQuotes(url: url)
    }
    
    // MARK: - Get Quotes for Specific Symbols
    
    func getQuotes(for symbols: [String]) async throws -> QuotesSnapshotResponse {
        let symbolsString = symbols.joined(separator: ",")
        let urlString = "\(baseURL)/v1/markets/quotes/snapshot?symbols=\(symbolsString)"
        guard let url = URL(string: urlString) else {
            throw APIError.invalidURL
        }
        return try await fetchQuotes(url: url)
    }
    
    // MARK: - Get Last Update Info
    
    func getLastUpdate() async throws -> LastUpdateResponse {
        let url = URL(string: "\(baseURL)/v1/markets/quotes/last_update")!
        
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(statusCode: httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(LastUpdateResponse.self, from: data)
    }
    
    // MARK: - Private Helpers
    
    private func fetchQuotes(url: URL) async throws -> QuotesSnapshotResponse {
        let (data, response) = try await URLSession.shared.data(from: url)
        
        guard let httpResponse = response as? HTTPURLResponse else {
            throw APIError.invalidResponse
        }
        
        guard httpResponse.statusCode == 200 else {
            throw APIError.httpError(statusCode: httpResponse.statusCode)
        }
        
        let decoder = JSONDecoder()
        return try decoder.decode(QuotesSnapshotResponse.self, from: data)
    }
}

enum APIError: Error {
    case invalidURL
    case invalidResponse
    case httpError(statusCode: Int)
    case decodingError(Error)
}
```

### Usage Examples

```swift
// Initialize the service
let quotesService = QuotesSnapshotService(baseURL: "https://your-api-domain.com")

// Example 1: Get all quotes
Task {
    do {
        let snapshot = try await quotesService.getAllQuotes()
        print("Fetched \(snapshot.count) quotes")
        print("Last updated: \(snapshot.lastUpdate)")
        
        for quote in snapshot.results {
            print("\(quote.symbol): \(quote.last)")
        }
    } catch {
        print("Error fetching quotes: \(error)")
    }
}

// Example 2: Get quotes for specific symbols
Task {
    do {
        let symbols = ["AAPL", "MSFT", "GOOGL"]
        let snapshot = try await quotesService.getQuotes(for: symbols)
        print("Fetched \(snapshot.count) quotes for requested symbols")
    } catch {
        print("Error fetching quotes: \(error)")
    }
}

// Example 3: Check if new data is available (polling pattern)
Task {
    do {
        let lastUpdate = try await quotesService.getLastUpdate()
        print("Snapshot has \(lastUpdate.count) quotes")
        print("Last updated: \(lastUpdate.lastUpdate)")
        
        // Parse timestamp and compare with your cached version
        let formatter = ISO8601DateFormatter()
        if let updateDate = formatter.date(from: lastUpdate.lastUpdate) {
            // Compare with your cached timestamp
            // If different, fetch full snapshot
        }
    } catch {
        print("Error checking last update: \(error)")
    }
}
```

---

## Best Practices

### 1. Polling Strategy

Since quotes refresh every 61 seconds, you don't need to poll more frequently:

```swift
// Good: Poll every 60-65 seconds
Timer.scheduledTimer(withTimeInterval: 65.0, repeats: true) { _ in
    // Check for updates
}

// Bad: Polling every second is wasteful
Timer.scheduledTimer(withTimeInterval: 1.0, repeats: true) { _ in
    // Too frequent!
}
```

### 2. Efficient Updates

Use the lightweight `last_update` endpoint to detect changes, then fetch full data only when needed:

```swift
func checkForUpdates() async {
    do {
        let lastUpdate = try await quotesService.getLastUpdate()
        
        // Compare with cached timestamp
        if lastUpdate.lastUpdate != cachedTimestamp {
            // New data available, fetch full snapshot
            let snapshot = try await quotesService.getAllQuotes()
            updateUI(with: snapshot)
            cachedTimestamp = lastUpdate.lastUpdate
        }
    } catch {
        print("Error checking for updates: \(error)")
    }
}
```

### 3. Filtering by Symbols

When you only need quotes for specific symbols, use the `symbols` query parameter:

```swift
// Good: Fetch only what you need
let watchlistSymbols = ["AAPL", "MSFT", "GOOGL"]
let snapshot = try await quotesService.getQuotes(for: watchlistSymbols)

// Less efficient: Fetch all quotes then filter client-side
let allQuotes = try await quotesService.getAllQuotes()
let filtered = allQuotes.results.filter { watchlistSymbols.contains($0.symbol) }
```

### 4. Error Handling

Always handle potential errors:

```swift
Task {
    do {
        let snapshot = try await quotesService.getAllQuotes()
        // Handle success
    } catch APIError.httpError(let statusCode) {
        if statusCode == 500 {
            // Server error - might be temporary
            // Retry after a delay
        }
    } catch {
        // Other errors (network, decoding, etc.)
        print("Error: \(error)")
    }
}
```

### 5. Caching

Cache the snapshot locally and only refresh when needed:

```swift
class QuotesCache {
    private var cachedSnapshot: QuotesSnapshotResponse?
    private var cachedTimestamp: String?
    
    func getCachedQuotes() -> QuotesSnapshotResponse? {
        return cachedSnapshot
    }
    
    func updateCache(_ snapshot: QuotesSnapshotResponse) {
        cachedSnapshot = snapshot
        cachedTimestamp = snapshot.lastUpdate
    }
    
    func isStale() -> Bool {
        // Check if cache is older than 65 seconds
        guard let timestamp = cachedTimestamp else { return true }
        // Parse and compare timestamps
        return true // Implement timestamp comparison
    }
}
```

---

## Response Times

- **Initial Availability:** Data is available within 5 seconds of server startup
- **Refresh Interval:** Quotes are refreshed every 61 seconds
- **API Response Time:** Typically < 100ms for filtered requests, < 500ms for all quotes

---

## Error Responses

### 500 Internal Server Error
The snapshot refresh may have failed. The previous snapshot data is preserved, so you can continue using cached data.

**Response:**
```json
{
  "detail": "Failed to retrieve quotes snapshot: [error message]"
}
```

### Handling Empty Snapshots

On initial startup (first 5 seconds), the snapshot may be empty:

```swift
let snapshot = try await quotesService.getAllQuotes()

if snapshot.count == 0 {
    // Snapshot not yet populated, wait and retry
    try await Task.sleep(nanoseconds: 2_000_000_000) // Wait 2 seconds
    let retrySnapshot = try await quotesService.getAllQuotes()
}
```

---

## Notes

1. **Symbol Filtering:** If you request symbols that don't exist in the snapshot, they simply won't appear in the results. No error is thrown.

2. **Data Freshness:** The `last_update` timestamp tells you when the data was last refreshed. Use this to determine if your cached data is still valid.

3. **Rate Limiting:** These endpoints are designed to be called frequently. The backend handles rate limiting for the external Tradier API internally.

4. **Background Refresh:** The backend automatically refreshes quotes every 61 seconds. You don't need to trigger refreshes manually.

---

## Quick Reference

| Endpoint | Method | Purpose | Use Case |
|----------|--------|---------|----------|
| `/v1/markets/quotes/snapshot` | GET | Get all or filtered quotes | Display quotes in UI |
| `/v1/markets/quotes/snapshot?symbols=AAPL,MSFT` | GET | Get quotes for specific symbols | Watchlist, search results |
| `/v1/markets/quotes/last_update` | GET | Check snapshot freshness | Polling for updates |

---

## Support

For issues or questions, refer to the API documentation or contact the backend team.


