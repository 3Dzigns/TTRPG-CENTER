/**
 * Health Check Endpoint
 * Used by Docker health checks and monitoring
 */

import { NextResponse } from 'next/server';

export const dynamic = 'force-dynamic'; // Disable caching

interface HealthStatus {
  status: 'healthy' | 'unhealthy';
  timestamp: string;
  uptime: number;
  environment: string;
  version: string;
}

export async function GET() {
  try {
    const healthStatus: HealthStatus = {
      status: 'healthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      environment: process.env.NODE_ENV || 'development',
      version: process.env.npm_package_version || '0.1.0',
    };

    return NextResponse.json(healthStatus, { status: 200 });
  } catch (error) {
    const errorStatus: HealthStatus = {
      status: 'unhealthy',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
      environment: process.env.NODE_ENV || 'development',
      version: process.env.npm_package_version || '0.1.0',
    };

    return NextResponse.json(errorStatus, { status: 503 });
  }
}
