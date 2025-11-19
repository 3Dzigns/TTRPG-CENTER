/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  transpilePackages: ["@ttrpg-center/api", "@ttrpg-center/types", "@ttrpg-center/ui", "@ttrpg-center/config"]
};

export default nextConfig;
