/**
 * Analytics & Reports Component
 *
 * Performance metrics, usage analytics, and system reports
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  BarChart3,
  TrendingUp,
  TrendingDown,
  Users,
  Clock,
  Database,
  Zap,
  Activity,
  Download,
  RefreshCw,
  Calendar,
  FileText,
  AlertTriangle,
  CheckCircle
} from 'lucide-react';

interface UsageMetrics {
  period: string;
  total_queries: number;
  unique_users: number;
  avg_response_time_ms: number;
  success_rate: number;
  peak_concurrent_users: number;
  data_processed_gb: number;
}

interface TopQuery {
  query: string;
  count: number;
  avg_response_time_ms: number;
  success_rate: number;
}

interface ErrorSummary {
  error_type: string;
  count: number;
  last_occurrence: string;
  severity: 'low' | 'medium' | 'high';
}

interface PerformanceReport {
  period: string;
  cpu_avg: number;
  memory_avg: number;
  disk_usage: number;
  network_io_gb: number;
  database_connections_avg: number;
  cache_hit_rate: number;
}

export default function Analytics() {
  const [usageMetrics, setUsageMetrics] = useState<UsageMetrics[]>([]);
  const [topQueries, setTopQueries] = useState<TopQuery[]>([]);
  const [errorSummary, setErrorSummary] = useState<ErrorSummary[]>([]);
  const [performanceReport, setPerformanceReport] = useState<PerformanceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [timePeriod, setTimePeriod] = useState<'24h' | '7d' | '30d' | '90d'>('24h');
  const [activeTab, setActiveTab] = useState<'usage' | 'performance' | 'errors' | 'reports'>('usage');

  const getAdminApiUrl = (): string => {
    const currentEnv = process.env.NODE_ENV || 'development';
    const portMap: Record<string, number> = {
      development: 8000,
      test: 8182,
      production: 8282
    };
    const port = portMap[currentEnv] || 8000;
    return `http://localhost:${port}`;
  };

  const loadAnalytics = async () => {
    setLoading(true);
    try {
      const adminApiUrl = getAdminApiUrl();

      // Mock data for development
      const mockUsageMetrics: UsageMetrics[] = [
        {
          period: '2024-01-15',
          total_queries: 1247,
          unique_users: 89,
          avg_response_time_ms: 245,
          success_rate: 97.8,
          peak_concurrent_users: 23,
          data_processed_gb: 2.4
        },
        {
          period: '2024-01-14',
          total_queries: 1156,
          unique_users: 76,
          avg_response_time_ms: 267,
          success_rate: 96.2,
          peak_concurrent_users: 19,
          data_processed_gb: 2.1
        },
        {
          period: '2024-01-13',
          total_queries: 1034,
          unique_users: 82,
          avg_response_time_ms: 223,
          success_rate: 98.1,
          peak_concurrent_users: 21,
          data_processed_gb: 1.9
        }
      ];

      const mockTopQueries: TopQuery[] = [
        {
          query: 'How do I create a character in D&D 5e?',
          count: 245,
          avg_response_time_ms: 189,
          success_rate: 99.2
        },
        {
          query: 'What are the rules for spellcasting?',
          count: 198,
          avg_response_time_ms: 234,
          success_rate: 97.5
        },
        {
          query: 'How does combat work in Pathfinder?',
          count: 167,
          avg_response_time_ms: 267,
          success_rate: 96.8
        },
        {
          query: 'What dice do I need for RPGs?',
          count: 134,
          avg_response_time_ms: 156,
          success_rate: 100.0
        },
        {
          query: 'How to be a good dungeon master?',
          count: 123,
          avg_response_time_ms: 298,
          success_rate: 94.3
        }
      ];

      const mockErrorSummary: ErrorSummary[] = [
        {
          error_type: 'Query Timeout',
          count: 23,
          last_occurrence: '2024-01-15T14:30:00Z',
          severity: 'medium'
        },
        {
          error_type: 'Database Connection Failed',
          count: 8,
          last_occurrence: '2024-01-15T11:15:00Z',
          severity: 'high'
        },
        {
          error_type: 'Invalid Query Format',
          count: 45,
          last_occurrence: '2024-01-15T16:45:00Z',
          severity: 'low'
        },
        {
          error_type: 'Rate Limit Exceeded',
          count: 12,
          last_occurrence: '2024-01-15T13:20:00Z',
          severity: 'medium'
        }
      ];

      const mockPerformanceReport: PerformanceReport = {
        period: '24h',
        cpu_avg: 34.2,
        memory_avg: 67.8,
        disk_usage: 45.3,
        network_io_gb: 12.4,
        database_connections_avg: 15.6,
        cache_hit_rate: 89.2
      };

      setUsageMetrics(mockUsageMetrics);
      setTopQueries(mockTopQueries);
      setErrorSummary(mockErrorSummary);
      setPerformanceReport(mockPerformanceReport);

    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setLoading(false);
    }
  };

  const exportReport = async (reportType: string) => {
    try {
      const adminApiUrl = getAdminApiUrl();
      // In a real implementation, this would trigger a report generation
      console.log(`Exporting ${reportType} report for period: ${timePeriod}`);
      alert(`${reportType} report export started. You will receive an email when ready.`);
    } catch (error) {
      console.error('Failed to export report:', error);
      alert('Failed to export report');
    }
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'high': return 'bg-red-100 text-red-800';
      case 'medium': return 'bg-yellow-100 text-yellow-800';
      case 'low': return 'bg-green-100 text-green-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getSeverityIcon = (severity: string) => {
    switch (severity) {
      case 'high': return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'medium': return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
      case 'low': return <CheckCircle className="h-4 w-4 text-green-500" />;
      default: return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const formatRelativeTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  };

  useEffect(() => {
    loadAnalytics();
  }, [timePeriod]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading analytics...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Analytics & Reports</h1>
          <p className="text-muted-foreground">
            System performance metrics, usage analytics, and detailed reports
          </p>
        </div>
        <div className="flex gap-2">
          <Select value={timePeriod} onValueChange={(value: any) => setTimePeriod(value)}>
            <SelectTrigger className="w-32">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="24h">Last 24h</SelectItem>
              <SelectItem value="7d">Last 7 days</SelectItem>
              <SelectItem value="30d">Last 30 days</SelectItem>
              <SelectItem value="90d">Last 90 days</SelectItem>
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            onClick={loadAnalytics}
            className="flex items-center gap-2"
          >
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
        </div>
      </div>

      {/* Key Metrics Overview */}
      {usageMetrics.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Queries</CardTitle>
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{usageMetrics[0].total_queries.toLocaleString()}</div>
              <p className="text-xs text-muted-foreground">
                {timePeriod === '24h' ? 'in last 24 hours' : `in last ${timePeriod}`}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Unique Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{usageMetrics[0].unique_users}</div>
              <p className="text-xs text-muted-foreground">
                Peak concurrent: {usageMetrics[0].peak_concurrent_users}
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Avg Response Time</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{usageMetrics[0].avg_response_time_ms}ms</div>
              <div className="flex items-center text-xs text-muted-foreground">
                {usageMetrics[0].avg_response_time_ms < usageMetrics[1]?.avg_response_time_ms ? (
                  <TrendingDown className="h-3 w-3 text-green-500 mr-1" />
                ) : (
                  <TrendingUp className="h-3 w-3 text-red-500 mr-1" />
                )}
                vs previous period
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Success Rate</CardTitle>
              <CheckCircle className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{usageMetrics[0].success_rate.toFixed(1)}%</div>
              <p className="text-xs text-muted-foreground">
                {usageMetrics[0].data_processed_gb.toFixed(1)} GB processed
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-2">
        <Button
          variant={activeTab === 'usage' ? 'default' : 'outline'}
          onClick={() => setActiveTab('usage')}
          className="flex items-center gap-2"
        >
          <Activity className="h-4 w-4" />
          Usage Analytics
        </Button>
        <Button
          variant={activeTab === 'performance' ? 'default' : 'outline'}
          onClick={() => setActiveTab('performance')}
          className="flex items-center gap-2"
        >
          <Zap className="h-4 w-4" />
          Performance
        </Button>
        <Button
          variant={activeTab === 'errors' ? 'default' : 'outline'}
          onClick={() => setActiveTab('errors')}
          className="flex items-center gap-2"
        >
          <AlertTriangle className="h-4 w-4" />
          Error Analysis
        </Button>
        <Button
          variant={activeTab === 'reports' ? 'default' : 'outline'}
          onClick={() => setActiveTab('reports')}
          className="flex items-center gap-2"
        >
          <FileText className="h-4 w-4" />
          Reports
        </Button>
      </div>

      {activeTab === 'usage' && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Usage Trends */}
          <Card>
            <CardHeader>
              <CardTitle>Usage Trends</CardTitle>
              <CardDescription>Query volume and user activity over time</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                <div className="space-y-4">
                  {usageMetrics.map((metric, index) => (
                    <div key={metric.period} className="flex items-center justify-between p-3 border rounded-lg">
                      <div>
                        <div className="font-medium">{new Date(metric.period).toLocaleDateString()}</div>
                        <div className="text-sm text-muted-foreground">
                          {metric.unique_users} users • {metric.total_queries} queries
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-medium">{metric.success_rate.toFixed(1)}%</div>
                        <div className="text-xs text-muted-foreground">{metric.avg_response_time_ms}ms avg</div>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>

          {/* Top Queries */}
          <Card>
            <CardHeader>
              <CardTitle>Top Queries</CardTitle>
              <CardDescription>Most frequent user queries and their performance</CardDescription>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-64">
                <div className="space-y-4">
                  {topQueries.map((query, index) => (
                    <div key={index} className="border rounded-lg p-3">
                      <div className="flex items-start justify-between mb-2">
                        <div className="text-sm font-medium line-clamp-2 flex-1 mr-2">
                          {query.query}
                        </div>
                        <Badge variant="secondary">{query.count}x</Badge>
                      </div>
                      <div className="flex justify-between text-xs text-muted-foreground">
                        <span>Avg: {query.avg_response_time_ms}ms</span>
                        <span>Success: {query.success_rate.toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'performance' && performanceReport && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* System Performance */}
          <Card>
            <CardHeader>
              <CardTitle>System Performance</CardTitle>
              <CardDescription>Resource utilization and system health metrics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">CPU Usage (Avg)</span>
                  <span className="text-sm">{performanceReport.cpu_avg.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${performanceReport.cpu_avg}%` }}
                  />
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Memory Usage (Avg)</span>
                  <span className="text-sm">{performanceReport.memory_avg.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${performanceReport.memory_avg}%` }}
                  />
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Disk Usage</span>
                  <span className="text-sm">{performanceReport.disk_usage.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-primary h-2 rounded-full transition-all"
                    style={{ width: `${performanceReport.disk_usage}%` }}
                  />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Database & Network */}
          <Card>
            <CardHeader>
              <CardTitle>Database & Network</CardTitle>
              <CardDescription>Database connections and network I/O statistics</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">DB Connections (Avg)</span>
                  <span className="text-sm">{performanceReport.database_connections_avg.toFixed(1)}</span>
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Cache Hit Rate</span>
                  <span className="text-sm">{performanceReport.cache_hit_rate.toFixed(1)}%</span>
                </div>
                <div className="w-full bg-secondary rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full transition-all"
                    style={{ width: `${performanceReport.cache_hit_rate}%` }}
                  />
                </div>

                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium">Network I/O</span>
                  <span className="text-sm">{performanceReport.network_io_gb.toFixed(1)} GB</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'errors' && (
        <Card>
          <CardHeader>
            <CardTitle>Error Analysis</CardTitle>
            <CardDescription>Error frequency and severity breakdown</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {errorSummary.map((error, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex items-start gap-3">
                      {getSeverityIcon(error.severity)}
                      <div>
                        <div className="font-medium">{error.error_type}</div>
                        <div className="text-sm text-muted-foreground">
                          Last occurred: {formatRelativeTime(error.last_occurrence)}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">{error.count} occurrences</Badge>
                      <Badge className={getSeverityColor(error.severity)}>
                        {error.severity}
                      </Badge>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'reports' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle>Usage Reports</CardTitle>
              <CardDescription>Detailed usage and activity reports</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                onClick={() => exportReport('User Activity')}
                className="w-full flex items-center gap-2"
              >
                <Download className="h-4 w-4" />
                Export User Activity Report
              </Button>
              <Button
                onClick={() => exportReport('Query Analytics')}
                className="w-full flex items-center gap-2"
                variant="outline"
              >
                <Download className="h-4 w-4" />
                Export Query Analytics Report
              </Button>
              <Button
                onClick={() => exportReport('Performance Summary')}
                className="w-full flex items-center gap-2"
                variant="outline"
              >
                <Download className="h-4 w-4" />
                Export Performance Summary
              </Button>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>System Reports</CardTitle>
              <CardDescription>Technical and operational reports</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Button
                onClick={() => exportReport('Error Analysis')}
                className="w-full flex items-center gap-2"
              >
                <Download className="h-4 w-4" />
                Export Error Analysis Report
              </Button>
              <Button
                onClick={() => exportReport('Security Audit')}
                className="w-full flex items-center gap-2"
                variant="outline"
              >
                <Download className="h-4 w-4" />
                Export Security Audit Log
              </Button>
              <Button
                onClick={() => exportReport('System Health')}
                className="w-full flex items-center gap-2"
                variant="outline"
              >
                <Download className="h-4 w-4" />
                Export System Health Report
              </Button>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}