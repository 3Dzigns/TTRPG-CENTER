/**
 * Artifact Viewer Component
 *
 * Browse and download test artifacts and reports
 */

import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Download,
  FileText,
  Image,
  Archive,
  Eye,
  RefreshCw,
  Folder
} from 'lucide-react';

interface ArtifactFile {
  name: string;
  size_bytes: number;
  modified_at: string;
  content_type?: string;
  checksum?: string;
}

interface ArtifactInfo {
  job_id: string;
  created_at: string;
  size_bytes: number;
  manifest_available: boolean;
  files: ArtifactFile[];
  status: string;
  environment: string;
}

interface ArtifactViewerProps {
  selectedExecutionId?: string;
}

export default function ArtifactViewer({ selectedExecutionId }: ArtifactViewerProps) {
  const [artifacts, setArtifacts] = useState<ArtifactInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactInfo | null>(null);

  useEffect(() => {
    loadArtifacts();
  }, [selectedExecutionId]);

  const loadArtifacts = async () => {
    setLoading(true);
    try {
      const adminApiUrl = getAdminApiUrl();
      const url = selectedExecutionId
        ? `${adminApiUrl}/artifacts?job_id=${selectedExecutionId}`
        : `${adminApiUrl}/artifacts`;

      const response = await fetch(url);
      if (response.ok) {
        const data = await response.json();
        setArtifacts(Array.isArray(data) ? data : [data]);
      }
    } catch (error) {
      console.error('Failed to load artifacts:', error);
    } finally {
      setLoading(false);
    }
  };

  const downloadArtifact = async (jobId: string, fileName?: string) => {
    try {
      const adminApiUrl = getAdminApiUrl();
      const url = fileName
        ? `${adminApiUrl}/artifacts/${jobId}/files/${fileName}`
        : `${adminApiUrl}/artifacts/${jobId}/download`;

      const response = await fetch(url);
      if (response.ok) {
        const blob = await response.blob();
        const downloadUrl = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = fileName || `artifacts-${jobId}.zip`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(downloadUrl);
        document.body.removeChild(a);
      }
    } catch (error) {
      console.error('Failed to download artifact:', error);
    }
  };

  const getFileIcon = (fileName: string, contentType?: string) => {
    const extension = fileName.split('.').pop()?.toLowerCase();

    if (contentType?.startsWith('image/') || ['png', 'jpg', 'jpeg', 'gif', 'svg'].includes(extension || '')) {
      return <Image className="h-4 w-4 text-blue-500" />;
    }

    if (['zip', 'tar', 'gz', 'rar'].includes(extension || '')) {
      return <Archive className="h-4 w-4 text-orange-500" />;
    }

    return <FileText className="h-4 w-4 text-gray-500" />;
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Folder className="h-5 w-5" />
              Test Artifacts
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={loadArtifacts}
              disabled={loading}
              className="flex items-center gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex justify-center py-8">
              <RefreshCw className="h-6 w-6 animate-spin" />
            </div>
          ) : artifacts.length === 0 ? (
            <p className="text-muted-foreground text-center py-8">
              No test artifacts found.
            </p>
          ) : (
            <div className="space-y-4">
              {artifacts.map((artifact) => (
                <div key={artifact.job_id} className="border rounded-lg p-4">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <div className="font-medium">Job: {artifact.job_id.slice(0, 16)}...</div>
                      <div className="text-sm text-muted-foreground">
                        {artifact.environment} • {new Date(artifact.created_at).toLocaleString()} • {formatFileSize(artifact.size_bytes)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant={artifact.status === 'available' ? 'default' : 'secondary'}>
                        {artifact.status}
                      </Badge>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => downloadArtifact(artifact.job_id)}
                        className="flex items-center gap-1"
                      >
                        <Download className="h-3 w-3" />
                        Download All
                      </Button>
                    </div>
                  </div>

                  {artifact.files.length > 0 && (
                    <div className="space-y-2">
                      <div className="text-sm font-medium text-muted-foreground">
                        Files ({artifact.files.length})
                      </div>
                      <ScrollArea className="max-h-40">
                        <div className="space-y-1">
                          {artifact.files.map((file, index) => (
                            <div key={index} className="flex items-center justify-between p-2 hover:bg-gray-50 rounded">
                              <div className="flex items-center gap-2">
                                {getFileIcon(file.name, file.content_type)}
                                <div>
                                  <div className="text-sm font-medium">{file.name}</div>
                                  <div className="text-xs text-muted-foreground">
                                    {formatFileSize(file.size_bytes)} • {new Date(file.modified_at).toLocaleString()}
                                  </div>
                                </div>
                              </div>
                              <div className="flex gap-1">
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => downloadArtifact(artifact.job_id, file.name)}
                                  className="h-8 w-8 p-0"
                                >
                                  <Download className="h-3 w-3" />
                                </Button>
                              </div>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}