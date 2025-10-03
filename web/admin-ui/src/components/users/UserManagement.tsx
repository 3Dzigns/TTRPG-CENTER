/**
 * User Management Component
 *
 * Role-based access control, user activity monitoring, and session management
 */

import { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  Users,
  UserPlus,
  UserX,
  Shield,
  Activity,
  Clock,
  Search,
  Filter,
  Edit,
  Trash2,
  RefreshCw,
  Eye,
  Ban,
  CheckCircle,
  AlertCircle
} from 'lucide-react';

interface User {
  id: string;
  username: string;
  email: string;
  role: 'admin' | 'moderator' | 'user';
  status: 'active' | 'inactive' | 'banned';
  last_login: string;
  created_at: string;
  session_count: number;
  total_queries: number;
}

interface UserSession {
  session_id: string;
  user_id: string;
  username: string;
  started_at: string;
  last_activity: string;
  ip_address: string;
  user_agent: string;
  query_count: number;
}

interface UserStats {
  total_users: number;
  active_users: number;
  new_users_24h: number;
  active_sessions: number;
  total_queries_24h: number;
}

export default function UserManagement() {
  const [users, setUsers] = useState<User[]>([]);
  const [sessions, setSessions] = useState<UserSession[]>([]);
  const [stats, setStats] = useState<UserStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'users' | 'sessions' | 'stats'>('users');

  // Filters
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState<string>('');
  const [statusFilter, setStatusFilter] = useState<string>('');

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

  const loadUserData = async () => {
    setLoading(true);
    try {
      const adminApiUrl = getAdminApiUrl();
      const [usersRes, sessionsRes, statsRes] = await Promise.all([
        fetch(`${adminApiUrl}/admin/users`),
        fetch(`${adminApiUrl}/admin/sessions`),
        fetch(`${adminApiUrl}/admin/user-stats`)
      ]);

      // Mock data for development since endpoints may not exist yet
      const mockUsers: User[] = [
        {
          id: 'user_1',
          username: 'admin_user',
          email: 'admin@ttrpg.center',
          role: 'admin',
          status: 'active',
          last_login: '2024-01-15T10:30:00Z',
          created_at: '2024-01-01T00:00:00Z',
          session_count: 45,
          total_queries: 1250
        },
        {
          id: 'user_2',
          username: 'moderator_jane',
          email: 'jane@ttrpg.center',
          role: 'moderator',
          status: 'active',
          last_login: '2024-01-15T09:15:00Z',
          created_at: '2024-01-03T00:00:00Z',
          session_count: 32,
          total_queries: 890
        },
        {
          id: 'user_3',
          username: 'player_bob',
          email: 'bob@example.com',
          role: 'user',
          status: 'active',
          last_login: '2024-01-14T20:45:00Z',
          created_at: '2024-01-10T00:00:00Z',
          session_count: 12,
          total_queries: 156
        },
        {
          id: 'user_4',
          username: 'inactive_user',
          email: 'inactive@example.com',
          role: 'user',
          status: 'inactive',
          last_login: '2024-01-01T12:00:00Z',
          created_at: '2023-12-15T00:00:00Z',
          session_count: 3,
          total_queries: 25
        }
      ];

      const mockSessions: UserSession[] = [
        {
          session_id: 'sess_1',
          user_id: 'user_1',
          username: 'admin_user',
          started_at: '2024-01-15T10:30:00Z',
          last_activity: '2024-01-15T11:45:00Z',
          ip_address: '192.168.1.100',
          user_agent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
          query_count: 15
        },
        {
          session_id: 'sess_2',
          user_id: 'user_2',
          username: 'moderator_jane',
          started_at: '2024-01-15T09:15:00Z',
          last_activity: '2024-01-15T11:30:00Z',
          ip_address: '192.168.1.101',
          user_agent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
          query_count: 8
        }
      ];

      const mockStats: UserStats = {
        total_users: 156,
        active_users: 89,
        new_users_24h: 12,
        active_sessions: 23,
        total_queries_24h: 456
      };

      setUsers(mockUsers);
      setSessions(mockSessions);
      setStats(mockStats);

    } catch (error) {
      console.error('Failed to load user data:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUserData();
  }, []);

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'inactive':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'banned':
        return <Ban className="h-4 w-4 text-red-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'bg-green-100 text-green-800';
      case 'inactive': return 'bg-yellow-100 text-yellow-800';
      case 'banned': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getRoleColor = (role: string) => {
    switch (role) {
      case 'admin': return 'bg-purple-100 text-purple-800';
      case 'moderator': return 'bg-blue-100 text-blue-800';
      case 'user': return 'bg-gray-100 text-gray-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.username.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         user.email.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesRole = !roleFilter || user.role === roleFilter;
    const matchesStatus = !statusFilter || user.status === statusFilter;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const formatRelativeTime = (dateString: string): string => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
        <span className="ml-2 text-muted-foreground">Loading user data...</span>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">User Management</h1>
          <p className="text-muted-foreground">
            Manage users, roles, permissions, and monitor activity
          </p>
        </div>
        <Button className="flex items-center gap-2">
          <UserPlus className="h-4 w-4" />
          Add User
        </Button>
      </div>

      {/* Stats Overview */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Total Users</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_users}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Users</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active_users}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">New Users (24h)</CardTitle>
              <UserPlus className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.new_users_24h}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Active Sessions</CardTitle>
              <Clock className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.active_sessions}</div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Queries (24h)</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{stats.total_queries_24h}</div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex gap-2">
        <Button
          variant={activeTab === 'users' ? 'default' : 'outline'}
          onClick={() => setActiveTab('users')}
          className="flex items-center gap-2"
        >
          <Users className="h-4 w-4" />
          Users
        </Button>
        <Button
          variant={activeTab === 'sessions' ? 'default' : 'outline'}
          onClick={() => setActiveTab('sessions')}
          className="flex items-center gap-2"
        >
          <Clock className="h-4 w-4" />
          Active Sessions
        </Button>
      </div>

      {activeTab === 'users' && (
        <>
          {/* Filters */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Filter className="h-5 w-5" />
                User Filters
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <Label htmlFor="search">Search Users</Label>
                  <div className="relative">
                    <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="search"
                      placeholder="Username or email..."
                      className="pl-8"
                      value={searchTerm}
                      onChange={(e) => setSearchTerm(e.target.value)}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="role-filter">Role</Label>
                  <Select value={roleFilter} onValueChange={setRoleFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All roles" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All Roles</SelectItem>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="moderator">Moderator</SelectItem>
                      <SelectItem value="user">User</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="status-filter">Status</Label>
                  <Select value={statusFilter} onValueChange={setStatusFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="All statuses" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="">All Statuses</SelectItem>
                      <SelectItem value="active">Active</SelectItem>
                      <SelectItem value="inactive">Inactive</SelectItem>
                      <SelectItem value="banned">Banned</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div className="flex items-end">
                  <Button onClick={loadUserData} disabled={loading} className="flex items-center gap-2">
                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                    Refresh
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Users List */}
          <Card>
            <CardHeader>
              <CardTitle>Users ({filteredUsers.length})</CardTitle>
            </CardHeader>
            <CardContent>
              <ScrollArea className="h-96">
                <div className="space-y-4">
                  {filteredUsers.map((user) => (
                    <div key={user.id} className="border rounded-lg p-4">
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex items-start gap-3">
                          <div className="mt-1">
                            {getStatusIcon(user.status)}
                          </div>
                          <div>
                            <div className="font-medium">{user.username}</div>
                            <div className="text-sm text-muted-foreground">{user.email}</div>
                            <div className="text-xs text-muted-foreground mt-1">
                              Last login: {formatRelativeTime(user.last_login)} •
                              Member since: {new Date(user.created_at).toLocaleDateString()}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge className={getRoleColor(user.role)}>
                            {user.role}
                          </Badge>
                          <Badge className={getStatusColor(user.status)}>
                            {user.status}
                          </Badge>
                        </div>
                      </div>

                      <div className="flex justify-between items-center text-sm text-muted-foreground mb-3">
                        <span>Sessions: {user.session_count}</span>
                        <span>Queries: {user.total_queries}</span>
                      </div>

                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="flex items-center gap-1">
                          <Eye className="h-3 w-3" />
                          View
                        </Button>
                        <Button size="sm" variant="outline" className="flex items-center gap-1">
                          <Edit className="h-3 w-3" />
                          Edit
                        </Button>
                        {user.status !== 'banned' && (
                          <Button size="sm" variant="outline" className="flex items-center gap-1 text-red-600">
                            <Ban className="h-3 w-3" />
                            Ban
                          </Button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </CardContent>
          </Card>
        </>
      )}

      {activeTab === 'sessions' && (
        <Card>
          <CardHeader>
            <CardTitle>Active Sessions ({sessions.length})</CardTitle>
            <CardDescription>Currently active user sessions</CardDescription>
          </CardHeader>
          <CardContent>
            <ScrollArea className="h-96">
              <div className="space-y-4">
                {sessions.map((session) => (
                  <div key={session.session_id} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div>
                        <div className="font-medium">{session.username}</div>
                        <div className="text-sm text-muted-foreground">
                          Session ID: {session.session_id}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          Started: {formatRelativeTime(session.started_at)} •
                          Last activity: {formatRelativeTime(session.last_activity)}
                        </div>
                      </div>
                      <Button size="sm" variant="outline" className="flex items-center gap-1 text-red-600">
                        <UserX className="h-3 w-3" />
                        End Session
                      </Button>
                    </div>

                    <div className="text-sm text-muted-foreground space-y-1">
                      <div>IP: {session.ip_address}</div>
                      <div>Queries in session: {session.query_count}</div>
                      <div className="truncate">User Agent: {session.user_agent}</div>
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>
      )}
    </div>
  );
}