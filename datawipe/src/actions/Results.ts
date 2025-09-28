"use server";

import {
  processQRResult,
  formatProcessedData,
  getProcessingSummary,
} from "./ProcessQRResult";

interface DisplayResult {
  success: boolean;
  formattedData?: string;
  summary?: string;
  error?: string;
  rawData?: string;
  format?: "encrypted" | "json";
}

export async function handleScannedQRResult(
  scannedText: string
): Promise<DisplayResult> {
  console.log("🎯 Handling scanned QR result...");

  try {
    // Process the QR result (handles both encrypted and JSON formats)
    const processResult = await processQRResult(scannedText);

    if (!processResult.success) {
      const summary = await getProcessingSummary(processResult);
      return {
        success: false,
        error: processResult.error,
        rawData: processResult.rawData,
        format: processResult.format,
        summary,
      };
    }

    // Format the data for display
    const formattedData = await formatProcessedData(
      processResult.data!,
      processResult.format!
    );

    const summary = await getProcessingSummary(processResult);

    console.log("✅ Successfully handled QR result");

    return {
      success: true,
      formattedData,
      summary,
      format: processResult.format,
      rawData: processResult.rawData,
    };
  } catch (error) {
    console.log("💥 Error handling QR result:", error);
    return {
      success: false,
      error: error instanceof Error ? error.message : "Unknown error occurred",
      rawData: scannedText,
      summary: "❌ Failed to handle QR result",
    };
  }
}

// Helper function to validate QR input before processing
export async function validateQRInput(
  input: string
): Promise<{ isValid: boolean; error?: string }> {
  if (!input || input.trim().length === 0) {
    return {
      isValid: false,
      error: "QR input is empty or contains only whitespace",
    };
  }

  const trimmed = input.trim();

  // Check minimum length
  if (trimmed.length < 10) {
    return {
      isValid: false,
      error: "QR input appears to be too short to contain valid data",
    };
  }

  return { isValid: true };
}

// Helper function to get supported formats
export async function getSupportedFormats(): Promise<string[]> {
  return [
    "Base64 encrypted text (existing format)",
    "Direct JSON format with sanitization data",
  ];
}

// Backward compatibility wrapper - automatically detects format
export async function processAnyQRFormat(
  scannedText: string
): Promise<DisplayResult> {
  console.log("🔄 Auto-processing QR data (backward compatible)...");

  // This function automatically handles both encrypted and JSON formats
  return await handleScannedQRResult(scannedText);
}
