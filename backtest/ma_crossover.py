
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

# 1. 读取历史行情
df = pd.read_csv("data/btc_daily.csv")
df["date"] = pd.to_datetime(df["date"], utc=True)
df = df.sort_values("date").reset_index(drop=True)

# 2. 参数
initial_capital = 1000.0
fee_rate = 0.001
fast_window = 5
slow_window = 20

# 3. 计算均线
df["ma_fast"] = df["close"].rolling(fast_window).mean()
df["ma_slow"] = df["close"].rolling(slow_window).mean()

# 4. 生成策略信号
# 有效均线出现之前，不允许买入
df["signal"] = (
    (df["ma_fast"] > df["ma_slow"])
    & df["ma_slow"].notna()
).astype(int)

# 5. 初始化模拟账户
cash = initial_capital
btc = 0.0
portfolio_values = []
trades = []

# 6. 逐日模拟交易
for i in range(len(df)):
    row = df.iloc[i]

    # 今天开盘时，只能使用昨天收盘后的信号
    target = int(df.iloc[i - 1]["signal"]) if i > 0 else 0

    open_price = float(row["open"])

    # 希望持有 BTC，但当前没有 BTC：买入
    if target == 1 and btc == 0 and cash > 0:
        btc = cash * (1 - fee_rate) / open_price
        cash = 0.0
        trades.append({
            "date": str(row["date"]),
            "action": "BUY",
            "price": open_price
        })

    # 希望持有现金，但当前有 BTC：卖出
    elif target == 0 and btc > 0:
        cash = btc * open_price * (1 - fee_rate)
        btc = 0.0
        trades.append({
            "date": str(row["date"]),
            "action": "SELL",
            "price": open_price
        })

    # 当天收盘时计算总资产
    value = cash + btc * float(row["close"])
    portfolio_values.append(value)

# 7. 计算收益与回撤
df["portfolio_value"] = portfolio_values

final_value = df["portfolio_value"].iloc[-1]
total_return = (final_value / initial_capital - 1) * 100

# 把初始 1000 USDT 也纳入最大回撤计算
equity = pd.Series([initial_capital] + portfolio_values)
drawdown = equity / equity.cummax() - 1
max_drawdown = drawdown.min() * 100

# 8. 输出结果
print(f"Initial Capital: {initial_capital:.2f} USDT")
print(f"Final Value: {final_value:.2f} USDT")
print(f"Total Return: {total_return:.2f}%")
print(f"Max Drawdown: {max_drawdown:.2f}%")
print(f"Number of Trades: {len(trades)}")

# 9. 保存结果
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

df.to_csv(output_dir / "ma_crossover.csv", index=False)
pd.DataFrame(
    trades,
    columns=["date", "action", "price"]
).to_csv(output_dir / "ma_trades.csv", index=False)

# 10. 绘制资产曲线
plt.figure(figsize=(10, 5))
plt.plot(df["date"], df["portfolio_value"], label="MA Crossover")
plt.axhline(
    initial_capital,
    linestyle="--",
    label="Initial Capital"
)
plt.title("BTC MA Crossover Backtest")
plt.xlabel("Date")
plt.ylabel("Portfolio Value (USDT)")
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(output_dir / "ma_crossover.png", dpi=150)
plt.show()
