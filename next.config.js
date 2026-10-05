/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: true,
  // API responses are live in-memory state; never let the browser cache them.
  async headers() {
    return [{ source: "/api/:path*", headers: [{ key: "Cache-Control", value: "no-store" }] }];
  },
};
