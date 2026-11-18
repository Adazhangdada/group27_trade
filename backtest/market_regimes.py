
from pathlib import Path
import json
import hashlib

import numpy as np
import pandas as pd

# ========== 实验配置 ==========

CAPITAL = 1000.0
FEE = 0.001
FAST = 5
SLOW = 20

REGIMES = {
    "bull": ("2020-10-01", "2021-04-30"),
    "bear": ("2022-01-01", "2022-12-31"),
    "sideways": ("2023-07-01", "2023-10-31"),
}

OUT = Path("results/regimes")
OUT.mkdir(parents=True, exist_ok=True)

DATA_FILE = Path("data/btc_daily.csv")
DATA_HASH = hashlib.sha256(DATA_FILE.read_bytes()).hexdigest()

# ========== 读取数据 ==========

df = pd.read_csv(DATA_FILE)
df["date"] = pd.to_datetime(df["date"], utc=True)
df = df.sort_values("date").reset_index(drop=True)

if df["date"].duplicated().any():
    raise ValueError("Duplicate dates")

df["ma5"] = df["close"].rolling(FAST).mean()
df["ma20"] = df["close"].rolling(SLOW).mean()

df["signal"] = (
    (df["ma5"] > df["ma20"])
    & df["ma20"].notna()
).astype(int)


# ========== 回测函数 ==========

def simulate(data, strategy, capital, prev_signal):
    cash = float(capital)
    btc = 0.0
    values = []
    trades = []

    for i, row in data.iterrows():
        price_open = float(row["open"])
        price_close = float(row["close"])

        if strategy == "buy_hold":
            target = 1
        elif strategy == "ma_cross":
            target = (
                prev_signal if i == 0
                else int(data.iloc[i - 1]["signal"])
            )
        else:
            raise ValueError("Unknown strategy")

        if target == 1 and btc == 0:
            btc = cash * (1 - FEE) / price_open
            cash = 0.0
            action = "BUY"

        elif target == 0 and btc > 0:
            cash = btc * price_open * (1 - FEE)
            btc = 0.0
            action = "SELL"

        else:
            action = None

        if action is not None:
            trades.append({
                "date": row["date"].isoformat(),
                "action": action,
                "price": price_open
            })

        value = cash + btc * price_close

        # 最后一天收盘统一平仓
        if i == len(data) - 1 and btc > 0:
            cash = btc * price_close * (1 - FEE)
            btc = 0.0
            value = cash

            trades.append({
                "date": row["date"].isoformat(),
                "action": "FINAL_SELL",
                "price": price_close
            })

        values.append(value)

    return pd.Series(values, dtype=float), trades


# ========== 绩效计算 ==========

def metrics(values, initial):
    equity = pd.concat([
        pd.Series([initial]),
        values.reset_index(drop=True)
    ], ignore_index=True)

    returns = equity.pct_change().dropna()
    drawdown = equity / equity.cummax() - 1

    std = returns.std(ddof=1)
    sharpe = (
        returns.mean() / std * np.sqrt(365)
        if std > 0 else 0.0
    )

    return {
        "return_pct": round(
            (equity.iloc[-1] / initial - 1) * 100, 4
        ),
        "max_drawdown_pct": round(
            drawdown.min() * 100, 4
        ),
        "sharpe": round(float(sharpe), 4),
        "final_value": round(float(equity.iloc[-1]), 4)
    }


# ========== 运行全部实验 ==========

records = []

for regime, (start, end) in REGIMES.items():

    start_ts = pd.Timestamp(start, tz="UTC")
    end_ts = pd.Timestamp(end, tz="UTC")

    earlier = df[df["date"] < start_ts]

    if len(earlier) < SLOW:
        raise ValueError("Insufficient warm-up data")

    prev_signal = int(earlier.iloc[-1]["signal"])

    period = df[
        (df["date"] >= start_ts)
        & (df["date"] <= end_ts)
    ].copy().reset_index(drop=True)

    if period.empty:
        raise ValueError(f"No data for {regime}")

    bh, bh_trades = simulate(
        period, "buy_hold", CAPITAL, prev_signal
    )

    ma, ma_trades = simulate(
        period, "ma_cross", CAPITAL, prev_signal
    )

    # 因为费用按比例收取，账户净值可线性缩放
    portfolio = 0.5 * bh + 0.5 * ma

    for name, values, trades_count in [
        ("buy_hold", bh, len(bh_trades)),
        ("ma_cross", ma, len(ma_trades)),
        ("portfolio_50_50", portfolio,
         len(bh_trades) + len(ma_trades)),
    ]:

        result = metrics(values, CAPITAL)

        record = {
            "regime": regime,
            "period": {
                "start": start,
                "end": end
            },
            "strategy": name,
            "params": {
                "fast": FAST,
                "slow": SLOW,
                "fee_rate": FEE,
                "initial_capital": CAPITAL
            },
            "execution": {
                "signal": "previous_close",
                "fill": "next_open",
                "final_liquidation": "last_close",
                "slippage": 0.0
            },
            "data_sha256": DATA_HASH,
            "metrics": result,
            "trade_count": trades_count
        }

        records.append(record)

        # 每个实验独立保存 JSON
        path = OUT / f"{regime}_{name}.json"
        path.write_text(
            json.dumps(
                record,
                indent=2,
                sort_keys=True,
                allow_nan=False
            ) + "\n",
            encoding="utf-8"
        )

    # 保存每日净值
    pd.DataFrame({
        "date": period["date"],
        "buy_hold": bh,
        "ma_cross": ma,
        "portfolio": portfolio
    }).to_csv(
        OUT / f"{regime}_daily.csv",
        index=False
    )


# ========== 汇总输出 ==========

summary = pd.DataFrame([
    {
        "regime": r["regime"],
        "strategy": r["strategy"],
        **r["metrics"],
        "trades": r["trade_count"]
    }
    for r in records
])

summary.to_csv(OUT / "summary.csv", index=False)

print("\n===== MARKET REGIME RESULTS =====")
print(summary.to_string(index=False))
print("\nSaved 9 JSON files in:", OUT)
