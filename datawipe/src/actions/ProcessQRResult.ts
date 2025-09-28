"use server";

import { decryptQRResult, formatDecryptedData } from "./DecryptResults";

interface QRData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

interface ProcessResult {
  success: boolean;
  data?: QRData;
  error?: string;
  format?: "encrypted" | "json";
  rawData?: string;
}

export async function processQRResult(
  scannedText: string
): Promise<ProcessResult> {
  console.log("🔍 Starting QR result processing...");
  console.log("📥 Input scanned text:", scannedText);
  console.log("📏 Input length:", scannedText.length);

  try {
    const cleanedText = scannedText.trim();

    // First, try to detect if it's JSON format
    if (isLikelyJSON(cleanedText)) {
      console.log("🔍 Detected JSON format, attempting JSON parsing...");
      return await processJSONFormat(cleanedText);
    } else {
      console.log("🔍 Detected encrypted format, attempting decryption...");
      return await processEncryptedFormat(cleanedText);
    }
  } catch (error) {
    console.log("💥 Unexpected error during QR processing:", error);
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Unknown processing error",
      rawData: scannedText,
    };
  }
}

function isLikelyJSON(text: string): boolean {
  // Check if the text starts and ends with curly braces or square brackets
  const trimmed = text.trim();
  const startsWithJSON = trimmed.startsWith("{") || trimmed.startsWith("[");
  const endsWithJSON = trimmed.endsWith("}") || trimmed.endsWith("]");

  // Additional check: see if it contains JSON-like patterns
  const hasJSONPatterns =
    /["']\s*:\s*["']/.test(trimmed) || /[{}\[\]]/.test(trimmed);

  // Check if it's NOT base64 (base64 doesn't typically contain these characters)
  const hasNonBase64Chars = /[{}"':,\[\]]/.test(trimmed);

  console.log("🔍 JSON detection - starts with JSON:", startsWithJSON);
  console.log("🔍 JSON detection - ends with JSON:", endsWithJSON);
  console.log("🔍 JSON detection - has JSON patterns:", hasJSONPatterns);
  console.log("🔍 JSON detection - has non-base64 chars:", hasNonBase64Chars);

  // Primary check: starts and ends with JSON brackets
  if (startsWithJSON && endsWithJSON) {
    return true;
  }

  // Secondary check: has clear JSON characteristics
  return hasJSONPatterns && hasNonBase64Chars;
}

async function processJSONFormat(jsonText: string): Promise<ProcessResult> {
  console.log("📄 Processing JSON format...");

  try {
    // Attempt to parse as JSON
    const parsedData = JSON.parse(jsonText);
    console.log("✅ Successfully parsed JSON:", parsedData);

    // Validate and map the JSON data to our expected structure
    const mappedData = mapJSONToQRData(parsedData);

    if (!mappedData.success) {
      return {
        success: false,
        error: mappedData.error,
        format: "json",
        rawData: jsonText,
      };
    }

    console.log("✅ Successfully mapped JSON data");
    return {
      success: true,
      data: mappedData.data,
      format: "json",
      rawData: jsonText,
    };
  } catch (parseError) {
    console.log("❌ JSON parsing failed:", parseError);
    return {
      success: false,
      error: `Invalid JSON format: ${
        parseError instanceof Error ? parseError.message : "Unknown JSON error"
      }`,
      format: "json",
      rawData: jsonText,
    };
  }
}

async function processEncryptedFormat(
  encryptedText: string
): Promise<ProcessResult> {
  console.log("🔐 Processing encrypted format...");

  // Use the existing decryption logic
  const decryptResult = await decryptQRResult(encryptedText);

  if (!decryptResult.success) {
    return {
      success: false,
      error: decryptResult.error,
      format: "encrypted",
      rawData: encryptedText,
    };
  }

  console.log("✅ Successfully decrypted data");
  return {
    success: true,
    data: decryptResult.data,
    format: "encrypted",
    rawData: encryptedText,
  };
}

interface MappingResult {
  success: boolean;
  data?: QRData;
  error?: string;
}

function mapJSONToQRData(jsonData: any): MappingResult {
  console.log("🗺️ Mapping JSON data to QR structure...");

  try {
    // Handle different possible JSON structures
    let sourceData = jsonData;

    // If the JSON is an array, take the first element
    if (Array.isArray(jsonData)) {
      if (jsonData.length === 0) {
        return {
          success: false,
          error: "JSON array is empty",
        };
      }
      sourceData = jsonData[0];
      console.log("📄 Using first element from JSON array");
    }

    // Map common field variations to our expected structure
    const fieldMappings: Record<string, string[]> = {
      DateTime: [
        "DateTime",
        "dateTime",
        "date_time",
        "timestamp",
        "date",
        "time",
        "completed_at",
        "completedAt",
        "created_at",
        "createdAt",
      ],
      Device: [
        "Device",
        "device",
        "deviceName",
        "device_name",
        "deviceId",
        "device_id",
        "device_model",
        "deviceModel",
        "model",
      ],
      Serial: [
        "Serial",
        "serial",
        "serialNumber",
        "serial_number",
        "serialNo",
        "serial_no",
        "session_id",
        "sessionId",
        "report_id",
        "reportId",
      ],
      SanitizationMethod: [
        "SanitizationMethod",
        "sanitizationMethod",
        "sanitization_method",
        "method",
        "sanitization",
        "sanitizeMethod",
        "sanitize_method",
        "algorithm",
        "wipe_method",
        "wipeMethod",
      ],
      Verification: [
        "Verification",
        "verification",
        "verified",
        "status",
        "verify",
        "verification_url",
        "verificationUrl",
        "verify_url",
        "verifyUrl",
      ],
      Operator: [
        "Operator",
        "operator",
        "user",
        "username",
        "operatorName",
        "operator_name",
        "technician",
        "admin",
        "performed_by",
        "performedBy",
      ],
      DigitalKey: [
        "DigitalKey",
        "digitalKey",
        "digital_key",
        "key",
        "signature",
        "hash",
        "session_id",
        "sessionId",
        "report_id",
        "reportId",
        "id",
      ],
    };

    const mappedData: Partial<QRData> = {};

    // Try to map each required field
    for (const [targetField, possibleKeys] of Object.entries(fieldMappings)) {
      let foundValue: string | undefined;

      for (const key of possibleKeys) {
        if (sourceData[key] !== undefined && sourceData[key] !== null) {
          foundValue = String(sourceData[key]).trim();
          console.log(`✅ Mapped ${key} -> ${targetField}: ${foundValue}`);
          break;
        }
      }

      if (foundValue) {
        (mappedData as any)[targetField] = foundValue;
      } else {
        console.log(`⚠️ Could not find value for ${targetField}`);
      }
    }

    // Validate that we have all required fields
    const requiredFields: (keyof QRData)[] = [
      "DateTime",
      "Device",
      "Serial",
      "SanitizationMethod",
      "Verification",
      "Operator",
      "DigitalKey",
    ];

    const missingFields = requiredFields.filter((field) => !mappedData[field]);

    // Handle missing fields with reasonable defaults or alternative logic
    if (missingFields.length > 0) {
      console.log("⚠️ Missing required fields in JSON:", missingFields);

      // Try to fill missing fields with reasonable defaults or combinations
      for (const missingField of missingFields) {
        switch (missingField) {
          case "Serial":
            // Use session_id as serial if serial is missing
            if (sourceData.session_id) {
              mappedData.Serial = sourceData.session_id;
              console.log("📄 Using session_id as Serial:", mappedData.Serial);
            } else if (sourceData.report_id) {
              mappedData.Serial = sourceData.report_id;
              console.log("📄 Using report_id as Serial:", mappedData.Serial);
            }
            break;
          case "DigitalKey":
            // Use session_id or report_id as digital key if missing
            if (sourceData.session_id) {
              mappedData.DigitalKey = sourceData.session_id;
              console.log(
                "🔑 Using session_id as DigitalKey:",
                mappedData.DigitalKey
              );
            } else if (sourceData.report_id) {
              mappedData.DigitalKey = sourceData.report_id;
              console.log(
                "🔑 Using report_id as DigitalKey:",
                mappedData.DigitalKey
              );
            }
            break;
          case "Operator":
            // Use a default operator if not specified
            mappedData.Operator = "System Generated";
            console.log("👤 Using default Operator:", mappedData.Operator);
            break;
        }
      }

      // Re-check missing fields after applying defaults
      const stillMissingFields = requiredFields.filter(
        (field) => !mappedData[field]
      );

      if (stillMissingFields.length > 0) {
        const availableKeys = Object.keys(sourceData);
        console.log("📋 Available keys in JSON:", availableKeys);
        console.log("❌ Still missing required fields:", stillMissingFields);

        return {
          success: false,
          error: `Missing required fields: ${stillMissingFields.join(
            ", "
          )}. Available fields: ${availableKeys.join(", ")}`,
        };
      }
    }

    console.log("✅ All required fields mapped successfully");
    return {
      success: true,
      data: mappedData as QRData,
    };
  } catch (error) {
    console.log("❌ Error during JSON mapping:", error);
    return {
      success: false,
      error: `Failed to map JSON data: ${
        error instanceof Error ? error.message : "Unknown mapping error"
      }`,
    };
  }
}

// Helper function to format the processed data for display
export async function formatProcessedData(
  data: QRData,
  format: "encrypted" | "json"
): Promise<string> {
  const formattedData = await formatDecryptedData(data);
  return `${formattedData}\n\nSource Format: ${format.toUpperCase()}`;
}

// Helper function to get a summary of the processing result
export async function getProcessingSummary(
  result: ProcessResult
): Promise<string> {
  if (result.success) {
    return `✅ Successfully processed ${result.format} format QR data`;
  } else {
    return `❌ Failed to process QR data: ${result.error}`;
  }
}
