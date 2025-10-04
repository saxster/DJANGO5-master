# Sprint 3: Resumable Uploads - Quick Reference

## 🚀 Quick Start (5 minutes)

### 1. Apply Migration
```bash
python manage.py migrate core
```

### 2. Add URLs to `intelliwiz_config/urls.py`
```python
path('api/v1/upload/', include('apps.core.urls_resumable_uploads')),
```

### 3. Test the API
```bash
# Run tests
pytest apps/core/tests/test_resumable_uploads.py -v

# Upload a test file
curl -X POST https://api.example.com/api/v1/upload/init \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -d '{"filename":"test.jpg","total_size":1024,"mime_type":"image/jpeg","file_hash":"abc123"}'
```

---

## 📡 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/v1/upload/init` | Initialize upload session |
| POST | `/api/v1/upload/chunk` | Upload a chunk |
| POST | `/api/v1/upload/complete` | Complete and assemble file |
| POST | `/api/v1/upload/cancel` | Cancel upload |
| GET | `/api/v1/upload/status/:id` | Get upload status |

---

## 💻 Python Client Example

```python
import hashlib, base64, requests

# Initialize
file_hash = hashlib.sha256(file_data).hexdigest()
session = requests.post(f'{api_url}/init', json={
    'filename': 'file.jpg',
    'total_size': len(file_data),
    'mime_type': 'image/jpeg',
    'file_hash': file_hash
}).json()

# Upload chunks
for i in range(session['total_chunks']):
    chunk = file_data[i*chunk_size:(i+1)*chunk_size]
    requests.post(f'{api_url}/chunk', json={
        'upload_id': session['upload_id'],
        'chunk_index': i,
        'chunk_data': base64.b64encode(chunk).decode(),
        'checksum': hashlib.sha256(chunk).hexdigest()
    })

# Complete
result = requests.post(f'{api_url}/complete', json={
    'upload_id': session['upload_id']
}).json()
```

---

## 🌐 JavaScript Client (Browser)

```javascript
// Include the client library
<script src="/static/js/resumable-upload-client.js"></script>

// Upload file
const uploader = new ResumableUploader({
  apiUrl: 'https://api.example.com/api/v1/upload',
  authToken: 'your_token'
});

await uploader.uploadFile(file, {
  onProgress: (pct) => console.log(`${pct}% done`),
  onComplete: (result) => console.log('Done!', result)
});
```

---

## ⚛️ React Integration

```jsx
import { useState } from 'react';

function FileUpload() {
  const [progress, setProgress] = useState(0);

  const handleUpload = async (file) => {
    const uploader = new ResumableUploader({
      apiUrl: '/api/v1/upload',
      authToken: getAuthToken()
    });

    await uploader.uploadFile(file, {
      onProgress: setProgress,
      onComplete: (result) => alert('Upload complete!')
    });
  };

  return (
    <div>
      <input type="file" onChange={(e) => handleUpload(e.target.files[0])} />
      {progress > 0 && <progress value={progress} max="100" />}
    </div>
  );
}
```

---

## 🔄 Resume Interrupted Upload

```python
# Get session status
status = requests.get(f'{api_url}/status/{upload_id}').json()

# Re-upload only missing chunks
for chunk_index in status['progress']['missing_chunks']:
    chunk = file_data[chunk_index*chunk_size:(chunk_index+1)*chunk_size]
    requests.post(f'{api_url}/chunk', json={
        'upload_id': upload_id,
        'chunk_index': chunk_index,
        'chunk_data': base64.b64encode(chunk).decode(),
        'checksum': hashlib.sha256(chunk).hexdigest()
    })

# Complete
requests.post(f'{api_url}/complete', json={'upload_id': upload_id})
```

---

## 🧹 Cleanup Automation

```bash
# Manual cleanup
python manage.py cleanup_expired_uploads --verbose

# Add to crontab (runs hourly)
crontab -e
0 * * * * /path/to/venv/bin/python /path/to/manage.py cleanup_expired_uploads
```

---

## 🔍 Monitoring & Debugging

```python
# Check session status
from apps.core.models.upload_session import UploadSession

session = UploadSession.objects.get(upload_id='...')
print(f"Status: {session.status}")
print(f"Progress: {session.progress_percentage}%")
print(f"Missing chunks: {session.missing_chunks}")
print(f"Expired: {session.is_expired}")
```

---

## ⚠️ Common Issues

**Q: Upload stuck at 99%**
```python
# Check for missing chunks
status = requests.get(f'/api/v1/upload/status/{upload_id}').json()
print(status['progress']['missing_chunks'])  # Re-upload these
```

**Q: "Session expired" error**
- Sessions expire after 24 hours
- Start a new session and re-upload

**Q: "Hash mismatch" on complete**
- File corrupted during transmission
- Cancel and restart upload

---

## 📊 Testing

```bash
# Run all tests
pytest apps/core/tests/test_resumable_uploads.py -v

# Run unit tests only
pytest apps/core/tests/test_resumable_uploads.py -m unit -v

# With coverage
pytest apps/core/tests/test_resumable_uploads.py --cov=apps.core --cov-report=html
```

---

## 🔒 Security Notes

- ✅ All endpoints require authentication
- ✅ Users can only access own sessions
- ✅ SHA-256 validation at chunk + file level
- ✅ MIME type + magic number validation
- ✅ Path traversal prevention
- ✅ 24-hour session TTL

---

## 📁 File Locations

```
apps/core/
├── models/
│   └── upload_session.py              # Session model
├── services/
│   └── resumable_upload_service.py    # Business logic
├── views/
│   └── resumable_upload_views.py      # API endpoints
├── urls_resumable_uploads.py          # URL routing
├── tests/
│   └── test_resumable_uploads.py      # Test suite
├── management/commands/
│   └── cleanup_expired_uploads.py     # Cleanup command
└── migrations/
    └── 0009_add_upload_session_model.py

docs/
├── RESUMABLE_UPLOAD_API.md            # Full API docs
├── resumable-upload-client.js         # JS client library
└── SPRINT3_IMPLEMENTATION_SUMMARY.md  # Implementation details
```

---

## 🎯 Key Features

✅ **1MB chunk size** (configurable)
✅ **24-hour session TTL** with auto-cleanup
✅ **Resume capability** after network failure
✅ **Out-of-order chunks** supported
✅ **Parallel uploads** (3-5 concurrent chunks)
✅ **Progress tracking** (real-time percentage)
✅ **Security validation** on final file
✅ **Transaction management** for consistency

---

## 📚 Full Documentation

- **API Reference**: `docs/RESUMABLE_UPLOAD_API.md`
- **Implementation Summary**: `SPRINT3_IMPLEMENTATION_SUMMARY.md`
- **JavaScript Client**: `docs/resumable-upload-client.js`

---

## 🆘 Support

**Issues?** Check the troubleshooting guide in `docs/RESUMABLE_UPLOAD_API.md`

**Need help?** Review the comprehensive examples in the documentation

**Want to contribute?** All code follows `.claude/rules.md` guidelines