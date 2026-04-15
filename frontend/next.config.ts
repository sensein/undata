import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  devIndicators: {
    position: "bottom-right",
  },
  async rewrites() {
    const backendUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || "http://localhost:8002";
    const meiliUrl =
      process.env.NEXT_PUBLIC_MEILI_URL || "http://localhost:7700";
    const migrationUrl =
      process.env.NEXT_PUBLIC_MIGRATION_URL || "http://localhost:8004";
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: "/api/search/:path*",
        destination: `${meiliUrl}/:path*`,
      },
      {
        source: "/api/migration/:path*",
        destination: `${migrationUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
