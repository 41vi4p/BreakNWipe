// Simple test to verify QR processing logic
const testJSON = `{"report_id":"BNW-4fd1921f-1758151679","session_id":"4fd1921f-7576-4815-a4de-abb72b273cc0","device_model":"ST3160215AS","algorithm":"nist-clear","completed_at":"2025-09-18T04:57:56.144457","verification_url":"http://127.0.0.1:8000/api/wipe/verify/4fd1921f-7576-4815-a4de-abb72b273cc0"}`;

console.log("🧪 Testing JSON detection...");

function isLikelyJSON(text) {
  const trimmed = text.trim();
  const startsWithJSON = trimmed.startsWith("{") || trimmed.startsWith("[");
  const endsWithJSON = trimmed.endsWith("}") || trimmed.endsWith("]");
  const hasJSONPatterns =
    /["']\s*:\s*["']/.test(trimmed) || /[{}\[\]]/.test(trimmed);
  const hasNonBase64Chars = /[{}"':,\[\]]/.test(trimmed);

  console.log("🔍 JSON detection - starts with JSON:", startsWithJSON);
  console.log("🔍 JSON detection - ends with JSON:", endsWithJSON);
  console.log("🔍 JSON detection - has JSON patterns:", hasJSONPatterns);
  console.log("🔍 JSON detection - has non-base64 chars:", hasNonBase64Chars);

  if (startsWithJSON && endsWithJSON) {
    return true;
  }

  return hasJSONPatterns && hasNonBase64Chars;
}

console.log("📄 Test JSON:", testJSON);
console.log("✅ Is JSON detected?", isLikelyJSON(testJSON));

// Parse and test mapping
try {
  const parsed = JSON.parse(testJSON);
  console.log("📊 Parsed JSON:", parsed);

  // Show field mapping
  const fieldMappings = {
    DateTime: ["completed_at", "DateTime", "dateTime"],
    Device: ["device_model", "Device", "device"],
    Serial: ["session_id", "report_id", "Serial"],
    SanitizationMethod: ["algorithm", "method", "SanitizationMethod"],
    Verification: ["verification_url", "Verification", "verification"],
    Operator: ["Operator", "operator", "user"],
    DigitalKey: ["session_id", "report_id", "DigitalKey"],
  };

  const mappedData = {};

  for (const [targetField, possibleKeys] of Object.entries(fieldMappings)) {
    let foundValue;

    for (const key of possibleKeys) {
      if (parsed[key] !== undefined && parsed[key] !== null) {
        foundValue = String(parsed[key]).trim();
        console.log(`✅ Mapped ${key} -> ${targetField}: ${foundValue}`);
        break;
      }
    }

    if (foundValue) {
      mappedData[targetField] = foundValue;
    } else if (targetField === "Operator") {
      mappedData[targetField] = "System Generated";
      console.log(`👤 Using default ${targetField}: System Generated`);
    }
  }

  console.log("🎯 Final mapped data:", mappedData);
} catch (error) {
  console.log("❌ Error:", error.message);
}
