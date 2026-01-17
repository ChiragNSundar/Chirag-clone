# 🧪 Testing Documentation

This document provides a comprehensive high-level and low-level explanation of the testing infrastructure for the **Chirag Clone v2.3** project. The test suite is designed to be robust, resilient to missing dependencies (like ChromaDB or System Audio), and covers everything from unit logic to full integration workflows.

---

## 🏗️ High-Level Testing Strategy

The testing strategy follows the **Testing Pyramid**:

1. **Unit Tests (`test_services.py`, `test_llm.py`, `test_parsers.py`)**: Fast, isolated tests that check individual functions and classes. They mock external dependencies and file I/O.
2. **API Tests (`test_main.py`)**: Checks the HTTP contract of the FastAPI endpoints. Ensures 200 OK responses, correct JSON structures, and error handling.
3. **Integration Tests (`test_integration.py`)**: Tests complete workflows (e.g., "Upload PDF -> Query Knowledge Base") by spinning up a `TestClient` and running real sequences of operations.

### Key Principles

- **Graceful Degradation**: Tests detect if optional dependencies (like `chromadb` or `pyaudio`) are missing and skip relevant tests instead of failing. This allows the suite to run in CI/CD environments or on lightweight machines.
- **Isolation**: Unit tests do not hit real external APIs (OpenAI, Gemini). They use mocks or direct import hacks to test logic without network calls.
- **markers**: We use pytest markers (`@pytest.mark.voice`, `@pytest.mark.vision`) to allow running specific feature subsets.

---

## 📂 Test Suites Breakdown

### 1. `test_main.py` (API Contract Tests)

**Goal**: Verify that all API endpoints are reachable, accept correct parameters, and return valid JSON.

- **`test_read_main`**:
  - *High-Level*: Checks the root endpoint (`/`).
  - *Low-Level*: GET `/` -> Expect 200 OK and `index.html` content.
- **`test_health_check`**:
  - *High-Level*: Verifies system health status.
  - *Low-Level*: GET `/api/health` -> Expect JSON `{"status": "healthy"}`.
- **`test_chat_endpoints`**:
  - *High-Level*: Ensures the chat API accepts messages.
  - *Low-Level*: POST `/api/chat/message` with payload `{"message": "Hello"}` -> Expect 200 OK. Mocking is used to prevent real LLM calls.
- **`test_voice_endpoints`**:
  - *High-Level*: Checks TTS/STT status.
  - *Low-Level*: GET `/api/voice/status` -> Check for keys `tts_available`, `stt_available`.

### 2. `test_integration.py` (Workflow & Feature Tests)

**Goal**: Validate that complex features work end-to-end. This is the most critical suite for v2.3 features.

- **`TestVoiceEndpoints`**:
  - **`test_voice_speak_requires_text`**:
    - *Check*: POST `/api/voice/speak` with empty body -> 422 Error.
  - **`test_voice_status`**:
    - *Check*: Connectivity to ElevenLabs/Whisper services (mocked or real).
- **`TestVisionEndpoints`**:
  - **`test_vision_analyze_requires_image`**:
    - *Check*: Sending request without image file returns error.
  - **`test_vision_desktop_with_base64`**:
    - *Check*: Simulates "Eye Mode" by sending a base64 png. Verifies that the endpoint accepts it and triggers analysis logic.
- **`TestKnowledgeEndpoints` (Brain Station)**:
  - **`test_knowledge_workflow`**:
    - *Mechanism*:
            1. **Upload**: POST a dummy PDF to `/api/knowledge/upload`.
            2. **Verify**: GET `/api/knowledge/documents` to see if it's listed.
            3. **Query**: POST `/api/knowledge/query` to search the uploaded content.
            4. **Delete**: DELETE the document and verify it's gone.
- **`TestCognitiveEndpoints`**:
  - **`test_core_memories`**: Checks retrieval of long-term memories.
  - **`test_learning_stats`**: Verifies that learning counters (facts learned, chats processed) are returned.

### 3. `test_services.py` (Resilience & Core Logic)

**Goal**: Test internal logic like Circuit Breakers, Rate Limiters, and Input Sanitization without spinning up the web server.

- **`TestCircuitBreaker`**:
  - *Logic*:
        1. Create a `CircuitBreaker` instance.
        2. `record_failure()` 3 times (threshold).
        3. Assert state changes from `CLOSED` to `OPEN`.
        4. Wait for timeout -> Assert state `HALF_OPEN`.
        5. `record_success()` -> Assert state `CLOSED`.
- **`TestRateLimiter`**:
  - *Logic*: Verifies that the rate limiter class correctly tracks request counts and generates standard headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`).
- **`TestInputValidation`**:
  - *Logic*: Tests utility functions that strip null bytes, trim whitespace, and validate session IDs.

### 4. `test_llm.py` (Model Management)

**Goal**: Verify model fallback logic and configuration.

- **`TestModelHierarchy`**:
  - *Check*: Ensures `config.py` lists `Gemma` models first (for speed) and `Gemini 1.x` models are NOT present (deprecated).
- **`TestProviderSupport`**:
  - *Check*: Verifies that necessary API keys (`GEMINI_API_KEY`) are present in `Config`.

### 5. `test_parsers.py` (Data Ingestion)

**Goal**: Ensure that chat logs from WhatsApp, Discord, etc., are parsed correctly into the common training format.

- **`TestWhatsAppParser`**:
  - *Input*: Raw string `"12/25/24, 10:30 AM - John: Hello"`.
  - *Output*: Dictionary `{'total_messages': 1, 'conversation_pairs': [...]}`.
- **`TestDiscordParser`**:
  - *Input*: JSON structure `{"messages": [{"content": "Hi", "author": ...}]}`.
  - *Output*: Normalized training data.

### 6. Frontend & E2E Testing (New in v2.5)

**Goal**: Validate UI interactions, responsiveness, and end-to-end user flows in a real browser environment.

- **E2E Tests (`frontend-react/e2e/`)**:
  - **Tool**: Playwright
  - **`app.spec.ts`**:
    - *Navigation*: Verifies all routes (Dashboard, Chat, Profile) load correctly.
    - *Chat*: Simulates typing a message and receiving a response.
    - *Accessibility*: Checks for basic ARIA compliance.
  - **Config**: Multi-browser support (Chromium, Firefox, WebKit) in `playwright.config.ts`.

- **Unit Tests (`src/test/`)**:
  - **Tool**: Vitest + React Testing Library
  - **Scope**: Tests individual React components (e.g., `ThinkingBubble`, `AudioVisualizer`) in isolation.

---

## 🏃 Method of Execution

### Running All Tests

```bash
# 1. Backend Tests
pytest

# 2. Frontend Unit Tests
cd frontend-react && npm test

# 3. Frontend E2E Tests
cd frontend-react && npx playwright test
```

### Running Specific Suites

```bash
# Run only integration tests
pytest backend/tests/test_integration.py

# Run only unit tests for logic
pytest backend/tests/test_services.py
```

### Running by Marker

We use custom markers to group tests by feature:

```bash
# Test only Voice features
pytest -m voice

# Test only Vision features
pytest -m vision

# Test only Knowledge Base (Brain Station)
pytest -m knowledge
```

### Handling Missing Dependencies

The test suite automatically skips tests if dependencies are missing:

- If `chromadb` is missing: Knowledge tests are skipped.
- If `pyaudio` is missing: Microphone tests are skipped.
- This allows `pytest` to always exit with code 0 (success) even on restricted environments.

---

## 🔧 Low-Level Implementation Details

### Fixtures (`conftest.py`)

Fixtures are reusable setup code.

- `client`: Creates a `TestClient(app)` for making API requests.
- `sample_voice_text`: Returns "Hello world" for TTS tests.
- `sample_base64_image`: Returns a 1x1 pixel base64 PNG for vision tests.
- `mock_chroma`: Patches the vector database to avoid creating real files on disk.

### Mocking

We use `unittest.mock.patch` extensively.

- **Why**: We don't want to pay for OpenAI/Gemini API calls during testing.
- **How**:

    ```python
    @patch('services.llm_service.generate_response')
    def test_chat(mock_generate):
        mock_generate.return_value = "Mocked AI response"
        # ... run test ...
    ```
