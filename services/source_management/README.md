# Source Management Service

🔒 **STATUS: LOCKED - PRODUCTION READY** (See `LOCKED.md` for change management)

A FastAPI microservice for managing document sources in the TTRPG Center application.

**Last Verified:** 2025-09-30
**Service Status:** ✅ HEALTHY & FUNCTIONAL
**Upload Methods:** ✅ Browse Button + Drag-and-Drop Working

## Overview

The Source Management service provides centralized document operations including:

- **Upload Management**: Secure file uploads with validation
- **Document Storage**: Organized file storage with metadata
- **File Operations**: List, view, and delete operations
- **Multi-Environment**: Support for dev/test/prod environments
- **Validation**: Content type, size, and safety validation

## API Endpoints

### Core Operations

- `GET /api/sources` - List all documents with metadata
- `POST /api/sources/upload` - Upload one or more documents
- `GET /api/sources/{filename}` - Get document information
- `GET /api/sources/{filename}/download` - Download document
- `DELETE /api/sources/{filename}` - Delete single document
- `DELETE /api/sources` - Delete multiple documents (bulk)

### System Operations

- `GET /healthz` - Service health check
- `GET /api/sources/stats` - Storage statistics and system info

## Configuration

### Environment Variables

- `TARGET_ENV`: Target environment (dev/test/prod)
- `SERVICE_NAME`: Service name (source_management)
- `PORT`: Service port (default: 8005)

### File Validation

Environment-specific validation rules:

**Development (`dev`)**:
- Max file size: 100MB
- Allowed types: PDF, TXT, MD, JSON, XML, DOCX, JPG, PNG

**Test (`test`)**:
- Max file size: 50MB
- Allowed types: PDF, TXT, MD, JSON, XML

**Production (`prod`)**:
- Max file size: 25MB
- Allowed types: PDF only

## Storage Structure

```
/app/env/{environment}/uploads/
├── document1.pdf
├── document2.txt
└── ...
```

## Security Features

- **Filename Sanitization**: Prevents directory traversal attacks
- **Content Validation**: MIME type and extension checking
- **Size Limits**: Configurable per environment
- **Safe Operations**: All file operations use sanitized paths

## Docker Integration

The service runs as a container with:

- **Port**: 8005
- **Volumes**: Mounted upload directories
- **Health Checks**: Built-in health monitoring
- **Logging**: Structured logging to stdout

## Usage Examples

### Upload Files
```bash
curl -X POST "http://localhost:8005/api/sources/upload" \
  -F "files=@document.pdf" \
  -F "env=dev" \
  -F "overwrite=false"
```

### List Documents
```bash
curl "http://localhost:8005/api/sources?env=dev&limit=10"
```

### Delete Document
```bash
curl -X DELETE "http://localhost:8005/api/sources/document.pdf?env=dev"
```

### Health Check
```bash
curl "http://localhost:8005/healthz"
```

## Development

### Running Locally
```bash
cd services/source_management
python -m uvicorn api:app --host 0.0.0.0 --port 8005 --reload
```

### Testing
```bash
# Run service tests
pytest tests/

# Test specific functionality
pytest tests/test_upload.py -v
```

## Monitoring

The service provides:

- **Health Checks**: `/healthz` endpoint with detailed status
- **Metrics**: Storage usage and file statistics
- **Logging**: Structured JSON logging
- **Error Tracking**: Detailed error messages and codes

## Error Handling

Common error responses:

- `400 Bad Request`: Invalid file or validation error
- `404 Not Found`: Document not found
- `409 Conflict`: File already exists (when overwrite=false)
- `413 Payload Too Large`: File exceeds size limit
- `415 Unsupported Media Type`: Invalid file type
- `500 Internal Server Error`: System or storage error

## Integration

### With Admin UI
The Admin UI consumes this service through:
- Upload forms and drag-and-drop
- Document listing and management
- Progress indicators and feedback

### With Other Services
- **Ingest Service**: Processes uploaded documents
- **Admin API**: Coordinates operations
- **Orchestrator**: Workflow management