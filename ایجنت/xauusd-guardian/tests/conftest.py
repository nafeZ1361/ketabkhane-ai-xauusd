import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from guardian.contracts.schemas import SymbolSpec  # noqa: E402

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "gold_candidates_20261104.json"

#: Fixture keeps verbatim MT5 names; SymbolSpec uses short domain names.
_MT5_TO_SPEC = {
    "name": "name",
    "path": "path",
    "description": "description",
    "trade_mode": "trade_mode",
    "digits": "digits",
    "point": "point",
    "trade_tick_size": "tick_size",
    "trade_tick_value": "tick_value",
    "trade_contract_size": "contract_size",
    "volume_min": "volume_min",
    "volume_max": "volume_max",
    "volume_step": "volume_step",
    "trade_stops_level": "stops_level",
    "trade_freeze_level": "freeze_level",
    "filling_mode": "filling_mode",
    "currency_base": "currency_base",
    "currency_profit": "currency_profit",
    "visible": "visible",
}


def load_captured_symbols() -> list[SymbolSpec]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    return [
        SymbolSpec(**{spec_key: row[mt5_key] for mt5_key, spec_key in _MT5_TO_SPEC.items()})
        for row in payload["symbols"]
    ]


@pytest.fixture()
def captured_symbols() -> list[SymbolSpec]:
    return load_captured_symbols()


@pytest.fixture()
def project_root() -> Path:
    return ROOT


@pytest.fixture()
def real_symbol_table() -> list[SymbolSpec]:
    """The five gold-like symbols observed on AronMarkets-Demo, 2026-11-04.

    Values are copied verbatim from the live broker response, not invented.
    """
    return [
        SymbolSpec(
            name="XAUUSD.",
            path=r"Pure\Spot Metals\Gold\XAUUSD.",
            description="Gold vs US Dollar / Spot",
            trade_mode=4,
            digits=2,
            point=0.01,
            tick_size=0.01,
            tick_value=1.0,
            contract_size=100.0,
            volume_min=0.01,
            volume_max=10.0,
            volume_step=0.01,
            stops_level=10,
            filling_mode=1,
            currency_base="USD",
            currency_profit="USD",
            visible=True,
        ),
        SymbolSpec(
            name="XAUEUR.",
            path=r"Pure\Spot Metals\Others\XAUEUR.",
            description="Gold vs Euro / Spot",
            trade_mode=4,
            digits=2,
            point=0.01,
            tick_size=0.01,
            contract_size=100.0,
            currency_base="EUR",
            currency_profit="EUR",
            visible=False,
        ),
        SymbolSpec(
            name="GoldmanSachs.",
            path=r"Pure\Shares\Shares USA\GoldmanSachs.",
            description="Goldman Sachs Group",
            trade_mode=4,
            digits=2,
            point=0.01,
            tick_size=0.01,
            contract_size=100.0,
            currency_base="USD",
            currency_profit="USD",
            visible=False,
        ),
        SymbolSpec(
            name="GOLD.",
            path=r"Pure\Shares\Shares USA\GOLD.",
            description="Barrick Gold Corp",
            trade_mode=4,
            digits=2,
            point=0.01,
            tick_size=0.01,
            contract_size=100.0,
            currency_base="USD",
            currency_profit="USD",
            visible=False,
        ),
        SymbolSpec(
            name="XAUXAG.",
            path=r"Pure\Spot Metals\XAUXAG.",
            description="Gold vs Silver",
            trade_mode=0,
            digits=3,
            point=0.001,
            tick_size=0.001,
            contract_size=1.0,
            currency_base="XAU",
            currency_profit="XAG",
            visible=False,
        ),
    ]
