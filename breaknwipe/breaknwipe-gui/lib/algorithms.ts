// Wiping algorithms offered in the GUI, mirroring the backend's WipeAlgorithm
// enum (breaknwipe/wipe_engine/algorithms.py) and its actual pass sequences.

export interface AlgorithmOption {
  value: string;
  label: string;
  passes: string;
  group: "Standard" | "REA (crypto-erase)";
  note?: string;
  description: string;
  ssdSuitable: boolean;
  configurablePasses?: boolean;
}

export const ALGORITHMS: AlgorithmOption[] = [
  {
    value: "nist-clear",
    label: "NIST SP 800-88 Clear",
    passes: "1 pass",
    group: "Standard",
    note: "General purpose",
    description: "A single zero-fill pass. Meets NIST's \"Clear\" bar for media staying within your organization — fast, and enough for routine reuse.",
    ssdSuitable: true,
  },
  {
    value: "nist-purge",
    label: "NIST SP 800-88 Purge",
    passes: "3 passes",
    group: "Standard",
    note: "High security",
    description: "Zeros, then ones, then a verified random pass. Meets NIST's stricter \"Purge\" bar — the right choice before a drive leaves your control (resale, donation, disposal).",
    ssdSuitable: true,
  },
  {
    value: "dod-3pass",
    label: "DoD 5220.22-M",
    passes: "3 passes",
    group: "Standard",
    note: "Government standard",
    description: "The classic 3-pass military standard: zeros, ones, then a verified random pass. Widely recognized, similar assurance to NIST Purge.",
    ssdSuitable: true,
  },
  {
    value: "dod-7pass",
    label: "DoD 5220.22-M (enhanced)",
    passes: "7 passes",
    group: "Standard",
    note: "Maximum overwrite",
    description: "Two full zero/ones/random cycles plus a final verified random pass. Higher assurance than the 3-pass standard, at roughly double the time.",
    ssdSuitable: false,
  },
  {
    value: "gutmann",
    label: "Gutmann",
    passes: "35 passes",
    group: "Standard",
    note: "Legacy magnetic drives",
    description: "35 passes: random data, then 27 patterns targeting old MFM/RLL magnetic encoding schemes, then more random. Designed for 1990s-era hard drives — massive overkill (and very slow) on anything modern.",
    ssdSuitable: false,
  },
  {
    value: "random",
    label: "Random data",
    passes: "configurable",
    group: "Standard",
    description: "One or more passes of cryptographically random data. Simple, high-entropy overwrite without following a named standard.",
    ssdSuitable: true,
    configurablePasses: true,
  },
  {
    value: "zeros",
    label: "Zero-fill",
    passes: "1 pass",
    group: "Standard",
    note: "Quick sanitization",
    description: "A single pass of zero bytes. The fastest option — good for a quick wipe before internal reuse, not for media leaving your control.",
    ssdSuitable: true,
  },
  {
    value: "custom",
    label: "Custom pattern",
    passes: "configurable",
    group: "Standard",
    description: "Define your own pass count and pattern. For advanced users with a specific compliance requirement this tool doesn't name directly.",
    ssdSuitable: true,
    configurablePasses: true,
  },
  {
    value: "rea-basic",
    label: "REA Basic",
    passes: "encrypt + 1 pass",
    group: "REA (crypto-erase)",
    description: "BreakNWipe's Randomized Encryption Algorithm: three layered pseudo-encryption passes, then a zero pass, then a final random pass. A lighter crypto-erase for routine use.",
    ssdSuitable: true,
  },
  {
    value: "rea-fast",
    label: "REA Fast",
    passes: "encrypt + fast",
    group: "REA (crypto-erase)",
    description: "One fast encryption-style pass plus a verified zero pass. The quickest crypto-erase option, trading some layering for speed.",
    ssdSuitable: true,
  },
  {
    value: "rea-multichain",
    label: "REA Multichain",
    passes: "encrypt + DoD",
    group: "REA (crypto-erase)",
    description: "Five chained encryption layers, each rotating key material, followed by a full verified DoD 3-pass overwrite. Heavier assurance than REA Basic.",
    ssdSuitable: true,
  },
  {
    value: "rea-extreme",
    label: "REA Extreme",
    passes: "encrypt + Gutmann",
    group: "REA (crypto-erase)",
    description: "Seven encryption layers plus 21 Gutmann-style overwrite patterns and a final random pass (31 passes total). Maximum paranoia — slow, and unnecessary on SSDs.",
    ssdSuitable: false,
  },
  {
    value: "rea-custom",
    label: "REA Custom",
    passes: "configurable",
    group: "REA (crypto-erase)",
    description: "Choose how many encryption layers to apply and which standard algorithm finishes the job (NIST Clear/Purge, DoD, random, or zero-fill).",
    ssdSuitable: true,
    configurablePasses: true,
  },
];

export function algorithmLabel(value: string): string {
  return ALGORITHMS.find((a) => a.value === value)?.label ?? value;
}
