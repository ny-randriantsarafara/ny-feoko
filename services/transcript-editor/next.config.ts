import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow serving audio files from data/ directory
  serverExternalPackages: ["csv-parse", "csv-stringify"],
};

export default nextConfig;
