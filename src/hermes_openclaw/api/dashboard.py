"""Security dashboard — demo UI for presentations and audits."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from hermes_openclaw.security.audit import AuditLogger
from hermes_openclaw.security.rate_limiter import ExecutionRateLimiter

_DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>HermesClaw — Security Dashboard</title>
  <style>
    body { font-family: system-ui, sans-serif; background: #0f172a; color: #e2e8f0; margin: 0; padding: 2rem; }
    h1 { color: #38bdf8; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
    .card { background: #1e293b; border-radius: 8px; padding: 1rem; border: 1px solid #334155; }
    .card h2 { margin-top: 0; color: #94a3b8; font-size: 0.9rem; text-transform: uppercase; }
    .ok { color: #4ade80; } .warn { color: #fbbf24; } .err { color: #f87171; }
    pre { background: #0f172a; padding: 0.75rem; border-radius: 4px; overflow-x: auto; font-size: 0.8rem; }
    .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem; background: #334155; }
  </style>
</head>
<body>
  <h1>Security Dashboard</h1>
  <p>A security-first open-source local AI agent framework</p>
  <div class="grid">
    <div class="card"><h2>Rate Limits</h2><div id="limits">Loading...</div></div>
    <div class="card"><h2>Audit Chain</h2><div id="chain">Loading...</div></div>
    <div class="card"><h2>Recent Audit Events</h2><pre id="events">Loading...</pre></div>
    <div class="card"><h2>Security Levels</h2>
      <p><span class="badge">Safe</span> Read-only</p>
      <p><span class="badge">Elevated</span> File modifications</p>
      <p><span class="badge">Dangerous</span> Desktop control</p>
      <p><span class="badge">Critical</span> Terminal / network</p>
    </div>
  </div>
  <script>
    fetch('/api/dashboard/state').then(r => r.json()).then(d => {
      document.getElementById('limits').innerHTML =
        `Actions/min: <b>${d.rate_limits.actions_last_minute}</b> / ${d.rate_limits.max_actions_per_minute}<br>` +
        `Parallel tasks: <b>${d.rate_limits.active_tasks}</b> / ${d.rate_limits.max_parallel_tasks}`;
      const chainOk = d.audit_chain.valid;
      document.getElementById('chain').innerHTML =
        `<span class="${chainOk ? 'ok' : 'err'}">${d.audit_chain.message}</span>`;
      document.getElementById('events').textContent =
        JSON.stringify(d.recent_events.slice(-10), null, 2);
    });
  </script>
</body>
</html>"""


def create_dashboard_router(
    audit: AuditLogger,
    rate_limiter: ExecutionRateLimiter,
) -> APIRouter:
    router = APIRouter()

    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard_page() -> str:
        return _DASHBOARD_HTML

    @router.get("/api/dashboard/state")
    async def dashboard_state() -> dict[str, Any]:
        valid, message = audit.verify_chain()
        return {
            "rate_limits": {
                "actions_last_minute": rate_limiter.actions_last_minute,
                "max_actions_per_minute": rate_limiter.config.max_actions_per_minute,
                "active_tasks": rate_limiter.active_tasks,
                "max_parallel_tasks": rate_limiter.config.max_parallel_tasks,
            },
            "audit_chain": {"valid": valid, "message": message},
            "recent_events": audit.read_all()[-20:],
            "tagline": "A security-first open-source local AI agent framework",
        }

    return router
