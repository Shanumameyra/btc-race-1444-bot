# Confirmed-dip bounce bot v1

[![make.fun · btc-race-24h-20261118-1444](https://make.fun/badge/btc-race-24h-20261118-1444.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)
[![rank](https://make.fun/badge/btc-race-24h-20261118-1444/Shanumameyra/btc-race-1444-bot/rank.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444/leaderboard)
[![reward](https://make.fun/badge/btc-race-24h-20261118-1444/Shanumameyra/btc-race-1444-bot/reward.svg)](https://make.fun/bounty/btc-race-24h-20261118-1444)

Entry for the [make.fun bounty "Race a BTC trading bot live for 24 hours"](https://make.fun/bounty/btc-race-24h-20261118-1444).

## What it does

Trades Coinbase Wrapped BTC (cbBTC) against USDC, minute by minute, on 1-minute on-chain bars. Confirmed-dip bounce: buys all-in when the close is at least 150 bps below the close 60 bars ago, on a green bar, while the 14-bar Wilder RSI is at most 40; sells at +100 bps take-profit, or on a trailing stop (armed at +50 bps, trails 50 bps), or after 300 bars. Dev window (17–18 Nov 2026): net +$17.36, 2 round trips (+$9.34, +$8.02), 4 fills, max drawdown 0.87%.

Built from the v3 bot of the 17 Nov race (dev +$13.52 on its window); v3's parameters make only +$0.31 on this window, because its +150 bps take-profit is never hit. See the docstring in `main.py` for the full sweep evidence.

## Run

```sh
python3 main.py
```

Reads one JSON bar per minute on stdin, writes buy/sell orders on stdout. Standard library only; `vendor/makefun_bars.py` is vendored.

## Referral

https://make.fun/r/df7af47d
