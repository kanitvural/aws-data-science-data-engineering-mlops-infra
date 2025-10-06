import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'export',
  trailingSlash: false, // Next.js + CloudFront + S3 config
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
