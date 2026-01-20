# 🧪 Testing Documentation

This document provides a comprehensive high-level and low-level explanation of the testing infrastructure for the **Chirag Clone v2.8** project. The test suite is designed to be robust, resilient to missing dependencies, and covers everything from unit logic to full integration workflows.

---

## 🏗️ High-Level Testing Strategy

The testing strategy follows the **Testing Pyramid**:

1. **Unit Tests**: Fast, isolated tests for individual services (Auth, Voice, RAG). They mock external dependencies and file I/O.
2. **API Tests (`test_main.py`)**: Checks the HTTP contract of the FastAPI endpoints.
3. **Integration Tests (`test_integration.py`)**: Tests complete workflows (e.g., "Upload PDF -> Query Knowledge Base").
4. **Frontend Tests**: Component-level tests using Vitest and React Testing Library.
5. **Hook Tests**: Custom React hook tests using `@testing-library/react`.

### Key Principles

- **Graceful Degradation**: Tests detect if optional dependencies are missing and skip relevant tests.
- **Isolation**: Unit tests do not hit real external APIs (OpenAI, Gemini). They use mocks.
- **Markers**: We use pytest markers (`@pytest.mark.voice`, `@pytest.mark.asyncio`) to allow running specific feature subsets.
- **Comprehensive Mocks**: Test setup includes mocks for AudioContext, MediaRecorder, localStorage, clipboard, etc.

---

## 📂 Test Suites Breakdown

### 1. `test_auth.py` (Authentication & Security) ✅

- **JWT Generation**: Validates token creation and signature verification.
- **OAuth URL**: Tests Google OAuth2 URL construction and state parameter generation.
- **Admin Whitelist**: Verifies that only `ALLOWED_ADMIN_EMAILS` can access protected routes.
- **Dependency Injection**: Tests `require_admin` dependency raises 403 for unauthorized users.

### 2. `test_voice.py` (Real-Time Audio) 🎙️

- **VoiceState Enum**: Tests state machine transitions (Listening -> Thinking -> Speaking).
- **VAD Logic**: Verifies Voice Activity Detection logic, including energy-based fallback.
- **Barge-In**: Tests logic for interrupting the bot when user speaks.

### 3. `test_prompt_guard.py` (Security) 🛡️

- **Injection Detection**: Tests identification of "Ignore all instructions" type attacks.
- **Sanitization**: Verifies HTML/Script tag stripping.
- **Threat Levels**: Checks classification of input safety (Safe, Risky, Critical).

### 4. `test_hybrid_rag.py` (Knowledge) 🧠

- **Search Algorithms**: Tests BM25 (keyword) and Semantic (vector) search independently.
- **Fusion**: Verifies Reciprocal Rank Fusion (RRF) correctly combines scores.
- **Document Handling**: Tests adding and indexing documents.

### 5. `test_circuit_breaker.py` (Resilience) 🔌

- **State Transitions**: CLOSED -> OPEN (failures) -> HALF_OPEN (timeout) -> CLOSED (success).
- **Thresholds**: asserts that failure counts trigger state changes correctly.

### 6. Frontend Tests (Vitest) ⚛️

- **`LoginPage.test.tsx`**: Tests Google Sign-In button rendering, OAuth status checking, and error display.
- **`VoiceChat.test.tsx`**: Mocks `WebSocket` and `MediaRecorder` to test real-time voice controls and status indicators.
- **`Dashboard.test.tsx`**: Tests analytics data fetching, chart rendering, and loading states.
- **`ChatInterface.test.tsx`**: Tests message sending, thinking indicators, and avatar controls.
- **`ThinkingBubble.test.tsx`**: Tests thinking step rendering and animations.

### 7. Hook Tests (`useUtilities.test.ts`) 🪝

- **`useDebounce`**: Tests debouncing behavior and timer cancellation.
- **`useLocalStorage`**: Tests read/write/update with mocked localStorage.
- **`usePrevious`**: Tests previous value tracking across renders.
- **`useWindowSize`**: Tests window dimension reporting.
- **`useCopyToClipboard`**: Tests clipboard API integration.
- **`useAsync`**: Tests async function execution, loading, and error states.

### 8. `test_export_import.py` (Brain Export/Import) 💾

- **Memory Export**: Tests `export_all_training_examples()` returns complete data.
- **Memory Import**: Tests `import_training_examples()` with roundtrip validation.
- **Personality Export**: Tests `export_profile()` contains all fields.
- **Personality Import**: Tests merge mode (adds to existing) and replace mode (full reset).
- **Format Validation**: Verifies JSON serialization and format versioning.

---

## 🏃 Method of Execution

### Running Backend Tests

```bash
# Run all tests
pytest backend/tests/ -v

# Run with coverage report
pytest backend/tests/ --cov=backend/services --cov-report=term-missing

# Run specific suite
pytest backend/tests/test_auth.py -v
```

### Running Frontend Tests

```bash
cd frontend-react
npm test
```

### E2E Tests (Playwright)

```bash
cd frontend-react
npx playwright test
```

---

## 🔧 Mocking Strategy

We use `unittest.mock` and `vitest.vi` extensively to avoid external API calls.

**Backend Mocking:**

```python
@patch('services.llm_service.generate_response')
def test_chat(mock_generate):
    mock_generate.return_value = "Mocked AI response"
```

**Frontend Mocking:**

```typescript
global.fetch = vi.fn(() => Promise.resolve({
    json: () => Promise.resolve({ success: true })
}));
```
