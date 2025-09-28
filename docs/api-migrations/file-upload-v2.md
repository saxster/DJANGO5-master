# Migration Guide: File Upload API v1 → v2

## Overview
The legacy `upload_attachment` GraphQL mutation has security vulnerabilities and is being replaced with `secure_file_upload`.

## Timeline
- **Deprecated**: 2025-09-27
- **Sunset**: 2026-06-30
- **Removed**: 2026-07-01

## Changes Summary

| Aspect | v1 (Deprecated) | v2 (Current) |
|--------|-----------------|--------------|
| Mutation Name | `upload_attachment` | `secure_file_upload` |
| Encoding | Base64 (inefficient) | Multipart upload |
| Validation | Basic | Comprehensive (file type, size, malware scan) |
| Security | ⚠️ Vulnerable | ✅ Secure |
| Performance | Slow (large payloads) | Fast (streaming) |

## Migration Steps

### 1. Update GraphQL Mutation

**Before (v1 - Deprecated)**:
```graphql
mutation UploadFile {
  upload_attachment(
    bytes: "base64encodeddata..."
    record: "{\"type\":\"asset\",\"id\":123}"
    biodata: "metadata"
  ) {
    output {
      rc
      msg
      recordcount
    }
  }
}
```

**After (v2 - Secure)**:
```graphql
mutation SecureUploadFile {
  secure_file_upload(
    file: $file  # Multipart file upload
    recordType: "asset"
    recordId: 123
    metadata: {
      description: "Equipment photo"
      category: "maintenance"
    }
  ) {
    output {
      rc
      msg
      recordcount
      fileUrl
      fileId
    }
  }
}
```

### 2. Update Client Code

#### Kotlin (Android)
```kotlin
// Before (v1)
val base64Data = file.toBase64String()
val mutation = UploadAttachmentMutation(
    bytes = base64Data,
    record = """{"type":"asset","id":123}""",
    biodata = "metadata"
)

// After (v2)
val file = File(context.filesDir, "photo.jpg")
val mutation = SecureFileUploadMutation(
    recordType = "asset",
    recordId = 123,
    metadata = FileMetadataInput(
        description = "Equipment photo",
        category = "maintenance"
    )
)
apolloClient.upload(mutation, file)
```

#### Swift (iOS)
```swift
// Before (v1)
let base64Data = fileData.base64EncodedString()
let mutation = UploadAttachmentMutation(
    bytes: base64Data,
    record: "{\"type\":\"asset\",\"id\":123}",
    biodata: "metadata"
)

// After (v2)
let fileURL = URL(fileURLWithPath: photoPath)
let mutation = SecureFileUploadMutation(
    recordType: "asset",
    recordId: 123,
    metadata: FileMetadataInput(
        description: "Equipment photo",
        category: "maintenance"
    )
)
apolloClient.upload(mutation: mutation, file: fileURL)
```

### 3. Update Network Configuration

#### Multipart Upload Support
Ensure your GraphQL client supports multipart requests:

**Kotlin (Apollo)**:
```kotlin
val apolloClient = ApolloClient.Builder()
    .serverUrl("https://api.youtility.in/api/graphql/")
    .addInterceptor(AuthInterceptor())
    .uploadInterceptor(MultipartUploadInterceptor())  // Add this
    .build()
```

**Swift (Apollo)**:
```swift
let client = ApolloClient(
    networkTransport: RequestChainNetworkTransport(
        interceptorProvider: InterceptorProvider(
            store: store,
            client: URLSessionClient(),
            shouldInvalidateClientOnDeinit: true
        ),
        endpointURL: URL(string: "https://api.youtility.in/api/graphql/")!
    )
)
```

## Benefits of Migration

### Security Improvements
- ✅ Comprehensive file validation (type, size, content)
- ✅ Malware scanning integration
- ✅ Path traversal protection
- ✅ MIME type verification

### Performance Improvements
- ✅ 70% reduction in payload size (multipart vs base64)
- ✅ Streaming uploads for large files
- ✅ Progress tracking support
- ✅ Parallel upload capabilities

### Developer Experience
- ✅ Better error messages
- ✅ Upload progress callbacks
- ✅ Automatic retry on failure
- ✅ Type-safe file metadata

## Testing Your Migration

### 1. Local Testing
```bash
# Test with cURL
curl -X POST https://api.youtility.in/api/graphql/ \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -F operations='{"query":"mutation($file: Upload!) { secure_file_upload(file: $file, recordType: \"asset\", recordId: 123) { output { rc msg } } }","variables":{"file":null}}' \
  -F map='{"0":["variables.file"]}' \
  -F 0=@test-file.jpg
```

### 2. Integration Testing
Use your SDK's test suite with the new mutation:

```kotlin
// Kotlin test
@Test
fun testSecureFileUpload() = runTest {
    val file = createTestFile()
    val result = apiClient.uploadFile(file, "asset", 123)
    assertEquals(0, result.rc)
    assertNotNull(result.fileUrl)
}
```

### 3. Monitoring
After migration, verify in dashboard:
- Zero usage of `upload_attachment`
- All uploads using `secure_file_upload`
- No upload failures

## Troubleshooting

### Issue: "File too large" error
**Solution**: The secure upload has stricter size limits. Maximum is 50MB per file.

### Issue: "Invalid file type" error
**Solution**: Only allowed file types: `jpg`, `png`, `pdf`, `docx`. Contact support to add types.

### Issue: "Multipart not supported" error
**Solution**: Update your Apollo client to latest version (3.7.0+ for Kotlin, 1.9.0+ for Swift).

## Rollback Plan

If critical issues occur after migration:

1. **Temporary**: Old mutation still works until 2026-06-30
2. **Revert Code**: Restore previous mutation in your app
3. **Contact Support**: Report issues to api-support@youtility.in
4. **Timeline**: We'll assist with migration issues

## Support Resources

- **Migration Support Email**: api-migration@youtility.in
- **Video Tutorial**: https://youtube.com/@youtility/file-upload-v2
- **Sample Code**: https://github.com/youtility/sdk-examples
- **Office Hours**: Tuesdays 10:00-11:00 UTC (Zoom link in email)

## Checklist

Before completing migration:

- [ ] Updated mutation name to `secure_file_upload`
- [ ] Changed from base64 to multipart upload
- [ ] Updated SDK to compatible version
- [ ] Tested file upload in staging
- [ ] Verified error handling
- [ ] Monitored upload success rate
- [ ] Removed `upload_attachment` from codebase
- [ ] Updated team documentation

---

**Guide Version**: 1.0
**Last Updated**: 2025-09-27
**Status**: Active Migration Period