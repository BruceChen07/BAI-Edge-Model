# Debug Session: ollama-timeout
- **Status**: [OPEN]
- **Issue**: Ollama requests are timing out during backend chat calls, and the current backend logging is insufficient to locate the root cause.
- **Debug Server**: pending
- **Log File**: .dbg/trae-debug-log-ollama-timeout.ndjson

## Reproduction Steps
1. Start backend service.
2. Trigger chat completion against local Ollama from the frontend or API.
3. Observe timeout or delayed failure from the backend.

## Hypotheses & Verification
| ID | Hypothesis | Likelihood | Effort | Evidence |
|----|------------|------------|--------|----------|
| A | Ollama service is not healthy or is unreachable from the backend process. | High | Low | Rejected |
| B | Request timeout configuration is too aggressive for currently selected models or hardware load. | High | Low | Confirmed |
| C | Request payload or model selection causes long-running generation before the first response. | Medium | Medium | Confirmed |
| D | Backend lacks end-to-end request logging, so the real exception path is being swallowed or rethrown without context. | High | Low | Confirmed |
| E | Host resource contention or model cold start causes excessive latency and eventual timeout. | Medium | Medium | Partially confirmed |

## Log Evidence
- `.dbg/trae-debug-log-ollama-timeout.ndjson:2-3` shows `GET /api/tags` succeeds with `200`, so local Ollama service is reachable.
- `.dbg/trae-debug-log-ollama-timeout.ndjson:4-5` shows `qwen3.5:9b` completes in `29119.04ms`.
- `.dbg/trae-debug-log-ollama-timeout.ndjson:9` records `gemma4:12b` chat request with `timeout_seconds=120.0`.
- `.dbg/trae-debug-log-ollama-timeout.ndjson:12` shows `gemma4:12b` failed after `120269.85ms` with full `httpx/httpcore` timeout stack.
- `.dbg/trae-debug-log-ollama-timeout.ndjson:13` shows the API layer only surfaces `timed out`, proving the previous logging path lacked contextual diagnostics.
- Runtime command evidence: `ollama ps` showed `gemma4:12b` running on `100% CPU`.
- Post-fix runtime evidence: with `OLLAMA_READ_TIMEOUT_SECONDS=300`, `gemma4:12b` returned `200` in `115114.16ms`.
- Post-fix timeout simulation: with `OLLAMA_READ_TIMEOUT_SECONDS=5`, `qwen3.5:9b` returned `502` in `6670.61ms`, and `/api/v1/logs?module=ollama` returned `ollama.chat.failed` entries containing timeout config, request payload, elapsed time, and exception stack.

## Verification Conclusion
- Root cause is not connectivity. The primary failure is a model-latency vs timeout mismatch on CPU-heavy models, amplified by insufficient structured logging around third-party calls.
- Implemented fix: configurable Ollama timeout handling and full structured backend logging with persistence, rotation, request trace ID, and module-level filtering.
- Pending user confirmation: keep debug session open until the user verifies the fix path in their own environment.
