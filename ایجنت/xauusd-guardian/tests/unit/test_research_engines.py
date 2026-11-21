from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from guardian.contracts.market import MarketBar, Timeframe
from guardian.contracts.signals import Direction, Signal
from guardian.domain.market.health import (
    FeedHealthSnapshot, HealthLimits, HealthStatus, evaluate_feed_health,
)
from guardian.domain.risk.controls import RiskLimits, RiskSnapshot, evaluate_risk
from guardian.research.backtest import ExecutionCostModel, run_backtest
from guardian.research.regimes import MarketRegime, classify_regime
from guardian.research.robustness import monte_carlo_trades
from guardian.research.walkforward import walk_forward_folds


def _bar(i, open_, high, low, close, spread=2):
    return MarketBar("XAUUSD.", Timeframe.M1, datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(minutes=i),
                     open_, high, low, close, spread_points=spread)


def test_risk_gate_blocks_daily_drawdown_and_loss_streak():
    limits = RiskLimits(Decimal(".03"), Decimal(".06"), Decimal(".10"), Decimal(".02"), 3)
    snap = RiskSnapshot(Decimal("9700"), Decimal("10000"), Decimal("10000"), Decimal("11000"),
                        Decimal("250"), 3)
    result = evaluate_risk(snap, limits)
    assert not result.allowed
    assert set(result.reasons) == {"DAILY_LOSS_LIMIT", "AGGREGATE_OPEN_RISK_LIMIT", "CONSECUTIVE_LOSS_LIMIT"}


def test_risk_gate_allows_safe_snapshot():
    limits = RiskLimits(Decimal(".03"), Decimal(".06"), Decimal(".10"), Decimal(".02"), 3)
    snap = RiskSnapshot(Decimal("10000"), Decimal("10000"), Decimal("10000"), Decimal("10500"),
                        Decimal("100"), 0)
    assert evaluate_risk(snap, limits).allowed


def test_risk_gate_rejects_invalid_snapshot():
    limits = RiskLimits(Decimal(".03"), Decimal(".06"), Decimal(".10"), Decimal(".02"), 3)
    snap = RiskSnapshot(Decimal("0"), Decimal("10000"), Decimal("10000"), Decimal("10000"), Decimal("0"), 0)
    with pytest.raises(ValueError):
        evaluate_risk(snap, limits)


def test_feed_health_detects_stale_tick_and_spread_anomaly():
    limits = HealthLimits(Decimal("5"), Decimal("30"), Decimal("2"))
    snap = FeedHealthSnapshot(True, Decimal("8"), Decimal("40"), Decimal("10"))
    result = evaluate_feed_health(snap, limits)
    assert result.status is HealthStatus.BLOCKED
    assert "TICK_STALE" in result.alerts
    assert "SPREAD_ANOMALY" in result.alerts


def test_feed_health_connection_loss_blocks():
    result = evaluate_feed_health(
        FeedHealthSnapshot(False, Decimal("1"), Decimal("10"), Decimal("10")),
        HealthLimits(Decimal("5"), Decimal("30"), Decimal("2")),
    )
    assert result.status is HealthStatus.BLOCKED
    assert "CONNECTION_LOST" in result.alerts


def test_backtest_executes_on_next_bar_and_accounts_for_costs():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 101, 104, 100, 103),
            _bar(2, 103, 105, 102, 104), _bar(3, 104, 105, 103, 104)]
    signal = Signal("XAUUSD.", "M1", bars[0].time_utc, Direction.LONG, Decimal("1"), "test", "LONG")
    result = run_backtest(
        bars, [signal], lots=Decimal("1"), initial_equity=Decimal("10000"),
        costs=ExecutionCostModel(Decimal("1"), Decimal("1"), Decimal("1"), Decimal("2")),
    )
    trade = result.trades[0]
    assert trade.entry_time_utc == bars[1].time_utc
    assert trade.exit_time_utc == bars[3].time_utc
    assert trade.commission == Decimal("4")
    assert result.final_equity == result.initial_equity + result.total_net_pnl


def test_backtest_stop_wins_if_stop_and_target_hit_same_bar():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 100, 110, 90, 100), _bar(2, 100, 101, 99, 100)]
    signal = Signal("XAUUSD.", "M1", bars[0].time_utc, Direction.LONG, Decimal("1"), "test", "LONG")
    result = run_backtest(
        bars, [signal], lots=Decimal("1"), initial_equity=Decimal("10000"),
        costs=ExecutionCostModel(Decimal("1"), Decimal("1")),
        stop_loss_points=Decimal("5"), take_profit_points=Decimal("5"),
    )
    assert result.trades[0].exit_reason == "STOP_LOSS"


def test_backtest_rejects_last_bar_signal():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 100, 101, 99, 100)]
    signal = Signal("XAUUSD.", "M1", bars[-1].time_utc, Direction.LONG, Decimal("1"), "test", "LONG")
    with pytest.raises(ValueError):
        run_backtest(bars, [signal], lots=Decimal("1"), initial_equity=Decimal("10000"),
                     costs=ExecutionCostModel(Decimal("1"), Decimal("1")))


def test_monte_carlo_is_seeded_and_reports_drawdown():
    pnls = [Decimal("10"), Decimal("-20"), Decimal("30"), Decimal("-5")]
    a = monte_carlo_trades(pnls, simulations=50, seed=7)
    b = monte_carlo_trades(pnls, simulations=50, seed=7)
    assert a == b
    assert len(a.max_drawdowns) == 50
    assert a.quantile(a.max_drawdowns, Decimal(".95")) >= Decimal("0")


def test_walk_forward_folds_are_chronological_and_purged():
    folds = walk_forward_folds(100, initial_train_size=40, test_size=10, step_size=10,
                               purge_bars=3, embargo_bars=2)
    assert len(folds) == 6
    for fold in folds:
        assert max(fold.train_indices) < min(fold.test_indices) - 2
        assert set(fold.train_indices).isdisjoint(fold.test_indices)
    assert all(folds[i].test_indices[-1] < folds[i + 1].test_indices[0] for i in range(len(folds) - 1))


def test_regime_classifier_returns_past_only_label():
    bars = []
    for i in range(130):
        close = 100 + i * 0.5
        bars.append(_bar(i, close - .2, close + .5, close - .5, close))
    report = classify_regime(bars, lookback=10, volatility_lookback=100)
    assert report.regime in (MarketRegime.TREND_UP, MarketRegime.HIGH_VOLATILITY)
    assert Decimal(0) <= report.efficiency_ratio <= Decimal(1)


def test_regime_classifier_requires_warmup():
    with pytest.raises(ValueError):
        classify_regime([_bar(i, 100, 101, 99, 100) for i in range(10)],
                        lookback=5, volatility_lookback=10)
