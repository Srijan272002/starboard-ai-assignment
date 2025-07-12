import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Configure image domains for remote images
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'images.unsplash.com',
        port: '',
        pathname: '/photo-**',
      },
      // Add additional domains if needed for property images
      {
        protocol: 'https',
        hostname: '*.googleapis.com',
        port: '',
        pathname: '/**',
      },
    ],
  },
  // Ensure trailing slashes are consistent
  trailingSlash: false,
  // Add rewrites for API if needed
  async rewrites() {
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
    
    return [
      // API routes
      {
        source: '/api/:path*',
        destination: `${apiBaseUrl}/:path*`,
      },
      // Property routes
      {
        source: '/properties/:path*',
        destination: `${apiBaseUrl}/properties/:path*`,
      },
      // Handle the root /properties endpoint
      {
        source: '/properties',
        destination: `${apiBaseUrl}/properties`,
      },
      // Health check endpoint
      {
        source: '/health',
        destination: `${apiBaseUrl}/health`,
      },
    ];
  },
};

export default nextConfig;
