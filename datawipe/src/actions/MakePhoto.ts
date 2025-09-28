"use client";

import html2canvas from "html2canvas";

interface ReportData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

export async function generateReportImage(data: ReportData): Promise<string> {
  // Create a temporary div element to render the report
  const tempDiv = document.createElement("div");
  tempDiv.style.position = "absolute";
  tempDiv.style.left = "-9999px";
  tempDiv.style.top = "-9999px";
  tempDiv.style.width = "800px";
  tempDiv.style.fontFamily = "Arial, sans-serif";
  tempDiv.style.backgroundColor = "#ffffff";
  tempDiv.style.boxSizing = "border-box";

  // Create the HTML content for the report
  tempDiv.innerHTML = `
    <div style="max-width: 100%; background: white; padding: 16px; margin: 0;">
  <!-- Header -->
  <div style="text-align: center; margin-bottom: 20px; border-bottom: 3px solid #1e40af; padding-bottom: 16px;">
    <h1 style="color: #1e40af; font-size: 22px; margin: 0 0 8px 0; font-weight: bold;">
      BreakNWipe Verification Report
    </h1>
    <p style="color: #6b7280; font-size: 16px; margin: 0;">
      Device Sanitization Certificate
    </p>
  </div>

  <!-- Verification Status Badge -->
  <div style="background: #dcfce7; border: 2px solid #16a34a; border-radius: 8px; padding: 12px; margin-bottom: 20px; text-align: center;">
    <div style="color: #16a34a; font-size: 20px; font-weight: bold;">
      ✓ Verification Complete
    </div>
  </div>

  <!-- Report Details Grid (Stacked on Mobile) -->
  <div style="display: flex; flex-direction: column; gap: 16px; margin-bottom: 20px;">
    <!-- Left Column -->
    <div>
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 12px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          DATE & TIME
        </div>
        <div style="color: #1e293b; font-size: 18px; font-family: monospace;">
          ${data.DateTime}
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 12px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          DEVICE
        </div>
        <div style="color: #1e293b; font-size: 18px;">
          ${data.Device}
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 12px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          SERIAL NUMBER
        </div>
        <div style="color: #1e293b; font-size: 18px; font-family: monospace;">
          ${data.Serial}
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          OPERATOR
        </div>
        <div style="color: #1e293b; font-size: 18px;">
          ${data.Operator}
        </div>
      </div>
    </div>

    <!-- Right Column (Stacked) -->
    <div>
      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 12px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          SANITIZATION METHOD
        </div>
        <div style="color: #1e293b; font-size: 18px;">
          ${data.SanitizationMethod}
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px; margin-bottom: 12px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 2px;">
          VERIFICATION STATUS
        </div>
        <div style="color: #1e293b; font-size: 18px;">
          ${data.Verification}
        </div>
      </div>

      <div style="background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 10px;">
        <div style="color: #64748b; font-size: 14px; font-weight: bold; margin-bottom: 5px;">
          DIGITAL KEY
        </div>
        <div style="color: #1e293b; font-size: 16px; font-family: monospace; word-break: break-word; line-height: 1.6;">
          ${data.DigitalKey}
        </div>
      </div>
    </div>
  </div>

  <!-- Certificate Validation -->
  <div style="background: #fef3c7; border: 2px solid #f59e0b; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
    <div style="color: #92400e; font-size: 18px; font-weight: bold; margin-bottom: 8px;">
      Certificate Validation
    </div>
    <div style="color: #78350f; font-size: 15px; line-height: 1.6;">
      This certificate verifies that the above device has been properly sanitized according to industry standards and security protocols.
    </div>
  </div>

  <!-- Footer -->
  <div style="border-top: 1px solid #e2e8f0; padding-top: 16px; display: flex; justify-content: center; align-items: center;">
    <div style="text-align: center;">
      <div style="color: #9ca3af; font-size: 14px;">
        Generated on ${new Date().toLocaleDateString()} at ${new Date().toLocaleTimeString()}
      </div>
      <div style="color: #9ca3af; font-size: 14px; margin-top: 4px;">
        BreakNWipe Security Solutions
      </div>
      <div style="color: #9ca3af; font-size: 14px; margin-top: 4px;">
        Confidential Document - Handle with Care
      </div>
    </div>
  </div>
</div>
  `;

  // Append to body temporarily
  document.body.appendChild(tempDiv);

  try {
    // Generate canvas from the HTML
    const canvas = await html2canvas(tempDiv, {
      backgroundColor: "#ffffff",
      scale: 5, // Higher resolution
      useCORS: true,
      allowTaint: true,
      width: 800,
      height: tempDiv.scrollHeight + 80,
    });

    // Convert canvas to blob URL
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const url = URL.createObjectURL(blob);
            resolve(url);
          } else {
            reject(new Error("Failed to create blob from canvas"));
          }
        },
        "image/png",
        1.0
      );
    });
  } finally {
    // Clean up - remove the temporary element
    document.body.removeChild(tempDiv);
  }
}

export async function downloadReportImage(data: ReportData): Promise<void> {
  try {
    const imageUrl = await generateReportImage(data);

    // Create download link
    const link = document.createElement("a");
    link.href = imageUrl;
    link.download = `BreakNWipe_Report_${
      new Date().toISOString().split("T")[0]
    }.png`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    // Clean up the blob URL
    URL.revokeObjectURL(imageUrl);
  } catch (error) {
    console.error("Error generating report image:", error);
    throw new Error("Failed to generate report image");
  }
}
