
import { network } from "hardhat";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  CONTRACT_ADDRESS,
  BACKTEST_FILE,
  PROOF_FILE,
} from "./backtest-config.js";

async function main() {
  // 1. 连接 Hardhat 选定的区块链网络
  const { ethers } = await network.create();

  // 2. 检查合约地址
  if (!ethers.isAddress(CONTRACT_ADDRESS)) {
    throw new Error("Please set a valid contract address");
  }

  const networkInfo = await ethers.provider.getNetwork();
  console.log("Chain ID:", networkInfo.chainId.toString());

  // 3. 读取本地回测 JSON 的原始字节
  const fileBytes = readFileSync(resolve(BACKTEST_FILE));

  // 4. 计算 SHA-256
  const hash = "0x" + createHash("sha256")
    .update(fileBytes)
    .digest("hex");

  console.log("Local SHA-256:", hash);

  // 5. 连接已经部署的智能合约
  const registry = await ethers.getContractAt(
    "BacktestRegistry",
    CONTRACT_ADDRESS
  );

  // 6. 向合约提交哈希
  console.log("Submitting transaction...");
  const tx = await registry.anchorBacktest(hash);

  console.log("Transaction Hash:", tx.hash);

  // 7. 等待区块链确认
  const receipt = await tx.wait();

  if (!receipt || receipt.status !== 1) {
    throw new Error("Transaction failed");
  }

  // 8. 从合约事件中读取 Record ID
  let recordId: string | undefined;

  for (const log of receipt.logs) {
    try {
      const parsed = registry.interface.parseLog(log);

      if (parsed?.name === "BacktestAnchored") {
        recordId = parsed.args.recordId.toString();
        break;
      }
    } catch {
      // 忽略不属于该合约事件的日志
    }
  }

  if (recordId === undefined) {
    throw new Error("BacktestAnchored event not found");
  }

  // 9. 保存链上存证凭据
  const proof = {
    contract_address: CONTRACT_ADDRESS,
    chain_id: networkInfo.chainId.toString(),
    record_id: recordId,
    transaction_hash: tx.hash,
    block_number: receipt.blockNumber,
    file: BACKTEST_FILE,
    sha256: hash
  };

  writeFileSync(
    resolve(PROOF_FILE),
    JSON.stringify(proof, null, 2) + "\n",
    "utf8"
  );

  console.log("\n===== ANCHOR SUCCESS =====");
  console.log("Record ID:", recordId);
  console.log("Proof saved:", PROOF_FILE);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
