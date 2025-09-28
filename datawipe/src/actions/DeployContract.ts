"use server";

import { ethers } from "ethers";
import ReportRegistryArtifact from "@/lib/ABI/ReportRegistryWithJson.json";

export async function deployContract() {
  if (!process.env.RPC_URL) {
    throw new Error("RPC_URL not set");
  }

  if (!process.env.PRIVATE_KEY) {
    throw new Error("PRIVATE_KEY not set - needed to deploy contract");
  }

  try {
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);

    // Check wallet balance
    const balance = await provider.getBalance(wallet.address);
    console.log("Deployer balance:", ethers.formatEther(balance), "ETH");

    if (balance === BigInt(0)) {
      throw new Error("Deployer wallet has no balance for gas fees");
    }

    // Create contract factory
    const contractFactory = new ethers.ContractFactory(
      ReportRegistryArtifact.abi,
      ReportRegistryArtifact.bytecode,
      wallet
    );

    console.log("Deploying contract...");
    const contract = await contractFactory.deploy();

    console.log("Waiting for deployment...");
    const receipt = await contract.deploymentTransaction()?.wait();

    const contractAddress = await contract.getAddress();

    return {
      success: true,
      contractAddress,
      transactionHash: receipt?.hash,
      deployerAddress: wallet.address,
      balance: ethers.formatEther(balance),
    };
  } catch (error: any) {
    console.error("Deployment error:", error);

    let errorMessage = error.message;
    if (error.code === "INSUFFICIENT_FUNDS") {
      errorMessage = "Insufficient funds for deployment";
    } else if (error.code === "NETWORK_ERROR") {
      errorMessage = "Network error - check RPC URL";
    }

    return {
      success: false,
      error: errorMessage,
    };
  }
}
