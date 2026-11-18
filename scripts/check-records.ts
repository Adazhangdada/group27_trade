
import { network } from "hardhat";
import { CONTRACT_ADDRESS } from "./backtest-config.js";

async function main() {
  const { ethers } = await network.create();

  const registry = await ethers.getContractAt(
    "BacktestRegistry",
    CONTRACT_ADDRESS
  );

  const count = await registry.recordCount();

  console.log("Total on-chain records:", count.toString());

  for (let i = 0n; i < count; i++) {
    const hash = await registry.getHash(i);
    console.log(`Record ${i}: ${hash}`);
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
