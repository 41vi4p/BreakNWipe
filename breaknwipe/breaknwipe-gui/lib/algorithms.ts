// Wiping algorithms offered in the GUI, mirroring the backend's WipeAlgorithm
// enum. Grouped for the picker; `passes` and `note` are for display only.

export interface AlgorithmOption {
  value: string;
  label: string;
  passes: string;
  group: "Standard" | "REA (crypto-erase)";
  note?: string;
  configurablePasses?: boolean;
}

export const ALGORITHMS: AlgorithmOption[] = [
  { value: "nist-clear", label: "NIST SP 800-88 Clear", passes: "1 pass", group: "Standard", note: "General purpose" },
  { value: "nist-purge", label: "NIST SP 800-88 Purge", passes: "3 passes", group: "Standard", note: "High security" },
  { value: "dod-3pass", label: "DoD 5220.22-M", passes: "3 passes", group: "Standard", note: "Government standard" },
  { value: "dod-7pass", label: "DoD 5220.22-M (enhanced)", passes: "7 passes", group: "Standard", note: "Maximum overwrite" },
  { value: "gutmann", label: "Gutmann", passes: "35 passes", group: "Standard", note: "Legacy magnetic drives" },
  { value: "random", label: "Random data", passes: "configurable", group: "Standard", configurablePasses: true },
  { value: "zeros", label: "Zero-fill", passes: "1 pass", group: "Standard", note: "Quick sanitization" },
  { value: "custom", label: "Custom pattern", passes: "configurable", group: "Standard", configurablePasses: true },
  { value: "rea-basic", label: "REA Basic", passes: "encrypt + 1 pass", group: "REA (crypto-erase)" },
  { value: "rea-fast", label: "REA Fast", passes: "encrypt + fast", group: "REA (crypto-erase)" },
  { value: "rea-multichain", label: "REA Multichain", passes: "encrypt + DoD", group: "REA (crypto-erase)" },
  { value: "rea-extreme", label: "REA Extreme", passes: "encrypt + Gutmann", group: "REA (crypto-erase)" },
  { value: "rea-custom", label: "REA Custom", passes: "configurable", group: "REA (crypto-erase)" },
];

export function algorithmLabel(value: string): string {
  return ALGORITHMS.find((a) => a.value === value)?.label ?? value;
}
