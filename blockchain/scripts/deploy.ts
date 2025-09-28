import { network } from "hardhat";

const { ethers } = await network.connect({
  network: "sepolia",
  chainType: "l1",
});
async function main() {
  console.log("Deploying ReportRegistryWithJson...");

  // Call getContractFactory directly on the imported ethers object
  const ReportRegistry = await ethers.getContractFactory(
    "ReportRegistryWithJson"
  );
  const reportRegistry = await ReportRegistry.deploy();

  await reportRegistry.waitForDeployment();

  const contractAddress = await reportRegistry.getAddress();
  console.log("✅ Contract deployed successfully at:", contractAddress);
}

main().catch((error) => {
  console.error("❌ Deployment failed:", error);
  process.exitCode = 1;
});
