# 🤖 Binance Futures Testnet Trading Bot

A clean, production-style Python CLI trading bot that places **Market**, **Limit**, and **Stop-Limit** orders on the Binance USDT-M Futures Testnet.

---

## ✨ Features

| Feature | Detail |
|---|---|
| Order Types | MARKET · LIMIT · STOP-LIMIT · STOP_MARKET |
| Sides | BUY · SELL |
| Input | Argparse CLI flags **or** guided interactive menu |
| Logging | Rotating file log + console, structured format |
| Error Handling | Validation errors, API errors, network failures |
| Structure | Layered: `client.py` → `orders.py` → `cli.py` |

---

## 📁 Project Structure

```
trading_bot/
├── bot/
│   ├── __init__.py          # Package exports
│   ├── client.py            # Binance REST client (signing, retries, error handling)
│   ├── orders.py            # Order placement + structured OrderResult
│   ├── validators.py        # All input validation logic
│   └── logging_config.py   # Rotating file + console logger
├── cli.py                   # CLI entry point (argparse)
├── logs/
│   └── trading_bot.log      # Auto-created on first run
├── README.md
└── requirements.txt
```

---

## ⚙️ Setup

### 1. Clone / unzip the project

```bash
git clone https://github.com/<your-username>/trading-bot.git
cd trading-bot
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate.bat     # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Get Binance Futures Testnet credentials

1. Visit [https://testnet.binancefuture.com](https://testnet.binancefuture.com)
2. Log in with your GitHub account.
3. Go to **API Key** tab → click **Generate Key**.
4. Copy your **API Key** and **Secret Key**.

### 5. Set environment variables (recommended — avoids hardcoding)

```bash
export BINANCE_TESTNET_API_KEY="your_api_key_here"
export BINANCE_TESTNET_API_SECRET="your_api_secret_here"
```

Alternatively, pass `--api-key` and `--api-secret` flags to every command.

---

## 🚀 How to Run

### Place a MARKET order (BUY)

```bash
python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
```

### Place a LIMIT order (SELL)

```bash
python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 3500
```

### Place a Stop-Limit order (BUY) [Bonus]

```bash
python cli.py place --symbol BTCUSDT --side BUY --type STOP \
    --qty 0.01 --price 96500 --stop-price 96000
```

### Place a Stop-Market order (SELL) [Bonus]

```bash
python cli.py place --symbol BTCUSDT --side SELL --type STOP_MARKET \
    --qty 0.01 --stop-price 90000
```

### Interactive guided mode (Bonus UX)

```bash
python cli.py interactive
```

> Walks you through symbol → side → type → quantity → price → confirmation with numbered menus.

### View account balances

```bash
python cli.py account
```

### View open orders

```bash
python cli.py open-orders --symbol BTCUSDT
```

### Verbose debug logging to console

```bash
python cli.py --log-level DEBUG place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01
```

---

## 📤 Sample Output

```
════════════════════════════════════════════════════
  ORDER REQUEST SUMMARY
────────────────────────────────────────────────────
  Symbol          : BTCUSDT
  Side            : BUY
  Type            : MARKET
  Quantity        : 0.01
  TimeInForce     : N/A

════════════════════════════════════════════════════
  ORDER RESPONSE
────────────────────────────────────────────────────
  Order ID        : 4751829
  Client Order ID : x-E9BIQR2Fe7c4f3a1
  Symbol          : BTCUSDT
  Side            : BUY
  Type            : MARKET
  Status          : FILLED
  Avg Price       : 97342.10
  Orig Qty        : 0.01
  Executed Qty    : 0.01

  ✅  Order placed successfully!
════════════════════════════════════════════════════
```

---

## 📋 CLI Reference

```
python cli.py [--api-key KEY] [--api-secret SECRET] [--log-level LEVEL] COMMAND

Commands:
  place           Place a new order
  interactive     Guided interactive order placement
  account         Show account balances
  open-orders     List open orders

place flags:
  --symbol        Trading pair, e.g. BTCUSDT     (required)
  --side          BUY or SELL                     (required)
  --type          MARKET | LIMIT | STOP | STOP_MARKET (required)
  --qty           Order quantity                  (required)
  --price         Limit price (LIMIT/STOP orders)
  --stop-price    Trigger price (STOP/STOP_MARKET)
  --tif           GTC | IOC | FOK  (default: GTC)
  --reduce-only   Flag to reduce position only
```

---

## 📝 Assumptions

- All orders are placed on the **USDT-M Futures Testnet** (`https://testnet.binancefuture.com`).
- `positionSide` defaults to `BOTH` (one-way mode). If your account uses hedge mode, pass `positionSide` manually by extending `client.place_order`.
- Quantity precision is not auto-adjusted to exchange step-size rules; for production use, fetch `LOT_SIZE` filter from `/fapi/v1/exchangeInfo` and round accordingly.
- The bot uses **synchronous** HTTP (no asyncio) — sufficient for CLI / testnet use.
- Stop-Limit (`STOP`) orders require both `--price` (limit fill price) and `--stop-price` (trigger price).

---

## 📦 Dependencies

```
requests>=2.31.0
urllib3>=2.0.0
```

Only the standard library + `requests` — no heavy SDKs required.

---

## 🪵 Log Files

Logs are written to `logs/trading_bot.log` automatically.  
The file rotates at 5 MB with 3 backups kept.

Sample log entries are included in `logs/trading_bot.log` covering:
- A successful MARKET BUY (BTCUSDT, status: FILLED)
- A successful LIMIT SELL (ETHUSDT, status: NEW)
- A successful STOP-LIMIT BUY (BTCUSDT, status: NEW)
- A failed MARKET order (invalid symbol → API error -1121)

---

## 🔧 Extending the Bot

| Goal | Where to change |
|---|---|
| Add a new order type | `validators.py` (`VALID_ORDER_TYPES`) + `client.py` (`place_order`) |
| Change testnet URL | `client.py` → `TESTNET_BASE_URL` constant |
| Add WebSocket price feed | New `bot/stream.py` module |
| Switch to async | Replace `requests` with `httpx[asyncio]` in `client.py` |
