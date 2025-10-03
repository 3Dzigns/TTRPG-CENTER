/**
 * Upload Manager Component
 *
 * Handles document upload to the Ingest Service (port 8003)
 * Provides file upload, job tracking, and progress monitoring
 */

import { useState, useRef, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Upload, FileText, Clock, CheckCircle, XCircle, AlertCircle, AlertTriangle, RefreshCw } from 'lucide-react';

interface UploadJob {
  job_id: string;
  filename: string;
  status: string;
  progress: number;
  current_pass?: string;
  created_at: string;
  size_mb?: number;
  estimated_duration_seconds?: number;
}

interface UploadResponse {
  job_id: string;
  status: string;
  message: string;
  estimated_duration_seconds?: number;
}

export default function UploadManager() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadJobs, setUploadJobs] = useState<UploadJob[]>([]);
  const [dragActive, setDragActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [isLoadingJobs, setIsLoadingJobs] = useState(true);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const getIngestApiUrl = (): string => {
    const currentEnv = process.env.NODE_ENV || 'development';

    // Check if we're running in a containerized environment (Admin UI served from nginx)
    const isContainerized = window.location.port === '3000';

    if (isContainerized) {
      // Use nginx proxy path for containerized deployment
      return '/api/ingest';
    }

    // For local development (Vite dev server)
    const portMap: Record<string, number> = {
      development: 8003,
      test: 8184,
      production: 8283
    };
    const port = portMap[currentEnv] || 8003;
    return `http://localhost:${port}`;
  };

  const handleFileSelect = (file: File) => {
    // Clear previous messages when selecting a new file
    setError(null);
    setSuccessMessage(null);

    if (file.type === 'application/pdf' || file.name.toLowerCase().endsWith('.pdf')) {
      setSelectedFile(file);
    } else {
      setError('Please select a PDF file. Only PDF files are supported for upload.');
    }
  };

  const retryUpload = () => {
    if (selectedFile) {
      uploadFile();
    }
  };

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragActive(false);

    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const uploadFile = async () => {
    if (!selectedFile) return;

    // Clear previous messages
    setError(null);
    setSuccessMessage(null);
    setIsUploading(true);

    try {
      // Client-side validation
      const maxSizeBytes = 500 * 1024 * 1024; // 500MB
      if (selectedFile.size > maxSizeBytes) {
        throw new Error(`File size (${Math.round(selectedFile.size / (1024 * 1024))}MB) exceeds the 500MB limit`);
      }

      const formData = new FormData();
      formData.append('file', selectedFile);

      const ingestApiUrl = getIngestApiUrl();
      console.log('Uploading to:', `${ingestApiUrl}/ingest/upload`);

      const response = await fetch(`${ingestApiUrl}/ingest/upload`, {
        method: 'POST',
        headers: {
          // For development, we'll use a placeholder token
          // In production, this would come from user authentication
          'Authorization': 'Bearer dev-token'
        },
        body: formData
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Upload failed (${response.status}): ${response.statusText}${errorText ? ` - ${errorText}` : ''}`);
      }

      const result: UploadResponse = await response.json();

      // Add to upload jobs list
      const newJob: UploadJob = {
        job_id: result.job_id,
        filename: selectedFile.name,
        status: result.status,
        progress: 0,
        created_at: new Date().toISOString(),
        size_mb: Math.round((selectedFile.size / (1024 * 1024)) * 100) / 100,
        estimated_duration_seconds: result.estimated_duration_seconds
      };

      setUploadJobs(prev => [newJob, ...prev]);
      setSelectedFile(null);

      // Show success message
      const estimatedTime = result.estimated_duration_seconds
        ? ` (estimated ${Math.round(result.estimated_duration_seconds / 60)} minutes)`
        : '';
      setSuccessMessage(`Upload successful! Job ${result.job_id} created${estimatedTime}`);

      // Auto-dismiss success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000);

      // Start polling for job status
      pollJobStatus(result.job_id);

    } catch (error) {
      console.error('Upload failed:', error);
      setError(`Upload failed: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsUploading(false);
    }
  };

  const pollJobStatus = async (jobId: string) => {
    try {
      const ingestApiUrl = getIngestApiUrl();
      const response = await fetch(`${ingestApiUrl}/ingest/jobs/${jobId}`, {
        headers: {
          'Authorization': 'Bearer dev-token'
        }
      });

      if (response.ok) {
        const jobStatus = await response.json();

        setUploadJobs(prev =>
          prev.map(job =>
            job.job_id === jobId
              ? { ...job, ...jobStatus }
              : job
          )
        );

        // Continue polling if job is still running
        if (jobStatus.status === 'processing' || jobStatus.status === 'queued') {
          setTimeout(() => pollJobStatus(jobId), 2000);
        }
      }
    } catch (error) {
      console.error('Failed to poll job status:', error);
    }
  };

  const loadUploadJobs = async () => {
    try {
      const ingestApiUrl = getIngestApiUrl();
      const response = await fetch(`${ingestApiUrl}/ingest/jobs`, {
        headers: {
          'Authorization': 'Bearer dev-token'
        }
      });

      if (response.ok) {
        const jobs = await response.json();
        setUploadJobs(jobs.map((job: any) => ({
          ...job,
          filename: job.filename || 'Unknown file'
        })));
      }
    } catch (error) {
      console.error('Failed to load jobs:', error);
      setError(`Failed to load jobs: ${error instanceof Error ? error.message : 'Unknown error'}`);
    } finally {
      setIsLoadingJobs(false);
    }
  };

  const getStatusBadge = (status: string) => {
    const variants: Record<string, any> = {
      queued: 'secondary',
      processing: 'default',
      completed: 'success',
      failed: 'destructive',
      skipped: 'secondary'
    };

    const icons: Record<string, React.ReactElement> = {
      queued: <Clock className="h-3 w-3" />,
      processing: <AlertCircle className="h-3 w-3" />,
      completed: <CheckCircle className="h-3 w-3" />,
      failed: <XCircle className="h-3 w-3" />,
      skipped: <AlertCircle className="h-3 w-3" />
    };

    return (
      <Badge variant={variants[status] || 'secondary'} className="flex items-center gap-1">
        {icons[status]}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Badge>
    );
  };

  // Load jobs on component mount
  useEffect(() => {
    loadUploadJobs();
  }, []);

  return (
    <div className="space-y-6">
      {/* Upload Section */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Upload className="h-5 w-5" />
            Document Upload
          </CardTitle>
          <CardDescription>
            Upload PDF documents for processing through the ingestion pipeline
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Error Alert */}
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Upload Error</AlertTitle>
              <AlertDescription className="flex items-center justify-between">
                <span>{error}</span>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={retryUpload}
                  disabled={!selectedFile || isUploading}
                  className="ml-4"
                >
                  <RefreshCw className="h-3 w-3 mr-1" />
                  Retry
                </Button>
              </AlertDescription>
            </Alert>
          )}

          {/* Success Alert */}
          {successMessage && (
            <Alert variant="success">
              <CheckCircle className="h-4 w-4" />
              <AlertTitle>Upload Successful</AlertTitle>
              <AlertDescription>{successMessage}</AlertDescription>
            </Alert>
          )}

          {/* File Drop Zone */}
          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center transition-colors ${
              dragActive
                ? 'border-primary bg-primary/5'
                : 'border-muted-foreground/25 hover:border-muted-foreground/50'
            }`}
            onDragEnter={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={(e) => { e.preventDefault(); setDragActive(false); }}
            onDragOver={(e) => e.preventDefault()}
            onDrop={handleFileDrop}
          >
            <FileText className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
            <p className="text-lg font-medium">
              {selectedFile ? selectedFile.name : 'Drop PDF file here or click to browse'}
            </p>
            <p className="text-sm text-muted-foreground mt-2">
              {selectedFile
                ? `Size: ${Math.round((selectedFile.size / (1024 * 1024)) * 100) / 100} MB`
                : 'Supports PDF files up to 500MB'
              }
            </p>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,application/pdf"
              onChange={handleFileInputChange}
              className="hidden"
            />

            <Button
              onClick={() => fileInputRef.current?.click()}
              variant="outline"
              className="mt-4"
            >
              Browse Files
            </Button>
          </div>

          {/* Upload Button */}
          {selectedFile && (
            <div className="flex gap-2">
              <Button
                onClick={uploadFile}
                disabled={isUploading}
                className="flex-1 flex items-center gap-2"
              >
                {isUploading && <RefreshCw className="h-4 w-4 animate-spin" />}
                {isUploading ? 'Uploading...' : 'Upload Document'}
              </Button>
              <Button
                variant="outline"
                onClick={() => {
                  setSelectedFile(null);
                  setError(null);
                  setSuccessMessage(null);
                }}
                disabled={isUploading}
              >
                Clear
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Jobs List */}
      <Card>
        <CardHeader>
          <div className="flex justify-between items-center">
            <div>
              <CardTitle>Upload Jobs</CardTitle>
              <CardDescription>Track document processing progress</CardDescription>
            </div>
            <Button variant="outline" onClick={loadUploadJobs}>
              Refresh
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <ScrollArea className="h-96">
            {uploadJobs.length === 0 ? (
              <p className="text-center text-muted-foreground py-8">
                No upload jobs found
              </p>
            ) : (
              <div className="space-y-4">
                {uploadJobs.map((job) => (
                  <div key={job.job_id} className="border rounded-lg p-4">
                    <div className="flex justify-between items-start mb-2">
                      <div>
                        <h4 className="font-medium">{job.filename}</h4>
                        <p className="text-sm text-muted-foreground">
                          Job ID: {job.job_id}
                        </p>
                      </div>
                      {getStatusBadge(job.status)}
                    </div>

                    {job.progress > 0 && job.progress < 1 && (
                      <div className="mb-2">
                        <div className="flex justify-between text-sm mb-1">
                          <span>Progress</span>
                          <span>{Math.round(job.progress * 100)}%</span>
                        </div>
                        <div className="w-full bg-secondary rounded-full h-2">
                          <div
                            className="bg-primary h-2 rounded-full transition-all"
                            style={{ width: `${job.progress * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {job.current_pass && (
                      <p className="text-sm text-muted-foreground">
                        Current: {job.current_pass}
                      </p>
                    )}

                    <div className="flex justify-between text-xs text-muted-foreground mt-2">
                      <span>
                        {job.size_mb && `${job.size_mb} MB`}
                      </span>
                      <span>
                        {new Date(job.created_at).toLocaleString()}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}