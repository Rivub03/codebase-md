import type { NextConfig } from "next";

// Where the FastAPI service lives. Used for the same-origin proxy below, which
// is what keeps deployments free of CORS configuration.
const backendOrigin = (
  process.env.BACKEND_URL ?? "http://localhost:8080"
).replace(/\/+$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendOrigin}/api/:path*` }];
  },
};

export default nextConfig;
