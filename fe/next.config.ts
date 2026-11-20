import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async redirects() {
    return [
      {
        source: "/companies/:id/streams",
        destination: "/companies/:id/edit",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
