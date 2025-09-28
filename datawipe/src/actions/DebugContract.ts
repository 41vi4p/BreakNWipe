"use server";

import { ethers } from "ethers";
import ReportRegistryArtifact from "@/lib/ABI/ReportRegistryWithJson.json";

export async function debugContract() {
  const debugInfo: any = {
    environment: {
      RPC_URL: process.env.RPC_URL,
      CONTRACT_ADDRESS: process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      PRIVATE_KEY_SET: !!process.env.PRIVATE_KEY,
    },
  };

  if (!process.env.RPC_URL) {
    return {
      success: false,
      error: "RPC_URL not set in environment variables",
      debugInfo,
    };
  }

  if (!process.env.NEXT_PUBLIC_CONTRACT_ADDRESS) {
    return {
      success: false,
      error: "NEXT_PUBLIC_CONTRACT_ADDRESS not set in environment variables",
      debugInfo,
    };
  }

  try {
    const provider = new ethers.JsonRpcProvider(process.env.RPC_URL);

    // Test provider connection
    const network = await provider.getNetwork();
    const blockNumber = await provider.getBlockNumber();

    debugInfo.network = {
      chainId: network.chainId.toString(),
      name: network.name,
      blockNumber: blockNumber.toString(),
    };

    // Check if there's code at the contract address
    const code = await provider.getCode(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS
    );
    debugInfo.contract = {
      address: process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      hasCode: code !== "0x",
      codeLength: code.length,
    };

    if (code === "0x") {
      return {
        success: false,
        error: "No contract deployed at the specified address",
        debugInfo,
        suggestion:
          "Make sure you've deployed the contract and are using the correct address",
      };
    }

    // Test contract connection
    const contract = new ethers.Contract(
      process.env.NEXT_PUBLIC_CONTRACT_ADDRESS,
      ReportRegistryArtifact.abi,
      provider
    );

    // Test a simple read function
    const totalReports = await contract.getTotalReports();
    debugInfo.contractCall = {
      totalReports: totalReports.toString(),
    };

    return {
      success: true,
      message: "Contract connection successful",
      debugInfo,
    };
  } catch (error: any) {
    console.error("Debug contract error:", error);

    debugInfo.error = {
      code: error.code,
      message: error.message,
      reason: error.reason,
    };

    let suggestion = "";
    if (error.code === "NETWORK_ERROR") {
      suggestion = "Check your RPC_URL and internet connection";
    } else if (error.code === "BAD_DATA") {
      suggestion =
        "The contract might not be deployed or the ABI might not match";
    }

    return {
      success: false,
      error: error.message,
      debugInfo,
      suggestion,
    };
  }
}
