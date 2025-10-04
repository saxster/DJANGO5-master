# Resumable Upload API Documentation

**Sprint 3 Implementation**: Chunked file upload system for large files with network resilience.

## Overview

The Resumable Upload API allows clients to upload large files in smaller chunks that can be uploaded independently and resumed after network interruptions. This is particularly useful for:

- **Large file uploads** (videos, high-resolution images, documents)
- **Poor network conditions** (mobile networks, unreliable connections)
- **Progress tracking** (real-time upload progress monitoring)
- **Bandwidth optimization** (pause/resume without starting over)

## Key Features

✅ **Chunked uploads** - Files split into 1MB chunks by default
✅ **Resume capability** - Continue from last successful chunk
✅ **24-hour session TTL** - Automatic cleanup of stale uploads
✅ **Security validation** - Full validation on reassembled file
✅ **Progress tracking** - Real-time progress monitoring
✅ **Out-of-order chunks** - Chunks can arrive in any order

## API Endpoints

Base URL: `/api/v1/upload/`

All endpoints require authentication via session or API key.

---

### 1. Initialize Upload Session

**Endpoint**: `POST /api/v1/upload/init`

Initialize a new upload session before uploading chunks.

#### Request

```json
{
  "filename": "large-file.jpg",
  "total_size": 52428800,
  "mime_type": "image/jpeg",
  "file_hash": "abc123def456...sha256hash"
}
```

**Parameters**:
- `filename` (string, required): Original filename
- `total_size` (integer, required): Total file size in bytes
- `mime_type` (string, required): MIME type of the file
- `file_hash` (string, required): SHA-256 hash of complete file for validation

#### Response

**Success (201 Created)**:
```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunk_size": 1048576,
  "total_chunks": 50,
  "expires_at": "2025-09-29T10:30:00Z"
}
```

**Error (400 Bad Request)**:
```json
{
  "error": "Invalid filename provided"
}
```

#### Example (cURL)

```bash
curl -X POST https://api.example.com/api/v1/upload/init \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{
    "filename": "video.mp4",
    "total_size": 104857600,
    "mime_type": "video/mp4",
    "file_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  }'
```

---

### 2. Upload Chunk

**Endpoint**: `POST /api/v1/upload/chunk`

Upload a single chunk of the file.

#### Request

```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000",
  "chunk_index": 0,
  "chunk_data": "base64_encoded_chunk_data",
  "checksum": "chunk_sha256_hash"
}
```

**Parameters**:
- `upload_id` (UUID, required): Session ID from init
- `chunk_index` (integer, required): Zero-based chunk index
- `chunk_data` (string, required): Base64-encoded chunk bytes
- `checksum` (string, required): SHA-256 hash of chunk for validation

#### Response

**Success (200 OK)**:
```json
{
  "progress": {
    "received_chunks": [0, 1, 2, 5, 7],
    "missing_chunks": [3, 4, 6, 8, 9],
    "progress_pct": 50
  }
}
```

**Error (400 Bad Request)**:
```json
{
  "error": "Chunk checksum mismatch"
}
```

#### Example (Python)

```python
import base64
import hashlib

chunk_data = file_content[0:1048576]  # First 1MB
chunk_hash = hashlib.sha256(chunk_data).hexdigest()
encoded_chunk = base64.b64encode(chunk_data).decode('utf-8')

response = requests.post(
    'https://api.example.com/api/v1/upload/chunk',
    headers={'Authorization': 'Bearer YOUR_TOKEN'},
    json={
        'upload_id': upload_id,
        'chunk_index': 0,
        'chunk_data': encoded_chunk,
        'checksum': chunk_hash
    }
)
```

---

### 3. Complete Upload

**Endpoint**: `POST /api/v1/upload/complete`

Finalize upload by reassembling and validating all chunks.

#### Request

```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Response

**Success (200 OK)**:
```json
{
  "file_path": "/media/uploads/resumable/large-file.jpg",
  "filename": "large-file.jpg",
  "size": 52428800,
  "upload_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Error (400 Bad Request)**:
```json
{
  "error": "Missing chunks: [3, 7, 12]"
}
```

#### Example (JavaScript)

```javascript
const response = await fetch('https://api.example.com/api/v1/upload/complete', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer YOUR_TOKEN'
  },
  body: JSON.stringify({
    upload_id: '550e8400-e29b-41d4-a716-446655440000'
  })
});

const result = await response.json();
console.log('Upload completed:', result.file_path);
```

---

### 4. Cancel Upload

**Endpoint**: `POST /api/v1/upload/cancel`

Cancel upload session and cleanup resources.

#### Request

```json
{
  "upload_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

#### Response

**Success (200 OK)**:
```json
{
  "status": "cancelled",
  "upload_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### 5. Get Upload Status

**Endpoint**: `GET /api/v1/upload/status/{upload_id}`

Query current status and progress of an upload session.

#### Response

**Success (200 OK)**:
```json
{
  "status": "active",
  "progress": {
    "received_chunks": [0, 1, 2, 3, 4],
    "missing_chunks": [5, 6, 7, 8, 9],
    "progress_pct": 50
  },
  "created_at": "2025-09-28T10:00:00Z",
  "expires_at": "2025-09-29T10:00:00Z",
  "is_expired": false
}
```

**Status values**:
- `active`: Accepting chunks
- `assembling`: Merging chunks into final file
- `completed`: Upload completed successfully
- `failed`: Upload failed with error
- `cancelled`: Upload cancelled by user
- `expired`: Session expired (24h TTL)

---

## Complete Upload Flow Example

### Python Client

```python
import os
import hashlib
import base64
import requests

def upload_file_resumable(file_path, api_url, auth_token):
    """Upload file using resumable upload API."""

    # Step 1: Calculate file hash and metadata
    with open(file_path, 'rb') as f:
        file_data = f.read()

    file_hash = hashlib.sha256(file_data).hexdigest()
    file_size = len(file_data)
    filename = os.path.basename(file_path)

    # Step 2: Initialize upload session
    init_response = requests.post(
        f'{api_url}/init',
        headers={'Authorization': f'Bearer {auth_token}'},
        json={
            'filename': filename,
            'total_size': file_size,
            'mime_type': 'image/jpeg',
            'file_hash': file_hash
        }
    )

    session = init_response.json()
    upload_id = session['upload_id']
    chunk_size = session['chunk_size']
    total_chunks = session['total_chunks']

    print(f"Upload session initialized: {upload_id}")
    print(f"Total chunks: {total_chunks}")

    # Step 3: Upload chunks
    for i in range(total_chunks):
        start = i * chunk_size
        end = min(start + chunk_size, file_size)
        chunk_data = file_data[start:end]

        chunk_hash = hashlib.sha256(chunk_data).hexdigest()
        encoded_chunk = base64.b64encode(chunk_data).decode('utf-8')

        chunk_response = requests.post(
            f'{api_url}/chunk',
            headers={'Authorization': f'Bearer {auth_token}'},
            json={
                'upload_id': upload_id,
                'chunk_index': i,
                'chunk_data': encoded_chunk,
                'checksum': chunk_hash
            }
        )

        progress = chunk_response.json()['progress']
        print(f"Chunk {i+1}/{total_chunks} uploaded ({progress['progress_pct']}%)")

    # Step 4: Complete upload
    complete_response = requests.post(
        f'{api_url}/complete',
        headers={'Authorization': f'Bearer {auth_token}'},
        json={'upload_id': upload_id}
    )

    result = complete_response.json()
    print(f"Upload completed: {result['file_path']}")
    return result

# Usage
result = upload_file_resumable(
    'large-video.mp4',
    'https://api.example.com/api/v1/upload',
    'your_auth_token'
)
```

---

## Error Handling

### Common Error Codes

| Status Code | Error | Description |
|-------------|-------|-------------|
| 400 | Invalid request data | Missing or malformed request parameters |
| 400 | Upload session expired | Session TTL exceeded (24 hours) |
| 400 | Chunk checksum mismatch | Chunk data corrupted during transmission |
| 400 | Invalid chunk index | Chunk index out of range |
| 400 | Missing chunks | Not all chunks uploaded before complete |
| 400 | Final file hash mismatch | Reassembled file doesn't match expected hash |
| 403 | Unauthorized | Wrong user trying to access session |
| 404 | Upload session not found | Invalid upload_id |

### Retry Strategy

```python
def upload_chunk_with_retry(upload_id, chunk_index, chunk_data, max_retries=3):
    """Upload chunk with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            response = upload_chunk(upload_id, chunk_index, chunk_data)
            return response
        except requests.exceptions.RequestException as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
```

---

## Security Considerations

1. **Authentication Required**: All endpoints require valid session or API key
2. **User Isolation**: Users can only access their own upload sessions
3. **File Validation**: Full security validation on reassembled file
4. **Hash Verification**: Both chunk-level and file-level hash validation
5. **Size Limits**: Enforced based on file type (images: 5MB, PDFs/docs: 10MB)
6. **MIME Type Validation**: Content type verified against file headers
7. **Magic Number Check**: File content validated using magic bytes

---

## Rate Limiting

- **Init endpoint**: 10 requests per minute per user
- **Chunk endpoint**: 100 requests per minute per user
- **Complete endpoint**: 5 requests per minute per user

---

## Cleanup and Maintenance

### Automatic Cleanup

Upload sessions are automatically cleaned up:
- **Expired sessions**: 24 hours after creation
- **Completed uploads**: 24 hours after completion
- **Failed uploads**: 24 hours after failure

### Manual Cleanup Command

```bash
# Cleanup expired sessions (default: 24 hours)
python manage.py cleanup_expired_uploads

# Cleanup with custom TTL
python manage.py cleanup_expired_uploads --hours=48

# Dry run (see what would be deleted)
python manage.py cleanup_expired_uploads --dry-run --verbose
```

### Cron Job Setup

```cron
# Run cleanup every hour
0 * * * * /path/to/venv/bin/python /path/to/manage.py cleanup_expired_uploads
```

---

## Performance Optimization

### Client-Side Best Practices

1. **Parallel chunk uploads**: Upload 3-5 chunks concurrently
2. **Resume on failure**: Track completed chunks, only retry failed ones
3. **Adaptive chunk size**: Increase chunk size on fast networks
4. **Progress persistence**: Save progress locally for browser refresh

### Server-Side Optimizations

- Temporary files stored in fast local storage
- Database queries optimized with `select_for_update()`
- Chunk validation runs in parallel with write
- Background task for file reassembly

---

## Monitoring and Metrics

Track these metrics for operational health:

- **Upload session success rate**: % of sessions that complete successfully
- **Average upload time**: Time from init to complete
- **Chunk retry rate**: % of chunks that require retries
- **Session expiration rate**: % of sessions that expire before completion
- **Storage cleanup efficiency**: Temp storage freed per cleanup run

---

## Support and Troubleshooting

### Common Issues

**Q: Upload stuck at 99%**
A: Check for missing chunks via status endpoint. Re-upload missing chunks.

**Q: "Session expired" error**
A: Sessions expire after 24 hours. Start new session and re-upload.

**Q: "Hash mismatch" on complete**
A: File corrupted during transmission. Cancel and restart upload.

**Q: Slow upload speed**
A: Try uploading 3-5 chunks in parallel. Increase chunk size if bandwidth allows.

---

## Changelog

### Version 1.0.0 (Sprint 3 - 2025-09)
- Initial release
- Chunked upload support
- 24-hour session TTL
- Automatic cleanup
- Comprehensive security validation