"use client";

import { useState } from "react";
import {
  storeReportOnChain,
  fetchReportByHash,
  getAllReportHashes,
  getStoredJsonByHash,
} from "@/actions/BlockReport";
import { debugContract } from "@/actions/DebugContract";
import { deployContract } from "@/actions/DeployContract";
import { ethers } from "ethers";

const json = '{ id: "001", name: "Test Report" }';
const hash = ethers.keccak256(ethers.toUtf8Bytes(json));
console.log(hash); // 0x + 64 hex chars

export default function ReportForm() {
  const [status, setStatus] = useState("");
  const [storedHash, setStoredHash] = useState("");

  async function handleStore() {
    const report = { id: "001", name: "Test Report", status: "verified" };
    setStatus("Storing report...");
    try {
      const { txHash, reportHash } = await storeReportOnChain(report);
      setStoredHash(reportHash);
      setStatus(`Stored! Tx: ${txHash}, Hash: ${reportHash}`);
    } catch (error) {
      setStatus(
        `Error storing report: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }
  }

  async function handleFetch(inputHash: string) {
    if (!inputHash || inputHash.length !== 66 || !inputHash.startsWith("0x")) {
      alert("Please enter a valid 32-byte report hash (0x...)");
      return;
    }

    setStatus("Fetching report...");
    try {
      const report = await fetchReportByHash(inputHash);
      if (report.exists) {
        // Convert BigInt values to strings for JSON serialization
        const displayReport = {
          ...report,
          timestamp: report.timestamp.toString(),
          timestampDate: new Date(
            Number(report.timestamp) * 1000
          ).toLocaleString(),
        };
        setStatus(JSON.stringify(displayReport, null, 2));
      } else {
        setStatus("Report not found on blockchain");
      }
    } catch (error) {
      setStatus(
        `Error fetching report: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }
  }

  function handleFetchStored() {
    if (storedHash) {
      handleFetch(storedHash);
    } else {
      alert("No report hash available. Please store a report first.");
    }
  }

  async function handleDebug() {
    setStatus("Debugging contract connection...");
    try {
      const result = await debugContract();
      setStatus(JSON.stringify(result, null, 2));
    } catch (error) {
      setStatus(
        `Debug error: ${error instanceof Error ? error.message : String(error)}`
      );
    }
  }

  async function handleDeploy() {
    setStatus("Deploying contract...");
    try {
      const result = await deployContract();
      if (result.success) {
        setStatus(
          `Contract deployed successfully!\n\n` +
            `Contract Address: ${result.contractAddress}\n` +
            `Transaction Hash: ${result.transactionHash}\n` +
            `Deployer: ${result.deployerAddress}\n` +
            `Balance: ${result.balance} ETH\n\n` +
            `Add this to your .env.local file:\n` +
            `NEXT_PUBLIC_CONTRACT_ADDRESS=${result.contractAddress}`
        );
      } else {
        setStatus(`Deployment failed: ${result.error}`);
      }
    } catch (error) {
      setStatus(
        `Deployment error: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }
  }

  async function handleGetAllReports() {
    setStatus("Fetching all stored reports...");
    try {
      const hashes = await getAllReportHashes();

      if (hashes.length === 0) {
        setStatus("No reports found on blockchain");
        return;
      }

      let allReports = `Found ${hashes.length} reports on blockchain:\n\n`;

      // Fetch details for each report
      for (let i = 0; i < hashes.length; i++) {
        const hash = hashes[i];
        try {
          const report = await fetchReportByHash(hash);
          allReports += `Report ${i + 1}:\n`;
          allReports += `  Hash: ${hash}\n`;
          allReports += `  Submitter: ${report.submitter}\n`;
          allReports += `  Timestamp: ${new Date(
            Number(report.timestamp) * 1000
          ).toLocaleString()}\n`;
          allReports += `  Stored On-Chain: ${report.storedOnChain}\n`;

          if (report.storedOnChain && report.json) {
            allReports += `  JSON Data: ${report.json}\n`;
          }

          if (report.ipfsCid) {
            allReports += `  IPFS CID: ${report.ipfsCid}\n`;
          }

          allReports += `\n`;
        } catch (error) {
          allReports += `Report ${i + 1}: Error fetching details - ${
            error instanceof Error ? error.message : String(error)
          }\n\n`;
        }
      }

      setStatus(allReports);
    } catch (error) {
      setStatus(
        `Error fetching reports: ${
          error instanceof Error ? error.message : String(error)
        }`
      );
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-6 text-center text-blue-700">
        Blockchain Report Demo
      </h2>

      {/* Action Buttons */}
      <div className="flex flex-wrap gap-4 mb-6 justify-center">
        <button
          onClick={handleDebug}
          className="px-4 py-2 bg-gray-200 text-black hover:bg-gray-300 rounded shadow"
        >
          Debug Contract
        </button>
        <button
          onClick={handleDeploy}
          className="px-4 py-2 bg-orange-500 text-white hover:bg-orange-600 rounded shadow"
        >
          Deploy Contract
        </button>
        <button
          onClick={handleStore}
          className="px-4 py-2 bg-blue-500 text-white hover:bg-blue-600 rounded shadow"
        >
          Store Report On-Chain
        </button>
        <button
          onClick={handleGetAllReports}
          className="px-4 py-2 bg-purple-500 text-white hover:bg-purple-600 rounded shadow"
        >
          Get All Reports
        </button>
        {storedHash && (
          <button
            onClick={handleFetchStored}
            className="px-4 py-2 bg-green-500 text-white hover:bg-green-600 rounded shadow"
          >
            Fetch Stored Report
          </button>
        )}
      </div>

      {/* Input + Fetch Button */}
      <div className="flex flex-col md:flex-row gap-4 items-center mb-6">
        <input
          id="hash"
          placeholder="Enter report hash (0x...)"
          className="flex-1 px-4 py-2 border border-gray-300 rounded shadow focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
        <button
          onClick={() =>
            handleFetch(
              (document.getElementById("hash") as HTMLInputElement).value.trim()
            )
          }
          className="px-4 py-2 bg-indigo-500 text-white hover:bg-indigo-600 rounded shadow"
        >
          Fetch Report by Hash
        </button>
      </div>

      {/* Status / Output */}
      <pre className="bg-gray-100 text-black p-4 rounded shadow whitespace-pre-wrap text-sm md:text-base">
        {status || "Status updates will appear here..."}
      </pre>
    </div>
  );
}
