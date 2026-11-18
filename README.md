# 区块链锚定的多策略投资组合回测框架

> 课程 5017 项目（Group 27）：把加密货币策略回测的参数、数据版本与绩效结果固化为结构化 JSON，再将其 SHA-256 哈希写入区块链，实现**可复现、可验证、防篡改**的回测存证。原始日志保存在链下，链上只存哈希。

## 一、项目简介

传统量化回测存在四个痛点：结果不可复现、日志可被事后篡改、缺少可信时间戳、依赖单一机构背书。本项目的应对方式：

1. 从 Binance 下载 BTCUSDT 历史日线数据，并对每个原始数据包和最终 CSV 计算 SHA-256（见 `data/data_manifest.json`）；
2. 在牛 / 熊 / 震荡三种行情区间下分别回测三种策略，每次回测输出一份结构化 JSON；
3. 对每份 JSON 计算 SHA-256，调用智能合约将哈希与链上时间戳写入 **chainlab 测试网**；
4. 验证脚本从链上读回哈希，与本地重算的哈希比对；篡改 JSON 后验证会失败，从而证明防篡改有效。

完整需求与验收标准见 [项目说明.md](项目说明.md)。

## 二、技术栈

| 部分 | 技术选型 |
|---|---|
| 数据下载与回测 | Python 3 + pandas + numpy + matplotlib |
| 智能合约 | Solidity 0.8.34，Hardhat 3 工程框架 |
| 链上交互 | TypeScript + ethers.js v6（Hardhat 3 的 `network.create()` API） |
| 合约部署 | Hardhat Ignition |
| 测试 | Mocha + Chai（TypeScript 集成测试）、forge-std（Solidity 单元测试 / fuzz） |
| JS 包管理 | Bun（`bun.lock`，Node.js 24） |
| 区块链网络 | **chainlab 测试网**（`https://testnet.chainlab.fun`，存证记录中的 chain ID 为 31337） |
| 数据源 | Binance 现货 BTCUSDT 日线，2020-01 至 2025-12 |

> 注意：本项目**不使用 Sepolia**。`hardhat.config.ts` 中的 Sepolia 配置仅作为注释保留，实际测试网为 chainlab。

## 三、目录结构

```
trade/
├── contracts/
│   ├── BacktestRegistry.sol   # 核心存证合约：anchorBacktest() 存哈希、getHash() 查哈希
│   ├── Counter.sol            # Hardhat 示例合约（脚手架，可忽略）
│   └── Counter.t.sol          # forge-std 风格 Solidity 测试示例
├── scripts/                   # Hardhat 运行的 TypeScript 脚本
│   ├── backtest-config.ts     # 合约地址与待验证文件路径配置
│   ├── anchor-backtest.ts     # 单份 JSON 上链
│   ├── anchor-all-backtests.ts# 9 份回测 JSON 批量上链（已存证的自动跳过）
│   ├── verify-backtest.ts     # 读链上哈希与本地重算哈希比对
│   ├── check-records.ts       # 遍历打印链上全部存证记录
│   └── send-op-tx.ts          # OP Stack 模拟链发交易示例
├── ignition/
│   └── modules/
│       ├── BacktestRegistry.ts# 存证合约的 Ignition 部署模块
│       └── Counter.ts         # 示例合约部署模块
├── test/
│   └── Counter.ts             # Mocha + ethers 集成测试示例
├── backtest/                  # Python 回测逻辑
│   ├── buy_and_hold.py        # 买入持有策略
│   ├── ma_crossover.py        # 均线交叉策略（快 5 / 慢 20）
│   ├── compare_strategies.py  # 全周期策略对比，输出对比表与图
│   └── market_regimes.py      # 牛/熊/震荡三段 × 三策略，输出 9 份 JSON
├── strategies/                # 交易策略扩展目录（预留）
├── data/
│   ├── raw/                   # Binance 月度 zip 原始包及 CHECKSUM
│   ├── btc_daily.csv          # 合并后的日线数据（回测输入）
│   └── data_manifest.json     # 数据版本清单（含 CSV 与各 zip 的 SHA-256）
├── results/                   # 回测绩效输出
│   └── regimes/               # 9 份回测 JSON + 9 份 .proof.json 链上存证凭据
├── download_data.py           # 下载并合并 Binance 历史数据
├── hardhat.config.ts          # Hardhat 3 配置（编译器、网络、插件）
└── 项目说明.md                 # 项目背景、方案设计与验收标准
```

## 四、环境准备

1. 安装 Node.js 24、Bun、Python 3；
2. 安装 JS 依赖（这步应该不用按照这个，我们课上已经安装好了）我觉得应该是启动hardhat：

   ```shell
   # bun install（nonono）
   bunx hardhat@v3 --init
   ```

3. 安装 Python 依赖：

   ```shell
   pip install pandas numpy matplotlib
   ```

4. 配置 chainlab 测试网账户私钥（这步我们课上也做好了）。`hardhat.config.ts` 通过 Hardhat Configuration Variable 读取 `PRIVATE_KEY`，不会出现明文私钥：

   ```shell
   npx hardhat keystore set PRIVATE_KEY
   ```

   也可以通过环境变量 `HARDHAT_PRIVATE_KEY` 注入。

## 五、快速开始（完整流程）

以下命令均在项目根目录执行。

### 1. 下载历史数据

```shell
python download_data.py
```

下载 2020-01 至 2025-12 的 BTCUSDT 月度 zip 到 `data/raw/`，解压合并为 `data/btc_daily.csv`，并生成带全部 SHA-256 的 `data/data_manifest.json`。

### 2. 运行回测

```shell
# 全周期（2020-02 ~ 2025-12）单策略回测与对比，输出到 results/
python backtest/buy_and_hold.py
python backtest/ma_crossover.py
python backtest/compare_strategies.py

# 牛/熊/震荡三段行情 × 三策略（买入持有、均线交叉、50/50 组合），输出 9 份 JSON
python backtest/market_regimes.py
```

三段行情区间定义在 `backtest/market_regimes.py` 中：牛市 2020-10 ~ 2021-04、熊市 2022 全年、震荡市 2023-07 ~ 2023-10。

### 3. 编译合约

```shell
npx hardhat compile
```

### 4. 部署存证合约到 chainlab 测试网

```shell
npx hardhat ignition deploy ignition/modules/BacktestRegistry.ts --network chainlab
```

部署后把合约地址填入 [scripts/backtest-config.ts](scripts/backtest-config.ts) 的 `CONTRACT_ADDRESS`。当前已部署的合约地址为：

```
0x35887245652F53eA72c8D6a9FD595c9bE78Cb284
```

### 5. 将回测结果哈希上链

```shell
# 批量处理 results/regimes/ 下的 9 份 JSON；已有存证的会先验证再跳过，不重复发交易
npx hardhat run scripts/anchor-all-backtests.ts --network chainlab

# 或只上链 backtest-config.ts 中指定的单份文件
npx hardhat run scripts/anchor-backtest.ts --network chainlab
```

每份 JSON 上链后会在同目录生成 `*.proof.json` 存证凭据，记录合约地址、chain ID、record ID、交易哈希、区块号和文件 SHA-256。

### 6. 验证与篡改演示

```shell
# 重新计算本地 JSON 的 SHA-256，与链上记录比对，输出 VERIFICATION PASSED / FAILED
npx hardhat run scripts/verify-backtest.ts --network chainlab

# 查看链上全部存证记录
npx hardhat run scripts/check-records.ts --network chainlab
```

手动修改 `results/regimes/` 下任意 JSON 中的一个数字后再次运行验证脚本，本地哈希变化而链上哈希不变，即输出 `VERIFICATION FAILED`，证明存证防篡改有效。

## 六、存证合约设计

[contracts/BacktestRegistry.sol](contracts/BacktestRegistry.sol) 是一个最小化存证合约：

- `anchorBacktest(bytes32 dataHash)`：提交一条哈希存证，返回记录 ID，并触发 `BacktestAnchored` 事件；记录中同时保存提交者地址和区块时间戳；
- `getHash(uint256 recordId)`：按记录 ID 查询链上哈希；
- `recordCount`：链上存证总数。

合约不保存原始回测内容，只保存 32 字节哈希，链下 JSON 与链上哈希通过 `*.proof.json` 中的 `record_id` 关联。

## 七、网络配置

`hardhat.config.ts` 中定义了四个网络：

| 网络名 | 类型 | 用途 |
|---|---|---|
| `hardhatMainnet` | 本地模拟（edr-simulated，L1） | 本地开发与测试 |
| `hardhatOp` | 本地模拟（OP Stack L2） | OP 链类型实验 |
| `chainlab` | HTTP 测试网 | **本项目实际使用的测试网**，账户私钥取自 `PRIVATE_KEY` 配置变量 |
| `sepolia` | 已整段注释 | 未使用，仅保留配置模板 |

## 八、运行测试

```shell
npx hardhat test            # 全部测试
npx hardhat test solidity   # 仅 Solidity（forge-std）测试
npx hardhat test mocha      # 仅 TypeScript（Mocha + ethers）测试
```

## 相关文档

- [项目说明.md](项目说明.md)：项目背景、痛点分析、数据流、JSON 日志接口约定与验收标准
- [AGENTS.md](AGENTS.md)：Hardhat 3 项目布局与 AI 协作约定
