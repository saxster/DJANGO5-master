/**
 * Resumable Upload Client Library
 *
 * JavaScript client for easy integration of resumable file uploads.
 * Handles chunking, progress tracking, retry logic, and resume capability.
 *
 * Features:
 * - Automatic chunking (default 1MB)
 * - Progress callbacks
 * - Retry with exponential backoff
 * - Resume after network failure
 * - Parallel chunk uploads
 * - Local progress persistence
 *
 * Usage:
 * ```javascript
 * const uploader = new ResumableUploader({
 *   apiUrl: 'https://api.example.com/api/v1/upload',
 *   authToken: 'your_auth_token'
 * });
 *
 * await uploader.uploadFile(file, {
 *   onProgress: (progress) => console.log(`${progress}% complete`),
 *   onComplete: (result) => console.log('Upload complete:', result),
 *   onError: (error) => console.error('Upload failed:', error)
 * });
 * ```
 */

class ResumableUploader {
  constructor(options = {}) {
    this.apiUrl = options.apiUrl || '/api/v1/upload';
    this.authToken = options.authToken;
    this.chunkSize = options.chunkSize || 1024 * 1024; // 1MB default
    this.maxRetries = options.maxRetries || 3;
    this.concurrentChunks = options.concurrentChunks || 3;
    this.persistProgress = options.persistProgress !== false;
  }

  /**
   * Calculate SHA-256 hash of data
   */
  async calculateHash(data) {
    const buffer = await data.arrayBuffer();
    const hashBuffer = await crypto.subtle.digest('SHA-256', buffer);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    return hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  }

  /**
   * Initialize upload session
   */
  async initSession(file) {
    const fileHash = await this.calculateHash(file);

    const response = await fetch(`${this.apiUrl}/init`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.authToken}`
      },
      body: JSON.stringify({
        filename: file.name,
        total_size: file.size,
        mime_type: file.type,
        file_hash: fileHash
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to initialize upload');
    }

    return await response.json();
  }

  /**
   * Upload a single chunk with retry logic
   */
  async uploadChunk(uploadId, chunkIndex, chunkBlob, retries = 0) {
    try {
      const chunkHash = await this.calculateHash(chunkBlob);
      const arrayBuffer = await chunkBlob.arrayBuffer();
      const base64Chunk = btoa(String.fromCharCode(...new Uint8Array(arrayBuffer)));

      const response = await fetch(`${this.apiUrl}/chunk`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${this.authToken}`
        },
        body: JSON.stringify({
          upload_id: uploadId,
          chunk_index: chunkIndex,
          chunk_data: base64Chunk,
          checksum: chunkHash
        })
      });

      if (!response.ok) {
        throw new Error(`Chunk upload failed: ${response.status}`);
      }

      return await response.json();
    } catch (error) {
      if (retries < this.maxRetries) {
        // Exponential backoff: 1s, 2s, 4s
        await new Promise(resolve => setTimeout(resolve, Math.pow(2, retries) * 1000));
        return this.uploadChunk(uploadId, chunkIndex, chunkBlob, retries + 1);
      }
      throw error;
    }
  }

  /**
   * Complete upload and get final file info
   */
  async completeUpload(uploadId) {
    const response = await fetch(`${this.apiUrl}/complete`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.authToken}`
      },
      body: JSON.stringify({ upload_id: uploadId })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.error || 'Failed to complete upload');
    }

    return await response.json();
  }

  /**
   * Cancel upload session
   */
  async cancelUpload(uploadId) {
    await fetch(`${this.apiUrl}/cancel`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${this.authToken}`
      },
      body: JSON.stringify({ upload_id: uploadId })
    });
  }

  /**
   * Get upload status
   */
  async getStatus(uploadId) {
    const response = await fetch(`${this.apiUrl}/status/${uploadId}`, {
      method: 'GET',
      headers: {
        'Authorization': `Bearer ${this.authToken}`
      }
    });

    if (!response.ok) {
      throw new Error('Failed to get upload status');
    }

    return await response.json();
  }

  /**
   * Persist upload progress to localStorage
   */
  persistUploadProgress(uploadId, progress) {
    if (!this.persistProgress) return;

    localStorage.setItem(
      `upload_${uploadId}`,
      JSON.stringify({
        uploadId,
        receivedChunks: progress.received_chunks,
        timestamp: new Date().toISOString()
      })
    );
  }

  /**
   * Restore upload progress from localStorage
   */
  restoreUploadProgress(uploadId) {
    if (!this.persistProgress) return null;

    const stored = localStorage.getItem(`upload_${uploadId}`);
    if (!stored) return null;

    const progress = JSON.parse(stored);
    // Check if progress is less than 24 hours old
    const age = Date.now() - new Date(progress.timestamp).getTime();
    if (age > 24 * 60 * 60 * 1000) {
      localStorage.removeItem(`upload_${uploadId}`);
      return null;
    }

    return progress;
  }

  /**
   * Clear stored progress
   */
  clearUploadProgress(uploadId) {
    if (!this.persistProgress) return;
    localStorage.removeItem(`upload_${uploadId}`);
  }

  /**
   * Main upload method with progress tracking
   */
  async uploadFile(file, callbacks = {}) {
    const {
      onProgress,
      onComplete,
      onError,
      onChunkComplete
    } = callbacks;

    try {
      // Initialize session
      const session = await this.initSession(file);
      const { upload_id, chunk_size, total_chunks } = session;

      // Check for existing progress
      const savedProgress = this.restoreUploadProgress(upload_id);
      const completedChunks = savedProgress ? new Set(savedProgress.receivedChunks) : new Set();

      // Create chunk upload tasks
      const chunks = [];
      for (let i = 0; i < total_chunks; i++) {
        if (!completedChunks.has(i)) {
          const start = i * chunk_size;
          const end = Math.min(start + chunk_size, file.size);
          const chunkBlob = file.slice(start, end);
          chunks.push({ index: i, blob: chunkBlob });
        }
      }

      // Upload chunks in parallel (limited concurrency)
      let uploadedCount = completedChunks.size;
      const uploadChunkWithProgress = async (chunk) => {
        const result = await this.uploadChunk(upload_id, chunk.index, chunk.blob);
        uploadedCount++;

        const progress = Math.round((uploadedCount / total_chunks) * 100);

        // Persist progress
        this.persistUploadProgress(upload_id, result.progress);

        // Callbacks
        if (onProgress) onProgress(progress);
        if (onChunkComplete) onChunkComplete(chunk.index, result);

        return result;
      };

      // Process chunks with limited concurrency
      for (let i = 0; i < chunks.length; i += this.concurrentChunks) {
        const batch = chunks.slice(i, i + this.concurrentChunks);
        await Promise.all(batch.map(uploadChunkWithProgress));
      }

      // Complete upload
      const result = await this.completeUpload(upload_id);

      // Clear stored progress
      this.clearUploadProgress(upload_id);

      if (onComplete) onComplete(result);
      return result;

    } catch (error) {
      if (onError) onError(error);
      throw error;
    }
  }

  /**
   * Resume an existing upload
   */
  async resumeUpload(uploadId, file, callbacks = {}) {
    const {
      onProgress,
      onComplete,
      onError,
      onChunkComplete
    } = callbacks;

    try {
      // Get current status
      const status = await this.getStatus(uploadId);

      if (status.status === 'completed') {
        if (onComplete) onComplete(status);
        return status;
      }

      if (status.status === 'expired') {
        throw new Error('Upload session expired. Please start a new upload.');
      }

      const missingChunks = status.progress.missing_chunks;
      const totalChunks = missingChunks.length + status.progress.received_chunks.length;

      // Upload missing chunks
      let uploadedCount = status.progress.received_chunks.length;
      for (const chunkIndex of missingChunks) {
        const start = chunkIndex * this.chunkSize;
        const end = Math.min(start + this.chunkSize, file.size);
        const chunkBlob = file.slice(start, end);

        const result = await this.uploadChunk(uploadId, chunkIndex, chunkBlob);
        uploadedCount++;

        const progress = Math.round((uploadedCount / totalChunks) * 100);
        if (onProgress) onProgress(progress);
        if (onChunkComplete) onChunkComplete(chunkIndex, result);
      }

      // Complete upload
      const result = await this.completeUpload(uploadId);
      this.clearUploadProgress(uploadId);

      if (onComplete) onComplete(result);
      return result;

    } catch (error) {
      if (onError) onError(error);
      throw error;
    }
  }
}

// Export for various module systems
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ResumableUploader;
}

if (typeof define === 'function' && define.amd) {
  define([], function() {
    return ResumableUploader;
  });
}

if (typeof window !== 'undefined') {
  window.ResumableUploader = ResumableUploader;
}

/* ============================================================================
 * USAGE EXAMPLES
 * ========================================================================= */

/**
 * Example 1: Basic upload with progress
 */
async function basicUploadExample() {
  const uploader = new ResumableUploader({
    apiUrl: 'https://api.example.com/api/v1/upload',
    authToken: 'your_auth_token'
  });

  const fileInput = document.getElementById('fileInput');
  const file = fileInput.files[0];

  const result = await uploader.uploadFile(file, {
    onProgress: (progress) => {
      console.log(`Upload progress: ${progress}%`);
      document.getElementById('progressBar').style.width = `${progress}%`;
    },
    onComplete: (result) => {
      console.log('Upload completed:', result.file_path);
      alert('File uploaded successfully!');
    },
    onError: (error) => {
      console.error('Upload failed:', error);
      alert('Upload failed: ' + error.message);
    }
  });
}

/**
 * Example 2: Resume interrupted upload
 */
async function resumeUploadExample(uploadId, file) {
  const uploader = new ResumableUploader({
    apiUrl: 'https://api.example.com/api/v1/upload',
    authToken: 'your_auth_token'
  });

  const result = await uploader.resumeUpload(uploadId, file, {
    onProgress: (progress) => {
      console.log(`Resume progress: ${progress}%`);
    },
    onComplete: (result) => {
      console.log('Upload resumed and completed:', result);
    }
  });
}

/**
 * Example 3: Upload with cancellation
 */
async function uploadWithCancellation() {
  const uploader = new ResumableUploader({
    apiUrl: 'https://api.example.com/api/v1/upload',
    authToken: 'your_auth_token'
  });

  const fileInput = document.getElementById('fileInput');
  const file = fileInput.files[0];

  let currentUploadId = null;

  // Cancel button handler
  document.getElementById('cancelBtn').onclick = async () => {
    if (currentUploadId) {
      await uploader.cancelUpload(currentUploadId);
      console.log('Upload cancelled');
    }
  };

  // Start upload
  const result = await uploader.uploadFile(file, {
    onProgress: (progress) => {
      console.log(`Progress: ${progress}%`);
    },
    onComplete: (result) => {
      currentUploadId = null;
      console.log('Completed:', result);
    }
  });
}

/**
 * Example 4: Multiple file uploads with queue
 */
async function multipleFileUploadExample(files) {
  const uploader = new ResumableUploader({
    apiUrl: 'https://api.example.com/api/v1/upload',
    authToken: 'your_auth_token'
  });

  const results = [];
  for (const file of files) {
    const result = await uploader.uploadFile(file, {
      onProgress: (progress) => {
        console.log(`${file.name}: ${progress}%`);
      }
    });
    results.push(result);
  }

  console.log('All uploads completed:', results);
  return results;
}

/**
 * Example 5: React component integration
 */
class FileUploadComponent extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      progress: 0,
      uploading: false,
      error: null
    };
    this.uploader = new ResumableUploader({
      apiUrl: props.apiUrl,
      authToken: props.authToken
    });
  }

  handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    this.setState({ uploading: true, progress: 0, error: null });

    try {
      const result = await this.uploader.uploadFile(file, {
        onProgress: (progress) => {
          this.setState({ progress });
        },
        onComplete: (result) => {
          this.setState({ uploading: false, progress: 100 });
          this.props.onUploadComplete(result);
        },
        onError: (error) => {
          this.setState({ uploading: false, error: error.message });
        }
      });
    } catch (error) {
      this.setState({ uploading: false, error: error.message });
    }
  };

  render() {
    return (
      <div>
        <input
          type="file"
          onChange={this.handleFileChange}
          disabled={this.state.uploading}
        />
        {this.state.uploading && (
          <div>
            <progress value={this.state.progress} max="100" />
            <span>{this.state.progress}%</span>
          </div>
        )}
        {this.state.error && (
          <div style={{ color: 'red' }}>{this.state.error}</div>
        )}
      </div>
    );
  }
}