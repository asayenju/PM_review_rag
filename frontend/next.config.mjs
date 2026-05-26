/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, { dev }) => {
    if (dev) {
      // Avoid stale filesystem cache corruption that can cause missing app/layout chunks in dev.
      config.cache = false;
    }
    return config;
  }
};

export default nextConfig;
