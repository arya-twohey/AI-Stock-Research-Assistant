from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from alpaca.data.historical import NewsClient, StockHistoricalDataClient
from alpaca.data.enums import DataFeed
from alpaca.data.requests import NewsRequest, StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

from app.config import public_demo_enabled, require_alpaca_credentials, trade_submit_enabled


ET = ZoneInfo("America/New_York")


def _client() -> TradingClient:
    key_id, secret_key = require_alpaca_credentials()
    return TradingClient(api_key=key_id, secret_key=secret_key, paper=True)


def _data_client() -> StockHistoricalDataClient:
    key_id, secret_key = require_alpaca_credentials()
    return StockHistoricalDataClient(api_key=key_id, secret_key=secret_key)


def _news_client() -> NewsClient:
    key_id, secret_key = require_alpaca_credentials()
    return NewsClient(api_key=key_id, secret_key=secret_key)


def _value(obj, name, default=None):
    value = getattr(obj, name, default)
    if hasattr(value, "value"):
        return value.value
    return value


def _number(value, fallback=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def account_summary() -> dict:
    if public_demo_enabled():
        now = datetime.now(tz=ET)
        next_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        next_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
        if now.hour >= 16:
            next_open = next_open + timedelta(days=1)
            next_close = next_close + timedelta(days=1)
        return {
            "status": "ACTIVE",
            "currency": "USD",
            "cash": 100000.0,
            "portfolioValue": 100000.0,
            "buyingPower": 400000.0,
            "equity": 100000.0,
            "daytradeCount": 0,
            "patternDayTrader": False,
            "tradingBlocked": False,
            "marketOpen": 9 <= now.hour < 16,
            "timestamp": str(now),
            "nextOpen": str(next_open),
            "nextClose": str(next_close),
        }

    account = _client().get_account()
    clock = _client().get_clock()
    return {
        "status": str(_value(account, "status")),
        "currency": account.currency,
        "cash": _number(account.cash),
        "portfolioValue": _number(account.portfolio_value),
        "buyingPower": _number(account.buying_power),
        "equity": _number(account.equity),
        "daytradeCount": _number(account.daytrade_count),
        "patternDayTrader": bool(account.pattern_day_trader),
        "tradingBlocked": bool(account.trading_blocked),
        "marketOpen": bool(clock.is_open),
        "timestamp": str(clock.timestamp),
        "nextOpen": str(clock.next_open),
        "nextClose": str(clock.next_close),
    }


def positions() -> list[dict]:
    if public_demo_enabled():
        return []

    return [
        {
            "symbol": p.symbol,
            "qty": _number(p.qty),
            "marketValue": _number(p.market_value),
            "avgEntryPrice": _number(p.avg_entry_price),
            "currentPrice": _number(p.current_price),
            "unrealizedPl": _number(p.unrealized_pl),
            "unrealizedPlpc": _number(p.unrealized_plpc),
        }
        for p in _client().get_all_positions()
    ]


def orders(status: str = "all", limit: int = 25) -> list[dict]:
    if public_demo_enabled():
        return [
            {
                "id": "demo-aapl-order",
                "symbol": "AAPL",
                "side": "buy",
                "type": "market",
                "qty": 1.0,
                "filledQty": 0.0,
                "status": "accepted",
                "submittedAt": "2026-07-01 20:11:00-04:00",
                "filledAt": None,
                "filledAvgPrice": None,
            }
        ][:limit]

    request = GetOrdersRequest(status=status, limit=limit)
    return [
        {
            "id": str(o.id),
            "symbol": o.symbol,
            "side": str(_value(o, "side")),
            "type": str(_value(o, "order_type")),
            "qty": _number(o.qty),
            "filledQty": _number(o.filled_qty),
            "status": str(_value(o, "status")),
            "submittedAt": str(o.submitted_at),
            "filledAt": str(o.filled_at) if o.filled_at else None,
            "filledAvgPrice": _number(o.filled_avg_price, None),
        }
        for o in _client().get_orders(filter=request)
    ]


def market_bars(symbol: str, days: int = 90) -> list[dict]:
    end = datetime.now(tz=ET)
    start = end - timedelta(days=days)
    request = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=start,
        end=end,
        feed=DataFeed.IEX,
    )
    raw = _data_client().get_stock_bars(request)
    frame = raw.df
    if frame.empty:
        return []

    symbol_frame = frame.xs(symbol, level=0) if "symbol" in frame.index.names else frame
    bars = []
    for timestamp, row in symbol_frame.tail(90).iterrows():
        bars.append(
            {
                "date": timestamp.strftime("%Y-%m-%d"),
                "open": _number(row["open"]),
                "high": _number(row["high"]),
                "low": _number(row["low"]),
                "close": _number(row["close"]),
                "volume": _number(row["volume"]),
            }
        )
    return bars


def latest_news(symbol: str, limit: int = 6) -> list[dict]:
    end = datetime.now(tz=ET)
    start = end - timedelta(days=14)
    request = NewsRequest(symbols=symbol, start=start, end=end, limit=limit)
    try:
        news_set = _news_client().get_news(request)
    except Exception:
        return []

    items = news_set.data.get("news", []) if hasattr(news_set, "data") else news_set
    return [
        {
            "headline": item.headline,
            "summary": item.summary,
            "source": item.source,
            "url": item.url,
            "createdAt": str(item.created_at),
        }
        for item in items
    ]


def _sma(values: list[float], window: int):
    if len(values) < window:
        return None
    return mean(values[-window:])


def _research_narrative(symbol: str, bars: list[dict], news: list[dict]) -> dict:
    if not bars:
        return {
            "summary": f"No recent daily bars were returned for {symbol}.",
            "risks": [
                "Market data was unavailable, so price trend, liquidity, and volatility risk could not be assessed.",
                "Without recent bars, entry, stop, and target levels should not be treated as reliable.",
            ],
            "bullCase": [],
            "bearCase": [],
        }

    closes = [bar["close"] for bar in bars]
    volumes = [bar["volume"] for bar in bars]
    last = closes[-1]
    first = closes[0]
    change = ((last - first) / first) * 100 if first else 0
    sma20 = _sma(closes, 20)
    sma50 = _sma(closes, 50)
    avg_volume = mean(volumes[-20:]) if volumes else 0
    recent_high = max(closes[-20:]) if len(closes) >= 20 else max(closes)
    recent_low = min(closes[-20:]) if len(closes) >= 20 else min(closes)
    pullback_from_high = ((last - recent_high) / recent_high) * 100 if recent_high else 0
    distance_from_low = ((last - recent_low) / recent_low) * 100 if recent_low else 0
    trend = "above" if sma20 and last >= sma20 else "below"
    long_trend = "above" if sma50 and last >= sma50 else "below"

    bull = [
        f"Price is {trend} the 20-day average, which supports near-term momentum." if sma20 else "Not enough data for a 20-day average.",
        f"Price is {long_trend} the 50-day average, giving a useful trend check." if sma50 else "Not enough data for a 50-day average.",
        "Recent headlines provide catalysts to review before sizing a trade." if news else "The setup is driven by price action here, not fetched headlines.",
    ]
    bear = [
        "A market order can fill away from the last shown price, especially at the open.",
        "A short research window can miss earnings, macro events, and broader sector pressure.",
        "Paper fills may not match live trading liquidity or slippage.",
    ]
    risks = [
        (
            f"Trend risk: {symbol} is trading {trend} its 20-day average and {long_trend} its 50-day average. "
            "A break back through these levels can turn a momentum setup into a failed breakout."
        ),
        (
            f"Price location risk: the latest close is {pullback_from_high:.2f}% from the recent 20-day high "
            f"and {distance_from_low:.2f}% above the recent 20-day low, so the entry may be exposed to either "
            "chasing strength or catching a reversal."
        ),
        (
            f"Liquidity and execution risk: recent average daily volume is about {avg_volume:,.0f} shares on the "
            "IEX feed sample. Market orders can still fill away from the displayed close during fast moves."
        ),
        (
            "Catalyst risk: earnings, guidance, analyst changes, product news, regulation, sector rotation, and "
            "macro rate moves can quickly outweigh the recent chart setup."
            if news
            else "Catalyst risk: no recent headlines were returned here, so earnings, guidance, analyst changes, "
            "sector rotation, and macro news should be checked separately."
        ),
    ]

    return {
        "summary": (
            f"{symbol} last closed near ${last:,.2f}. Over the sampled period it moved "
            f"{change:+.2f}%, with recent average volume around {avg_volume:,.0f} shares."
        ),
        "bullCase": bull,
        "bearCase": bear,
        "risks": risks,
        "indicators": {
            "lastClose": last,
            "periodChangePct": change,
            "sma20": sma20,
            "sma50": sma50,
            "avgVolume20": avg_volume,
        },
    }


def research(symbol: str) -> dict:
    clean_symbol = symbol.strip().upper()
    bars = market_bars(clean_symbol)
    news = latest_news(clean_symbol)
    narrative = _research_narrative(clean_symbol, bars, news)
    return {"symbol": clean_symbol, "bars": bars, "news": news, **narrative}


def trade_preview(symbol: str, side: str, qty: float) -> dict:
    clean_symbol = symbol.strip().upper()
    bars = market_bars(clean_symbol, days=30)
    latest = bars[-1]["close"] if bars else None
    quantity = float(qty)
    side = side.lower()

    if latest:
        if side == "buy":
            stop = latest * 0.97
            target = latest * 1.06
        else:
            stop = latest * 1.03
            target = latest * 0.94
        notional = latest * quantity
    else:
        stop = None
        target = None
        notional = None

    confidence = "medium" if latest and len(bars) >= 20 else "low"
    reasons = [
        "Uses current paper account context and recent daily price data.",
        "Keeps execution human-confirmed through a separate submit step.",
        "Stop and target are illustrative guardrails, not automated exits.",
    ]

    return {
        "symbol": clean_symbol,
        "side": side,
        "qty": quantity,
        "entry": latest,
        "stop": stop,
        "target": target,
        "estimatedNotional": notional,
        "confidence": confidence,
        "reasons": reasons,
    }


def submit_market_order(symbol: str, side: str, qty: float) -> dict:
    if public_demo_enabled() or not trade_submit_enabled():
        raise RuntimeError("Trade submission is disabled for this public demo.")

    order_side = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
    request = MarketOrderRequest(
        symbol=symbol.strip().upper(),
        qty=float(qty),
        side=order_side,
        time_in_force=TimeInForce.DAY,
    )
    order = _client().submit_order(order_data=request)
    return {
        "id": str(order.id),
        "symbol": order.symbol,
        "side": str(_value(order, "side")),
        "qty": _number(order.qty),
        "status": str(_value(order, "status")),
        "submittedAt": str(order.submitted_at),
    }
