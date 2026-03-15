import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";
    const meiliUrl =
      process.env.NEXT_PUBLIC_MEILI_URL || "http://localhost:7700";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/api/search/:path*",
        destination: `${meiliUrl}/:path*`,
      },
    ];
  },
};

export default nextConfig;
