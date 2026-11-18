import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path

# 1. 读取我们刚下载的 BTC 历史数据
data_path = Path("data/btc_daily.csv")
df = pd.read_csv(data_path)

df["date"] = pd.to_datetime(df["date"], utc=True)
df = df.sort_values("date").reset_index(drop=True)

# 2. 设置回测参数
initial_capital = 1000.0
fee_rate = 0.001  # 假设买入手续费 0.1%

# 3. 在第一天开盘时买入 BTC
buy_price = df["open"].iloc[0]

# 扣除手续费后，可实际用于持有 BTC 的资金
btc_amount = initial_capital * (1 - fee_rate) / buy_price

# 4. 计算每天持有的资产价值
df["portfolio_value"] = btc_amount * df["close"]

# 5. 计算每日收益率和最大回撤
df["daily_return"] = df["portfolio_value"].pct_change().fillna(0)

running_max = df["portfolio_value"].cummax()
df["drawdown"] = df["portfolio_value"] / running_max - 1

# 6. 计算总收益率
final_value = df["portfolio_value"].iloc[-1]
total_return = (final_value / initial_capital - 1) * 100
max_drawdown = df["drawdown"].min() * 100

# 7. 输出结果
print(f"Initial Capital: {initial_capital:.2f} USDT")
print(f"Buy Price: {buy_price:.2f} USDT")
print(f"BTC Amount: {btc_amount:.8f} BTC")
print(f"Final Value: {final_value:.2f} USDT")
print(f"Total Return: {total_return:.2f}%")
print(f"Max Drawdown: {max_drawdown:.2f}%")

# 8. 保存结果
output_dir = Path("results")
output_dir.mkdir(exist_ok=True)

df.to_csv(output_dir / "buy_and_hold.csv", index=False)

# 9. 绘制资产价值变化曲线
plt.figure(figsize=(10, 5))
plt.plot(df["date"], df["portfolio_value"])
plt.title("BTC Buy & Hold Backtest")
plt.xlabel("Date")
plt.ylabel("Portfolio Value (USDT)")
plt.grid(True)
plt.tight_layout()
plt.savefig(output_dir / "buy_and_hold.png", dpi=150)
plt.show()
