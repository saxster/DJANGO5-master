# Voice Input API - Conversational Onboarding

## Overview

The Voice Input API enables hands-free interaction with the Conversational Onboarding system using speech-to-text transcription powered by Google Cloud Speech API. This feature supports 10+ languages including English and major Indian languages, making it ideal for field teams and multilingual environments.

## Architecture

```
┌─────────────────┐
│  Mobile/Web App │
│  Records Audio  │
└────────┬────────┘
         │ POST /conversation/{id}/voice/
         │ (multipart/form-data with audio file)
         ▼
┌────────────────────────────────────────────┐
│ Django Server                              │
│                                            │
│ 1. OnboardingSpeechService                │
│    └─> SpeechToTextService (reused)      │
│        └─> Google Cloud Speech API        │
│                                            │
│ 2. Audio → Text Transcription             │
│    └─> "मुझे 5 गार्ड चाहिए"             │
│                                            │
│ 3. LLM Processing (existing flow)         │
│    └─> process_voice_input()             │
│        └─> process_conversation_step()    │
│                                            │
│ 4. Response Generation                     │
│    └─> "How many shifts do you need?"     │
└────────────────────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  JSON Response  │
│  + Transcript   │
│  + LLM Reply    │
└─────────────────┘
```

## API Endpoints

### 1. Check Voice Capabilities

**Endpoint:** `GET /api/v1/onboarding/voice/capabilities/`

**Authentication:** Required (Bearer token or session)

**Response:**
```json
{
  "voice_enabled": true,
  "service_available": true,
  "supported_languages": {
    "en": "en-US",
    "hi": "hi-IN",
    "mr": "mr-IN",
    "ta": "ta-IN",
    "te": "te-IN",
    "kn": "kn-IN",
    "gu": "gu-IN",
    "bn": "bn-IN",
    "ml": "ml-IN",
    "or": "or-IN"
  },
  "configuration": {
    "max_audio_duration_seconds": 60,
    "max_file_size_mb": 10,
    "default_language": "en-US",
    "min_confidence_threshold": 0.6
  },
  "supported_formats": [
    "audio/webm",
    "audio/wav",
    "audio/mp3",
    "audio/ogg",
    "audio/m4a",
    "audio/aac",
    "audio/flac"
  ],
  "features": {
    "real_time_transcription": false,
    "speaker_identification": false,
    "noise_cancellation": true,
    "multi_language_detection": false,
    "auto_language_detection": false
  }
}
```

### 2. Submit Voice Input

**Endpoint:** `POST /api/v1/onboarding/conversation/{conversation_id}/voice/`

**Authentication:** Required (Bearer token or session)

**Content-Type:** `multipart/form-data`

**Request Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `audio` | File | Yes | Audio file in supported format |
| `language` | String | No | BCP-47 language code (default: session preference or 'en-US') |
| `context` | JSON | No | Additional context for processing |

**Example Request (cURL):**
```bash
curl -X POST \
  'https://api.example.com/api/v1/onboarding/conversation/abc-123-def/voice/' \
  -H 'Authorization: Bearer YOUR_TOKEN' \
  -F 'audio=@recording.webm' \
  -F 'language=hi-IN'
```

**Example Request (JavaScript):**
```javascript
const formData = new FormData();
formData.append('audio', audioBlob, 'recording.webm');
formData.append('language', 'hi-IN');

fetch(`/api/v1/onboarding/conversation/${conversationId}/voice/`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`
  },
  body: formData
})
.then(response => response.json())
.then(data => console.log(data));
```

**Success Response (200 OK):**
```json
{
  "conversation_id": "abc-123-def-456",
  "transcription": {
    "text": "मुझे पांच गार्ड चाहिए",
    "confidence": 0.95,
    "language": "hi-IN",
    "duration_seconds": 3.2,
    "processing_time_ms": 1250
  },
  "response": "आपको कौन से शिफ्ट चाहिए? सुबह, दोपहर या रात?",
  "next_questions": [
    {
      "question": "How many shifts do you need?",
      "options": ["Morning", "Afternoon", "Night", "All shifts"]
    }
  ],
  "state": "in_progress",
  "voice_interaction_count": 3
}
```

**Error Response (400 Bad Request):**
```json
{
  "error": "Missing audio file. Please provide audio in multipart/form-data format."
}
```

**Error Response (400 Bad Request - Unsupported Language):**
```json
{
  "error": "Language 'xx-YY' is not supported for voice input",
  "supported_languages": {
    "en": "en-US",
    "hi": "hi-IN",
    ...
  }
}
```

**Error Response (500 Internal Server Error):**
```json
{
  "error": "Voice transcription failed",
  "details": "Audio file too large: 12582912 bytes exceeds limit of 10485760 bytes",
  "fallback": "Please use text input instead"
}
```

## Supported Languages

| Language | Code | Native Name | Notes |
|----------|------|-------------|-------|
| English (US) | `en-US` | English | Default language |
| Hindi | `hi-IN` | हिन्दी | Full support |
| Marathi | `mr-IN` | मराठी | Full support |
| Tamil | `ta-IN` | தமிழ் | Full support |
| Telugu | `te-IN` | తెలుగు | Full support |
| Kannada | `kn-IN` | ಕನ್ನಡ | Full support |
| Gujarati | `gu-IN` | ગુજરાતી | Full support |
| Bengali | `bn-IN` | বাংলা | Full support |
| Malayalam | `ml-IN` | മലയാളം | Full support |
| Odia | `or-IN` | ଓଡ଼ିଆ | Full support |

## Audio Requirements

### File Specifications

- **Maximum Duration:** 60 seconds per audio clip
- **Maximum File Size:** 10 MB
- **Supported Formats:**
  - WebM (`.webm`) - Recommended for web browsers
  - WAV (`.wav`) - High quality, larger file size
  - MP3 (`.mp3`) - Good compression
  - OGG (`.ogg`) - Open source codec
  - M4A (`.m4a`) - Apple devices
  - AAC (`.aac`) - Advanced audio codec
  - FLAC (`.flac`) - Lossless compression

### Quality Recommendations

- **Sample Rate:** Minimum 16 kHz (auto-converted if different)
- **Bit Depth:** Minimum 16-bit
- **Channels:** Mono (auto-converted from stereo)
- **Environment:** Minimize background noise for better accuracy
- **Distance:** Speak 6-12 inches from microphone

### Automatic Processing

All audio files are automatically:
1. Converted to 16kHz mono WAV format
2. Processed for noise reduction
3. Transcribed using Google Cloud Speech API
4. Deleted immediately after transcription (no storage)

## Integration Examples

### React/JavaScript Web App

```javascript
import React, { useState } from 'react';

function VoiceInput({ conversationId, onTranscript }) {
  const [recording, setRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState(null);

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const recorder = new MediaRecorder(stream);
    const audioChunks = [];

    recorder.ondataavailable = (event) => {
      audioChunks.push(event.data);
    };

    recorder.onstop = async () => {
      const audioBlob = new Blob(audioChunks, { type: 'audio/webm' });
      await sendVoiceInput(audioBlob);
    };

    recorder.start();
    setMediaRecorder(recorder);
    setRecording(true);
  };

  const stopRecording = () => {
    if (mediaRecorder) {
      mediaRecorder.stop();
      setRecording(false);
    }
  };

  const sendVoiceInput = async (audioBlob) => {
    const formData = new FormData();
    formData.append('audio', audioBlob, 'recording.webm');
    formData.append('language', 'hi-IN');

    const response = await fetch(
      `/api/v1/onboarding/conversation/${conversationId}/voice/`,
      {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: formData
      }
    );

    const data = await response.json();
    onTranscript(data);
  };

  return (
    <div>
      <button onClick={recording ? stopRecording : startRecording}>
        {recording ? '⏹️ Stop' : '🎤 Start Recording'}
      </button>
    </div>
  );
}
```

### Python Client

```python
import requests

def send_voice_input(conversation_id, audio_file_path, language='en-US'):
    """Send voice input to conversational onboarding API."""
    url = f'https://api.example.com/api/v1/onboarding/conversation/{conversation_id}/voice/'

    with open(audio_file_path, 'rb') as audio_file:
        files = {'audio': audio_file}
        data = {'language': language}
        headers = {'Authorization': f'Bearer {get_token()}'}

        response = requests.post(url, files=files, data=data, headers=headers)

        if response.status_code == 200:
            result = response.json()
            print(f"Transcript: {result['transcription']['text']}")
            print(f"Response: {result['response']}")
            return result
        else:
            print(f"Error: {response.json()}")
            return None

# Usage
result = send_voice_input(
    conversation_id='abc-123-def',
    audio_file_path='recording.wav',
    language='hi-IN'
)
```

### Mobile (React Native)

```javascript
import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';

async function recordAndSendVoice(conversationId, language = 'en-US') {
  // Start recording
  const { recording } = await Audio.Recording.createAsync(
    Audio.RecordingOptionsPresets.HIGH_QUALITY
  );

  // Wait for user to finish (add UI controls)
  await new Promise(resolve => setTimeout(resolve, 5000));

  // Stop and get URI
  await recording.stopAndUnloadAsync();
  const uri = recording.getURI();

  // Upload to API
  const formData = new FormData();
  formData.append('audio', {
    uri: uri,
    type: 'audio/m4a',
    name: 'recording.m4a'
  });
  formData.append('language', language);

  const response = await fetch(
    `https://api.example.com/api/v1/onboarding/conversation/${conversationId}/voice/`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      },
      body: formData
    }
  );

  return await response.json();
}
```

## Error Handling

### Common Error Scenarios

| Status | Error | Cause | Resolution |
|--------|-------|-------|------------|
| 400 | Missing audio file | No `audio` file in request | Include audio file in multipart/form-data |
| 400 | Language not supported | Invalid or unsupported language code | Use one of the supported language codes |
| 403 | Voice input not enabled | Feature disabled in settings | Contact administrator |
| 404 | Conversation not found | Invalid `conversation_id` | Verify conversation ID |
| 413 | File too large | Audio file > 10 MB | Reduce audio duration or quality |
| 500 | Transcription failed | Google Cloud Speech API error | Retry or use text input fallback |

### Recommended Error Handling

```javascript
async function handleVoiceInput(audioBlob, conversationId) {
  try {
    const response = await sendVoiceInput(audioBlob, conversationId);

    if (response.error) {
      // Check if fallback to text is recommended
      if (response.fallback) {
        showTextInputFallback();
      }
      showError(response.error);
    } else {
      displayTranscript(response.transcription.text);
      displayLLMResponse(response.response);
    }
  } catch (error) {
    console.error('Voice input failed:', error);
    showTextInputFallback();
  }
}
```

## Performance Metrics

### Typical Response Times

| Audio Duration | Transcription Time | Total Response Time |
|----------------|-------------------|---------------------|
| 3 seconds | 800-1200ms | 1500-2000ms |
| 10 seconds | 1200-1800ms | 2000-3000ms |
| 30 seconds | 2000-3500ms | 3000-5000ms |
| 60 seconds | 3500-6000ms | 5000-8000ms |

### Accuracy Metrics

- **Clean Audio (low noise):** 95-98% accuracy
- **Moderate Noise:** 85-92% accuracy
- **High Noise:** 70-85% accuracy
- **Confidence Threshold:** 0.6 minimum (configurable)

## Security & Privacy

### Data Handling

1. **Audio Files:** Deleted immediately after transcription
2. **Transcripts:** Stored in `ConversationSession.audio_transcripts` (encrypted at rest)
3. **PII Protection:** Transcripts treated as sensitive user data
4. **Access Control:** Requires authenticated session, user can only access own conversations

### Compliance

- **GDPR:** Transcripts can be deleted via conversation deletion
- **Data Retention:** Follows conversation retention policy
- **Audit Trail:** All voice interactions logged with timestamps
- **Encryption:** TLS 1.2+ for transit, AES-256 for storage

## Configuration

### Environment Variables

```bash
# Enable/disable voice input
ENABLE_ONBOARDING_VOICE_INPUT=true

# Processing limits
ONBOARDING_VOICE_MAX_DURATION=60
ONBOARDING_VOICE_MAX_FILE_SIZE=10

# Language settings
ONBOARDING_VOICE_DEFAULT_LANGUAGE=en-US

# Quality settings
ONBOARDING_VOICE_MIN_CONFIDENCE=0.6
ONBOARDING_VOICE_AUTO_FALLBACK=true

# Google Cloud credentials (required)
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
```

### Django Settings

Located in `intelliwiz_config/settings/onboarding.py`:

```python
ENABLE_ONBOARDING_VOICE_INPUT = True
ONBOARDING_VOICE_MAX_DURATION_SECONDS = 60
ONBOARDING_VOICE_MAX_FILE_SIZE_MB = 10
ONBOARDING_VOICE_DEFAULT_LANGUAGE = 'en-US'
ONBOARDING_VOICE_MIN_CONFIDENCE = 0.6
ONBOARDING_VOICE_SUPPORTED_LANGUAGES = ['en-US', 'hi-IN', 'mr-IN', ...]
```

## Troubleshooting

### Issue: Transcription always fails

**Solutions:**
1. Verify Google Cloud credentials configured
2. Check Speech API enabled in Google Cloud Console
3. Verify API quota not exceeded
4. Test with capability endpoint first

### Issue: Low transcription accuracy

**Solutions:**
1. Improve audio quality (reduce background noise)
2. Speak clearly and at moderate pace
3. Use correct language code for audio
4. Consider increasing `min_confidence_threshold`

### Issue: Audio file rejected

**Solutions:**
1. Check file size < 10 MB
2. Verify audio duration < 60 seconds
3. Use supported audio format
4. Ensure file is not corrupted

## Future Enhancements (Roadmap)

- [ ] Real-time streaming transcription
- [ ] Text-to-Speech for voice responses
- [ ] Speaker identification (multi-user sessions)
- [ ] Automatic language detection
- [ ] Offline voice processing via mobile SDK
- [ ] Voice command shortcuts
- [ ] Custom wake words
- [ ] Noise cancellation improvements

## Support

For issues or questions:
- **Documentation:** https://docs.example.com/voice-api
- **GitHub Issues:** https://github.com/example/intelliwiz/issues
- **Email:** support@example.com

---

**Last Updated:** 2025-09-28
**API Version:** v1
**Service:** Google Cloud Speech API v2