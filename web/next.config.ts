import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  experimental: {
    // Let the Next.js proxy stream archives up to the same 5 GB limit enforced
    // by the API. The UI validates earlier so users get an immediate message.
    proxyClientMaxBodySize: "5gb",
  },
  async rewrites() {
    const backendUrl = process.env.BACKEND_URL || "http://api:8080";
    return {
      beforeFiles: [
        {
          source: "/api/:path*",
          destination: `${backendUrl}/api/:path*`,
        },
      ],
    };
  },
};

export default nextConfig;
