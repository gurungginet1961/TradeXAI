# 🤖 Gold Futures Trading Bot

This project is an **AI-powered trading bot** designed to trade **Gold Futures (GC)** during the **New York session**.  
It uses a combination of **EMA alignment, MACD momentum, and Volume confirmation** to generate high-probability buy/sell signals.  
The bot trades **only one contract per signal** with strict risk management.

---

## 📊 Strategy Overview

- **Market:** COMEX Gold Futures (GC)  
- **Session:** New York (08:30 – 16:00 EST)  
- **Indicators:** EMA (9, 21, 60, 200), MACD, VWAP, Volume  
- **Trade Size:** 1 contract only  
- **Risk Management:** 15% max loss per contract, 1:3 risk/reward  

---

### ✅ Buy (Long) Conditions
- **HTF (1H/4H) trend bullish**  
  - Price above EMA200  
  - MACD histogram > 0  
- **LTF (5m/15m) setup**  
  - EMA alignment: EMA9 > EMA21 > EMA60  
  - Price closes above EMA21 and VWAP  
  - Strong bullish candle (close > open)  
- **Volume confirmation**  
  - Volume > 20-period SMA of volume  
- **Action** → Enter **Buy 1 contract**  

---

### ❌ Sell (Short) Conditions
- **HTF (1H/4H) trend bearish**  
  - Price below EMA200  
  - MACD histogram < 0  
- **LTF (5m/15m) setup**  
  - EMA alignment: EMA9 < EMA21 < EMA60  
  - Price closes below EMA21 and VWAP  
  - Strong bearish candle (close < open)  
- **Volume confirmation**  
  - Volume > 20-period SMA of volume  
- **Action** → Enter **Sell 1 contract**  

---

### 🏁 Exit Conditions
- **Risk Management**
  - Stop-loss: 15% max loss on contract  
  - Take-profit: 1:3 Risk/Reward  
- **Technical Exit**
  - MACD flips direction  
  - Price closes across EMA9 opposite to trade  
- **Session Exit**
  - Force close all positions at **16:00 EST**  

---

### ⚠️ Filters
- No trades if price is within ±0.5% of EMA200 (chop zone)  
- Skip if ADX < 20 on HTF (weak trend)  
- Avoid during high-impact news (NFP, CPI, FOMC)


