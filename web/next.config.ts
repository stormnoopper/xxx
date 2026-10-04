import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static HTML in out/ for GitHub Pages; repo pages live under /<repo>.
  output: "export",
  basePath: process.env.PAGES_BASE_PATH || "",
};

export default nextConfig;
