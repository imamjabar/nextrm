/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  distDir: process.env.NEXTRM_BUILD_DIR || ".next",
  reactStrictMode: true,
};

export default nextConfig;
