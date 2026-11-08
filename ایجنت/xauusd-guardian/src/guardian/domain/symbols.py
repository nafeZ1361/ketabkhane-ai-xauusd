"""Gold symbol identification.

Three policies exist:

``xauusd_identity_v3``  (default after D-003)
    Exact-identity resolution: match the exact symbol name from a configurable
    alias list, then corroborate with live broker metadata. No scoring, no
    substitution. This is the production path.

``xauusd_strict_v1``
    The literal rule from the build specification. Retained for replay and
    audit. On the current broker it returns AMBIGUOUS — that is a true result.

``spot_metal_usd_v2``
    The scoring rule with a hard class pre-filter. Superseded by v3; kept so the
    investigation history stays executable.

Pure functions only: no MT5 import, no I/O, no logging.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable

from guardian.contracts.schemas import (
    ResolutionStatus,
    SymbolResolution,
    SymbolSpec,
)

IDENTITY_POLICY = "xauusd_identity_v3"
STRICT_POLICY = "xauusd_strict_v1"
AMENDED_POLICY = "spot_metal_usd_v2"
KNOWN_POLICIES = (IDENTITY_POLICY, STRICT_POLICY, AMENDED_POLICY)

MIN_SCORE = 5
MIN_MARGIN = 2

#: Score weights fixed by the specification (§7).
WEIGHT_METADATA_GOLD = 2
WEIGHT_CONTRACT_100 = 2
WEIGHT_BASE_XAU = 3
WEIGHT_DIGITS_2 = 1
WEIGHT_TICK_001 = 1

_EXACT_GOLD_NAME = re.compile(r"^XAUUSD\.?$", re.IGNORECASE)
_CONTRACT_EPS = 1e-9
_TICK_EPS = 1e-12


def score_symbol(spec: SymbolSpec) -> int:
    """Apply the specification's scoring rule to one symbol."""
    score = 0
    blob = f"{spec.path or ''} {spec.description or ''}".upper()
    if "XAU" in blob or "GOLD" in blob:
        score += WEIGHT_METADATA_GOLD
    if abs(float(spec.contract_size) - 100.0) < _CONTRACT_EPS:
        score += WEIGHT_CONTRACT_100
    if (spec.currency_base or "").upper() == "XAU":
        score += WEIGHT_BASE_XAU
    if int(spec.digits) == 2:
        score += WEIGHT_DIGITS_2
    if abs(float(spec.tick_size) - 0.01) < _TICK_EPS:
        score += WEIGHT_TICK_001
    return score


def _eligible_strict(spec: SymbolSpec, account_currency: str) -> bool:
    return True
def _eligible_amended(spec: SymbolSpec, account_currency: str) -> bool:
    if int(spec.trade_mode) != 4:
        return False
    if "Spot Metals" not in (spec.path or ""):
        return False
    if (spec.currency_profit or "").upper() != (account_currency or "").upper():
        return False
    name_ok = _EXACT_GOLD_NAME.match(spec.name) is not None
    desc_ok = (spec.description or "").strip().lower().startswith("gold vs us dollar")
    return name_ok or desc_ok


_POLICY_FILTERS: dict[str, Callable[[SymbolSpec, str], bool]] = {
    STRICT_POLICY: _eligible_strict,
    AMENDED_POLICY: _eligible_amended,
}

FULL_TRADE_MODE = 4
_NUM_EPS = 1e-9


@dataclass(frozen=True, slots=True)
class GoldExpectations:
    """Broker-specific expectations, configurable and versioned.

    An expected value of ``None`` disables that single check; it does not make
    the resolver permissive, because identity and the remaining checks still
    apply.
    """

    schema_version: int = 1
    aliases: tuple[str, ...] = ("XAUUSD.",)
    #: When set, the matched name must equal this exactly (case-insensitive).
    required_symbol_name: str | None = None
    required_path_token: str = "Spot Metals"
    required_profit_currency: str = ""  # empty -> account currency
    contract_size: float | None = 100.0
    tick_size: float | None = 0.01
    digits: int | None = 2
    require_full_trade_mode: bool = True

    def wanted_names(self) -> frozenset[str]:
        return frozenset(a.strip().upper() for a in self.aliases if a.strip())


#: Market execution is reported, never used as a gate: it is a broker setting,
#: not an identity of the instrument.


def _resolve_by_identity(
    symbols: Iterable[SymbolSpec],
    expectations: GoldExpectations,
    account_currency: str,
) -> SymbolResolution:
    wanted = expectations.wanted_names()
    if not wanted:
        return SymbolResolution(
            status=ResolutionStatus.NOT_FOUND,
            policy=IDENTITY_POLICY,
            reason="no symbol aliases configured; refusing to guess",
        )

    exact = [spec for spec in symbols if spec.name.strip().upper() in wanted]
    if not exact:
        return SymbolResolution(
            status=ResolutionStatus.NOT_FOUND,
            policy=IDENTITY_POLICY,
            reason="no symbol matched the exact alias list " + str(sorted(wanted)),
        )
    if len(exact) > 1:
        return SymbolResolution(
            status=ResolutionStatus.AMBIGUOUS,
            policy=IDENTITY_POLICY,
            ranked=tuple(sorted(((score_symbol(s), s.name) for s in exact), key=lambda i: (-i[0], i[1]))),
            reason=f"{len(exact)} symbols match the alias list: " + ", ".join(sorted(s.name for s in exact)),
        )

    target = exact[0]
    mismatches: list[tuple[str, str, str]] = []

    if expectations.required_symbol_name:
        required_name = expectations.required_symbol_name.strip()
        if target.name.strip().lower() != required_name.lower():
            mismatches.append(("symbol_name", required_name, target.name))

    token = (expectations.required_path_token or "").strip()
    if token and token.lower() not in (target.path or "").lower():
        mismatches.append(("path", f"contains {token!r}", target.path or ""))

    expected_profit = (expectations.required_profit_currency or account_currency or "").upper()
    actual_profit = (target.currency_profit or "").upper()
    if expected_profit and actual_profit != expected_profit:
        mismatches.append(("currency_profit", expected_profit, actual_profit or "<empty>"))

    if expectations.contract_size is not None and (
        abs(float(target.contract_size) - float(expectations.contract_size)) > _NUM_EPS
    ):
        mismatches.append(
            ("contract_size", f"{expectations.contract_size:g}", f"{target.contract_size:g}")
        )

    if expectations.tick_size is not None and (
        abs(float(target.tick_size) - float(expectations.tick_size)) > _NUM_EPS
    ):
        mismatches.append(("tick_size", f"{expectations.tick_size:g}", f"{target.tick_size:g}"))

    if expectations.digits is not None and int(target.digits) != int(expectations.digits):
        mismatches.append(("digits", str(expectations.digits), str(target.digits)))

    if expectations.require_full_trade_mode and int(target.trade_mode) != FULL_TRADE_MODE:
        mismatches.append(("trade_mode", str(FULL_TRADE_MODE), str(target.trade_mode)))

    observed = (
        ("name", target.name),
        ("path", target.path),
        ("description", target.description),
        ("currency_base", target.currency_base),
        ("currency_profit", target.currency_profit),
        ("contract_size", f"{target.contract_size:g}"),
        ("digits", str(target.digits)),
        ("point", f"{target.point:g}"),
        ("tick_size", f"{target.tick_size:g}"),
        ("tick_value", f"{target.tick_value:g}"),
        ("volume_min", f"{target.volume_min:g}"),
        ("volume_max", f"{target.volume_max:g}"),
        ("volume_step", f"{target.volume_step:g}"),
        ("trade_mode", str(target.trade_mode)),
        ("stops_level", str(target.stops_level)),
        ("freeze_level", str(target.freeze_level)),
        ("filling_mode", str(target.filling_mode)),
    )

    if mismatches:
        first = mismatches[0]
        return SymbolResolution(
            status=ResolutionStatus.METADATA_MISMATCH,
            policy=IDENTITY_POLICY,
            symbol_name=target.name,
            mismatches=tuple(mismatches),
            observed=observed,
            reason=(
                f"{len(mismatches)} field(s) differ from the expected profile; "
                f"first: {first[0]} expected {first[1]!r} got {first[2]!r}"
            ),
        )

    return SymbolResolution(
        status=ResolutionStatus.VERIFIED,
        policy=IDENTITY_POLICY,
        symbol_name=target.name,
        observed=observed,
        reason=f"exact identity {target.name!r} corroborated by live broker metadata",
    )


def identify_gold_symbol(
    symbols: Iterable[SymbolSpec],
    *,
    policy: str = IDENTITY_POLICY,
    account_currency: str = "USD",
    expectations: GoldExpectations | None = None,
    min_score: int = MIN_SCORE,
    min_margin: int = MIN_MARGIN,
) -> SymbolResolution:
    """Return the single acceptable gold symbol, or a blocking status.

    Fails closed: anything other than one verified winner returns a non-permissive
    status. ``xauusd_identity_v3`` never substitutes another symbol.
    """
    if policy == IDENTITY_POLICY:
        return _resolve_by_identity(
            symbols,
            expectations or GoldExpectations(),
            account_currency,
        )

    if policy not in _POLICY_FILTERS:
        raise ValueError(f"unknown symbol policy: {policy!r}")

    eligible_filter = _POLICY_FILTERS[policy]
    scored: list[tuple[int, str]] = sorted(
        (
            (score_symbol(spec), spec.name)
            for spec in symbols
            if eligible_filter(spec, account_currency)
        ),
        key=lambda item: (-item[0], item[1]),
    )

    if not scored:
        return SymbolResolution(
            status=ResolutionStatus.NOT_FOUND,
            policy=policy,
            reason="no symbol passed the policy filter",
        )

    top_score, top_name = scored[0]
    if top_score < min_score:
        return SymbolResolution(
            status=ResolutionStatus.NOT_FOUND,
            policy=policy,
            ranked=tuple(scored[:5]),
            reason=f"best score {top_score} is below the required {min_score}",
        )

    second_score = scored[1][0] if len(scored) > 1 else None
    margin = None if second_score is None else top_score - second_score
    ranked = tuple(scored[:5])

    if margin is not None and margin < min_margin:
        tied = [name for score, name in scored if score == top_score]
        return SymbolResolution(
            status=ResolutionStatus.AMBIGUOUS,
            policy=policy,
            ranked=ranked,
            margin=margin,
            reason=(
                f"{len(tied)} symbols tie at score {top_score} "
                f"(margin {margin} < required {min_margin}): {', '.join(tied)}"
            ),
        )

    return SymbolResolution(
        status=ResolutionStatus.RESOLVED,
        policy=policy,
        symbol_name=top_name,
        ranked=ranked,
        margin=margin,
        reason=f"unique winner at score {top_score}",
    )
