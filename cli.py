#!/usr/bin/env python3
"""
cli.py — Command-line entry point for the Binance Futures Testnet Trading Bot.

Usage modes
-----------
1. Direct flags (non-interactive):
   python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

2. Interactive guided menu (bonus UX):
   python cli.py interactive

3. Account info:
   python cli.py account

4. Open orders:
   python cli.py open-orders --symbol BTCUSDT

Environment variables (preferred over hardcoding keys):
   BINANCE_TESTNET_API_KEY
   BINANCE_TESTNET_API_SECRET

Or pass via CLI flags:
   --api-key   YOUR_KEY
   --api-secret YOUR_SECRET
"""

from __future__ import annotations

import argparse
import os
import sys
import json

from bot import (
    BinanceFuturesClient,
    BinanceAPIError,
    BinanceNetworkError,
    place_order,
    validate_all,
    ValidationError,
    setup_logging,
    get_logger,
)

# ---------------------------------------------------------------------------
# Logger (initialised after arg parsing so --log-level works)
# ---------------------------------------------------------------------------
logger = None  # set in main()


# ---------------------------------------------------------------------------
# Helper: build client from args / env
# ---------------------------------------------------------------------------

def _build_client(args: argparse.Namespace) -> BinanceFuturesClient:
    api_key = args.api_key or os.getenv("BINANCE_TESTNET_API_KEY", "")
    api_secret = args.api_secret or os.getenv("BINANCE_TESTNET_API_SECRET", "")

    if not api_key or not api_secret:
        print(
            "\n❌  API credentials not found.\n"
            "    Set them via:\n"
            "      export BINANCE_TESTNET_API_KEY=<key>\n"
            "      export BINANCE_TESTNET_API_SECRET=<secret>\n"
            "    or pass --api-key / --api-secret flags.\n"
        )
        sys.exit(1)

    return BinanceFuturesClient(api_key=api_key, api_secret=api_secret)


# ---------------------------------------------------------------------------
# Sub-command handlers
# ---------------------------------------------------------------------------

def cmd_place(args: argparse.Namespace) -> int:
    """Handle the 'place' sub-command."""
    try:
        params = validate_all(
            symbol=args.symbol,
            side=args.side,
            order_type=args.type,
            quantity=args.qty,
            price=args.price,
            stop_price=getattr(args, "stop_price", None),
        )
    except ValidationError as exc:
        print(f"\n❌  Validation Error: {exc}\n")
        logger.error("Validation failed: %s", exc)
        return 1

    client = _build_client(args)

    # Connectivity check
    if not client.ping():
        print("\n⚠️   Could not reach Binance Testnet. Check your internet connection.\n")
        return 1

    result = place_order(
        client=client,
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params["price"],
        stop_price=params["stop_price"],
        time_in_force=args.tif,
        reduce_only=args.reduce_only,
    )

    return 0 if result.success else 1


def cmd_account(args: argparse.Namespace) -> int:
    """Print account balances."""
    client = _build_client(args)
    try:
        info = client.get_account()
        balances = [a for a in info.get("assets", []) if float(a.get("walletBalance", 0)) > 0]
        print(f"\n{'═' * 52}")
        print("  ACCOUNT BALANCES")
        print(f"{'─' * 52}")
        if not balances:
            print("  No non-zero balances found.")
        for asset in balances:
            print(
                f"  {asset['asset']:<10} wallet={asset['walletBalance']:>14}  "
                f"unrealised PnL={asset.get('unrealizedProfit', '0'):>12}"
            )
        print(f"{'═' * 52}\n")
        return 0
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(f"\n❌  {exc}\n")
        logger.error("Account fetch failed: %s", exc)
        return 1


def cmd_open_orders(args: argparse.Namespace) -> int:
    """List open orders."""
    client = _build_client(args)
    symbol = getattr(args, "symbol", None)
    try:
        orders = client.get_open_orders(symbol=symbol)
        print(f"\n{'═' * 52}")
        print(f"  OPEN ORDERS{' for ' + symbol if symbol else ''}")
        print(f"{'─' * 52}")
        if not orders:
            print("  No open orders.")
        for o in orders:
            print(
                f"  [{o['orderId']}] {o['side']} {o['type']} | "
                f"qty={o['origQty']} price={o['price']} status={o['status']}"
            )
        print(f"{'═' * 52}\n")
        return 0
    except (BinanceAPIError, BinanceNetworkError) as exc:
        print(f"\n❌  {exc}\n")
        logger.error("Open orders fetch failed: %s", exc)
        return 1


# ---------------------------------------------------------------------------
# Interactive (bonus UX) mode
# ---------------------------------------------------------------------------

def _prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    val = input(f"  {label}{suffix}: ").strip()
    return val if val else default


def _select(label: str, options: list[str]) -> str:
    print(f"\n  {label}:")
    for i, opt in enumerate(options, 1):
        print(f"    {i}. {opt}")
    while True:
        raw = input("  Choose [1-{}]: ".format(len(options))).strip()
        if raw.isdigit() and 1 <= int(raw) <= len(options):
            return options[int(raw) - 1]
        print(f"  ⚠️   Please enter a number between 1 and {len(options)}.")


def cmd_interactive(args: argparse.Namespace) -> int:
    """Guided interactive order placement."""
    print(f"\n{'═' * 52}")
    print("  🤖  Binance Futures Testnet — Interactive Mode")
    print(f"{'═' * 52}")

    # Credentials (env or prompt)
    api_key = os.getenv("BINANCE_TESTNET_API_KEY") or input("\n  API Key    : ").strip()
    api_secret = os.getenv("BINANCE_TESTNET_API_SECRET") or input("  API Secret : ").strip()

    if not api_key or not api_secret:
        print("\n❌  Credentials cannot be empty.\n")
        return 1

    # Temporarily inject into args for _build_client
    args.api_key = api_key
    args.api_secret = api_secret

    client = BinanceFuturesClient(api_key=api_key, api_secret=api_secret)
    print("\n  🔗 Connecting to testnet …", end=" ", flush=True)
    if not client.ping():
        print("FAILED\n  ❌  Cannot reach Binance Testnet.\n")
        return 1
    print("OK ✅\n")

    symbol = _prompt("Symbol (e.g. BTCUSDT)", "BTCUSDT").upper()
    side = _select("Side", ["BUY", "SELL"])
    order_type = _select("Order Type", ["MARKET", "LIMIT", "STOP_MARKET", "STOP"])
    qty_raw = _prompt("Quantity")
    price_raw = None
    stop_price_raw = None

    if order_type in ("LIMIT", "STOP"):
        price_raw = _prompt("Price")
    if order_type in ("STOP", "STOP_MARKET"):
        stop_price_raw = _prompt("Stop/Trigger Price")

    tif = "GTC"
    if order_type in ("LIMIT", "STOP"):
        tif = _select("Time In Force", ["GTC", "IOC", "FOK"])

    reduce_only_raw = _select("Reduce Only?", ["No", "Yes"])
    reduce_only = reduce_only_raw == "Yes"

    # Validate
    try:
        params = validate_all(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=qty_raw,
            price=price_raw if price_raw else None,
            stop_price=stop_price_raw if stop_price_raw else None,
        )
    except ValidationError as exc:
        print(f"\n  ❌  Validation Error: {exc}\n")
        logger.error("Interactive validation failed: %s", exc)
        return 1

    # Confirm
    print(f"\n{'─' * 52}")
    print("  Confirm Order:")
    print(f"    Symbol   : {params['symbol']}")
    print(f"    Side     : {params['side']}")
    print(f"    Type     : {params['order_type']}")
    print(f"    Qty      : {params['quantity']}")
    if params["price"]:
        print(f"    Price    : {params['price']}")
    if params["stop_price"]:
        print(f"    StopPrice: {params['stop_price']}")
    print(f"    TIF      : {tif}")
    print(f"    ReduceOnly: {reduce_only}")

    confirm = input("\n  Proceed? (yes/no): ").strip().lower()
    if confirm not in ("yes", "y"):
        print("  ⚠️   Order cancelled by user.\n")
        return 0

    result = place_order(
        client=client,
        symbol=params["symbol"],
        side=params["side"],
        order_type=params["order_type"],
        quantity=params["quantity"],
        price=params["price"],
        stop_price=params["stop_price"],
        time_in_force=tif,
        reduce_only=reduce_only,
    )
    return 0 if result.success else 1


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading_bot",
        description="Binance Futures Testnet Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Market BUY
  python cli.py place --symbol BTCUSDT --side BUY --type MARKET --qty 0.01

  # Limit SELL
  python cli.py place --symbol ETHUSDT --side SELL --type LIMIT --qty 0.1 --price 3500

  # Stop-Limit BUY
  python cli.py place --symbol BTCUSDT --side BUY --type STOP \\
                      --qty 0.01 --price 95000 --stop-price 94500

  # Interactive mode
  python cli.py interactive

  # Account balances
  python cli.py account

  # Open orders for BTCUSDT
  python cli.py open-orders --symbol BTCUSDT
        """,
    )

    # Global flags
    parser.add_argument("--api-key",    default="", help="Binance Testnet API key")
    parser.add_argument("--api-secret", default="", help="Binance Testnet API secret")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Console log verbosity (default: INFO)",
    )

    sub = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    # ── place ──────────────────────────────────────────────────────────────
    place_p = sub.add_parser("place", help="Place a new order")
    place_p.add_argument("--symbol",     required=True, help="Trading pair (e.g. BTCUSDT)")
    place_p.add_argument("--side",       required=True, choices=["BUY", "SELL"])
    place_p.add_argument("--type",       required=True,
                         choices=["MARKET", "LIMIT", "STOP", "STOP_MARKET"],
                         metavar="TYPE", help="MARKET | LIMIT | STOP | STOP_MARKET")
    place_p.add_argument("--qty",        required=True, type=float, help="Order quantity")
    place_p.add_argument("--price",      type=float, default=None,
                         help="Limit price (required for LIMIT/STOP)")
    place_p.add_argument("--stop-price", type=float, default=None, dest="stop_price",
                         help="Stop/trigger price (required for STOP/STOP_MARKET)")
    place_p.add_argument("--tif",        default="GTC", choices=["GTC", "IOC", "FOK"],
                         help="Time in force (default: GTC)")
    place_p.add_argument("--reduce-only", action="store_true", dest="reduce_only",
                         help="Reduce-only order flag")

    # ── interactive ────────────────────────────────────────────────────────
    sub.add_parser("interactive", help="Guided interactive order placement (bonus UX)")

    # ── account ────────────────────────────────────────────────────────────
    sub.add_parser("account", help="Show account balances")

    # ── open-orders ────────────────────────────────────────────────────────
    oo_p = sub.add_parser("open-orders", help="List open orders")
    oo_p.add_argument("--symbol", default=None, help="Filter by symbol")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

COMMAND_MAP = {
    "place":        cmd_place,
    "interactive":  cmd_interactive,
    "account":      cmd_account,
    "open-orders":  cmd_open_orders,
}


def main() -> None:
    global logger
    parser = build_parser()
    args = parser.parse_args()

    setup_logging(args.log_level)
    logger = get_logger("cli")
    logger.info("Command: %s", args.command)

    handler = COMMAND_MAP.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
