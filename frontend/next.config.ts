import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Development only: the docs and scripts use 127.0.0.1 (on Windows "localhost" resolves IPv6 first).
  allowedDevOrigins: ["127.0.0.1"],
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
