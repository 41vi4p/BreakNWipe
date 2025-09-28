"use server";

interface DecryptedData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

interface DecryptResult {
  success: boolean;
  data?: DecryptedData;
  error?: string;
  rawDecrypted?: string;
}

export async function decryptQRResult(
  encryptedText: string
): Promise<DecryptResult> {
  console.log("🔍 Starting decryption process...");
  console.log("📥 Input encrypted text:", encryptedText);
  console.log("📏 Input length:", encryptedText.length);

  try {
    // Remove any whitespace and validate base64 format
    const cleanedText = encryptedText.trim();
    console.log("🧹 Cleaned text:", cleanedText);
    console.log("🧹 Cleaned text length:", cleanedText.length);

    // Check if it looks like base64
    const base64Regex = /^[A-Za-z0-9+/]*={0,2}$/;
    const isValidBase64 = base64Regex.test(cleanedText);
    console.log("✅ Base64 validation result:", isValidBase64);

    if (!isValidBase64) {
      console.log("❌ Invalid base64 format detected");
      return {
        success: false,
        error: "Invalid encrypted format. Expected base64 encoded text.",
      };
    }

    // Decode from base64
    let decodedText: string;
    try {
      console.log("🔓 Attempting base64 decode...");
      decodedText = Buffer.from(cleanedText, "base64").toString("utf-8");
      console.log("✅ Successfully decoded base64");
      console.log("📄 Decoded text:", decodedText);
      console.log("📄 Decoded text length:", decodedText.length);
    } catch (error) {
      console.log("❌ Base64 decode failed:", error);
      return {
        success: false,
        error: "Failed to decode base64 text.",
      };
    }

    // Parse the decoded text to extract structured data
    console.log("🔍 Parsing decoded text...");
    const lines = decodedText.split("\n").filter((line) => line.trim() !== "");
    console.log("📝 Split into lines:", lines.length);
    console.log("📝 Lines:", lines);

    const data: Partial<DecryptedData> = {};

    for (const line of lines) {
      console.log("🔍 Processing line:", line);

      if (line.includes("DateTime:")) {
        // Handle DateTime and Device on the same line
        const dateTimePart = line.split("DateTime:")[1].split("|")[0].trim();
        data.DateTime = dateTimePart;
        console.log("📅 Found DateTime:", data.DateTime);

        // Check if Device is also on this line
        if (line.includes("Device:")) {
          data.Device = line.split("Device:")[1].trim();
          console.log("💻 Found Device:", data.Device);
        }
      } else if (line.includes("Device:") && !data.Device) {
        // Handle Device on a separate line (fallback)
        data.Device = line.split("Device:")[1].trim();
        console.log("💻 Found Device:", data.Device);
      } else if (line.includes("Serial:")) {
        data.Serial = line.split("Serial:")[1].trim();
        console.log("🔢 Found Serial:", data.Serial);
      } else if (line.includes("Sanitization Method:")) {
        data.SanitizationMethod = line.split("Sanitization Method:")[1].trim();
        console.log("🧽 Found Sanitization Method:", data.SanitizationMethod);
      } else if (line.includes("Verification:")) {
        data.Verification = line.split("Verification:")[1].trim();
        console.log("✅ Found Verification:", data.Verification);
      } else if (line.includes("Operator:")) {
        data.Operator = line.split("Operator:")[1].trim();
        console.log("👤 Found Operator:", data.Operator);
      } else if (line.includes("DigitalKey:")) {
        data.DigitalKey = line.split("DigitalKey:")[1].trim();
        console.log("🔑 Found DigitalKey:", data.DigitalKey);
      } else {
        console.log("⚠️ Unrecognized line format:", line);
      }
    }

    console.log("📊 Extracted data object:", data);

    // Validate that we have all required fields
    const requiredFields: (keyof DecryptedData)[] = [
      "DateTime",
      "Device",
      "Serial",
      "SanitizationMethod",
      "Verification",
      "Operator",
      "DigitalKey",
    ];

    console.log("🔍 Validating required fields...");
    const missingFields = requiredFields.filter((field) => {
      const isMissing = !data[field];
      if (isMissing) {
        console.log(`❌ Missing field: ${field}`);
      } else {
        console.log(`✅ Found field: ${field} = "${data[field]}"`);
      }
      return isMissing;
    });

    if (missingFields.length > 0) {
      console.log("❌ Validation failed. Missing fields:", missingFields);
      return {
        success: false,
        error: `Missing required fields: ${missingFields.join(", ")}`,
        rawDecrypted: decodedText,
      };
    }

    console.log("✅ All required fields found. Decryption successful!");
    return {
      success: true,
      data: data as DecryptedData,
      rawDecrypted: decodedText,
    };
  } catch (error) {
    console.log("💥 Unexpected error during decryption:", error);
    console.log(
      "💥 Error stack:",
      error instanceof Error ? error.stack : "No stack trace"
    );
    return {
      success: false,
      error:
        error instanceof Error ? error.message : "Unknown decryption error",
    };
  }
}

// Helper function to format the decrypted data for display
export async function formatDecryptedData(
  data: DecryptedData
): Promise<string> {
  return `DateTime: ${data.DateTime}
Device: ${data.Device}
Serial: ${data.Serial}
Sanitization Method: ${data.SanitizationMethod}
Verification: ${data.Verification}
Operator: ${data.Operator}
DigitalKey: ${data.DigitalKey}`;
}
