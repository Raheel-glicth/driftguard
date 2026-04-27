from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from driftguard.models import TraceFeedback
from driftguard.sdk import DriftGuard


def create_dashboard_router(guard: DriftGuard) -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def home() -> str:
        return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>DriftGuard Demo Hub</title>
  <style>
    :root {
      --bg: #f4ecdf;
      --panel: rgba(255, 250, 242, 0.92);
      --line: rgba(31, 41, 51, 0.12);
      --text: #1f2933;
      --muted: #52606d;
      --accent: #0f766e;
      --accent-strong: #0b5d57;
      --danger: #b91c1c;
      --shadow: 0 22px 60px rgba(31, 41, 51, 0.1);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at 12% 15%, rgba(15, 118, 110, 0.14), transparent 24%),
        radial-gradient(circle at 88% 0%, rgba(185, 28, 28, 0.08), transparent 20%),
        linear-gradient(180deg, #fff7eb 0%, var(--bg) 100%);
    }
    .page {
      width: min(1180px, calc(100% - 40px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }
    header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 28px;
    }
    .brand {
      display: flex;
      flex-direction: column;
      gap: 4px;
    }
    .eyebrow {
      text-transform: uppercase;
      letter-spacing: 0.16em;
      font-size: 0.8rem;
      color: var(--muted);
    }
    .brand strong {
      font-size: 1.35rem;
    }
    .links {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .link-pill {
      text-decoration: none;
      color: var(--text);
      padding: 10px 16px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      font-weight: 700;
    }
    .hero {
      display: grid;
      grid-template-columns: minmax(0, 1.2fr) minmax(320px, 0.8fr);
      gap: 22px;
      margin-bottom: 22px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 26px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }
    .hero-copy {
      padding: 34px;
    }
    .hero-copy h1 {
      margin: 0 0 14px;
      font-size: clamp(2.4rem, 6vw, 4.4rem);
      line-height: 0.96;
      letter-spacing: 0.02em;
    }
    .hero-copy p {
      margin: 0 0 18px;
      font-size: 1.05rem;
      line-height: 1.6;
      color: var(--muted);
      max-width: 56ch;
    }
    .cta-row {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      margin-top: 18px;
    }
    .cta {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      text-decoration: none;
      border-radius: 999px;
      padding: 13px 18px;
      font-weight: 700;
      border: 1px solid transparent;
    }
    .cta.primary {
      background: linear-gradient(135deg, var(--accent-strong), #14b8a6);
      color: white;
    }
    .cta.secondary {
      color: var(--text);
      border-color: var(--line);
      background: rgba(255, 255, 255, 0.82);
    }
    .hero-side {
      padding: 22px;
      display: grid;
      gap: 14px;
      align-content: start;
    }
    .stat {
      border-radius: 18px;
      border: 1px solid var(--line);
      padding: 16px 18px;
      background: rgba(255, 255, 255, 0.78);
    }
    .stat-label {
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      font-size: 0.78rem;
      margin-bottom: 8px;
    }
    .stat strong {
      display: block;
      font-size: 1.75rem;
      margin-bottom: 4px;
    }
    .status-ok {
      color: var(--accent-strong);
      font-weight: 700;
    }
    .status-warn {
      color: var(--danger);
      font-weight: 700;
    }
    .options {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 22px;
    }
    .option {
      padding: 26px;
      display: flex;
      flex-direction: column;
      gap: 14px;
      min-height: 260px;
    }
    .option h2 {
      margin: 0;
      font-size: 1.7rem;
    }
    .option p {
      margin: 0;
      color: var(--muted);
      line-height: 1.6;
    }
    .feature-list {
      display: grid;
      gap: 8px;
      color: var(--text);
      font-size: 0.98rem;
    }
    .feature {
      padding: 11px 13px;
      border-radius: 14px;
      background: rgba(255, 255, 255, 0.75);
      border: 1px solid var(--line);
    }
    @media (max-width: 900px) {
      .hero, .options { grid-template-columns: 1fr; }
      .page { width: min(100% - 28px, 1180px); }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <div class="page">
    <header>
      <div class="brand">
        <div class="eyebrow">LLM Safety Demo</div>
        <strong>DriftGuard Project Hub</strong>
      </div>
      <div class="links">
        <a class="link-pill" href="/chat">Live Chat Demo</a>
        <a class="link-pill" href="/reports">DriftGuard Reports</a>
      </div>
    </header>

    <section class="hero">
      <article class="panel hero-copy">
        <div class="eyebrow">One Project, Two Views</div>
        <h1>Chat with the bot. Inspect the risk report.</h1>
        <p>
          This project now has a clean demo flow for presentations: one option opens a live chatbot,
          and the other opens the DriftGuard monitoring report with recent traces, trust score trends,
          and flagged requests.
        </p>
        <p>
          Use the chatbot to create real examples, then open the report view to show how DriftGuard
          scores prompt injection, semantic drift, and trust in the same pipeline.
        </p>
        <div class="cta-row">
          <a class="cta primary" href="/chat">Open Live Chat</a>
          <a class="cta secondary" href="/reports">Open Report Dashboard</a>
        </div>
      </article>

      <aside class="panel hero-side">
        <div class="stat">
          <div class="stat-label">Service Health</div>
          <strong id="health-status">Loading</strong>
          <div id="health-note">Checking detector readiness...</div>
        </div>
        <div class="stat">
          <div class="stat-label">Total Requests</div>
          <strong id="total-requests">--</strong>
          <div id="flag-summary">Collecting dashboard stats...</div>
        </div>
        <div class="stat">
          <div class="stat-label">Average Trust</div>
          <strong id="avg-trust">--</strong>
          <div id="drift-summary">Waiting for trace analytics...</div>
        </div>
      </aside>
    </section>

    <section class="options">
      <article class="panel option">
        <div class="eyebrow">Option 1</div>
        <h2>Live Chatbot Demo</h2>
        <p>
          Talk to the bot in real time and generate project examples on the spot.
          Each reply creates a DriftGuard trace behind the scenes.
        </p>
        <div class="feature-list">
          <div class="feature">Browser chat interface for quick demos</div>
          <div class="feature">OpenAI-backed responses with your configured model</div>
          <div class="feature">Per-message trace id and trust metrics</div>
        </div>
        <div class="cta-row">
          <a class="cta primary" href="/chat">Start Chatting</a>
        </div>
      </article>

      <article class="panel option">
        <div class="eyebrow">Option 2</div>
        <h2>DriftGuard Report View</h2>
        <p>
          Open the monitoring page to show recent traces, flagged prompts, trust score changes,
          and the raw report data generated by your pipeline.
        </p>
        <div class="feature-list">
          <div class="feature">Recent trace table with auto refresh</div>
          <div class="feature">Stats cards for request volume and trust</div>
          <div class="feature">Focused report mode for a selected trace</div>
        </div>
        <div class="cta-row">
          <a class="cta secondary" href="/reports">View Reports</a>
        </div>
      </article>
    </section>
  </div>

  <script>
    async function loadHubStats() {
      try {
        const [statsRes, healthRes] = await Promise.all([
          fetch('/stats'),
          fetch('/health'),
        ]);
        const stats = await statsRes.json();
        const health = await healthRes.json();

        document.getElementById('health-status').textContent = health.status === 'ok' ? 'Ready' : 'Offline';
        document.getElementById('health-status').className = health.status === 'ok' ? 'status-ok' : 'status-warn';
        document.getElementById('health-note').textContent = health.detector_ready
          ? `Detector ready with baseline size ${health.baseline_size}.`
          : 'Detector is still warming up.';

        document.getElementById('total-requests').textContent = String(stats.total_requests);
        document.getElementById('flag-summary').textContent = `${stats.flagged_count} flagged requests recorded.`;
        document.getElementById('avg-trust').textContent = stats.avg_trust_score.toFixed(3);
        document.getElementById('drift-summary').textContent = `Injection rate ${stats.injection_rate.toFixed(3)} | Drift rate ${stats.drift_rate.toFixed(3)}`;
      } catch (error) {
        document.getElementById('health-status').textContent = 'Unavailable';
        document.getElementById('health-status').className = 'status-warn';
        document.getElementById('health-note').textContent = 'Could not load status right now.';
        document.getElementById('flag-summary').textContent = 'Stats are not available yet.';
        document.getElementById('drift-summary').textContent = 'Try refreshing after the server is fully started.';
      }
    }

    loadHubStats();
  </script>
</body>
</html>
        """

    @router.get("/reports", response_class=HTMLResponse)
    @router.get("/dashboard", response_class=HTMLResponse)
    async def dashboard() -> str:
        return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>DriftGuard Reports</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f1e8;
      --panel: #fffaf2;
      --text: #1f2933;
      --muted: #52606d;
      --accent: #0f766e;
      --danger: #b91c1c;
      --line: rgba(31, 41, 51, 0.08);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Times New Roman", serif;
      background: radial-gradient(circle at top, #fff7e6, #efe7d8 70%);
      color: var(--text);
    }
    header {
      padding: 24px 32px;
      background: rgba(255,255,255,0.65);
      backdrop-filter: blur(12px);
      border-bottom: 1px solid rgba(15,118,110,0.15);
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 16px;
      flex-wrap: wrap;
    }
    h1 {
      margin: 0 0 6px;
      letter-spacing: 0.04em;
    }
    header p {
      margin: 0;
      color: var(--muted);
    }
    header a {
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
    }
    .nav {
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
    }
    .nav a {
      padding: 10px 14px;
      border-radius: 999px;
      border: 1px solid rgba(15,118,110,0.15);
      background: rgba(255,255,255,0.78);
    }
    main { padding: 24px 32px; }
    .meta {
      display: flex;
      gap: 16px;
      margin: 0 0 18px;
      flex-wrap: wrap;
    }
    .card, .focus-card {
      padding: 16px 18px;
      background: rgba(255,250,242,0.92);
      border: 1px solid rgba(15,118,110,0.1);
      border-radius: 14px;
    }
    .card {
      min-width: 160px;
    }
    .focus-card {
      margin-bottom: 20px;
      display: none;
      box-shadow: 0 14px 40px rgba(31,41,51,0.08);
    }
    .focus-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 14px;
      margin-top: 14px;
    }
    .focus-grid pre {
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: "Courier New", monospace;
      font-size: 0.9rem;
      line-height: 1.5;
    }
    .pill {
      display: inline-block;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 0.85rem;
      font-weight: 700;
      background: rgba(15,118,110,0.12);
      color: var(--accent);
    }
    .flagged { color: var(--danger); font-weight: 700; }
    .ok { color: var(--accent); font-weight: 700; }
    table {
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border-radius: 16px;
      overflow: hidden;
      box-shadow: 0 14px 40px rgba(31,41,51,0.08);
    }
    th, td {
      padding: 12px 14px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
    }
    th {
      font-size: 0.9rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    tr.highlight {
      background: rgba(15,118,110,0.08);
    }
    .trace-link {
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }
    @media (max-width: 900px) {
      .focus-grid { grid-template-columns: 1fr; }
      main { padding: 18px; }
      header { padding: 18px; }
    }
  </style>
</head>
<body>
  <header>
    <div>
      <h1>DriftGuard Reports</h1>
      <p>Recent LLM traces refresh every 10 seconds. Open the chat demo to generate live examples.</p>
    </div>
    <div class="nav">
      <a href="/">Project Hub</a>
      <a href="/chat">Live Chat Demo</a>
    </div>
  </header>
  <main>
    <section class="focus-card" id="focus-card">
      <div class="pill">Focused Trace Report</div>
      <h2 id="focus-title">Selected trace</h2>
      <div id="focus-summary">Loading selected trace...</div>
      <div class="focus-grid">
        <div>
          <h3>Prompt</h3>
          <pre id="focus-prompt"></pre>
        </div>
        <div>
          <h3>Response</h3>
          <pre id="focus-response"></pre>
        </div>
      </div>
    </section>

    <section class="meta" id="stats"></section>
    <table>
      <thead>
        <tr>
          <th>Time</th>
          <th>Model</th>
          <th>Trust</th>
          <th>Injection</th>
          <th>Drift</th>
          <th>Status</th>
          <th>Trace</th>
          <th>Prompt</th>
        </tr>
      </thead>
      <tbody id="trace-rows"></tbody>
    </table>
  </main>
  <script>
    const focusTraceId = new URLSearchParams(window.location.search).get('trace_id');

    async function loadFocusTrace() {
      if (!focusTraceId) {
        return;
      }

      const response = await fetch(`/traces/${focusTraceId}`);
      if (!response.ok) {
        return;
      }

      const trace = await response.json();
      const card = document.getElementById('focus-card');
      card.style.display = 'block';
      document.getElementById('focus-title').textContent = `Trace ${trace.trace_id}`;
      document.getElementById('focus-summary').innerHTML = `
        <span class="${trace.flagged ? 'flagged' : 'ok'}">${trace.flagged ? 'Flagged' : 'OK'}</span>
        | Model ${trace.model}
        | Trust ${trace.trust_score.toFixed(3)}
        | Injection ${trace.injection_score.toFixed(3)}
        | Drift ${trace.drift_score.toFixed(3)}
        | Hallucination ${trace.hallucination_risk.toFixed(3)}
      `;
      document.getElementById('focus-prompt').textContent = trace.prompt;
      document.getElementById('focus-response').textContent = trace.response;
    }

    async function refresh() {
      const [tracesRes, statsRes] = await Promise.all([
        fetch('/traces?limit=20'),
        fetch('/stats'),
      ]);
      const traces = await tracesRes.json();
      const stats = await statsRes.json();

      document.getElementById('stats').innerHTML = `
        <div class="card"><strong>${stats.total_requests}</strong><br/>Total Requests</div>
        <div class="card"><strong>${stats.flagged_count}</strong><br/>Flagged</div>
        <div class="card"><strong>${stats.avg_trust_score.toFixed(3)}</strong><br/>Avg Trust</div>
      `;

      document.getElementById('trace-rows').innerHTML = traces.map((trace) => `
        <tr class="${trace.trace_id === focusTraceId ? 'highlight' : ''}">
          <td>${new Date(trace.timestamp).toLocaleString()}</td>
          <td>${trace.model}</td>
          <td>${trace.trust_score.toFixed(3)}</td>
          <td>${trace.injection_score.toFixed(3)}</td>
          <td>${trace.drift_score.toFixed(3)}</td>
          <td class="${trace.flagged ? 'flagged' : 'ok'}">${trace.flagged ? 'Flagged' : 'OK'}</td>
          <td><a class="trace-link" href="/reports?trace_id=${trace.trace_id}">${trace.trace_id.slice(0, 8)}</a></td>
          <td>${trace.prompt.slice(0, 120)}</td>
        </tr>
      `).join('');
    }

    loadFocusTrace();
    refresh();
    setInterval(refresh, 10000);
  </script>
</body>
</html>
        """

    @router.get("/traces")
    async def list_traces(limit: int = 50, offset: int = 0, flagged_only: bool = False):
        return await guard.db.list_traces(limit=limit, offset=offset, flagged_only=flagged_only)

    @router.get("/stats")
    async def stats():
        return await guard.db.get_stats()

    @router.get("/traces/{trace_id}")
    async def get_trace(trace_id: str):
        trace = await guard.db.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        return trace

    @router.get("/health")
    async def health():
        detector_ready = await guard.drift_detector.ready()
        return {
            "status": "ok",
            "baseline_size": guard.drift_detector.baseline_size,
            "detector_ready": detector_ready,
        }

    @router.post("/traces/{trace_id}/feedback")
    async def add_feedback(trace_id: str, feedback: TraceFeedback):
        trace = await guard.db.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found")
        await guard.db.add_feedback(trace_id, feedback)
        await guard.db.update_trace_metadata(trace_id, {"feedback": feedback.model_dump()})
        return {"status": "stored", "trace_id": trace_id}

    return router
