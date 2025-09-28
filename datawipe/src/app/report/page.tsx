"use client";
import { useSearchParams, useRouter } from "next/navigation";
import { Suspense, useState, useEffect } from "react";
import { generatePdfReport } from "@/actions/MakePdf";
import { generateReportImage, downloadReportImage } from "@/actions/MakePhoto";
import { storeReportOnChain, fetchReportByHash } from "@/actions/BlockReport";
import { ethers } from "ethers";

interface DecryptedData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

function ReportContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);
  const [isGeneratingImage, setIsGeneratingImage] = useState(false);
  const [reportImage, setReportImage] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"image" | "text">("image");

  // Blockchain states
  const [blockchainStatus, setBlockchainStatus] = useState<
    | "checking"
    | "exists"
    | "uploading"
    | "uploaded"
    | "error"
    | "not_configured"
  >("checking");
  const [reportHash, setReportHash] = useState<string | null>(null);
  const [blockchainData, setBlockchainData] = useState<any>(null);
  const [blockchainError, setBlockchainError] = useState<string | null>(null);

  // Parse the data from URL parameters
  const dataParam = searchParams.get("data");
  let decryptedData: DecryptedData | null = null;

  if (dataParam) {
    try {
      decryptedData = JSON.parse(decodeURIComponent(dataParam));
    } catch (error) {
      console.error("Error parsing data:", error);
    }
  }

  const handleGenerateImage = async () => {
    if (!decryptedData) return;

    setIsGeneratingImage(true);
    try {
      const imageUrl = await generateReportImage(decryptedData);
      setReportImage(imageUrl);
    } catch (error) {
      console.error("Error generating image:", error);
      alert("Failed to generate image. Please try again.");
    } finally {
      setIsGeneratingImage(false);
    }
  };

  // Auto-generate image when component loads
  useEffect(() => {
    if (decryptedData && !reportImage && !isGeneratingImage) {
      handleGenerateImage();
    }
  }, [decryptedData]);

  // Auto-check blockchain when component loads
  useEffect(() => {
    if (decryptedData && blockchainStatus === "checking") {
      handleBlockchainIntegration();
    }
  }, [decryptedData]);

  const handleGoBack = () => {
    router.push("/");
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDownloadPdf = async () => {
    if (!decryptedData) return;

    setIsGeneratingPdf(true);
    try {
      const pdfData = await generatePdfReport(decryptedData);

      // Create blob and download
      const blob = new Blob([new Uint8Array(pdfData)], {
        type: "application/pdf",
      });
      const url = URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `DataWipe_Report_${
        new Date().toISOString().split("T")[0]
      }.pdf`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);

      URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error generating PDF:", error);
      alert("Failed to generate PDF. Please try again.");
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const handleDownloadImage = async () => {
    if (!decryptedData) return;

    setIsGeneratingImage(true);
    try {
      await downloadReportImage(decryptedData);
    } catch (error) {
      console.error("Error downloading image:", error);
      alert("Failed to download image. Please try again.");
    } finally {
      setIsGeneratingImage(false);
    }
  };

  // Blockchain functionality
  const handleBlockchainIntegration = async () => {
    if (!decryptedData) return;

    // Check if we're in development mode and blockchain might not be set up
    const isDevelopment = process.env.NODE_ENV === "development";

    try {
      setBlockchainStatus("checking");
      setBlockchainError(null);

      // Generate report hash from the decrypted data
      const reportJson = JSON.stringify(decryptedData);
      const hash = ethers.keccak256(ethers.toUtf8Bytes(reportJson));
      setReportHash(hash);

      // First try to check if report exists
      try {
        const existingReport = await fetchReportByHash(hash);

        if (existingReport.exists) {
          setBlockchainStatus("exists");
          setBlockchainData({
            ...existingReport,
            timestamp: existingReport.timestamp.toString(),
          });
          return;
        }
      } catch (checkError: any) {
        console.error("Error checking existing report:", checkError);

        // If we can't even check the blockchain, likely not configured or deployed
        if (
          checkError.message?.includes("Contract call failed") ||
          checkError.message?.includes("BAD_DATA") ||
          checkError.message?.includes("missing revert data")
        ) {
          if (isDevelopment) {
            setBlockchainStatus("not_configured");
            setBlockchainError(
              "Blockchain not configured for development. Deploy contract first or configure environment variables."
            );
          } else {
            setBlockchainStatus("error");
            setBlockchainError("Blockchain service temporarily unavailable");
          }
          return;
        }
      }

      // Try to upload to blockchain
      try {
        setBlockchainStatus("uploading");
        const result = await storeReportOnChain(decryptedData);
        setBlockchainStatus("uploaded");

        // Fetch the uploaded data to confirm
        const uploadedReport = await fetchReportByHash(result.reportHash);
        setBlockchainData({
          ...uploadedReport,
          timestamp: uploadedReport.timestamp.toString(),
        });
      } catch (uploadError: any) {
        console.error("Error uploading to blockchain:", uploadError);

        let errorMessage = "Failed to upload to blockchain";

        if (
          uploadError.message?.includes("missing revert data") ||
          uploadError.message?.includes("CALL_EXCEPTION")
        ) {
          errorMessage = isDevelopment
            ? "Contract not deployed or Hardhat network not running"
            : "Blockchain service unavailable";
        } else if (uploadError.message?.includes("INSUFFICIENT_FUNDS")) {
          errorMessage = "Insufficient funds for blockchain transaction";
        } else if (uploadError.message?.includes("already stored")) {
          errorMessage = "Report already exists on blockchain";
        }

        setBlockchainError(errorMessage);
        setBlockchainStatus("error");
      }
    } catch (error: any) {
      console.error("Blockchain integration error:", error);
      setBlockchainError("Blockchain integration failed");
      setBlockchainStatus("error");
    }
  };

  if (!decryptedData) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-900 via-gray-800 to-black">
        <div className="bg-white/6 backdrop-blur-md shadow-2xl rounded-2xl p-8 max-w-md w-full text-center border border-white/10">
          <h1 className="text-2xl font-semibold text-white mb-4">
            No Data Found
          </h1>
          <p className="text-gray-400 mb-6">
            No verification data was provided.
          </p>
          <button
            onClick={handleGoBack}
            className="px-6 py-2 bg-blue-600 text-white rounded-md shadow hover:bg-blue-700 transition-colors"
          >
            Go Back to Scanner
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-900 via-gray-800 to-black py-8 px-2">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <div className="bg-white/6 backdrop-blur-md shadow-2xl rounded-2xl px-2 py-4 mb-6 border border-white/10">
          <div className="flex flex-col mx-auto md:flex-row gap-4 items-center justify-center">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 bg-gradient-to-r from-blue-500 to-indigo-600 rounded-md flex items-center justify-center">
                <div className="w-4 h-4 bg-white rounded-sm"></div>
              </div>
              <div>
                <h1 className="text-xl font-semibold text-white">
                  BreakNWipe Verification Report
                </h1>
                <p className="text-gray-400 text-sm">
                  Device Sanitization Certificate
                </p>
              </div>
            </div>
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={handleDownloadPdf}
                disabled={isGeneratingPdf}
                className="px-4 py-2 bg-purple-600 text-white rounded-md shadow hover:bg-purple-700 transition-colors disabled:bg-purple-400 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isGeneratingPdf ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></div>
                    Generating...
                  </>
                ) : (
                  "Download PDF"
                )}
              </button>
              <button
                onClick={handleGoBack}
                className="px-4 py-2 bg-blue-600 text-white rounded-md shadow hover:bg-blue-700 transition-colors"
              >
                Back to Scanner
              </button>
            </div>
          </div>
        </div>

        {/* Report Content */}
        <div className="bg-white/6 backdrop-blur-md shadow-2xl rounded-2xl py-4 px-2 border border-white/10 print:bg-white print:text-black print:shadow-none">
          {/* Verification Status */}
          {/* <div className="mb-8 text-center">
            <div className="inline-flex items-center gap-2 px-6 py-3 bg-green-900/30 rounded-full border border-green-500/30">
              <span className="text-xl">✅</span>
              <span className="text-lg font-semibold text-green-400">
                Verification Complete
              </span>
            </div>
          </div> */}

          {/* Blockchain Status */}
          <div className="mb-6">
            {blockchainStatus === "checking" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-blue-900/30 rounded-full border border-blue-500/30">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-blue-400 border-t-transparent"></div>
                  <span className="text-lg font-semibold text-blue-400">
                    Checking Blockchain...
                  </span>
                </div>
              </div>
            )}

            {blockchainStatus === "exists" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-green-900/30 rounded-full border border-green-500/30 mb-4">
                  <span className="text-xl">🔗</span>
                  <span className="text-lg font-semibold text-green-400">
                    Report Verified on Blockchain
                  </span>
                </div>
                {blockchainData && (
                  <div className="bg-white/5 rounded-lg p-4 border border-white/10 max-w-2xl mx-auto">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-400">Block Hash:</span>
                        <p className="text-white font-mono text-xs break-all">
                          {reportHash}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Submitter:</span>
                        <p className="text-white font-mono text-xs">
                          {blockchainData.submitter}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Timestamp:</span>
                        <p className="text-white">
                          {new Date(
                            Number(blockchainData.timestamp) * 1000
                          ).toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Stored On-Chain:</span>
                        <p className="text-white">
                          {blockchainData.storedOnChain ? "Yes" : "No"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {blockchainStatus === "uploading" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-yellow-900/30 rounded-full border border-yellow-500/30">
                  <div className="animate-spin rounded-full h-4 w-4 border-2 border-yellow-400 border-t-transparent"></div>
                  <span className="text-lg font-semibold text-yellow-400">
                    Uploading to Blockchain...
                  </span>
                </div>
              </div>
            )}

            {blockchainStatus === "uploaded" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-emerald-900/30 rounded-full border border-emerald-500/30 mb-4">
                  <span className="text-xl">✅</span>
                  <span className="text-lg font-semibold text-emerald-400">
                    Report Uploaded to Blockchain
                  </span>
                </div>
                {blockchainData && (
                  <div className="bg-white/5 rounded-lg p-4 border border-white/10 max-w-2xl mx-auto">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                      <div>
                        <span className="text-gray-400">Block Hash:</span>
                        <p className="text-white font-mono text-xs break-all">
                          {reportHash}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Submitter:</span>
                        <p className="text-white font-mono text-xs">
                          {blockchainData.submitter}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Timestamp:</span>
                        <p className="text-white">
                          {new Date(
                            Number(blockchainData.timestamp) * 1000
                          ).toLocaleString()}
                        </p>
                      </div>
                      <div>
                        <span className="text-gray-400">Stored On-Chain:</span>
                        <p className="text-white">
                          {blockchainData.storedOnChain ? "Yes" : "No"}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            )}

            {blockchainStatus === "error" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-red-900/30 rounded-full border border-red-500/30 mb-2">
                  <span className="text-xl">⚠️</span>
                  <span className="text-lg font-semibold text-red-400">
                    Blockchain Error
                  </span>
                </div>
                {blockchainError && (
                  <p className="text-red-300 text-sm max-w-2xl mx-auto">
                    {blockchainError}
                  </p>
                )}
                <button
                  onClick={handleBlockchainIntegration}
                  className="mt-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 transition-colors text-sm"
                >
                  Retry Blockchain Integration
                </button>
              </div>
            )}

            {blockchainStatus === "not_configured" && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-6 py-3 bg-gray-900/30 rounded-full border border-gray-500/30 mb-3">
                  <span className="text-xl">ℹ️</span>
                  <span className="text-lg font-semibold text-gray-400">
                    Blockchain Integration Available
                  </span>
                </div>
                <div className="bg-white/5 rounded-lg p-4 border border-white/10 max-w-2xl mx-auto">
                  <p className="text-gray-300 text-sm mb-3">
                    This report has been generated successfully. For enhanced
                    security and immutable verification, blockchain integration
                    can be configured to store and verify reports on-chain.
                  </p>
                  {blockchainError && (
                    <p className="text-yellow-300 text-xs mb-3 font-mono bg-yellow-900/20 p-2 rounded border border-yellow-500/30">
                      {blockchainError}
                    </p>
                  )}
                  <div className="text-xs text-gray-400">
                    <p>Report Hash (for manual verification):</p>
                    <p className="font-mono break-all mt-1 text-gray-300">
                      {reportHash}
                    </p>
                  </div>
                  <button
                    onClick={handleBlockchainIntegration}
                    className="mt-3 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
                  >
                    Try Blockchain Integration
                  </button>
                </div>
              </div>
            )}
          </div>

          {/* Tab Navigation */}
          <div className="mb-4">
            <div className="flex space-x-1 bg-white/5 rounded-lg p-1">
              <button
                onClick={() => setActiveTab("image")}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-md font-medium transition-all ${
                  activeTab === "image"
                    ? "bg-emerald-600 text-white shadow-lg"
                    : "text-gray-300 hover:text-white hover:bg-white/10"
                }`}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
                Image View
              </button>
              <button
                onClick={() => setActiveTab("text")}
                className={`flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-md font-medium transition-all ${
                  activeTab === "text"
                    ? "bg-blue-600 text-white shadow-lg"
                    : "text-gray-300 hover:text-white hover:bg-white/10"
                }`}
              >
                <svg
                  className="w-5 h-5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                  />
                </svg>
                Text View
              </button>
            </div>
          </div>

          {/* Tab Content */}
          <div className="mb-4">
            {activeTab === "image" ? (
              // Image Tab Content
              <div>
                {isGeneratingImage ? (
                  <div className="flex flex-col items-center justify-center py-10 text-center">
                    <div className="animate-spin rounded-full h-12 w-12 border-4 border-emerald-400 border-t-transparent mb-4"></div>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Generating Report Image
                    </h3>
                    <p className="text-gray-400">
                      Please wait while we create your mobile-friendly report...
                    </p>
                  </div>
                ) : reportImage ? (
                  <div>
                    <div className="bg-white rounded-lg">
                      <img
                        src={reportImage}
                        alt="DataWipe Verification Report"
                        className="w-full h-auto rounded-lg border border-gray-200"
                        style={{ maxWidth: "100%", height: "auto" }}
                      />
                    </div>

                    <div className="flex justify-center mt-4">
                      <button
                        onClick={handleDownloadImage}
                        disabled={isGeneratingImage}
                        className="px-6 py-3 bg-emerald-600 text-white rounded-lg shadow-lg hover:bg-emerald-700 transition-colors disabled:bg-emerald-400 disabled:cursor-not-allowed flex items-center gap-2"
                      >
                        <svg
                          className="w-5 h-5"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                          />
                        </svg>
                        Download Image
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="text-red-400 text-4xl mb-4">⚠️</div>
                    <h3 className="text-xl font-semibold text-white mb-2">
                      Failed to Generate Image
                    </h3>
                    <p className="text-gray-400 mb-4">
                      Unable to create the report image. Please try again.
                    </p>
                    <button
                      onClick={handleGenerateImage}
                      className="px-6 py-3 bg-emerald-600 text-white rounded-lg shadow-lg hover:bg-emerald-700 transition-colors"
                    >
                      Retry Generate Image
                    </button>
                  </div>
                )}
              </div>
            ) : (
              // Text Tab Content
              <div>
                {/* Report Details Grid */}
                <div className="grid md:grid-cols-2 gap-4 mb-4">
                  <div className="space-y-4">
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Date & Time
                      </h3>
                      <p className="text-lg text-white font-mono">
                        {decryptedData.DateTime}
                      </p>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Device
                      </h3>
                      <p className="text-lg text-white">
                        {decryptedData.Device}
                      </p>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Serial Number
                      </h3>
                      <p className="text-lg text-white font-mono">
                        {decryptedData.Serial}
                      </p>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Operator
                      </h3>
                      <p className="text-lg text-white">
                        {decryptedData.Operator}
                      </p>
                    </div>
                  </div>

                  <div className="space-y-4">
                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Sanitization Method
                      </h3>
                      <p className="text-lg text-white">
                        {decryptedData.SanitizationMethod}
                      </p>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Verification Status
                      </h3>
                      <p className="text-lg text-white">
                        {decryptedData.Verification}
                      </p>
                    </div>

                    <div className="bg-white/5 rounded-lg p-4 border border-white/10">
                      <h3 className="text-sm font-medium text-gray-400 mb-1">
                        Digital Key
                      </h3>
                      <p className="text-sm text-white font-mono break-all">
                        {decryptedData.DigitalKey}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Certificate Footer */}
          <div className="border-t border-white/10 pt-6 text-center">
            <p className="text-gray-400 text-sm mb-2">
              This certificate verifies that the above device has been properly
              sanitized according to industry standards and security protocols.
            </p>
            <p className="text-gray-500 text-xs">
              Generated on {new Date().toLocaleDateString()} at{" "}
              {new Date().toLocaleTimeString()}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ReportPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-gradient-to-b from-gray-900 via-gray-800 to-black">
          <div className="text-white">Loading report...</div>
        </div>
      }
    >
      <ReportContent />
    </Suspense>
  );
}
