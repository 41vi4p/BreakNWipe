import type { NextConfig } from "next";

// BreakNWipe GUI is built as a static-export SPA (`output: 'export'` -> `out/`)
// and served by the Python/FastAPI backend, so a single `sudo breaknwipe --gui`
// still launches one server on one port. All data comes from the backend's
// REST/WebSocket API via client components (see lib/api.ts), so no server-side
// rendering features are used. `trailingSlash` makes each route emit
// `route/index.html`, which FastAPI's StaticFiles(html=True) serves cleanly.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
};

export default nextConfig;
