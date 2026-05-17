# iOS Client Update: Adding Rho Greek Support

## Overview

The options chain API now includes the `rho` Greek in contract responses. Rho measures an option's sensitivity to changes in interest rates. This guide shows how to update your iOS client to handle the new `rho` field.

**Key Points:**
- `rho` is **optional** and may be `null` (vendor-provided only)
- Tradier provides rho; Massive/Polygon does not
- When `rho` is `null`, it means the vendor doesn't provide it or the feature flag is disabled
- Your app should gracefully handle `null` rho values

---

## 1. Update Data Models

### Option Contract Model

Add `rho` as an optional `Double?` field to your contract model:

```swift
import Foundation

struct OptionContract: Codable {
    let symbol: String
    let expiry: String
    let strike: Double
    let type: String  // "call" or "put"
    let bid: Double
    let ask: Double
    let last: Double
    let volume: Int
    let openInterest: Int
    
    // Greeks
    let delta: Double
    let gamma: Double
    let theta: Double
    let vega: Double
    let iv: Double  // Implied volatility
    let rho: Double?  // NEW: Optional rho (may be nil)
    
    enum CodingKeys: String, CodingKey {
        case symbol
        case expiry
        case strike
        case type
        case bid
        case ask
        case last
        case volume
        case openInterest = "open_interest"
        case delta
        case gamma
        case theta
        case vega
        case iv
        case rho
    }
}

struct OptionsChainResponse: Codable {
    let symbol: String
    let expiry: String
    let contracts: [OptionContract]
}
```

### If Using Separate Greeks Model

If you have a separate `Greeks` struct:

```swift
struct Greeks: Codable {
    let delta: Double
    let gamma: Double
    let theta: Double
    let vega: Double
    let iv: Double
    let rho: Double?  // NEW: Optional rho
}

struct OptionContract: Codable {
    // ... other fields ...
    let greeks: Greeks
}
```

---

## 2. API Response Example

The API response now includes `rho` (which may be `null`):

```json
{
  "symbol": "AAPL",
  "expiry": "2025-11-28",
  "contracts": [
    {
      "symbol": "AAPL",
      "expiry": "2025-11-28",
      "strike": 175.0,
      "type": "call",
      "bid": 5.50,
      "ask": 5.60,
      "last": 5.55,
      "volume": 1000,
      "open_interest": 5000,
      "delta": 0.565,
      "gamma": 0.057,
      "theta": -0.334,
      "vega": 0.075,
      "iv": 0.358,
      "rho": 0.012  // Present when Tradier provides it
    },
    {
      "symbol": "AAPL",
      "expiry": "2025-11-28",
      "strike": 180.0,
      "type": "put",
      "bid": 4.50,
      "ask": 4.60,
      "last": 4.55,
      "volume": 800,
      "open_interest": 4000,
      "delta": -0.435,
      "gamma": 0.057,
      "theta": -0.334,
      "vega": 0.075,
      "iv": 0.358,
      "rho": null  // null when vendor doesn't provide it
    }
  ]
}
```

---

## 3. Displaying Rho in UI

### Safe Display Helper

Create a helper to safely format rho for display:

```swift
extension OptionContract {
    /// Returns formatted rho string, or "N/A" if rho is nil
    var rhoDisplayString: String {
        guard let rho = rho else {
            return "N/A"
        }
        return String(format: "%.4f", rho)
    }
    
    /// Returns rho with sign indicator
    var rhoFormatted: String {
        guard let rho = rho else {
            return "—"
        }
        let sign = rho >= 0 ? "+" : ""
        return String(format: "%@%.4f", sign, rho)
    }
    
    /// Returns true if rho is available
    var hasRho: Bool {
        return rho != nil
    }
}
```

### SwiftUI Example

```swift
import SwiftUI

struct GreeksView: View {
    let contract: OptionContract
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Delta:")
                Spacer()
                Text(String(format: "%.4f", contract.delta))
            }
            
            HStack {
                Text("Gamma:")
                Spacer()
                Text(String(format: "%.4f", contract.gamma))
            }
            
            HStack {
                Text("Theta:")
                Spacer()
                Text(String(format: "%.4f", contract.theta))
            }
            
            HStack {
                Text("Vega:")
                Spacer()
                Text(String(format: "%.4f", contract.vega))
            }
            
            HStack {
                Text("IV:")
                Spacer()
                Text(String(format: "%.2f%%", contract.iv * 100))
            }
            
            // NEW: Rho display with null handling
            HStack {
                Text("Rho:")
                Spacer()
                if let rho = contract.rho {
                    Text(String(format: "%.4f", rho))
                        .foregroundColor(.primary)
                } else {
                    Text("N/A")
                        .foregroundColor(.secondary)
                        .italic()
                }
            }
        }
        .font(.system(.body, design: .monospaced))
    }
}
```

### UIKit Example

```swift
func configureGreeksCell(for contract: OptionContract) {
    deltaLabel.text = String(format: "%.4f", contract.delta)
    gammaLabel.text = String(format: "%.4f", contract.gamma)
    thetaLabel.text = String(format: "%.4f", contract.theta)
    vegaLabel.text = String(format: "%.4f", contract.vega)
    ivLabel.text = String(format: "%.2f%%", contract.iv * 100)
    
    // NEW: Handle optional rho
    if let rho = contract.rho {
        rhoLabel.text = String(format: "%.4f", rho)
        rhoLabel.textColor = .label
    } else {
        rhoLabel.text = "N/A"
        rhoLabel.textColor = .secondaryLabel
        rhoLabel.font = .italicSystemFont(ofSize: rhoLabel.font.pointSize)
    }
}
```

---

## 4. Filtering/Sorting by Rho

### Filter Contracts with Rho Available

```swift
// Get only contracts that have rho data
let contractsWithRho = contracts.filter { $0.rho != nil }

// Get contracts without rho (e.g., from Massive/Polygon fallback)
let contractsWithoutRho = contracts.filter { $0.rho == nil }
```

### Sort by Rho

```swift
// Sort by rho (ascending), handling nil values
let sortedByRho = contracts.sorted { contract1, contract2 in
    guard let rho1 = contract1.rho, let rho2 = contract2.rho else {
        // Put contracts without rho at the end
        if contract1.rho == nil && contract2.rho != nil { return false }
        if contract1.rho != nil && contract2.rho == nil { return true }
        return false
    }
    return rho1 < rho2
}
```

---

## 5. Calculations Using Rho

### Interest Rate Sensitivity

Rho represents the expected change in option price for a 1% change in interest rates:

```swift
extension OptionContract {
    /// Calculate expected price change for a given interest rate change
    /// - Parameter rateChangePercent: Interest rate change in percentage points (e.g., 0.5 for 0.5%)
    /// - Returns: Expected price change, or nil if rho is not available
    func expectedPriceChangeForRateChange(_ rateChangePercent: Double) -> Double? {
        guard let rho = rho else { return nil }
        return rho * rateChangePercent
    }
    
    /// Example: If rho is 0.012 and rates increase by 0.5%, 
    /// expected price change = 0.012 * 0.5 = 0.006 (0.6 cents per share)
}

// Usage
if let priceChange = contract.expectedPriceChangeForRateChange(0.5) {
    print("Expected price change for 0.5% rate increase: \(priceChange)")
}
```

---

## 6. Migration Guide

### Backward Compatibility

Since `rho` is optional, your existing code will continue to work without changes. However, to take advantage of rho:

1. **Update Models**: Add `rho: Double?` to your contract model
2. **Update UI**: Add rho display where you show other Greeks
3. **Handle Nulls**: Use optional binding (`if let`) or nil coalescing (`??`) when accessing rho

### Gradual Rollout

You can gradually add rho support:

```swift
// Phase 1: Just decode it (no UI changes)
let rho: Double?  // Already in model

// Phase 2: Add to debug/advanced view
if showAdvancedGreeks {
    // Display rho
}

// Phase 3: Add to main UI
// Show rho alongside other Greeks
```

---

## 7. Testing

### Test Cases

```swift
func testRhoDecoding() {
    // Test with rho present
    let jsonWithRho = """
    {
        "symbol": "AAPL",
        "strike": 175.0,
        "type": "call",
        "delta": 0.5,
        "gamma": 0.02,
        "theta": -0.05,
        "vega": 0.15,
        "iv": 0.25,
        "rho": 0.012
    }
    """.data(using: .utf8)!
    
    let contract = try! JSONDecoder().decode(OptionContract.self, from: jsonWithRho)
    XCTAssertEqual(contract.rho, 0.012)
    
    // Test with rho null
    let jsonWithoutRho = """
    {
        "symbol": "AAPL",
        "strike": 175.0,
        "type": "call",
        "delta": 0.5,
        "gamma": 0.02,
        "theta": -0.05,
        "vega": 0.15,
        "iv": 0.25,
        "rho": null
    }
    """.data(using: .utf8)!
    
    let contractNoRho = try! JSONDecoder().decode(OptionContract.self, from: jsonWithoutRho)
    XCTAssertNil(contractNoRho.rho)
}
```

---

## 8. Best Practices

1. **Always Check for Nil**: Never force-unwrap rho (`contract.rho!`). Use optional binding or nil coalescing.

2. **User-Friendly Display**: When rho is `null`, show "N/A", "—", or gray it out rather than showing "0.0000".

3. **Context Matters**: Rho is more relevant for longer-term options. Consider showing it prominently for LEAPS (Long-Term Equity Anticipation Securities).

4. **Performance**: Rho calculations are lightweight, but filtering/sorting large arrays with optional values should be optimized.

5. **Error Handling**: If your app requires rho for certain features, gracefully degrade when it's unavailable.

---

## 9. Example: Complete Contract View

```swift
struct OptionContractDetailView: View {
    let contract: OptionContract
    
    var body: some View {
        Form {
            Section(header: Text("Pricing")) {
                LabeledContent("Bid", value: String(format: "$%.2f", contract.bid))
                LabeledContent("Ask", value: String(format: "$%.2f", contract.ask))
                LabeledContent("Last", value: String(format: "$%.2f", contract.last))
            }
            
            Section(header: Text("Greeks")) {
                LabeledContent("Delta", value: String(format: "%.4f", contract.delta))
                LabeledContent("Gamma", value: String(format: "%.4f", contract.gamma))
                LabeledContent("Theta", value: String(format: "%.4f", contract.theta))
                LabeledContent("Vega", value: String(format: "%.4f", contract.vega))
                LabeledContent("IV", value: String(format: "%.2f%%", contract.iv * 100))
                
                // NEW: Rho with conditional display
                HStack {
                    Text("Rho")
                    Spacer()
                    if let rho = contract.rho {
                        Text(String(format: "%.4f", rho))
                            .foregroundColor(.primary)
                    } else {
                        Text("N/A")
                            .foregroundColor(.secondary)
                            .italic()
                    }
                }
            }
        }
        .navigationTitle("\(contract.symbol) \(contract.type.capitalized)")
    }
}
```

---

## Summary

- Add `rho: Double?` to your `OptionContract` model
- Use optional binding (`if let`) when accessing rho
- Display "N/A" or "—" when rho is `null`
- Test with both null and non-null rho values
- Your existing code will continue to work (backward compatible)

The rho field is now available in all options chain responses. Update your models and UI to take advantage of this new data!


