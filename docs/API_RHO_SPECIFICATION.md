# API Specification: Accessing Rho Greek

## Overview

Rho is an optional Greek field included in options chain contract responses. It measures an option's sensitivity to changes in interest rates. Rho is vendor-provided only and may be `null` when the vendor doesn't supply it.

**Endpoint:** `GET /v1/markets/chain`

---

## Request

### Endpoint

```
GET /v1/markets/chain
```

### Query Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbol` | string | Yes | Underlying symbol (e.g., "NFLX", "AAPL") |
| `expiry` | string | Yes | Expiration date in `YYYY-MM-DD` format (e.g., "2026-06-18") |

### Example Request

```bash
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18"
```

---

## Response

### Response Structure

```json
{
  "symbol": "NFLX",
  "expiry": "2026-06-18",
  "contracts": [
    {
      "symbol": "NFLX",
      "expiry": "2026-06-18",
      "strike": 500.0,
      "type": "call",
      "bid": 25.50,
      "ask": 25.60,
      "last": 25.55,
      "volume": 1000,
      "open_interest": 5000,
      "delta": 0.565,
      "gamma": 0.057,
      "theta": -0.334,
      "vega": 0.075,
      "iv": 0.358,
      "rho": 0.012
    }
  ]
}
```

### Contract Object Fields

| Field | Type | Description | Notes |
|-------|------|-------------|-------|
| `symbol` | string | Underlying symbol | Always present |
| `expiry` | string | Expiration date (YYYY-MM-DD) | Always present |
| `strike` | number | Strike price | Always present |
| `type` | string | Option type: "call" or "put" | Always present |
| `bid` | number | Bid price | Always present |
| `ask` | number | Ask price | Always present |
| `last` | number | Last traded price | Always present |
| `volume` | integer | Trading volume | Always present |
| `open_interest` | integer | Open interest | Always present |
| `delta` | number | Delta Greek | Always present |
| `gamma` | number | Gamma Greek | Always present |
| `theta` | number | Theta Greek | Always present |
| `vega` | number | Vega Greek | Always present |
| `iv` | number | Implied volatility | Always present |
| `rho` | number \| null | **Rho Greek** | **Optional - may be null** |

---

## Rho Field Specification

### Field Details

- **Field Name:** `rho`
- **Type:** `number | null`
- **Required:** No (optional field)
- **Description:** Measures an option's sensitivity to changes in interest rates. Represents the expected change in option price for a 1% change in interest rates.

### When Rho is Available

- **Tradier (Primary Vendor):** Rho is provided when available in Tradier's greeks object
- **Massive/Polygon (Fallback):** Rho is always `null` (vendor does not provide it)

### When Rho is Null

Rho will be `null` in the following cases:

1. **Vendor doesn't provide it:** Massive/Polygon fallback is used
2. **Feature flag disabled:** `ENABLE_RHO_GREEK=false` (rare, for operational control)
3. **Vendor omits it:** Tradier response doesn't include rho in greeks object
4. **Invalid/missing data:** Vendor provides invalid or missing rho value

### Rho Value Characteristics

- **Type:** Floating-point number (typically 4-6 decimal places)
- **Range:** Usually between -0.1 and +0.1 for most options
- **Sign:** 
  - Positive for call options (price increases with rising rates)
  - Negative for put options (price decreases with rising rates)
- **Magnitude:** Larger for longer-term options (LEAPS)

---

## Examples

### Example 1: Contract with Rho (Tradier)

**Request:**
```bash
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18"
```

**Response:**
```json
{
  "symbol": "NFLX",
  "expiry": "2026-06-18",
  "contracts": [
    {
      "symbol": "NFLX",
      "expiry": "2026-06-18",
      "strike": 500.0,
      "type": "call",
      "delta": 0.565,
      "gamma": 0.057,
      "theta": -0.334,
      "vega": 0.075,
      "iv": 0.358,
      "rho": 0.012
    }
  ]
}
```

**Analysis:**
- `rho: 0.012` indicates a call option
- For a 1% interest rate increase, the option price would theoretically increase by $0.012 per share

### Example 2: Contract without Rho (Massive/Polygon Fallback)

**Request:**
```bash
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18"
```

**Response:**
```json
{
  "symbol": "NFLX",
  "expiry": "2026-06-18",
  "contracts": [
    {
      "symbol": "NFLX",
      "expiry": "2026-06-18",
      "strike": 500.0,
      "type": "call",
      "delta": 0.565,
      "gamma": 0.057,
      "theta": -0.334,
      "vega": 0.075,
      "iv": 0.358,
      "rho": null
    }
  ]
}
```

**Analysis:**
- `rho: null` indicates the vendor (Massive/Polygon) doesn't provide rho
- Client should display "N/A" or handle gracefully

### Example 3: Filtering Contracts by Rho Availability

**Request:**
```bash
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18" | jq '.contracts[] | select(.rho != null)'
```

**Response:**
```json
{
  "symbol": "NFLX",
  "strike": 500.0,
  "type": "call",
  "rho": 0.012
}
```

### Example 4: Extracting Only Greeks Including Rho

**Request:**
```bash
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18" | jq '.contracts[0] | {delta, gamma, theta, vega, iv, rho}'
```

**Response:**
```json
{
  "delta": 0.565,
  "gamma": 0.057,
  "theta": -0.334,
  "vega": 0.075,
  "iv": 0.358,
  "rho": 0.012
}
```

---

## Client Implementation Guidelines

### 1. Data Model

Always model `rho` as an optional/nullable field:

**TypeScript/JavaScript:**
```typescript
interface OptionContract {
  // ... other fields ...
  rho: number | null;
}
```

**Swift:**
```swift
struct OptionContract: Codable {
    // ... other fields ...
    let rho: Double?
}
```

**Python:**
```python
from typing import Optional

class OptionContract:
    # ... other fields ...
    rho: Optional[float]
```

### 2. Null Handling

**Always check for null before using rho:**

```javascript
// JavaScript/TypeScript
if (contract.rho !== null && contract.rho !== undefined) {
    console.log(`Rho: ${contract.rho}`);
} else {
    console.log("Rho: N/A");
}
```

```swift
// Swift
if let rho = contract.rho {
    print("Rho: \(rho)")
} else {
    print("Rho: N/A")
}
```

```python
# Python
if contract.rho is not None:
    print(f"Rho: {contract.rho}")
else:
    print("Rho: N/A")
```

### 3. Display Formatting

**Recommended display formats:**

- **When rho is available:** `"0.0120"` or `"+0.0120"` (4 decimal places)
- **When rho is null:** `"N/A"`, `"—"`, or `"Not Available"` (grayed out/secondary color)

### 4. Calculations

**Interest Rate Sensitivity:**

Rho represents the expected price change per 1% interest rate change:

```
Expected Price Change = rho × Interest Rate Change (in percentage points)
```

**Example:**
- Rho = 0.012
- Interest rate increases by 0.5%
- Expected price change = 0.012 × 0.5 = 0.006 ($0.006 per share)

---

## Error Handling

### Standard HTTP Status Codes

| Status Code | Meaning | Action |
|-------------|---------|--------|
| 200 | Success | Parse response, check for `rho` field |
| 400 | Bad Request | Check query parameters |
| 422 | Validation Error | Verify `symbol` and `expiry` format |
| 502 | Bad Gateway | Vendor API error, retry or show error |

### Response Validation

1. **Check response structure:** Ensure `contracts` array exists
2. **Check contract structure:** Ensure `rho` field exists (may be `null`)
3. **Type checking:** Verify `rho` is either a number or `null`, never missing

**Example validation:**

```javascript
function validateContract(contract) {
    if (!contract.hasOwnProperty('rho')) {
        throw new Error('Contract missing rho field');
    }
    if (contract.rho !== null && typeof contract.rho !== 'number') {
        throw new Error('Rho must be number or null');
    }
    return true;
}
```

---

## Best Practices

### 1. Always Handle Null

Never assume `rho` will be present. Always implement null-safe access patterns.

### 2. User Experience

- **Show rho when available:** Display the value with appropriate formatting
- **Graceful degradation:** When `rho` is `null`, show "N/A" or hide the field
- **Visual distinction:** Use secondary color/style for null values

### 3. Performance

- **Optional filtering:** If your app requires rho, filter contracts: `contracts.filter(c => c.rho !== null)`
- **Caching:** Cache chain responses; rho values update with each refresh

### 4. Testing

Test both scenarios:
- Contracts with rho (Tradier responses)
- Contracts without rho (Massive/Polygon fallback or when Tradier omits it)

---

## Rate Limiting

- **No additional rate limits** for accessing rho
- Same rate limits apply as the chain endpoint
- Rho is included in standard chain responses (no extra API calls)

---

## Versioning

- **API Version:** v1
- **Rho Support:** Available in all v1 chain responses
- **Backward Compatible:** Clients that don't read `rho` continue to work

---

## Vendor-Specific Behavior

### Tradier (Primary)

- **Rho Availability:** Provided when available in Tradier's greeks object
- **Typical Range:** -0.1 to +0.1
- **Update Frequency:** Real-time with chain refresh

### Massive/Polygon (Fallback)

- **Rho Availability:** Always `null` (vendor does not provide rho)
- **Behavior:** All contracts will have `rho: null` when using this vendor

---

## Quick Reference

### cURL Examples

```bash
# Get chain with rho
curl "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18"

# Extract only rho values
curl -s "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18" \
  | jq '.contracts[] | {strike, type, rho}'

# Filter contracts with rho
curl -s "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18" \
  | jq '.contracts[] | select(.rho != null)'

# Get first contract's Greeks including rho
curl -s "https://hm3q56yisx.us-east-1.awsapprunner.com/v1/markets/chain?symbol=NFLX&expiry=2026-06-18" \
  | jq '.contracts[0] | {delta, gamma, theta, vega, iv, rho}'
```

### Response Field Summary

```
GET /v1/markets/chain?symbol={SYMBOL}&expiry={YYYY-MM-DD}
  ↓
{
  "symbol": string,
  "expiry": string,
  "contracts": [
    {
      ...standard fields...,
      "delta": number,
      "gamma": number,
      "theta": number,
      "vega": number,
      "iv": number,
      "rho": number | null  ← NEW FIELD
    }
  ]
}
```

---

## Support

For questions or issues:
- Check API health: `GET /healthz`
- Check diagnostic info: `GET /v1/markets/quotes/diagnostic`
- Review API version: `GET /version`

---

**Last Updated:** 2024-11-21  
**API Version:** v1  
**Rho Support:** Available in all chain responses


