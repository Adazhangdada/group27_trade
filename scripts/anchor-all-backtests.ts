
import { network } from "hardhat";
import { createHash } from "node:crypto";
import {
  existsSync,
  readFileSync,
  writeFileSync,
} from "node:fs";
import { resolve } from "node:path";
import { CONTRACT_ADDRESS } from "./backtest-config.js";

// 9 份需要上链的回测记录
const REGIMES = ["bull", "bear", "sideways"];
const STRATEGIES = [
  "buy_hold",
  "ma_cross",
  "portfolio_50_50",
];

function fileHash(path: string): string {
  return "0x" + createHash("sha256")
    .update(readFileSync(resolve(path)))
    .digest("hex");
}

async function main() {
  const { ethers } = await network.create();
  const provider = ethers.provider;
  const net = await provider.getNetwork();

  if (!ethers.isAddress(CONTRACT_ADDRESS)) {
    throw new Error("Invalid contract address");
  }

  const contract = await ethers.getContractAt(
    "BacktestRegistry",
    CONTRACT_ADDRESS
  );

  const code = await provider.getCode(CONTRACT_ADDRESS);

  if (code === "0x") {
    throw new Error("Contract not found on this network");
  }

  // 用创世区块标识当前网络实例
  const genesis = await provider.getBlock(0);
  if (!genesis) {
    throw new Error("Cannot read genesis block");
  }

  console.log("Chain ID:", net.chainId.toString());
  console.log("Contract:", CONTRACT_ADDRESS);
  console.log("Genesis:", genesis.hash);

  // 逐份处理
  for (const regime of REGIMES) {
    for (const strategy of STRATEGIES) {
      const name = `${regime}_${strategy}`;
      const jsonPath = `results/regimes/${name}.json`;
      const proofPath = `results/regimes/${name}.proof.json`;

      console.log(`\nProcessing: ${name}`);

      if (!existsSync(resolve(jsonPath))) {
        throw new Error(`Missing JSON: ${jsonPath}`);
      }

      const hash = fileHash(jsonPath);

      // 已有存证：验证后跳过，避免重复交易
      if (existsSync(resolve(proofPath))) {
        const proof = JSON.parse(
          readFileSync(resolve(proofPath), "utf8")
        );

        if (
          proof.contract_address.toLowerCase() !==
            CONTRACT_ADDRESS.toLowerCase() ||
          proof.chain_id !== net.chainId.toString()
        ) {
          throw new Error(
            `Proof network/contract mismatch: ${name}`
          );
        }

        if (
          proof.genesis_hash &&
          proof.genesis_hash !== genesis.hash
        ) {
          throw new Error(
            `Network genesis mismatch: ${name}`
          );
        }

        const onChainHash = await contract.getHash(
          BigInt(proof.record_id)
        );

        if (
          hash.toLowerCase() !==
            onChainHash.toLowerCase() ||
          hash.toLowerCase() !==
            proof.sha256.toLowerCase()
        ) {
          throw new Error(
            `Existing proof verification failed: ${name}`
          );
        }

        console.log("Already anchored. Verified; skipping.");
        continue;
      }

      // 尚无存证：提交区块链交易
      const tx = await contract.anchorBacktest(hash);
      console.log("Transaction:", tx.hash);

      const receipt = await tx.wait();

      if (!receipt || receipt.status !== 1) {
        throw new Error(`Transaction failed: ${name}`);
      }

      // 读取合约事件，获取 Record ID
      let recordId: string | undefined;

      for (const log of receipt.logs) {
        if (
          log.address.toLowerCase() !==
          CONTRACT_ADDRESS.toLowerCase()
        ) {
          continue;
        }

        try {
          const parsed = contract.interface.parseLog(log);

          if (parsed?.name === "BacktestAnchored") {
            if (
              parsed.args.dataHash.toLowerCase() !==
              hash.toLowerCase()
            ) {
              throw new Error("Event hash mismatch");
            }

            recordId = parsed.args.recordId.toString();
            break;
          }
        } catch (error) {
          throw error;
        }
      }

      if (recordId === undefined) {
        throw new Error(`Event not found: ${name}`);
      }

      // 再从合约状态中核对
      const storedHash = await contract.getHash(
        BigInt(recordId)
      );

      if (storedHash.toLowerCase() !== hash.toLowerCase()) {
        throw new Error("Stored hash mismatch");
      }

      const proof = {
        chain_id: net.chainId.toString(),
        genesis_hash: genesis.hash,
        contract_address: CONTRACT_ADDRESS,
        record_id: recordId,
        transaction_hash: tx.hash,
        block_number: receipt.blockNumber,
        file: jsonPath,
        sha256: hash,
      };

      writeFileSync(
        resolve(proofPath),
        JSON.stringify(proof, null, 2) + "\n",
        { encoding: "utf8", flag: "wx" }
      );

      console.log("Anchored successfully. ID:", recordId);
    }
  }

  console.log("\nAll 9 records processed.");
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
