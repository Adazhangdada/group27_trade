
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import io
import re
import time
import urllib.request
import zipfile

import pandas as pd
import matplotlib.pyplot as plt

# ===== 1. 基本配置 =====
SYMBOL = "BTCUSDT"
START_YEAR = 2020
END_YEAR = 2025

DATA_DIR = Path("data")
RAW_DIR = DATA_DIR / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = (
    f"https://data.binance.vision/data/spot/monthly/"
    f"klines/{SYMBOL}/1d"
)

COLUMNS = [
    "open_time", "open", "high", "low", "close",
    "volume", "close_time", "quote_volume",
    "trades", "taker_base", "taker_quote", "ignore"
]


# ===== 2. 下载文件（失败后重试） =====
def download(url, path):
    if path.exists():
        return path.read_bytes()

    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                content = response.read()

            path.write_bytes(content)
            return content

        except Exception as e:
            print(f"  Download failed: {e}")
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


# ===== 3. 下载并验证每个月 =====
all_frames = []
source_hashes = {}

for year in range(START_YEAR, END_YEAR + 1):
    for month in range(1, 13):
        name = f"{SYMBOL}-1d-{year}-{month:02d}.zip"
        url = f"{BASE_URL}/{name}"

        print(f"Processing {year}-{month:02d} ...")

        zip_path = RAW_DIR / name
        checksum_path = RAW_DIR / f"{name}.CHECKSUM"

        zip_bytes = download(url, zip_path)
        checksum_bytes = download(
            url + ".CHECKSUM", checksum_path
        )

        # 检查 ZIP 的 SHA-256 是否匹配官方记录
        checksum_text = checksum_bytes.decode("utf-8")
        match = re.search(
            r"\b[a-fA-F0-9]{64}\b", checksum_text
        )

        if not match:
            raise ValueError(f"Invalid CHECKSUM: {name}")

        expected_hash = match.group(0).lower()
        actual_hash = hashlib.sha256(
            zip_bytes
        ).hexdigest()

        if actual_hash != expected_hash:
            raise ValueError(
                f"SHA-256 mismatch: {name}"
            )

        source_hashes[name] = actual_hash

        # 解压 CSV
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
            csv_names = [
                n for n in z.namelist()
                if n.endswith(".csv")
            ]

            if len(csv_names) != 1:
                raise ValueError(
                    f"Unexpected ZIP contents: {name}"
                )

            with z.open(csv_names[0]) as f:
                df = pd.read_csv(
                    f, header=None, names=COLUMNS
                )

        # 2025 年起 Spot 时间戳为微秒
        unit = "us" if year >= 2025 else "ms"

        df["date"] = pd.to_datetime(
            df["open_time"],
            unit=unit,
            utc=True
        )

        for col in [
            "open", "high", "low", "close", "volume"
        ]:
            df[col] = pd.to_numeric(
                df[col], errors="raise"
            )

        df = df[[
            "date", "open", "high",
            "low", "close", "volume"
        ]]

        all_frames.append(df)


# ===== 4. 合并全部数据 =====
data = pd.concat(
    all_frames, ignore_index=True
)

data = data.sort_values(
    "date"
).reset_index(drop=True)


# ===== 5. 检查数据质量 =====
if data["date"].duplicated().any():
    raise ValueError("Duplicate dates found!")

if data.isna().any().any():
    raise ValueError("Missing values found!")

if (data[["open", "high", "low", "close"]] <= 0).any().any():
    raise ValueError("Invalid prices found!")

# 验证每天都有一条记录
expected_dates = pd.date_range(
    start=f"{START_YEAR}-01-01",
    end=f"{END_YEAR}-12-31",
    freq="D",
    tz="UTC"
)

missing_dates = expected_dates.difference(data["date"])
extra_dates = data.loc[
    ~data["date"].isin(expected_dates), "date"
]

if len(missing_dates) or len(extra_dates):
    raise ValueError(
        f"Missing dates: {len(missing_dates)}, "
        f"unexpected dates: {len(extra_dates)}"
    )


# ===== 6. 保存 CSV =====
output_path = DATA_DIR / "btc_daily.csv"

data.to_csv(
    output_path,
    index=False,
    date_format="%Y-%m-%dT%H:%M:%SZ",
    float_format="%.8f"
)

csv_hash = hashlib.sha256(
    output_path.read_bytes()
).hexdigest()

# 记录数据版本信息
import json

manifest = {
    "symbol": SYMBOL,
    "market": "binance_spot",
    "interval": "1d",
    "start": f"{START_YEAR}-01-01",
    "end": f"{END_YEAR}-12-31",
    "rows": len(data),
    "csv_sha256": csv_hash,
    "source_zip_sha256": source_hashes,
    "generated_at_utc": datetime.now(
        timezone.utc
    ).isoformat()
}

(DATA_DIR / "data_manifest.json").write_text(
    json.dumps(manifest, indent=2),
    encoding="utf-8"
)


# ===== 7. 绘图 =====
plt.figure(figsize=(12, 5))
plt.plot(data["date"], data["close"])
plt.title("BTC/USDT Daily Price (2020-2025)")
plt.xlabel("Date")
plt.ylabel("BTC Price (USDT)")
plt.grid(True)
plt.tight_layout()

plt.savefig(
    DATA_DIR / "btc_price.png",
    dpi=150
)
plt.close()


# ===== 8. 输出总结 =====
print("\n========== DATA SUMMARY ==========")
print("Rows:", len(data))
print("Start:", data["date"].min())
print("End:", data["date"].max())
print("CSV SHA-256:", csv_hash)
print("Output:", output_path)
print("All monthly checksums verified.")
print("==================================")
