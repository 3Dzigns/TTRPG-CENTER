/**
 * HGRN Review Component
 *
 * Human Generated Review Notes interface for approving/rejecting content
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  RefreshCw,
  Search,
  Filter,
  User,
  Calendar
} from 'lucide-react';

interface HGRNAction {
  id: string;
  item_type: string;
  item_id: string;
  action: 'approve' | 'reject' | 'request_changes' | 'defer';
  reviewer: string;
  notes: string;
  metadata: Record<string, any>;
  created_at: string;
  expires_at?: string;
}

interface HGRNActionCreate {
  item_type: string;
  item_id: string;
  action: 'approve' | 'reject' | 'request_changes' | 'defer';
  reviewer: string;
  notes: string;
  metadata?: Record<string, any>;
  expires_at?: string;
}

export default function HGRNReview() {
  const [actions, setActions] = useState<HGRNAction[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterType, setFilterType] = useState<string>('');
  const [filterAction, setFilterAction] = useState<string>('');

  // New review form
  const [showReviewForm, setShowReviewForm] = useState(false);
  const [reviewForm, setReviewForm] = useState<Partial<HGRNActionCreate>>({
    item_type: '',
    item_id: '',
    action: 'approve',
    reviewer: '',
    notes: '',
    metadata: {}
  });

  useEffect(() => {
    loadHGRNActions();
  }, []);

  const loadHGRNActions = async () => {
    setLoading(true);
    try {
      const adminApiUrl = getAdminApiUrl();
      const params = new URLSearchParams();

      if (filterType) params.append('item_type', filterType);
      if (filterAction) params.append('action', filterAction);
      if (searchTerm) params.append('item_id', searchTerm);

      const response = await fetch(`${adminApiUrl}/hgrn/actions?${params.toString()}`);
      if (response.ok) {
        const data = await response.json();
        setActions(data);
      }
    } catch (error) {
      console.error('Failed to load HGRN actions:', error);
    } finally {
      setLoading(false);
    }
  };

  const submitReview = async () => {
    if (!reviewForm.item_type || !reviewForm.item_id || !reviewForm.reviewer || !reviewForm.notes) {
      alert('Please fill in all required fields');
      return;
    }

    try {
      const adminApiUrl = getAdminApiUrl();
      const response = await fetch(`${adminApiUrl}/hgrn/actions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(reviewForm)
      });

      if (response.ok) {
        setShowReviewForm(false);
        setReviewForm({
          item_type: '',
          item_id: '',
          action: 'approve',
          reviewer: '',
          notes: '',
          metadata: {}
        });
        loadHGRNActions();
      } else {
        const error = await response.json();
        alert(`Failed to submit review: ${error.detail || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to submit review:', error);
      alert('Failed to submit review');
    }
  };

  const getActionIcon = (action: string) => {
    switch (action) {
      case 'approve':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'reject':
        return <XCircle className="h-4 w-4 text-red-500" />;
      case 'request_changes':
        return <AlertCircle className="h-4 w-4 text-yellow-500" />;
      case 'defer':
        return <Clock className="h-4 w-4 text-blue-500" />;
      default:
        return <Clock className="h-4 w-4 text-gray-500" />;
    }
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'approve': return 'bg-green-100 text-green-800';
      case 'reject': return 'bg-red-100 text-red-800';
      case 'request_changes': return 'bg-yellow-100 text-yellow-800';
      case 'defer': return 'bg-blue-100 text-blue-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  const getAdminApiUrl = (): string => {
    const currentEnv = process.env.NODE_ENV || 'development';
    const portMap = {
      development: 8001,
      test: 8182,
      production: 8283
    };
    const port = portMap[currentEnv] || 8001;
    return `http://localhost:${port}`;
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">HGRN Review</h1>
          <p className="text-muted-foreground">
            Human Generated Review Notes for content approval and quality control
          </p>
        </div>
        <Button onClick={() => setShowReviewForm(!showReviewForm)}>
          {showReviewForm ? 'Cancel' : 'New Review'}
        </Button>
      </div>

      {/* New Review Form */}
      {showReviewForm && (
        <Card>
          <CardHeader>
            <CardTitle>Submit New Review</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="item-type">Item Type</Label>
                <Select
                  value={reviewForm.item_type}
                  onValueChange={(value) => setReviewForm(prev => ({ ...prev, item_type: value }))}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="Select item type" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="job">Ingestion Job</SelectItem>
                    <SelectItem value="entry">Dictionary Entry</SelectItem>
                    <SelectItem value="chunk">Content Chunk</SelectItem>
                    <SelectItem value="artifact">Test Artifact</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="item-id">Item ID</Label>
                <Input
                  id="item-id"
                  placeholder="e.g., job_123, entry_456"
                  value={reviewForm.item_id}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, item_id: e.target.value }))}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="action">Action</Label>
                <Select
                  value={reviewForm.action}
                  onValueChange={(value: any) => setReviewForm(prev => ({ ...prev, action: value }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="approve">Approve</SelectItem>
                    <SelectItem value="reject">Reject</SelectItem>
                    <SelectItem value="request_changes">Request Changes</SelectItem>
                    <SelectItem value="defer">Defer</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="space-y-2">
                <Label htmlFor="reviewer">Reviewer</Label>
                <Input
                  id="reviewer"
                  placeholder="Reviewer name or ID"
                  value={reviewForm.reviewer}
                  onChange={(e) => setReviewForm(prev => ({ ...prev, reviewer: e.target.value }))}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="notes">Review Notes</Label>
              <textarea
                id="notes"
                className="w-full min-h-[100px] p-3 border rounded-md"
                placeholder="Detailed review notes and feedback..."
                value={reviewForm.notes}
                onChange={(e) => setReviewForm(prev => ({ ...prev, notes: e.target.value }))}
              />
            </div>

            <div className="flex gap-2">
              <Button onClick={submitReview}>Submit Review</Button>
              <Button variant="outline" onClick={() => setShowReviewForm(false)}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Filter className="h-5 w-5" />
            Filters & Search
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="space-y-2">
              <Label htmlFor="search">Search Item ID</Label>
              <div className="relative">
                <Search className="absolute left-2 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  id="search"
                  placeholder="Search..."
                  className="pl-8"
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="filter-type">Item Type</Label>
              <Select value={filterType} onValueChange={setFilterType}>
                <SelectTrigger>
                  <SelectValue placeholder="All types" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Types</SelectItem>
                  <SelectItem value="job">Jobs</SelectItem>
                  <SelectItem value="entry">Entries</SelectItem>
                  <SelectItem value="chunk">Chunks</SelectItem>
                  <SelectItem value="artifact">Artifacts</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="filter-action">Action</Label>
              <Select value={filterAction} onValueChange={setFilterAction}>
                <SelectTrigger>
                  <SelectValue placeholder="All actions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="">All Actions</SelectItem>
                  <SelectItem value="approve">Approved</SelectItem>
                  <SelectItem value="reject">Rejected</SelectItem>
                  <SelectItem value="request_changes">Changes Requested</SelectItem>
                  <SelectItem value="defer">Deferred</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="flex items-end">
              <Button onClick={loadHGRNActions} disabled={loading} className="flex items-center gap-2">
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                {loading ? 'Loading...' : 'Apply Filters'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Review Actions List */}
      <Card>
        <CardHeader>
          <CardTitle>Review History</CardTitle>
        </CardHeader>
        <CardContent>
          <ScrollArea className="max-h-[600px]">
            <div className="space-y-4">
              {actions.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No review actions found. Try adjusting your filters or submit a new review.
                </p>
              ) : (
                actions.map((action) => (
                  <div key={action.id} className="border rounded-lg p-4">
                    <div className="flex items-start justify-between mb-3">
                      <div className="flex items-start gap-3">
                        {getActionIcon(action.action)}
                        <div>
                          <div className="font-medium">
                            {action.item_type}: {action.item_id}
                          </div>
                          <div className="text-sm text-muted-foreground flex items-center gap-4">
                            <span className="flex items-center gap-1">
                              <User className="h-3 w-3" />
                              {action.reviewer}
                            </span>
                            <span className="flex items-center gap-1">
                              <Calendar className="h-3 w-3" />
                              {new Date(action.created_at).toLocaleString()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <Badge className={getActionColor(action.action)}>
                        {action.action.replace('_', ' ')}
                      </Badge>
                    </div>

                    <div className="bg-gray-50 rounded-md p-3 mb-3">
                      <div className="text-sm font-medium mb-1">Review Notes:</div>
                      <div className="text-sm">{action.notes}</div>
                    </div>

                    {Object.keys(action.metadata).length > 0 && (
                      <div className="text-xs text-muted-foreground">
                        <div className="font-medium mb-1">Metadata:</div>
                        <pre className="text-xs overflow-x-auto">
                          {JSON.stringify(action.metadata, null, 2)}
                        </pre>
                      </div>
                    )}

                    {action.expires_at && (
                      <div className="text-xs text-muted-foreground mt-2">
                        Expires: {new Date(action.expires_at).toLocaleString()}
                      </div>
                    )}
                  </div>
                ))
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}