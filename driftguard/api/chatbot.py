from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from openai import AsyncOpenAI

from driftguard.config import DriftGuardSettings
from driftguard.models import ChatMessage, ChatRequest, ChatResponse
from driftguard.sdk import DriftGuard


class OpenAIChatService:
    def __init__(self, settings: DriftGuardSettings, guard: DriftGuard) -> None:
        self.settings = settings
        self.guard = guard
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if not self.settings.openai_api_key:
            raise HTTPException(
                status_code=503,
                detail="OPENAI_API_KEY is not configured. Set it before using the local chatbot.",
            )
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._client

    async def chat(self, request: ChatRequest) -> ChatResponse:
        client = self._get_client()
        model = request.model or self.settings.chat_model
        system_prompt = request.system_prompt or self.settings.chat_system_prompt

        conversation = self._build_messages(
            system_prompt=system_prompt,
            history=request.history,
            message=request.message,
        )
        trace_prompt = self._render_trace_prompt(conversation)
        metadata = {
            "session_id": request.session_id or "local-browser-chat",
            "source": "local-chatbot",
            **request.metadata,
        }

        async with self.guard.trace(prompt=trace_prompt, model=model, metadata=metadata) as trace:
            response = await client.chat.completions.create(model=model, messages=conversation)
            reply = response.choices[0].message.content or ""
            trace.set_response(reply)

        return ChatResponse(
            reply=reply,
            model=model,
            trace_id=trace.trace_id,
            created_at=datetime.now(timezone.utc),
        )

    def _build_messages(
        self,
        *,
        system_prompt: str,
        history: list[ChatMessage],
        message: str,
    ) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for item in history[-12:]:
            if item.role not in {"user", "assistant", "system"}:
                continue
            messages.append({"role": item.role, "content": item.content})
        messages.append({"role": "user", "content": message})
        return messages

    def _render_trace_prompt(self, messages: list[dict[str, str]]) -> str:
        lines = [f"{message['role'].upper()}: {message['content']}" for message in messages]
        return "\n".join(lines)


def create_chat_router(guard: DriftGuard, settings: DriftGuardSettings | None = None) -> APIRouter:
    router = APIRouter()
    chat_settings = settings or guard.settings
    service = OpenAIChatService(chat_settings, guard)

    @router.get("/chat", response_class=HTMLResponse)
    async def chat_page() -> str:
        default_model = chat_settings.chat_model
        default_system_prompt = chat_settings.chat_system_prompt.replace("`", "'")
        return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>DriftGuard Local Chat</title>
  <style>
    :root {{
      --bg: #efe7db;
      --panel: rgba(255, 250, 242, 0.92);
      --line: rgba(31, 41, 51, 0.12);
      --text: #1f2933;
      --muted: #52606d;
      --accent: #0f766e;
      --accent-soft: #d7f2ee;
      --danger: #b91c1c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 15% 15%, rgba(15, 118, 110, 0.10), transparent 28%),
        radial-gradient(circle at 85% 0%, rgba(185, 28, 28, 0.08), transparent 20%),
        linear-gradient(180deg, #fff8eb 0%, var(--bg) 100%);
    }}
    header {{
      padding: 22px 28px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    header a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 2fr) minmax(320px, 1fr);
      gap: 20px;
      padding: 0 24px 24px;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 22px;
      box-shadow: 0 18px 50px rgba(31, 41, 51, 0.08);
      backdrop-filter: blur(12px);
    }}
    .chat-shell {{
      display: grid;
      grid-template-rows: auto 1fr auto;
      min-height: calc(100vh - 110px);
    }}
    .chat-top {{
      padding: 22px 24px 14px;
      border-bottom: 1px solid var(--line);
    }}
    .chat-top h1 {{
      margin: 0 0 6px;
      font-size: 2rem;
      letter-spacing: 0.03em;
    }}
    .chat-top p {{
      margin: 0;
      color: var(--muted);
    }}
    .messages {{
      padding: 18px 20px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .bubble {{
      max-width: 78%;
      padding: 14px 16px;
      border-radius: 18px;
      line-height: 1.45;
      white-space: pre-wrap;
      animation: fadeUp 180ms ease-out;
    }}
    .user {{
      align-self: flex-end;
      background: linear-gradient(135deg, #0f766e, #14b8a6);
      color: white;
      border-bottom-right-radius: 6px;
    }}
    .assistant {{
      align-self: flex-start;
      background: #fffdf7;
      border: 1px solid rgba(15, 118, 110, 0.18);
      border-bottom-left-radius: 6px;
    }}
    .composer {{
      padding: 18px 20px 20px;
      border-top: 1px solid var(--line);
    }}
    textarea, input {{
      width: 100%;
      border-radius: 16px;
      border: 1px solid rgba(31, 41, 51, 0.15);
      background: rgba(255,255,255,0.85);
      padding: 12px 14px;
      font: inherit;
      color: inherit;
    }}
    textarea {{
      min-height: 110px;
      resize: vertical;
    }}
    .controls {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 12px;
      margin-bottom: 12px;
    }}
    .actions {{
      margin-top: 12px;
      display: flex;
      gap: 12px;
      align-items: center;
    }}
    button {{
      border: 0;
      border-radius: 999px;
      padding: 12px 18px;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: linear-gradient(135deg, #0f766e, #14b8a6);
      color: white;
    }}
    button.secondary {{
      background: white;
      color: var(--text);
      border: 1px solid var(--line);
    }}
    .side {{
      padding: 20px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }}
    .metric {{
      padding: 14px 16px;
      border-radius: 16px;
      background: rgba(255,255,255,0.75);
      border: 1px solid var(--line);
    }}
    .metric strong {{
      display: block;
      font-size: 1.2rem;
      margin-bottom: 4px;
    }}
    .status {{
      color: var(--muted);
      font-size: 0.95rem;
    }}
    .status.flagged {{
      color: var(--danger);
      font-weight: 700;
    }}
    .reasons {{
      margin: 8px 0 0;
      padding-left: 18px;
    }}
    .hint {{
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.5;
    }}
    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(6px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 980px) {{
      .layout {{ grid-template-columns: 1fr; }}
      .chat-shell {{ min-height: auto; }}
      .bubble {{ max-width: 92%; }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <div style="font-size:0.9rem;color:#52606d;text-transform:uppercase;letter-spacing:0.16em;">Local AI Chatbot</div>
      <div style="font-size:1.1rem;font-weight:700;">DriftGuard + OpenAI</div>
    </div>
    <div style="display:flex;gap:12px;flex-wrap:wrap;">
      <a href="/">Project Hub</a>
      <a href="/reports">Open DriftGuard Reports</a>
    </div>
  </header>
  <div class="layout">
    <section class="panel chat-shell">
      <div class="chat-top">
        <h1>Chat Locally</h1>
        <p>Every answer is routed through DriftGuard and linked to a trace report.</p>
      </div>
      <div class="messages" id="messages">
        <div class="bubble assistant">Hi. I’m your local browser chatbot. Ask anything, and I’ll show the DriftGuard report for each answer.</div>
      </div>
      <form class="composer" id="chat-form">
        <div class="controls">
          <input id="model" value="{default_model}" />
          <input id="session-id" value="browser-session-001" />
        </div>
        <div style="margin-bottom:12px;">
          <textarea id="system-prompt">{default_system_prompt}</textarea>
        </div>
        <textarea id="message" placeholder="Ask a question, or try a prompt injection attempt to see DriftGuard score it."></textarea>
        <div class="actions">
          <button type="submit">Send Message</button>
          <button class="secondary" type="button" id="clear-chat">Clear Chat</button>
          <span class="status" id="send-status">Ready.</span>
        </div>
      </form>
    </section>
    <aside class="panel side">
      <div class="metric">
        <div style="color:#52606d;text-transform:uppercase;letter-spacing:0.1em;font-size:0.82rem;">Trace</div>
        <strong id="trace-id">No trace yet</strong>
        <div class="status" id="trace-status">Send a message to generate a report.</div>
        <div style="margin-top:10px;">
          <a id="trace-link" href="/reports" style="color:#0f766e;font-weight:700;text-decoration:none;">Open report view</a>
        </div>
      </div>
      <div class="metric">
        <div style="color:#52606d;text-transform:uppercase;letter-spacing:0.1em;font-size:0.82rem;">Trust Score</div>
        <strong id="trust-score">--</strong>
        <div class="status" id="flagged-state">Waiting for trace data</div>
      </div>
      <div class="metric">
        <div style="color:#52606d;text-transform:uppercase;letter-spacing:0.1em;font-size:0.82rem;">Injection / Drift / Hallucination Risk</div>
        <strong id="score-line">--</strong>
        <ul class="reasons" id="flag-reasons"></ul>
      </div>
      <div class="hint">
        Reports come from the same DriftGuard pipeline you already built. If a trace is still processing, this panel will refresh automatically for a few seconds.
      </div>
    </aside>
  </div>
  <script>
    const history = [];
    const form = document.getElementById('chat-form');
    const messages = document.getElementById('messages');
    const statusEl = document.getElementById('send-status');
    const messageEl = document.getElementById('message');
    const traceLinkEl = document.getElementById('trace-link');

    function addBubble(role, content) {{
      const node = document.createElement('div');
      node.className = `bubble ${{role}}`;
      node.textContent = content;
      messages.appendChild(node);
      messages.scrollTop = messages.scrollHeight;
    }}

    function renderTracePending(traceId) {{
      document.getElementById('trace-id').textContent = traceId;
      document.getElementById('trace-status').textContent = 'Waiting for DriftGuard worker...';
      traceLinkEl.href = `/reports?trace_id=${{traceId}}`;
      traceLinkEl.textContent = 'Open selected trace report';
      document.getElementById('trust-score').textContent = '--';
      document.getElementById('score-line').textContent = '--';
      document.getElementById('flagged-state').textContent = 'Processing';
      document.getElementById('flagged-state').className = 'status';
      document.getElementById('flag-reasons').innerHTML = '';
    }}

    async function loadTrace(traceId, attempts = 10) {{
      for (let i = 0; i < attempts; i += 1) {{
        const res = await fetch(`/traces/${{traceId}}`);
        if (res.ok) {{
          const trace = await res.json();
          document.getElementById('trace-id').textContent = trace.trace_id;
          document.getElementById('trace-status').textContent = `Model: ${{trace.model}}`;
          traceLinkEl.href = `/reports?trace_id=${{trace.trace_id}}`;
          traceLinkEl.textContent = 'Open selected trace report';
          document.getElementById('trust-score').textContent = trace.trust_score.toFixed(3);
          document.getElementById('score-line').textContent = `${{trace.injection_score.toFixed(3)}} / ${{trace.drift_score.toFixed(3)}} / ${{trace.hallucination_risk.toFixed(3)}}`;
          const flagged = document.getElementById('flagged-state');
          flagged.textContent = trace.flagged ? 'Flagged' : 'Not flagged';
          flagged.className = trace.flagged ? 'status flagged' : 'status';
          const reasons = document.getElementById('flag-reasons');
          reasons.innerHTML = trace.flag_reasons.length
            ? trace.flag_reasons.map((reason) => `<li>${{reason}}</li>`).join('')
            : '<li>No flag reasons for this trace.</li>';
          return;
        }}
        await new Promise((resolve) => setTimeout(resolve, 700));
      }}
      document.getElementById('trace-status').textContent = 'Trace not available yet. Check the report view.';
    }}

    form.addEventListener('submit', async (event) => {{
      event.preventDefault();
      const message = messageEl.value.trim();
      if (!message) {{
        return;
      }}

      const payload = {{
        message,
        model: document.getElementById('model').value.trim() || null,
        system_prompt: document.getElementById('system-prompt').value.trim() || null,
        session_id: document.getElementById('session-id').value.trim() || null,
        history,
      }};

      addBubble('user', message);
      messageEl.value = '';
      statusEl.textContent = 'Thinking...';

      const response = await fetch('/api/chat', {{
        method: 'POST',
        headers: {{ 'Content-Type': 'application/json' }},
        body: JSON.stringify(payload),
      }});

      if (!response.ok) {{
        const error = await response.json();
        addBubble('assistant', `Error: ${{error.detail || 'Request failed'}}`);
        statusEl.textContent = 'Request failed.';
        return;
      }}

      const data = await response.json();
      addBubble('assistant', data.reply);
      history.push({{ role: 'user', content: message }});
      history.push({{ role: 'assistant', content: data.reply }});
      renderTracePending(data.trace_id);
      statusEl.textContent = `Answered with ${{data.model}}`;
      loadTrace(data.trace_id);
    }});

    document.getElementById('clear-chat').addEventListener('click', () => {{
      history.length = 0;
      messages.innerHTML = '<div class="bubble assistant">Chat cleared. Ask a new question whenever you are ready.</div>';
      document.getElementById('trace-id').textContent = 'No trace yet';
      document.getElementById('trace-status').textContent = 'Send a message to generate a report.';
      traceLinkEl.href = '/reports';
      traceLinkEl.textContent = 'Open report view';
      document.getElementById('trust-score').textContent = '--';
      document.getElementById('score-line').textContent = '--';
      document.getElementById('flagged-state').textContent = 'Waiting for trace data';
      document.getElementById('flagged-state').className = 'status';
      document.getElementById('flag-reasons').innerHTML = '';
    }});
  </script>
</body>
</html>
        """

    @router.post("/api/chat", response_model=ChatResponse)
    async def chat(request: ChatRequest) -> ChatResponse:
        if not request.message.strip():
            raise HTTPException(status_code=400, detail="Message cannot be empty")
        return await service.chat(request)

    return router
