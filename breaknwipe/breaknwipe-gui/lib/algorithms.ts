// Wiping algorithms offered in the GUI, mirroring the backend's WipeAlgorithm
// enum (breaknwipe/wipe_engine/algorithms.py) and its actual pass sequences.

export type AlgorithmGroup = "Standard" | "REA (crypto-erase)" | "Custom";

export interface AlgorithmOption {
  value: string;
  label: string;
  passes: string;
  group: AlgorithmGroup;
  note?: string;
  description: string;
  ssdSuitable: boolean;
  configurablePasses?: boolean;
}

export interface AlgorithmCategory {
  id: AlgorithmGroup;
  title: string;
  description: string;
}

// Shown first, as the entry point into picking an algorithm -- narrows the
// choice before the user sees any individual algorithm, instead of a single
// flat list mixing named standards, BreakNWipe's own crypto-erase family, and
// user-tunable options together.
export const CATEGORIES: AlgorithmCategory[] = [
  {
    id: "Standard",
    title: "Standard",
    description: "Named, industry-recognized overwrite standards — NIST SP 800-88, DoD 5220.22-M, Gutmann, and simple zero/random fills. Pick this when you need a wipe method by a recognized name.",
  },
  {
    id: "REA (crypto-erase)",
    title: "REA (crypto-erase)",
    description: "BreakNWipe's own Randomized Encryption Algorithm: encrypts the drive's data with rotating key material, then finishes with a real overwrite pass. A modern crypto-erase approach layered on top of standard overwriting.",
  },
  {
    id: "Custom",
    title: "Custom",
    description: "Configure your own pass count, overwrite pattern, or REA encryption layers. For advanced users with a specific requirement the named standards don't cover.",
  },
];

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
    value: "zeros",
    label: "Zero-fill",
    passes: "1 pass",
    group: "Standard",
    note: "Quick sanitization",
    description: "A single pass of zero bytes. The fastest option — good for a quick wipe before internal reuse, not for media leaving your control.",
    ssdSuitable: true,
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
    value: "random",
    label: "Random data",
    passes: "configurable",
    group: "Custom",
    description: "One or more passes of cryptographically random data. Simple, high-entropy overwrite without following a named standard.",
    ssdSuitable: true,
    configurablePasses: true,
  },
  {
    value: "custom",
    label: "Custom pattern",
    passes: "configurable",
    group: "Custom",
    description: "Define your own pass count and pattern. For advanced users with a specific compliance requirement this tool doesn't name directly.",
    ssdSuitable: true,
    configurablePasses: true,
  },
  {
    value: "rea-custom",
    label: "REA Custom",
    passes: "configurable",
    group: "Custom",
    description: "Choose how many encryption layers to apply and which standard algorithm finishes the job (NIST Clear/Purge, DoD, random, or zero-fill).",
    ssdSuitable: true,
    configurablePasses: true,
  },
];

export function algorithmLabel(value: string): string {
  return ALGORITHMS.find((a) => a.value === value)?.label ?? value;
}

export function algorithmGroup(value: string): AlgorithmGroup | undefined {
  return ALGORITHMS.find((a) => a.value === value)?.group;
}
