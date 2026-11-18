
import { network } from "hardhat";
import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import {
  BACKTEST_FILE,
  PROOF_FILE,
} from "./backtest-config.js";

async function main() {
  const { ethers } = await network.create();

  // 1. 读取之前保存的存证凭据
  const proof = JSON.parse(
    readFileSync(resolve(PROOF_FILE), "utf8")
  );

  const networkInfo = await ethers.provider.getNetwork();

  // 2. 确认当前连接的是存证时使用的链
  if (networkInfo.chainId.toString() !== proof.chain_id) {
    throw new Error("Wrong blockchain network");
  }

  // 3. 重新计算本地 JSON 文件的 SHA-256
  const fileBytes = readFileSync(resolve(BACKTEST_FILE));

  const localHash = "0x" + createHash("sha256")
    .update(fileBytes)
    .digest("hex");

  // 4. 从链上读取原始哈希
  const registry = await ethers.getContractAt(
    "BacktestRegistry",
    proof.contract_address
  );

  const onChainHash: string = await registry.getHash(
    BigInt(proof.record_id)
  );

  // 5. 比较两个哈希
  const matches =
    localHash.toLowerCase() === onChainHash.toLowerCase();

  console.log("\n===== VERIFICATION =====");
  console.log("File:", BACKTEST_FILE);
  console.log("Local Hash:", localHash);
  console.log("On-chain Hash:", onChainHash);

  if (matches) {
    console.log("\nVERIFICATION PASSED");
  } else {
    console.log("\nVERIFICATION FAILED");
    process.exitCode = 1;
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});