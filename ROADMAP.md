# Roadmap

Security-first development priorities. Features never come before safety.

---

## Phase 0 — Foundation (Current)

**Goal:** Secure architecture, documentation, and contributor infrastructure.

- [x] Structured task schemas (Pydantic)
- [x] Plan validator (trust boundary)
- [x] Path guard (filesystem security)
- [x] Command policy (allowlist only)
- [x] Network policy (offline-first)
- [x] Approval gate (user confirmation)
- [x] Audit logger (append-only, redacted)
- [x] Orchestrator pipeline (validate → approve → execute)
- [x] Dry-run mode
- [x] Execution timeout
- [x] FastAPI endpoint (localhost-only)
- [x] CI pipeline (lint + test)
- [x] Docker support
- [x] Security documentation
- [x] Hermes planner integration (CLI via `hermes -z`)
- [x] OpenClaw executor bridge (gateway API)

---

## Phase 1 — Agent Integration

**Goal:** Connect Hermes and OpenClaw through the secure orchestrator.

- [x] Hermes adapter — invoke planner, receive JSON only
- [x] OpenClaw adapter — gateway API with permission scopes
- [ ] Feedback loop — execution results back to Hermes
- [ ] Retry logic with alternative plans
- [ ] Rollback capability for file operations
- [ ] Integration tests with mock agents

---

## Phase 2 — Hardening

**Goal:** Production-grade security audit and hardening.

- [ ] Plugin sandbox with permission scopes
- [ ] Signed plugin verification
- [ ] Rate limiting on API endpoints
- [ ] Action allowlist configuration file
- [ ] Configurable denied path list
- [ ] Security audit by third party
- [ ] Fuzz testing for plan validator
- [ ] Prompt injection test suite

---

## Phase 3 — Memory & Persistence

**Goal:** Context persistence without compromising privacy.

- [ ] SQLite workflow history (local only)
- [ ] User preference storage
- [ ] Workflow replay from audit logs
- [ ] Optional ChromaDB for semantic recall (local, opt-in)
- [ ] Memory encryption at rest

---

## Phase 4 — Developer Experience

**Goal:** Make this a respected open-source framework.

- [ ] Plugin SDK with typed interfaces
- [ ] CLI interactive mode
- [ ] Web UI (Electron, localhost-only)
- [ ] Architecture diagrams in docs
- [ ] Video demo / tutorial
- [ ] PyPI package publishing
- [ ] Contributor onboarding guide

---

## Phase 5 — Research & Extensions

**Goal:** Academic value and future agent types.

- [ ] Performance benchmarks (latency, accuracy)
- [ ] Comparison with monolithic agent approaches
- [ ] Browser agent (sandboxed)
- [ ] Vision agent (screenshot analysis)
- [ ] Voice interaction agent
- [ ] Research paper draft
- [ ] Conference presentation materials

---

## Non-Goals

These will **never** be prioritized:

- Cloud dependency or telemetry
- Arbitrary shell execution
- Bypassing approval gates in production
- Hidden network calls
- Storing credentials in plaintext
- Auto-executing LLM output without validation

---

## Priority Order

1. **Security**
2. **Reliability**
3. **Transparency**
4. **Maintainability**
5. **Extensibility**
6. **Performance**
7. **Features**

---

## How to Contribute to the Roadmap

Open a [Feature Request issue](.github/ISSUE_TEMPLATE/feature_request.md) describing:

- What you want to build
- Why it matters for security or reliability
- How it fits the architecture

Roadmap items are discussed in issues before implementation begins.
