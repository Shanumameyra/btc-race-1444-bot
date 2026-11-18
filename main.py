"""Confirmed-dip bounce bot for cbBTC (agent-fun/bars-replay/v1), v1 for
btc-race-24h-20261118-1444.

Built from the v3 bot of the 17 Nov race ("Deep-dip scale-in bot v3",
dev +$13.52 on ITS window), re-tuned on THIS race's dev window
(17 Nov 14:44 UTC - 18 Nov 14:44 UTC, 1,440 bars, close $65,083.31 ->
$63,260.75, -2.80%; low $63,076.34, high $65,189.54). The window is a
steady downtrend with two tradeable bounce episodes: a sharp -2.6% drop
in the first ~70 bars recovering ~+1.6%, and a second dip-and-recover
later in the day.

What changed vs v3, and why (sweeps of ~4,300 parameterisations of this
family on THIS window, exact integer simulator mirroring the kit engine):
  * v3's parameters on this window make only +$0.31 (1 RT, DD 1.09%):
    its +150 bps take-profit is never hit -- the bounce peaks just
    below it and the 90 bps trailing stop gives most of the move back.
  * Take-profit +100 bps (was +150): sells the bounce instead of
    trailing it away. TP 80 gives $14.38, TP 100 $17.36, TP 120 $15.27
    on the winning configuration, so the gain is broad, not one point.
  * All-in first tranche, 100% of cash (was 50% + scale-in): the
    second tranche never improves this window (it buys while the price
    is still falling and drags the average entry); size 5000 + scale-in
    makes $15.41, all-in $17.36.
  * Entry needs confirmation (new): buy only on a green bar
    (close above the previous close) while the 60-bar return is still
    <= -150 bps AND the 14-bar Wilder RSI is <= 40. The confirmation
    alone lifts the config from $13.10 to $15.03; with the RSI filter
    to $17.36. It avoids buying into a still-falling knife.
  * Entry dip -150 bps (was -170): with confirmation, -150 catches
    both episodes; -170 catches only the first as cleanly ($15.03).
  * Trailing stop arms at +50 bps, trails 50 bps (was +80/90): the
    backstop for a bounce that stalls below the take-profit.
  * Max hold 300 bars (kept) and re-arm rule kept (no re-buy until the
    60-bar return is above -50 bps).

Long only, at most one position, at most one order per batch, max slippage
50 bps. A full-size round trip costs about 12 bps in fees and slippage
plus pool impact.

Dev window, verified with the real bot as a subprocess
(`python3 -P -s main.py`, PYTHONHASHSEED=0, local replay driver, exact
integer port of the kit engine): net PnL +$17.36 from 2 round trips
(+$9.34, +$8.02), 4 fills, max drawdown 0.87%, fees $1.61, no rejected
orders, two runs byte-identical. Neighbourhood (drop 150-170 bps,
take-profit 80-120 bps, size 5000-10000, confirmation on) makes
$13.10-17.36, so the gain is broad, not a single tuned point.
With fees doubled the same run nets +$15.45.

Honest caveat: the profit comes from two bounce episodes in a falling
window (biggest-trade share 54%). The live race depends on
dip-and-recover episodes occurring in the race window, as they did in
the dev window; the confirmation + RSI filter and the +100 bps
take-profit are the best-measured way to bank them if they do, and the
re-arm rule keeps the bot in cash (not bleeding) when they do not.

Everything is deterministic: no clock, no network, no randomness, no
files. The only state is the list of closes seen so far and a few numbers
derived from it, so two runs on the same data produce byte-identical
replies.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))
import makefun_bars

SYMBOL = "CBBTC"

# --- strategy parameters (chosen on the dev window; see the docstring) ---
DROP_BARS = 60            # dip measured against the close 60 bars ago
DROP_BPS = 150            # buy when the close is >= 150 bps below it
RSI_PERIOD = 14           # Wilder RSI period
RSI_MAX = 40.0            # buy only while the RSI is at most 40 (oversold)
ACTIVATE_BPS = 50         # arm the trailing stop once +50 bps above the entry
TRAIL_BPS = 50            # sell when the close falls 50 bps below the peak since entry
TAKE_PROFIT_BPS = 100     # sell once the close is +100 bps above the average entry
MAX_HOLD = 300            # backstop: sell after 300 bars in the trade (5 hours)
MAX_SLIP_BPS = 50         # max slippage on every order
REARM_BPS = -50           # re-arm buying only once the 60-bar return is above -50 bps

# --- per-run state ---
_closes = []
_entry_px = None          # average entry price (raw price units) from cost/qty
_peak = None              # highest close since entry
_hold_bars = 0
_armed = True
_trail_on = False


def _entry_price(state):
    """Average entry price from the position's cost and qty (raw price units)."""
    pos = state.positions.get(SYMBOL)
    if pos is None or pos.qty == 0:
        return None
    # value(qty, price) = qty * price * 10**6 // 10**13, so price = cost * 10**7 // qty
    return pos.cost * 10 ** 7 // pos.qty


def _rsi(closes, period=RSI_PERIOD):
    """Wilder RSI of the closes so far (causal; None until `period` diffs exist)."""
    if len(closes) <= period:
        return None
    gains = [0.0] * len(closes)
    losses = [0.0] * len(closes)
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains[i] = d if d > 0 else 0.0
        losses[i] = -d if d < 0 else 0.0
    ag = sum(gains[1:period + 1]) / period
    al = sum(losses[1:period + 1]) / period
    for i in range(period, len(closes)):
        if i > period:
            ag = (ag * (period - 1) + gains[i]) / period
            al = (al * (period - 1) + losses[i]) / period
    if al == 0:
        return 100.0
    return 100.0 - 100.0 / (1.0 + ag / al)


def on_batch(state, batch):
    global _entry_px, _peak, _hold_bars, _armed, _trail_on
    close = state.close(SYMBOL)
    if close is None:
        return []
    _closes.append(close)
    pos = state.positions.get(SYMBOL)

    if pos is None:
        # Flat: buy all-in on a confirmed oversold dip.
        if len(_closes) > DROP_BARS:
            ref = _closes[-1 - DROP_BARS]
            drop_bps = (close - ref) * 10_000 // ref
            if not _armed:
                if drop_bps > REARM_BPS:
                    _armed = True
                return []
            if drop_bps <= -DROP_BPS:
                # Confirmation: a green bar (close above the previous close)
                # and an oversold RSI -- do not buy a still-falling knife.
                if close <= _closes[-2]:
                    return []
                rsi = _rsi(_closes)
                if rsi is None or rsi > RSI_MAX:
                    return []
                return [{"side": "buy", "symbol": SYMBOL,
                         "notional_quote_units": state.cash,
                         "max_slippage_bps": MAX_SLIP_BPS}]
        return []

    # In a position: maintain the entry price, the peak and the hold count.
    entry = _entry_price(state)
    if entry is None:
        return []
    if _entry_px is None:
        _entry_px = entry
        _peak = close
        _hold_bars = 0
        _trail_on = False
    if close > _peak:
        _peak = close
    _hold_bars += 1

    # Arm the trailing stop once the trade is in profit.
    if not _trail_on and close >= _entry_px * (10_000 + ACTIVATE_BPS) // 10_000:
        _trail_on = True

    hit = False
    if close >= _entry_px * (10_000 + TAKE_PROFIT_BPS) // 10_000:
        hit = True
    if _trail_on and close <= _peak * (10_000 - TRAIL_BPS) // 10_000:
        hit = True
    if _hold_bars >= MAX_HOLD:
        hit = True
    if hit:
        _entry_px = None
        _peak = None
        _hold_bars = 0
        _armed = False
        _trail_on = False
        return [{"side": "sell", "symbol": SYMBOL, "qty": pos.qty,
                 "max_slippage_bps": MAX_SLIP_BPS}]
    return []


makefun_bars.run(on_batch)
