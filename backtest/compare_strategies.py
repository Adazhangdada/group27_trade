
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# ========== 1. 实验参数 ==========

INITIAL_CAPITAL = 1000.0
FEE_RATE = 0.001

FAST_MA = 5
SLOW_MA = 20

START_DATE = "2020-02-01"
END_DATE = "2025-12-31"

DATA_PATH = Path("data/btc_daily.csv")
OUTPUT_DIR = Path("results")
OUTPUT_DIR.mkdir(exist_ok=True)


# ========== 2. 读取历史数据 ==========

df = pd.read_csv(DATA_PATH)
df["date"] = pd.to_datetime(df["date"], utc=True)
df = df.sort_values("date").reset_index(drop=True)

if df["date"].duplicated().any():
    raise ValueError("Duplicate dates found")

# 先在完整历史数据上计算均线
# 这样回测开始时已经有之前的历史作为预热
df["ma_fast"] = df["close"].rolling(FAST_MA).mean()
df["ma_slow"] = df["close"].rolling(SLOW_MA).mean()

df["ma_signal"] = (
    (df["ma_fast"] > df["ma_slow"])
    & df["ma_slow"].notna()
).astype(int)

# 保留回测起始日前一日的信息
start = pd.Timestamp(START_DATE, tz="UTC")
end = pd.Timestamp(END_DATE, tz="UTC")

period = df[
    (df["date"] >= start) &
    (df["date"] <= end)
].copy()

if period.empty:
    raise ValueError("No data in selected period")

# 第一天使用回测开始前一天的 MA 信号
previous_rows = df[df["date"] < start]

if len(previous_rows) < SLOW_MA:
    raise ValueError("Not enough warm-up data")

first_previous_signal = int(
    previous_rows.iloc[-1]["ma_signal"]
)

period = period.reset_index(drop=True)


# ========== 3. 统一回测函数 ==========

def run_backtest(strategy, capital):
    cash = float(capital)
    btc = 0.0

    values = []
    trades = []

    for i in range(len(period)):
        row = period.iloc[i]

        open_price = float(row["open"])
        close_price = float(row["close"])

        # 根据策略，确定今天希望持有的资产
        if strategy == "buy_hold":
            target = 1

        elif strategy == "ma_cross":
            if i == 0:
                target = first_previous_signal
            else:
                target = int(
                    period.iloc[i - 1]["ma_signal"]
                )
        else:
            raise ValueError("Unknown strategy")

        # 买入：使用当天开盘价
        if target == 1 and btc == 0 and cash > 0:
            btc = cash * (1 - FEE_RATE) / open_price
            cash = 0.0

            trades.append({
                "date": str(row["date"]),
                "action": "BUY",
                "price": open_price,
                "fee_rate": FEE_RATE
            })

        # 卖出
        elif target == 0 and btc > 0:
            cash = btc * open_price * (1 - FEE_RATE)
            btc = 0.0

            trades.append({
                "date": str(row["date"]),
                "action": "SELL",
                "price": open_price,
                "fee_rate": FEE_RATE
            })

        # 每天收盘计算资产价值
        value = cash + btc * close_price

        # 最后一天统一平仓
        if i == len(period) - 1 and btc > 0:
            cash = btc * close_price * (1 - FEE_RATE)
            btc = 0.0
            value = cash

            trades.append({
                "date": str(row["date"]),
                "action": "FINAL_SELL",
                "price": close_price,
                "fee_rate": FEE_RATE
            })

        values.append(value)

    return pd.Series(values, dtype=float), trades


# ========== 4. 运行两个策略 ==========

# 单策略各自投入 1000
bh_values, bh_trades = run_backtest(
    "buy_hold", INITIAL_CAPITAL
)

ma_values, ma_trades = run_backtest(
    "ma_cross", INITIAL_CAPITAL
)

# 组合：各分配 500
bh_half, bh_half_trades = run_backtest(
    "buy_hold", INITIAL_CAPITAL * 0.5
)

ma_half, ma_half_trades = run_backtest(
    "ma_cross", INITIAL_CAPITAL * 0.5
)

portfolio_values = bh_half + ma_half


# ========== 5. 绩效计算函数 ==========

def calculate_metrics(values, capital):
    equity = pd.concat([
        pd.Series([capital]),
        values.reset_index(drop=True)
    ], ignore_index=True)

    returns = equity.pct_change().dropna()

    total_return = (
        equity.iloc[-1] / capital - 1
    ) * 100

    drawdown = equity / equity.cummax() - 1
    max_drawdown = drawdown.min() * 100

    # 加密货币日线按每年 365 天计算
    if returns.std(ddof=1) > 0:
        sharpe = (
            returns.mean()
            / returns.std(ddof=1)
            * np.sqrt(365)
        )
    else:
        sharpe = 0.0

    return {
        "Total Return (%)": round(total_return, 2),
        "Max Drawdown (%)": round(max_drawdown, 2),
        "Sharpe Ratio": round(sharpe, 3),
        "Final Value (USDT)": round(
            float(equity.iloc[-1]), 2
        )
    }


# ========== 6. 汇总实验结果 ==========

results = {
    "Buy & Hold": calculate_metrics(
        bh_values, INITIAL_CAPITAL
    ),
    "MA Crossover": calculate_metrics(
        ma_values, INITIAL_CAPITAL
    ),
    "Portfolio 50/50": calculate_metrics(
        portfolio_values, INITIAL_CAPITAL
    )
}

summary = pd.DataFrame.from_dict(
    results, orient="index"
)

print("\n========== BACKTEST RESULTS ==========")
print(summary.to_string())
print("\nTrading activity:")
print("Buy & Hold:", len(bh_trades))
print("MA Crossover:", len(ma_trades))
print("Portfolio:", len(bh_half_trades) + len(ma_half_trades))
print("======================================")

summary.to_csv(OUTPUT_DIR / "strategy_comparison.csv")

# 保存每日净值
daily = pd.DataFrame({
    "date": period["date"],
    "buy_hold": bh_values,
    "ma_crossover": ma_values,
    "portfolio_50_50": portfolio_values
})

daily.to_csv(
    OUTPUT_DIR / "strategy_daily_values.csv",
    index=False
)

# 保存交易日志
pd.DataFrame(
    bh_trades
).to_csv(OUTPUT_DIR / "bh_trades.csv", index=False)

pd.DataFrame(
    ma_trades
).to_csv(OUTPUT_DIR / "ma_trades.csv", index=False)


# ========== 7. 绘制对比图 ==========

plt.figure(figsize=(12, 6))

plt.plot(
    period["date"], bh_values,
    label="Buy & Hold"
)

plt.plot(
    period["date"], ma_values,
    label="MA Crossover"
)

plt.plot(
    period["date"], portfolio_values,
    label="Portfolio 50/50"
)

plt.title("Multi-Strategy BTC Backtest")
plt.xlabel("Date")
plt.ylabel("Portfolio Value (USDT)")
plt.legend()
plt.grid(True)
plt.tight_layout()

plt.savefig(
    OUTPUT_DIR / "strategy_comparison.png",
    dpi=150
)

plt.show()
