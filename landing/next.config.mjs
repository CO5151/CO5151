/** @type {import('next').NextConfig} */
const isGithubActions = process.env.GITHUB_ACTIONS || false;
let basePath = "";
let assetPrefix = "";

if (isGithubActions) {
  const repo = process.env.GITHUB_REPOSITORY
    ? `/${process.env.GITHUB_REPOSITORY.split("/")[1]}`
    : "/CO5151";
  basePath = repo;
  assetPrefix = repo;
}

const nextConfig = {
  output: "export",
  basePath: basePath,
  assetPrefix: assetPrefix,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
  images: {
    unoptimized: true,
  },
};

export default nextConfig;
