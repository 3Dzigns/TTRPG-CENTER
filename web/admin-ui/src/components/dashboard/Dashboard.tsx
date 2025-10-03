/**
 * Admin Dashboard Component
 *
 * Real-time system monitoring, health indicators, and metrics overview
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import {
  Activity,
  Server,
  Database,
  Users,
  Upload,
  CheckCircle,
  AlertTriangle,
  XCircle,
  RefreshCw,
  TrendingUp,
  Clock,
  Cpu,
  HardDrive,
  Server
} from 'lucide-react';

interface SystemMetrics {
  status: 'healthy' | 'warning' | 'error';
  uptime: number;
  memory_usage: number;
  cpu_usage: number;
  disk_usage: number;
  active_connections: number;
  processed_jobs_24h: number;
  failed_jobs_24h: number;
  average_response_time: number;
}

interface ServiceStatus {
  name: string;
  status: 'running' | 'degraded' | 'down';
  port: number;
  uptime: number;
  last_check: string;
}

export default function Dashboard() {
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [services, setServices] = useState<ServiceStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isUsingMockData, setIsUsingMockData] = useState(false);

  const getAdminApiUrl = (): string => {
    // Check if we're running in a containerized environment (Admin UI served from nginx)
    const isContainerized = window.location.port === '3000';

    if (isContainerized) {
      // Use nginx proxy path for containerized deployment
      return '/api/admin';
    }

    // For local development (Vite dev server)
    const currentEnv = process.env.NODE_ENV || 'development';
    const portMap: Record<string, number> = {
      development: 8000,
      test: 8182,
      production: 8282
    };
    const port = portMap[currentEnv] || 8000;
    return `http://localhost:${port}`;
  };

  const loadSystemMetrics = async () => {
    try {
      const adminApiUrl = getAdminApiUrl();
      const [metricsRes, servicesRes] = await Promise.all([
        fetch(`${adminApiUrl}/admin/metrics`),
        fetch(`${adminApiUrl}/admin/services`)
      ]);

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json();
        setMetrics(metricsData);
      }

      if (servicesRes.ok) {
        const servicesData = await servicesRes.json();
        setServices(servicesData);
      }
    } catch (error) {
      console.error('Failed to load system metrics:', error);
      setError(error instanceof Error ? error.message : 'Failed to load system metrics');
      setIsUsingMockData(true);

      // Set realistic development data while API is being fixed
      setMetrics({
        status: 'warning', // Indicate this is mock data
        uptime: Math.floor(Date.now() / 1000) - 86400,
        memory_usage: 65.4 + Math.random() * 10,
        cpu_usage: 23.1 + Math.random() * 20,
        disk_usage: 47.8,
        active_connections: 12 + Math.floor(Math.random() * 8),
        processed_jobs_24h: 45,
        failed_jobs_24h: 2,
        average_response_time: 245 + Math.random() * 100
      });

      setServices([
        { name: 'Admin API', status: 'degraded', port: 8000, uptime: 86400, last_check: new Date().toISOString() },
        { name: 'User API', status: 'running', port: 8002, uptime: 86400, last_check: new Date().toISOString() },
        { name: 'Ingest Service', status: 'running', port: 8003, uptime: 86400, last_check: new Date().toISOString() },
        { name: 'Orchestrator', status: 'running', port: 8004, uptime: 86400, last_check: new Date().toISOString() },
        { name: 'Cassandra DB', status: 'running', port: 9042, uptime: 172800, last_check: new Date().toISOString() },
        { name: 'Redis Cache', status: 'running', port: 6379, uptime: 172800, last_check: new Date().toISOString() }
      ]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSystemMetrics();
    const interval = setInterval(loadSystemMetrics, 30000); // Refresh every 30 seconds
    return () => clearInterval(interval);
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'running':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'warning':
      case 'degraded':
        return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'error':
      case 'down':
        return <XCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'healthy':
      case 'running':
        return 'bg-green-100 text-green-800';
      case 'warning':
      case 'degraded':
        return 'bg-yellow-100 text-yellow-800';
      case 'error':
      case 'down':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const formatUptime = (seconds: number): string => {
    const days = Math.floor(seconds / 86400);
    const hours = Math.floor((seconds % 86400) / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);

    if (days > 0) return `${days}d ${hours}h ${minutes}m`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading system metrics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Dashboard</h1>
          <p className="text-muted-foreground">
            Real-time monitoring and system health overview
          </p>
        </div>
        <Badge className={`${getStatusColor(metrics?.status || 'error')} flex items-center gap-1`}>
          {getStatusIcon(metrics?.status || 'error')}
          System {metrics?.status || 'Unknown'}
        </Badge>
      </div>

      {/* Mock Data Warning */}
      {isUsingMockData && (
        <Card className="border-yellow-200 bg-yellow-50">
          <CardContent className="pt-4">
            <div className="flex items-center gap-2 text-yellow-800">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm font-medium">
                Development Mode: API endpoints unavailable, displaying mock data for demonstration.
              </span>
            </div>
            {error && (
              <div className="mt-2 text-xs text-yellow-700">
                Technical: {error}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Key Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">CPU Usage</CardTitle>
              <Cpu className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.cpu_usage.toFixed(1)}%</div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{ width: `${metrics.cpu_usage}%` }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Memory Usage</CardTitle>
              <Server className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.memory_usage.toFixed(1)}%</div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{ width: `${metrics.memory_usage}%` }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Disk Usage</CardTitle>
              <HardDrive className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.disk_usage.toFixed(1)}%</div>
              <div className="w-full bg-secondary rounded-full h-2 mt-2">
                <div
                  className="bg-primary h-2 rounded-full transition-all"
                  style={{ width: `${metrics.disk_usage}%` }}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Connections</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{metrics.active_connections}</div>
              <p className="text-xs text-muted-foreground">
                Current active sessions
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Service Status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Service Status
            </CardTitle>
            <CardDescription>
              Health and status of all microservices
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-64">
              <div className="space-y-3">
                {services.map((service) => (
                  <div key={service.name} className="flex items-center justify-between p-3 border rounded-lg">
                    <div className="flex items-center gap-3">
                      {getStatusIcon(service.status)}
                      <div>
                        <div className="font-medium">{service.name}</div>
                        <div className="text-sm text-muted-foreground">
                          Port {service.port} • Uptime: {formatUptime(service.uptime)}
                        </div>
                      </div>
                    </div>
                    <Badge className={getStatusColor(service.status)}>
                      {service.status}
                    </Badge>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        {/* Performance Metrics */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5" />
              Performance Overview
            </CardTitle>
            <CardDescription>
              24-hour system performance summary
            </CardDescription>
          </CardHeader>
          <CardContent>
            {metrics && (
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">System Uptime</span>
                  <span className="text-sm">{formatUptime(metrics.uptime)}</span>
                </div>
                <Separator />

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Jobs Processed (24h)</span>
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500" />
                    <span className="text-sm">{metrics.processed_jobs_24h}</span>
                  </div>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Failed Jobs (24h)</span>
                  <div className="flex items-center gap-2">
                    <XCircle className="h-4 w-4 text-red-500" />
                    <span className="text-sm">{metrics.failed_jobs_24h}</span>
                  </div>
                </div>

                <Separator />

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Avg Response Time</span>
                  <span className="text-sm">{metrics.average_response_time}ms</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Success Rate</span>
                  <span className="text-sm">
                    {((metrics.processed_jobs_24h / (metrics.processed_jobs_24h + metrics.failed_jobs_24h)) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}