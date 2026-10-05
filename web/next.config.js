const API_URL = process.env.API_URL || "http://localhost:8000";

/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // The browser only talks to this origin; /api/* is forwarded to the FastAPI backend.
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};
