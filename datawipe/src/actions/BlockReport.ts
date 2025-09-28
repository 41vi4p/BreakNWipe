"use server";

import { ethers } from "ethers";
import ReportRegistryArtifact from "@/lib/ABI/ReportRegistryWithJson.json";

export async function storeReportOnChain(report: object) {
  const reportJson = JSON.stringify(report);

  if (!process.env.RPC_URL) {
    throw new Error("RPC_URL not set in environment variables");
  }

  if (!process.env.PRIVATE_KEY) {
    throw new Error("PRIVATE_KEY not set in environment variables");
  }

  if (!process.env.NEXT_PUBLIC_CONTRACT_ADDRESS) {
    throw new Error(
      "NEXT_PUBLIC_CONTRACT_ADDRESS not set in environment variables"
    );
  }

  try {
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);
    const wallet = new ethers.Wallet(process.env.PRIVATE_KEY, provider);

    const contract = new ethers.Contract(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      ReportRegistryArtifact.abi,
      wallet
    );

    // Store full JSON on-chain (expensive)
    const tx = await contract.storeReportOnChain(reportJson);
    await tx.wait();

    const reportHash = ethers.keccak256(ethers.toUtf8Bytes(reportJson));

    return { txHash: tx.hash, reportHash };
  } catch (error: any) {
    console.error("Error in storeReportOnChain:", error);

    if (error.code === "INSUFFICIENT_FUNDS") {
      throw new Error("Insufficient funds to complete transaction");
    }

    if (error.code === "NETWORK_ERROR") {
      throw new Error("Network error - check RPC URL and internet connection");
    }

    if (error.reason && error.reason.includes("already stored")) {
      throw new Error("Report with this hash has already been stored");
    }

    throw new Error(`Transaction failed: ${error.message || error}`);
  }
}

export async function fetchReportByHash(hash: string) {
  if (!process.env.NEXT_PUBLIC_CONTRACT_ADDRESS) {
    throw new Error("Contract address not set in env");
  }

  if (!process.env.RPC_URL) {
    throw new Error("RPC_URL not set in env");
  }

  // Ensure hash is valid bytes32
  if (!hash.startsWith("0x") || hash.length !== 66) {
    throw new Error(
      "Invalid bytes32 hash format - must be 0x followed by 64 hex characters"
    );
  }

  try {
    // Use provider for read-only calls
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);

    const contract = new ethers.Contract(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      ReportRegistryArtifact.abi,
      provider
    );

    // Call verifyReport
    const [exists, submitter, timestamp, storedOnChain, ipfsCid] =
      await contract.verifyReport(hash);

    let json = "";
    if (storedOnChain) {
      json = await contract.getStoredJson(hash);
    }

    return { exists, submitter, timestamp, storedOnChain, ipfsCid, json };
  } catch (error: any) {
    console.error("Error in fetchReportByHash:", error);

    if (error.code === "BAD_DATA" && error.value === "0x") {
      throw new Error(
        "Contract call failed - check if contract address is correct and deployed"
      );
    }

    if (error.code === "NETWORK_ERROR") {
      throw new Error("Network error - check RPC URL and internet connection");
    }

    throw new Error(`Blockchain error: ${error.message || error}`);
  }
}

export async function getAllReportHashes() {
  if (!process.env.NEXT_PUBLIC_CONTRACT_ADDRESS) {
    throw new Error("Contract address not set in env");
  }

  if (!process.env.RPC_URL) {
    throw new Error("RPC_URL not set in env");
  }

  try {
    // Use provider for read-only calls
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);

    const contract = new ethers.Contract(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      ReportRegistryArtifact.abi,
      provider
    );

    // Get total number of reports
    const totalReports = await contract.getTotalReports();
    const totalReportsNum = Number(totalReports);

    // Get all report hashes
    const hashes: string[] = [];
    for (let i = 0; i < totalReportsNum; i++) {
      const hash = await contract.getReportHashByIndex(i);
      hashes.push(hash);
    }

    return hashes;
  } catch (error: any) {
    console.error("Error in getAllReportHashes:", error);

    if (error.code === "BAD_DATA" && error.value === "0x") {
      throw new Error(
        "Contract call failed - check if contract address is correct and deployed"
      );
    }

    if (error.code === "NETWORK_ERROR") {
      throw new Error("Network error - check RPC URL and internet connection");
    }

    throw new Error(`Blockchain error: ${error.message || error}`);
  }
}

export async function getStoredJsonByHash(reportHash: string) {
  if (!process.env.NEXT_PUBLIC_CONTRACT_ADDRESS) {
    throw new Error("Contract address not set in env");
  }

  if (!process.env.RPC_URL) {
    throw new Error("RPC_URL not set in env");
  }

  // Ensure hash is valid bytes32
  if (!reportHash.startsWith("0x") || reportHash.length !== 66) {
    throw new Error(
      "Invalid bytes32 hash format - must be 0x followed by 64 hex characters"
    );
  }

  try {
    // Use provider for read-only calls
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);

    const contract = new ethers.Contract(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      ReportRegistryArtifact.abi,
      provider
    );

    // Call getStoredJson with the hash parameter
    const storedJson = await contract.getStoredJson(reportHash);
    return storedJson;
  } catch (error: any) {
    console.error("Error in getStoredJsonByHash:", error);

    if (error.code === "BAD_DATA" && error.value === "0x") {
      throw new Error(
        "Contract call failed - check if contract address is correct and deployed"
      );
    }

    if (error.code === "NETWORK_ERROR") {
      throw new Error("Network error - check RPC URL and internet connection");
    }

    throw new Error(`Blockchain error: ${error.message || error}`);
  }
}
