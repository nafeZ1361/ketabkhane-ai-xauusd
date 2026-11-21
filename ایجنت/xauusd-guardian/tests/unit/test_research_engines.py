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
    assert set(result.reasons) == {"DAILY_LOSS_LIMIT", "MAX_DRAWDOWN", "AGGREGATE_OPEN_RISK_LIMIT", "CONSECUTIVE_LOSS_LIMIT"}


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


def test_kill_switch_latches_severe_risk_breach_until_owner_reset():
    from guardian.domain.risk.kill_switch import (
        KillSwitchLevel, KillSwitchState, reset_kill_switch, trip_kill_switch,
    )
    limits = RiskLimits(Decimal(".03"), Decimal(".06"), Decimal(".10"), Decimal(".02"), 3)
    snapshot = RiskSnapshot(Decimal("9500"), Decimal("10000"), Decimal("10000"), Decimal("10000"),
                            Decimal("0"), 0)
    decision = evaluate_risk(snapshot, limits)
    state = trip_kill_switch(KillSwitchState(), decision)
    assert state.level is KillSwitchLevel.LATCHED
    assert not state.allows_new_decisions
    with pytest.raises(ValueError):
        reset_kill_switch(state, owner_approved=False)
    assert reset_kill_switch(state, owner_approved=True).level is KillSwitchLevel.NONE


def test_kill_switch_does_not_auto_clear_when_risk_recovers():
    from guardian.domain.risk.kill_switch import KillSwitchLevel, KillSwitchState, trip_kill_switch
    from guardian.domain.risk.controls import RiskDecision
    latched = KillSwitchState(KillSwitchLevel.LATCHED, ("MAX_DRAWDOWN",))
    safe = RiskDecision(allowed=True, reasons=())
    assert trip_kill_switch(latched, safe) == latched


def test_monte_carlo_block_bootstrap_is_seeded_and_exposes_percentiles():
    from guardian.research.robustness import compare_bootstrap_methods
    pnls = [Decimal("10"), Decimal("-20"), Decimal("30"), Decimal("-5"), Decimal("-15")]
    iid_a, block_a = compare_bootstrap_methods(pnls, simulations=80, seed=19, block_size=2)
    iid_b, block_b = compare_bootstrap_methods(pnls, simulations=80, seed=19, block_size=2)
    assert iid_a == iid_b
    assert block_a == block_b
    assert block_a.block_size == 2
    assert set(block_a.percentile_summary()["max_drawdown"]) == {"p05", "p25", "p50", "p75", "p95"}


def test_backtest_past_trade_is_unchanged_by_future_bar_corruption():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 101, 103, 100, 102),
            _bar(2, 102, 104, 101, 103)]
    signals = [
        Signal("XAUUSD.", "M1", bars[0].time_utc, Direction.LONG, Decimal("1"), "test", "LONG"),
        Signal("XAUUSD.", "M1", bars[1].time_utc, Direction.FLAT, Decimal("0"), "test", "EXIT"),
    ]
    costs = ExecutionCostModel(Decimal("1"), Decimal("1"))
    prefix = run_backtest(bars, signals, lots=Decimal("1"), initial_equity=Decimal("10000"), costs=costs)
    corrupted_future = bars + [_bar(3, 500, 900, 100, 600, spread=20)]
    full = run_backtest(corrupted_future, signals, lots=Decimal("1"), initial_equity=Decimal("10000"), costs=costs)
    assert prefix.trades[0] == full.trades[0]


def test_backtest_higher_slippage_cannot_improve_same_trade_pnl():
    bars = [_bar(0, 100, 101, 99, 100), _bar(1, 101, 103, 100, 102),
            _bar(2, 102, 104, 101, 103)]
    signals = [
        Signal("XAUUSD.", "M1", bars[0].time_utc, Direction.LONG, Decimal("1"), "test", "LONG"),
        Signal("XAUUSD.", "M1", bars[1].time_utc, Direction.FLAT, Decimal("0"), "test", "EXIT"),
    ]
    base = run_backtest(bars, signals, lots=Decimal("1"), initial_equity=Decimal("10000"),
                        costs=ExecutionCostModel(Decimal("1"), Decimal("1")))
    stressed = run_backtest(bars, signals, lots=Decimal("1"), initial_equity=Decimal("10000"),
                            costs=ExecutionCostModel(Decimal("1"), Decimal("1"), Decimal("2")))
    assert stressed.total_net_pnl < base.total_net_pnl


def test_feed_health_rejects_wrong_runtime_types():
    result = evaluate_feed_health(
        FeedHealthSnapshot(True, 3.0, 10.0, Decimal("10")),
        HealthLimits(Decimal("5"), Decimal("30"), Decimal("2")),
    )
    assert result.status is HealthStatus.BLOCKED
    assert "TICK_AGE_INVALID" in result.alerts
    assert "SPREAD_INVALID" in result.alerts


def test_walk_forward_rejects_boolean_step_size():
    with pytest.raises(ValueError):
        walk_forward_folds(100, initial_train_size=40, test_size=10, step_size=True)


def test_monte_carlo_rejects_unseeded_or_non_integer_seed():
    with pytest.raises(ValueError):
        monte_carlo_trades([Decimal("1")], simulations=2, seed=None)  # type: ignore[arg-type]


def test_regime_classifier_rejects_non_finite_ohlc():
    bad = _bar(130, float("nan"), 101, 99, 100)
    bars = [_bar(i, 100, 101, 99, 100) for i in range(130)] + [bad]
    with pytest.raises(ValueError):
        classify_regime(bars, lookback=10, volatility_lookback=100)
