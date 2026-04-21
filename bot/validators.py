"""
validators.py
All CLI / user-input validation lives here — keeps cli.py and orders.py clean.
"""

from __future__ import annotations

from typing import Optional

from .logging_config import get_logger

logger = get_logger("validators")

VALID_SIDES = {"BUY", "SELL"}
VALID_ORDER_TYPES = {"MARKET", "LIMIT", "STOP_MARKET", "STOP"}

# Minimum notional / qty sanity guards (rough; real limits come from exchange)
MIN_QUANTITY = 0.001
MAX_QUANTITY = 10_000.0
MIN_PRICE = 0.01


class ValidationError(ValueError):
    """Raised when user input fails validation."""


def validate_symbol(symbol: str) -> str:
    """Normalise and validate trading symbol."""
    symbol = symbol.strip().upper()
    if len(symbol) < 3:
        raise ValidationError(f"Symbol '{symbol}' is too short.")
    if not symbol.isalnum():
        raise ValidationError(
            f"Symbol '{symbol}' contains invalid characters. Use alphanumerics only (e.g. BTCUSDT)."
        )
    logger.debug("Symbol validated: %s", symbol)
    return symbol


def validate_side(side: str) -> str:
    """Validate and normalise order side."""
    side = side.strip().upper()
    if side not in VALID_SIDES:
        raise ValidationError(
            f"Side '{side}' is invalid. Choose from: {', '.join(sorted(VALID_SIDES))}."
        )
    logger.debug("Side validated: %s", side)
    return side


def validate_order_type(order_type: str) -> str:
    """Validate and normalise order type."""
    order_type = order_type.strip().upper()
    if order_type not in VALID_ORDER_TYPES:
        raise ValidationError(
            f"Order type '{order_type}' is not supported. "
            f"Choose from: {', '.join(sorted(VALID_ORDER_TYPES))}."
        )
    logger.debug("Order type validated: %s", order_type)
    return order_type


def validate_quantity(quantity: str | float) -> float:
    """Validate order quantity."""
    try:
        qty = float(quantity)
    except (TypeError, ValueError):
        raise ValidationError(f"Quantity '{quantity}' is not a valid number.")
    if qty <= 0:
        raise ValidationError("Quantity must be greater than zero.")
    if qty < MIN_QUANTITY:
        raise ValidationError(f"Quantity {qty} is below the minimum allowed ({MIN_QUANTITY}).")
    if qty > MAX_QUANTITY:
        raise ValidationError(f"Quantity {qty} exceeds the maximum allowed ({MAX_QUANTITY}).")
    logger.debug("Quantity validated: %s", qty)
    return qty


def validate_price(price: str | float | None, order_type: str) -> Optional[float]:
    """
    Validate price field.

    * Required for LIMIT and STOP orders.
    * Ignored (and set to None) for MARKET orders.
    """
    order_type = order_type.strip().upper()

    if order_type == "MARKET":
        if price is not None:
            logger.warning(
                "Price '%s' supplied for MARKET order — it will be ignored.", price
            )
        return None

    # LIMIT / STOP require a price
    if price is None:
        raise ValidationError(
            f"Price is required for {order_type} orders. Pass it with --price."
        )
    try:
        p = float(price)
    except (TypeError, ValueError):
        raise ValidationError(f"Price '{price}' is not a valid number.")
    if p < MIN_PRICE:
        raise ValidationError(
            f"Price {p} is below the minimum allowed ({MIN_PRICE})."
        )
    logger.debug("Price validated: %s", p)
    return p


def validate_stop_price(stop_price: str | float | None, order_type: str) -> Optional[float]:
    """Validate stopPrice — required for STOP / STOP_MARKET orders."""
    order_type = order_type.strip().upper()
    if order_type not in {"STOP", "STOP_MARKET"}:
        return None
    if stop_price is None:
        raise ValidationError(
            f"--stop-price is required for {order_type} orders."
        )
    try:
        sp = float(stop_price)
    except (TypeError, ValueError):
        raise ValidationError(f"Stop price '{stop_price}' is not a valid number.")
    if sp < MIN_PRICE:
        raise ValidationError(f"Stop price {sp} is below minimum ({MIN_PRICE}).")
    logger.debug("Stop price validated: %s", sp)
    return sp


def validate_all(
    symbol: str,
    side: str,
    order_type: str,
    quantity: str | float,
    price: str | float | None = None,
    stop_price: str | float | None = None,
) -> dict:
    """
    Run all validators in one call.

    Returns:
        dict: Cleaned / normalised parameter dict ready for order placement.
    """
    return {
        "symbol": validate_symbol(symbol),
        "side": validate_side(side),
        "order_type": validate_order_type(order_type),
        "quantity": validate_quantity(quantity),
        "price": validate_price(price, order_type),
        "stop_price": validate_stop_price(stop_price, order_type),
    }
