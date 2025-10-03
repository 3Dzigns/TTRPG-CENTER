/**
 * System Configuration Component
 *
 * Feature flags, environment settings, and administrative configuration
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import {
  Settings,
  Flag,
  Save,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  Database,
  Server,
  Shield,
  Zap,
  Eye,
  EyeOff,
  RotateCcw,
  Download,
  Upload
} from 'lucide-react';

interface FeatureFlag {
  name: string;
  key: string;
  description: string;
  enabled: boolean;
  environment: 'all' | 'dev' | 'test' | 'prod';
  type: 'boolean' | 'string' | 'number';
  value?: string | number;
}

interface EnvironmentConfig {
  name: string;
  api_base_url: string;
  database_url: string;
  redis_url: string;
  log_level: 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';
  max_concurrent_jobs: number;
  enable_metrics: boolean;
  enable_tracing: boolean;
}

interface SystemSettings {
  maintenance_mode: boolean;
  max_upload_size_mb: number;
  session_timeout_minutes: number;
  rate_limit_per_minute: number;
  enable_user_registration: boolean;
  require_email_verification: boolean;
  default_user_role: 'user' | 'moderator' | 'admin';
}

export default function SystemConfiguration() {
  const [featureFlags, setFeatureFlags] = useState<FeatureFlag[]>([]);
  const [envConfig, setEnvConfig] = useState<EnvironmentConfig | null>(null);
  const [systemSettings, setSystemSettings] = useState<SystemSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState<'flags' | 'environment' | 'system'>('flags');
  const [showSensitive, setShowSensitive] = useState(false);

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

  const loadConfiguration = async () => {
    setLoading(true);
    try {
      const adminApiUrl = getAdminApiUrl();

      // Mock data for development
      const mockFeatureFlags: FeatureFlag[] = [
        {
          name: 'Advanced Query Processing',
          key: 'enable_advanced_qic',
          description: 'Enable query intent classification and advanced routing',
          enabled: true,
          environment: 'all',
          type: 'boolean'
        },
        {
          name: 'Workflow Management',
          key: 'enable_workflow_graphs',
          description: 'Enable graph-based workflow planning and execution',
          enabled: false,
          environment: 'dev',
          type: 'boolean'
        },
        {
          name: 'Real-time Updates',
          key: 'enable_realtime_updates',
          description: 'Enable WebSocket connections for real-time UI updates',
          enabled: true,
          environment: 'all',
          type: 'boolean'
        },
        {
          name: 'Beta Features',
          key: 'enable_beta_features',
          description: 'Enable experimental and beta features for testing',
          enabled: false,
          environment: 'dev',
          type: 'boolean'
        },
        {
          name: 'Query Cache TTL',
          key: 'query_cache_ttl_seconds',
          description: 'Time-to-live for query result caching in seconds',
          enabled: true,
          environment: 'all',
          type: 'number',
          value: 300
        },
        {
          name: 'Default Model',
          key: 'default_ai_model',
          description: 'Default AI model for query processing',
          enabled: true,
          environment: 'all',
          type: 'string',
          value: 'gpt-4o-mini'
        }
      ];

      const mockEnvConfig: EnvironmentConfig = {
        name: 'development',
        api_base_url: 'http://localhost:8000',
        database_url: 'cassandra://localhost:9042',
        redis_url: 'redis://localhost:6379',
        log_level: 'INFO',
        max_concurrent_jobs: 10,
        enable_metrics: true,
        enable_tracing: false
      };

      const mockSystemSettings: SystemSettings = {
        maintenance_mode: false,
        max_upload_size_mb: 100,
        session_timeout_minutes: 60,
        rate_limit_per_minute: 100,
        enable_user_registration: true,
        require_email_verification: false,
        default_user_role: 'user'
      };

      setFeatureFlags(mockFeatureFlags);
      setEnvConfig(mockEnvConfig);
      setSystemSettings(mockSystemSettings);

    } catch (error) {
      console.error('Failed to load configuration:', error);
    } finally {
      setLoading(false);
    }
  };

  const saveConfiguration = async () => {
    setSaving(true);
    try {
      const adminApiUrl = getAdminApiUrl();

      // In a real implementation, we would save to the backend
      await new Promise(resolve => setTimeout(resolve, 1000)); // Simulate API call

      console.log('Configuration saved:', { featureFlags, envConfig, systemSettings });
      alert('Configuration saved successfully!');

    } catch (error) {
      console.error('Failed to save configuration:', error);
      alert('Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const toggleFeatureFlag = (key: string) => {
    setFeatureFlags(prev => prev.map(flag =>
      flag.key === key ? { ...flag, enabled: !flag.enabled } : flag
    ));
  };

  const updateFeatureFlagValue = (key: string, value: string | number) => {
    setFeatureFlags(prev => prev.map(flag =>
      flag.key === key ? { ...flag, value } : flag
    ));
  };

  const maskSensitiveValue = (value: string): string => {
    if (value.includes('://')) {
      const [protocol, rest] = value.split('://');
      const [credentials, hostPath] = rest.split('@');
      if (hostPath) {
        return `${protocol}://*****@${hostPath}`;
      }
    }
    return value.length > 20 ? value.substring(0, 10) + '*****' + value.substring(value.length - 5) : value;
  };

  useEffect(() => {
    loadConfiguration();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading configuration...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">System Configuration</h1>
          <p className="text-muted-foreground">
            Manage feature flags, environment settings, and system configuration
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => setShowSensitive(!showSensitive)}
            className="flex items-center gap-2"
          >
            {showSensitive ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            {showSensitive ? 'Hide' : 'Show'} Sensitive
          </Button>
          <Button
            onClick={saveConfiguration}
            disabled={saving}
            className="flex items-center gap-2"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </div>
      </div>

      {/* Navigation Tabs */}
      <div className="flex gap-2">
        <Button
          variant={activeTab === 'flags' ? 'default' : 'outline'}
          onClick={() => setActiveTab('flags')}
          className="flex items-center gap-2"
        >
          <Flag className="h-4 w-4" />
          Feature Flags
        </Button>
        <Button
          variant={activeTab === 'environment' ? 'default' : 'outline'}
          onClick={() => setActiveTab('environment')}
          className="flex items-center gap-2"
        >
          <Server className="h-4 w-4" />
          Environment
        </Button>
        <Button
          variant={activeTab === 'system' ? 'default' : 'outline'}
          onClick={() => setActiveTab('system')}
          className="flex items-center gap-2"
        >
          <Settings className="h-4 w-4" />
          System Settings
        </Button>
      </div>

      {activeTab === 'flags' && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Flag className="h-5 w-5" />
              Feature Flags
            </CardTitle>
            <CardDescription>
              Control feature availability and behavior across environments
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              {featureFlags.map((flag) => (
                <div key={flag.key} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div>
                      <div className="font-medium">{flag.name}</div>
                      <div className="text-sm text-muted-foreground">{flag.description}</div>
                      <div className="text-xs text-muted-foreground mt-1">
                        Key: {flag.key} • Environment: {flag.environment} • Type: {flag.type}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={flag.environment === 'prod' ? 'default' : 'secondary'}>
                        {flag.environment}
                      </Badge>
                      <Badge variant={flag.enabled ? 'default' : 'secondary'}>
                        {flag.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    {flag.type === 'boolean' ? (
                      <Button
                        size="sm"
                        variant={flag.enabled ? 'default' : 'outline'}
                        onClick={() => toggleFeatureFlag(flag.key)}
                        className="flex items-center gap-1"
                      >
                        {flag.enabled ? <CheckCircle className="h-3 w-3" /> : <AlertTriangle className="h-3 w-3" />}
                        {flag.enabled ? 'Enabled' : 'Disabled'}
                      </Button>
                    ) : (
                      <div className="flex items-center gap-2">
                        <Label htmlFor={`flag-${flag.key}`} className="text-sm">Value:</Label>
                        <Input
                          id={`flag-${flag.key}`}
                          type={flag.type === 'number' ? 'number' : 'text'}
                          value={flag.value || ''}
                          onChange={(e) => updateFeatureFlagValue(
                            flag.key,
                            flag.type === 'number' ? Number(e.target.value) : e.target.value
                          )}
                          className="w-32"
                        />
                      </div>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'environment' && envConfig && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-5 w-5" />
              Environment Configuration
            </CardTitle>
            <CardDescription>
              Current environment settings and connection details
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="env-name">Environment</Label>
                  <Input
                    id="env-name"
                    value={envConfig.name}
                    onChange={(e) => setEnvConfig(prev => prev ? { ...prev, name: e.target.value } : null)}
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="log-level">Log Level</Label>
                  <Select
                    value={envConfig.log_level}
                    onValueChange={(value: any) => setEnvConfig(prev => prev ? { ...prev, log_level: value } : null)}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="DEBUG">DEBUG</SelectItem>
                      <SelectItem value="INFO">INFO</SelectItem>
                      <SelectItem value="WARNING">WARNING</SelectItem>
                      <SelectItem value="ERROR">ERROR</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <Database className="h-5 w-5" />
                  Database & Cache Configuration
                </h3>

                <div className="grid grid-cols-1 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="api-url">API Base URL</Label>
                    <Input
                      id="api-url"
                      value={envConfig.api_base_url}
                      onChange={(e) => setEnvConfig(prev => prev ? { ...prev, api_base_url: e.target.value } : null)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="db-url">Database URL</Label>
                    <Input
                      id="db-url"
                      type={showSensitive ? 'text' : 'password'}
                      value={showSensitive ? envConfig.database_url : maskSensitiveValue(envConfig.database_url)}
                      onChange={(e) => setEnvConfig(prev => prev ? { ...prev, database_url: e.target.value } : null)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="redis-url">Redis URL</Label>
                    <Input
                      id="redis-url"
                      type={showSensitive ? 'text' : 'password'}
                      value={showSensitive ? envConfig.redis_url : maskSensitiveValue(envConfig.redis_url)}
                      onChange={(e) => setEnvConfig(prev => prev ? { ...prev, redis_url: e.target.value } : null)}
                    />
                  </div>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <Zap className="h-5 w-5" />
                  Performance & Monitoring
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="max-jobs">Max Concurrent Jobs</Label>
                    <Input
                      id="max-jobs"
                      type="number"
                      value={envConfig.max_concurrent_jobs}
                      onChange={(e) => setEnvConfig(prev => prev ? { ...prev, max_concurrent_jobs: Number(e.target.value) } : null)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label>Enable Metrics</Label>
                    <Button
                      size="sm"
                      variant={envConfig.enable_metrics ? 'default' : 'outline'}
                      onClick={() => setEnvConfig(prev => prev ? { ...prev, enable_metrics: !prev.enable_metrics } : null)}
                      className="w-full"
                    >
                      {envConfig.enable_metrics ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>Enable Tracing</Label>
                    <Button
                      size="sm"
                      variant={envConfig.enable_tracing ? 'default' : 'outline'}
                      onClick={() => setEnvConfig(prev => prev ? { ...prev, enable_tracing: !prev.enable_tracing } : null)}
                      className="w-full"
                    >
                      {envConfig.enable_tracing ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {activeTab === 'system' && systemSettings && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Settings className="h-5 w-5" />
              System Settings
            </CardTitle>
            <CardDescription>
              Global system configuration and security settings
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-6">
              <div className="space-y-4">
                <h3 className="text-lg font-medium flex items-center gap-2">
                  <Shield className="h-5 w-5" />
                  Security & Access Control
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Maintenance Mode</Label>
                    <Button
                      size="sm"
                      variant={systemSettings.maintenance_mode ? 'destructive' : 'outline'}
                      onClick={() => setSystemSettings(prev => prev ? { ...prev, maintenance_mode: !prev.maintenance_mode } : null)}
                      className="w-full"
                    >
                      {systemSettings.maintenance_mode ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>User Registration</Label>
                    <Button
                      size="sm"
                      variant={systemSettings.enable_user_registration ? 'default' : 'outline'}
                      onClick={() => setSystemSettings(prev => prev ? { ...prev, enable_user_registration: !prev.enable_user_registration } : null)}
                      className="w-full"
                    >
                      {systemSettings.enable_user_registration ? 'Enabled' : 'Disabled'}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label>Email Verification</Label>
                    <Button
                      size="sm"
                      variant={systemSettings.require_email_verification ? 'default' : 'outline'}
                      onClick={() => setSystemSettings(prev => prev ? { ...prev, require_email_verification: !prev.require_email_verification } : null)}
                      className="w-full"
                    >
                      {systemSettings.require_email_verification ? 'Required' : 'Optional'}
                    </Button>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="default-role">Default User Role</Label>
                    <Select
                      value={systemSettings.default_user_role}
                      onValueChange={(value: any) => setSystemSettings(prev => prev ? { ...prev, default_user_role: value } : null)}
                    >
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="user">User</SelectItem>
                        <SelectItem value="moderator">Moderator</SelectItem>
                        <SelectItem value="admin">Admin</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>
              </div>

              <Separator />

              <div className="space-y-4">
                <h3 className="text-lg font-medium">Resource Limits</h3>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="upload-size">Max Upload Size (MB)</Label>
                    <Input
                      id="upload-size"
                      type="number"
                      value={systemSettings.max_upload_size_mb}
                      onChange={(e) => setSystemSettings(prev => prev ? { ...prev, max_upload_size_mb: Number(e.target.value) } : null)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="session-timeout">Session Timeout (minutes)</Label>
                    <Input
                      id="session-timeout"
                      type="number"
                      value={systemSettings.session_timeout_minutes}
                      onChange={(e) => setSystemSettings(prev => prev ? { ...prev, session_timeout_minutes: Number(e.target.value) } : null)}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="rate-limit">Rate Limit (per minute)</Label>
                    <Input
                      id="rate-limit"
                      type="number"
                      value={systemSettings.rate_limit_per_minute}
                      onChange={(e) => setSystemSettings(prev => prev ? { ...prev, rate_limit_per_minute: Number(e.target.value) } : null)}
                    />
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}