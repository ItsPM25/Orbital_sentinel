const API_URL = process.env.API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // globe.gl and three need to be transpiled to run in Next.js
  transpilePackages: ["globe.gl", "three"],
  // The browser only talks to this origin; /api/* is forwarded to the FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
  webpack(config, { isServer }) {
    if (isServer) {
      // canvas is an optional native dep of some three.js image loaders; exclude from server bundle
      config.externals = [...(config.externals || []), "canvas"];
    }
    return config;
  },
};

