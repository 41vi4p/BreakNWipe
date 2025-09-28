"use server";

import jsPDF from "jspdf";

interface ReportData {
  DateTime: string;
  Device: string;
  Serial: string;
  SanitizationMethod: string;
  Verification: string;
  Operator: string;
  DigitalKey: string;
}

export async function generatePdfReport(data: ReportData): Promise<Uint8Array> {
  try {
    // Create a new PDF document
    const doc = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: "a4",
    });

    // Set default font
    doc.setFont("helvetica");

    // Header Section
    doc.setFontSize(24);
    doc.setTextColor(30, 64, 175); // Blue color
    doc.text("BreakNWipe Verification Report", 20, 30);

    doc.setFontSize(12);
    doc.setTextColor(107, 114, 128); // Gray color
    doc.text("Device Sanitization Certificate", 20, 40);

    // Add verification status badge
    doc.setFillColor(220, 252, 231); // Light green background
    doc.rect(20, 50, 80, 12, "F");
    doc.setFontSize(12);
    doc.setTextColor(22, 163, 74); // Green color
    doc.text("✓ Verification Complete", 25, 58);

    // Reset color for main content
    doc.setTextColor(0, 0, 0);

    // Main content area
    let yPosition = 80;

    // Function to add a field
    const addField = (label: string, value: string, y: number) => {
      // Label background
      doc.setFillColor(243, 244, 246); // Light gray
      doc.rect(20, y, 60, 10, "F");

      // Value background
      doc.setFillColor(255, 255, 255); // White
      doc.rect(80, y, 100, 10, "F");

      // Add borders
      doc.setDrawColor(229, 231, 235); // Border gray
      doc.rect(20, y, 60, 10, "S");
      doc.rect(80, y, 100, 10, "S");

      // Label text
      doc.setFontSize(10);
      doc.setFont("helvetica", "bold");
      doc.setTextColor(55, 65, 81); // Dark gray
      doc.text(label, 22, y + 7);

      // Value text
      doc.setFont("helvetica", "normal");
      doc.setTextColor(17, 24, 39); // Almost black
      const wrappedText = doc.splitTextToSize(value, 95);
      doc.text(wrappedText, 82, y + 7);

      return y + Math.max(10, wrappedText.length * 5);
    };

    // Add all fields
    yPosition = addField("Date & Time", data.DateTime, yPosition);
    yPosition = addField("Device", data.Device, yPosition);
    yPosition = addField("Serial Number", data.Serial, yPosition);
    yPosition = addField(
      "Sanitization Method",
      data.SanitizationMethod,
      yPosition
    );
    yPosition = addField("Verification Status", data.Verification, yPosition);
    yPosition = addField("Operator", data.Operator, yPosition);

    // Digital Key field (special handling for long text)
    doc.setFillColor(243, 244, 246);
    doc.rect(20, yPosition, 60, 20, "F");
    doc.setFillColor(255, 255, 255);
    doc.rect(80, yPosition, 100, 20, "F");
    doc.setDrawColor(229, 231, 235);
    doc.rect(20, yPosition, 60, 20, "S");
    doc.rect(80, yPosition, 100, 20, "S");

    doc.setFontSize(10);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(55, 65, 81);
    doc.text("Digital Key", 22, yPosition + 7);

    doc.setFont("helvetica", "normal");
    doc.setFontSize(8);
    doc.setTextColor(17, 24, 39);
    const digitalKeyWrapped = doc.splitTextToSize(data.DigitalKey, 95);
    doc.text(digitalKeyWrapped, 82, yPosition + 7);

    yPosition += 30;

    // Certificate validation section
    doc.setFillColor(254, 243, 199); // Light yellow background
    doc.rect(20, yPosition, 170, 25, "F");
    doc.setDrawColor(245, 158, 11); // Orange border
    doc.rect(20, yPosition, 170, 25, "S");

    doc.setFontSize(12);
    doc.setFont("helvetica", "bold");
    doc.setTextColor(146, 64, 14); // Dark orange
    doc.text("Certificate Validation", 25, yPosition + 8);

    doc.setFontSize(9);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(120, 53, 15);
    doc.text(
      "This certificate verifies that the above device has been properly sanitized",
      25,
      yPosition + 15
    );
    doc.text(
      "according to industry standards and security protocols.",
      25,
      yPosition + 20
    );

    yPosition += 35;

    // Footer section
    const currentDate = new Date().toLocaleDateString();
    const currentTime = new Date().toLocaleTimeString();

    doc.setFontSize(8);
    doc.setFont("helvetica", "normal");
    doc.setTextColor(156, 163, 175); // Light gray
    doc.text(`Generated on ${currentDate} at ${currentTime}`, 20, yPosition);
    doc.text("BreakNWipe Security Solutions", 20, yPosition + 5);
    doc.text("Confidential Document - Handle with Care", 20, yPosition + 10);

    // Add a QR code placeholder
    // doc.setDrawColor(229, 231, 235);
    // doc.rect(150, yPosition - 20, 30, 30, "S");
    // doc.setFontSize(8);
    // doc.setTextColor(107, 114, 128);
    // doc.text("QR Code", 160, yPosition - 10, { align: "center" });
    // doc.text("Placeholder", 160, yPosition - 5, { align: "center" });

    // Convert to Uint8Array
    const pdfOutput = doc.output("arraybuffer");
    return new Uint8Array(pdfOutput);
  } catch (error) {
    console.error("Error generating PDF:", error);
    throw new Error("Failed to generate PDF report");
  }
}
