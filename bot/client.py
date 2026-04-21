"""
client.py
Low-level Binance Futures Testnet REST client.

Handles:
  - HMAC-SHA256 request signing
  - Timestamp synchronisation
  - HTTP request dispatch with retry
  - Raw API error surfacing
"""

from __future__ import annotations

import hashlib
import hmac
import time
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .logging_config import get_logger

logger = get_logger("client")

TESTNET_BASE_URL = "https://testnet.binancefuture.com"
DEFAULT_TIMEOUT = 10  # seconds


class BinanceAPIError(Exception):
    """Wraps a Binance API error response."""

    def __init__(self, code: int, message: str, status_code: int = 0):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(f"Binance API Error {code}: {message}")


class BinanceNetworkError(ConnectionError):
    """Raised on connectivity / timeout failures."""


class BinanceFuturesClient:
    """
    Minimal async-free Binance USDT-M Futures REST client.

    Args:
        api_key:    Testnet API key.
        api_secret: Testnet API secret.
        base_url:   Override base URL (default: testnet).
        timeout:    Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        api_secret: str,
        base_url: str = TESTNET_BASE_URL,
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_secret:
            raise ValueError("Both api_key and api_secret must be provided.")
        self._api_key = api_key
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._session = self._build_session()
        self._time_offset_ms = 0
        logger.info("BinanceFuturesClient initialised — base URL: %s", self._base_url)

    # ------------------------------------------------------------------
    # Session / retry setup
    # ------------------------------------------------------------------

    @staticmethod
    def _build_session() -> requests.Session:
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST", "DELETE"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    # ------------------------------------------------------------------
    # Signing helpers
    # ------------------------------------------------------------------

    def _sign(self, params: Dict[str, Any]) -> str:
        """Return HMAC-SHA256 hex signature for the given param dict."""
        query_string = urlencode(params)
        return hmac.new(
            self._api_secret.encode("utf-8"),
            query_string.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    def _signed_params(self, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Merge caller params with timestamp and append signature."""
        p = dict(params or {})
        p["timestamp"] = int(time.time() * 1000) + self._time_offset_ms
        p["signature"] = self._sign(p)
        return p

    def _sync_time_offset(self) -> None:
        """Sync local timestamp offset against Binance server time."""
        url = f"{self._base_url}/fapi/v1/time"
        try:
            response = self._session.get(url, timeout=self._timeout)
            response.raise_for_status()
            server_time = int(response.json()["serverTime"])
            local_time = int(time.time() * 1000)
            self._time_offset_ms = server_time - local_time
            logger.info("Time offset synced: %dms", self._time_offset_ms)
        except Exception as exc:
            logger.warning("Failed to sync server time offset: %s", exc)

    # ------------------------------------------------------------------
    # HTTP dispatch
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {"X-MBX-APIKEY": self._api_key}

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        signed: bool = True,
    ) -> Dict[str, Any]:
        """
        Core request dispatcher.

        Args:
            method:   HTTP verb ("GET", "POST", "DELETE").
            endpoint: API path e.g. "/fapi/v1/order".
            params:   Query / body parameters.
            signed:   Whether to attach timestamp + HMAC signature.

        Returns:
            Parsed JSON response as dict.

        Raises:
            BinanceAPIError:     Non-200 Binance response.
            BinanceNetworkError: Connectivity / timeout.
        """
        url = f"{self._base_url}{endpoint}"
        for attempt in range(2):
            final_params = self._signed_params(params) if signed else (params or {})

            logger.debug("→ %s %s | params: %s", method.upper(), endpoint, final_params)

            try:
                if method.upper() in ("GET", "DELETE"):
                    response = self._session.request(
                        method,
                        url,
                        params=final_params,
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
                else:  # POST
                    response = self._session.request(
                        method,
                        url,
                        data=final_params,
                        headers=self._headers(),
                        timeout=self._timeout,
                    )
            except requests.exceptions.Timeout as exc:
                logger.error("Request timed out: %s %s", method, url)
                raise BinanceNetworkError(f"Request timed out after {self._timeout}s.") from exc
            except requests.exceptions.ConnectionError as exc:
                logger.error("Connection error: %s %s — %s", method, url, exc)
                raise BinanceNetworkError(f"Connection error: {exc}") from exc

            logger.debug("← HTTP %s | body: %s", response.status_code, response.text[:500])

            try:
                data = response.json()
            except ValueError:
                raise BinanceAPIError(
                    code=-1,
                    message=f"Non-JSON response (HTTP {response.status_code}): {response.text[:200]}",
                    status_code=response.status_code,
                )

            if response.ok:
                return data

            code = data.get("code", -1)
            msg = data.get("msg", "Unknown error")

            if signed and code == -1021 and attempt == 0:
                logger.warning("Timestamp drift detected. Syncing server time and retrying once.")
                self._sync_time_offset()
                continue

            logger.error("API error %s: %s", code, msg)
            raise BinanceAPIError(code=code, message=msg, status_code=response.status_code)

        raise BinanceAPIError(code=-1, message="Request failed after retry.")

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Test connectivity to the testnet."""
        try:
            self._request("GET", "/fapi/v1/ping", signed=False)
            logger.info("Ping successful.")
            return True
        except (BinanceAPIError, BinanceNetworkError) as exc:
            logger.warning("Ping failed: %s", exc)
            return False

    def get_exchange_info(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """Return exchange info (optionally filtered by symbol)."""
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/fapi/v1/exchangeInfo", params=params, signed=False)

    def place_order(
        self,
        symbol: str,
        side: str,
        order_type: str,
        quantity: float,
        price: Optional[float] = None,
        stop_price: Optional[float] = None,
        time_in_force: str = "GTC",
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        Place a new futures order.

        Args:
            symbol:        Trading pair, e.g. "BTCUSDT".
            side:          "BUY" or "SELL".
            order_type:    "MARKET", "LIMIT", "STOP", or "STOP_MARKET".
            quantity:      Order quantity in base asset.
            price:         Limit price (LIMIT / STOP orders).
            stop_price:    Trigger price (STOP / STOP_MARKET orders).
            time_in_force: "GTC", "IOC", "FOK" (default "GTC").
            reduce_only:   Only reduce an existing position.

        Returns:
            Raw Binance order response dict.
        """
        params: Dict[str, Any] = {
            "symbol": symbol,
            "side": side,
            "type": order_type,
            "quantity": quantity,
        }

        if order_type in ("LIMIT", "STOP"):
            params["timeInForce"] = time_in_force
            if price is not None:
                params["price"] = price

        if stop_price is not None:
            params["stopPrice"] = stop_price

        if reduce_only:
            params["reduceOnly"] = "true"

        logger.info(
            "Placing %s %s order | symbol=%s qty=%s price=%s stopPrice=%s",
            side,
            order_type,
            symbol,
            quantity,
            price,
            stop_price,
        )

        return self._request("POST", "/fapi/v1/order", params=params)

    def get_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Fetch an existing order by ID."""
        return self._request("GET", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id})

    def cancel_order(self, symbol: str, order_id: int) -> Dict[str, Any]:
        """Cancel an open order."""
        return self._request(
            "DELETE", "/fapi/v1/order", params={"symbol": symbol, "orderId": order_id}
        )

    def get_open_orders(self, symbol: Optional[str] = None) -> list:
        """Return all open orders, optionally filtered by symbol."""
        params = {"symbol": symbol} if symbol else {}
        return self._request("GET", "/fapi/v1/openOrders", params=params)

    def get_account(self) -> Dict[str, Any]:
        """Return account / balance information."""
        return self._request("GET", "/fapi/v2/account")
