import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  trailingSlash: true,
  images: {
    unoptimized: true,
  },
  distDir: 'out',
  basePath: '',
  assetPrefix: '',
  eslint: {
  ignoreDuringBuilds: true,
  },
};

export default nextConfig;
