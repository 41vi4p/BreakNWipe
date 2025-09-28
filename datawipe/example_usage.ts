// Example of how to use the new QR processing functions

import { processQRResult } from "./src/actions/ProcessQRResult";
import { handleScannedQRResult } from "./src/actions/Results";

// Your JSON data
const jsonQRData = `{"report_id":"BNW-4fd1921f-1758151679","session_id":"4fd1921f-7576-4815-a4de-abb72b273cc0","device_model":"ST3160215AS","algorithm":"nist-clear","completed_at":"2025-09-18T04:57:56.144457","verification_url":"http://127.0.0.1:8000/api/wipe/verify/4fd1921f-7576-4815-a4de-abb72b273cc0"}`;

// Method 1: Using processQRResult (lower level)
async function example1() {
  console.log("=== Using processQRResult ===");
  const result = await processQRResult(jsonQRData);

  if (result.success) {
    console.log("✅ Success!");
    console.log("📊 Data:", result.data);
    console.log("📄 Format:", result.format); // Will be "json"
  } else {
    console.log("❌ Error:", result.error);
  }
}

// Method 2: Using handleScannedQRResult (higher level, recommended)
async function example2() {
  console.log("\n=== Using handleScannedQRResult ===");
  const result = await handleScannedQRResult(jsonQRData);

  if (result.success) {
    console.log("✅ Success!");
    console.log("📄 Formatted Data:");
    console.log(result.formattedData);
    console.log("\n📋 Summary:", result.summary);
  } else {
    console.log("❌ Error:", result.error);
    console.log("📋 Summary:", result.summary);
  }
}

// Don't use decryptQRResult directly for JSON data!
// ❌ Wrong way:
// const result = await decryptQRResult(jsonQRData); // This will fail

// ✅ Correct way:
// const result = await processQRResult(jsonQRData); // This will work
// or
// const result = await handleScannedQRResult(jsonQRData); // This is even better

export { example1, example2 };
