"""
orders.py
High-level order placement layer — sits between the CLI and the raw client.

Responsibilities:
  - Accept validated parameters
  - Call BinanceFuturesClient
  - Format and return a structured OrderResult
  - Print human-readable summaries
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from .client import BinanceFuturesClient, BinanceAPIError, BinanceNetworkError
from .logging_config import get_logger

logger = get_logger("orders")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class OrderResult:
    """Carries both the raw API response and derived display fields."""

    success: bool
    order_id: Optional[int] = None
    client_order_id: Optional[str] = None
    symbol: Optional[str] = None
    side: Optional[str] = None
    order_type: Optional[str] = None
    status: Optional[str] = None
    price: Optional[str] = None
    avg_price: Optional[str] = None
    orig_qty: Optional[str] = None
    executed_qty: Optional[str] = None
    time_in_force: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[int] = None
    error_message: Optional[str] = None

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "OrderResult":
        return cls(
            success=True,
            order_id=data.get("orderId"),
            client_order_id=data.get("clientOrderId"),
            symbol=data.get("symbol"),
            side=data.get("side"),
            order_type=data.get("type"),
            status=data.get("status"),
            price=data.get("price"),
            avg_price=data.get("avgPrice"),
            orig_qty=data.get("origQty"),
            executed_qty=data.get("executedQty"),
            time_in_force=data.get("timeInForce"),
            raw=data,
        )

    @classmethod
    def from_error(cls, error_code: int, error_message: str) -> "OrderResult":
        return cls(
            success=False,
            error_code=error_code,
            error_message=error_message,
        )

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def print_summary(self, request_params: Dict[str, Any]) -> None:
        """Print a formatted order summary to stdout."""
        sep = "─" * 52

        print(f"\n{'═' * 52}")
        print("  ORDER REQUEST SUMMARY")
        print(sep)
        for key, val in request_params.items():
            if val is not None:
                print(f"  {key:<16}: {val}")

        if self.success:
            print(f"\n{'═' * 52}")
            print("  ORDER RESPONSE")
            print(sep)
            fields = [
                ("Order ID",       self.order_id),
                ("Client Order ID",self.client_order_id),
                ("Symbol",         self.symbol),
                ("Side",           self.side),
                ("Type",           self.order_type),
                ("Status",         self.status),
                ("Price",          self.price),
                ("Avg Price",      self.avg_price),
                ("Orig Qty",       self.orig_qty),
                ("Executed Qty",   self.executed_qty),
                ("Time In Force",  self.time_in_force),
            ]
            for label, value in fields:
                if value is not None:
                    print(f"  {label:<16}: {value}")
            print(f"\n  ✅  Order placed successfully!")
        else:
            print(f"\n{'═' * 52}")
            print("  ORDER FAILED")
            print(sep)
            print(f"  Error Code   : {self.error_code}")
            print(f"  Error Message: {self.error_message}")
            print(f"\n  ❌  Order placement failed.")

        print(f"{'═' * 52}\n")

    def to_dict(self) -> Dict[str, Any]:
        """Serialise result to a plain dict (useful for logging / testing)."""
        return {
            "success": self.success,
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "status": self.status,
            "avg_price": self.avg_price,
            "executed_qty": self.executed_qty,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


# ---------------------------------------------------------------------------
# Order placement function
# ---------------------------------------------------------------------------

def place_order(
    client: BinanceFuturesClient,
    symbol: str,
    side: str,
    order_type: str,
    quantity: float,
    price: Optional[float] = None,
    stop_price: Optional[float] = None,
    time_in_force: str = "GTC",
    reduce_only: bool = False,
) -> OrderResult:
    """
    Place an order and return a structured OrderResult.

    Args:
        client:        Authenticated BinanceFuturesClient instance.
        symbol:        Trading symbol (e.g. "BTCUSDT").
        side:          "BUY" or "SELL".
        order_type:    "MARKET" | "LIMIT" | "STOP" | "STOP_MARKET".
        quantity:      Order size in base asset.
        price:         Limit price (required for LIMIT / STOP).
        stop_price:    Trigger price (required for STOP / STOP_MARKET).
        time_in_force: Default "GTC".
        reduce_only:   Reduce-only flag.

    Returns:
        OrderResult instance.
    """
    request_params = {
        "Symbol":      symbol,
        "Side":        side,
        "Type":        order_type,
        "Quantity":    quantity,
        "Price":       price,
        "Stop Price":  stop_price,
        "TimeInForce": time_in_force if order_type != "MARKET" else "N/A",
        "Reduce Only": reduce_only,
    }

    logger.info(
        "Order dispatch | %s",
        json.dumps({k: str(v) for k, v in request_params.items() if v is not None}),
    )

    try:
        response = client.place_order(
            symbol=symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            time_in_force=time_in_force,
            reduce_only=reduce_only,
        )
        result = OrderResult.from_api_response(response)
        logger.info(
            "Order success | id=%s status=%s executedQty=%s avgPrice=%s",
            result.order_id,
            result.status,
            result.executed_qty,
            result.avg_price,
        )

    except BinanceAPIError as exc:
        logger.error("BinanceAPIError | code=%s msg=%s", exc.code, exc.message)
        result = OrderResult.from_error(exc.code, exc.message)

    except BinanceNetworkError as exc:
        logger.error("BinanceNetworkError | %s", exc)
        result = OrderResult.from_error(-1, str(exc))

    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected error during order placement: %s", exc)
        result = OrderResult.from_error(-1, f"Unexpected error: {exc}")

    result.print_summary(request_params)
    return result
