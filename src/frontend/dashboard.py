"""FastAPI dashboard — control center for Relay.

Provides a small JSON API plus a single static HTML page so the user
can browse reminders, notes, calendar events, the activity log, and
pending actions, and can mark items complete or send commands through
Relay.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ImportError as exc:  # pragma: no cover - exercised only when missing
    raise ImportError(
        "FastAPI is required for the dashboard. Install with `pip install "
        "fastapi uvicorn`."
    ) from exc

from ..core.orchestrator import RelayOrchestrator


class CommandRequest(BaseModel):
    text: str
    source: str = "web"


class ConfirmRequest(BaseModel):
    action_id: Optional[str] = None


def create_app(orchestrator: Optional[RelayOrchestrator] = None) -> FastAPI:
    """Build the FastAPI app, wiring in the given orchestrator."""
    relay = orchestrator or RelayOrchestrator()
    app = FastAPI(title="Relay Dashboard", version="0.1.0")

    static_dir = Path(__file__).parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(_DASHBOARD_HTML)

    @app.get("/api/state")
    def state() -> Dict[str, Any]:
        return {
            "reminders": [r.to_public() for r in relay.reminders.list_active(limit=50)],
            "notes": [n.to_public() for n in relay.notes.list_recent(limit=50)],
            "events": [e.to_public() for e in relay.calendar.list_upcoming(limit=50)],
            "logs": [le.to_public() for le in relay.logs.list_recent(limit=100)],
            "pending": [p.to_public() for p in relay.pending_actions.list_pending(limit=20)],
        }

    @app.get("/api/reminders")
    def list_reminders(active: bool = True) -> List[Dict[str, Any]]:
        items = relay.reminders.list_active(limit=200) if active \
            else relay.reminders.list_all(limit=200)
        return [r.to_public() for r in items]

    @app.post("/api/reminders/{reminder_id}/complete")
    def complete_reminder(reminder_id: str) -> Dict[str, Any]:
        ok = relay.reminders.mark_completed(reminder_id)
        if not ok:
            raise HTTPException(status_code=404, detail="reminder not found")
        return {"status": "ok"}

    @app.delete("/api/reminders/{reminder_id}")
    def delete_reminder(reminder_id: str) -> Dict[str, Any]:
        ok = relay.reminders.delete(reminder_id)
        if not ok:
            raise HTTPException(status_code=404, detail="reminder not found")
        return {"status": "ok"}

    @app.get("/api/notes")
    def list_notes() -> List[Dict[str, Any]]:
        return [n.to_public() for n in relay.notes.list_recent(limit=200)]

    @app.delete("/api/notes/{note_id}")
    def delete_note(note_id: str) -> Dict[str, Any]:
        if not relay.notes.delete(note_id):
            raise HTTPException(status_code=404, detail="note not found")
        return {"status": "ok"}

    @app.get("/api/calendar")
    def list_calendar() -> List[Dict[str, Any]]:
        return [e.to_public() for e in relay.calendar.list_upcoming(limit=200)]

    @app.delete("/api/calendar/{event_id}")
    def delete_event(event_id: str) -> Dict[str, Any]:
        if not relay.calendar.delete(event_id):
            raise HTTPException(status_code=404, detail="event not found")
        return {"status": "ok"}

    @app.get("/api/logs")
    def list_logs(limit: int = 200) -> List[Dict[str, Any]]:
        return [le.to_public() for le in relay.logs.list_recent(limit=limit)]

    @app.get("/api/pending")
    def list_pending() -> List[Dict[str, Any]]:
        return [p.to_public() for p in relay.pending_actions.list_pending(limit=50)]

    @app.post("/api/command")
    def post_command(payload: CommandRequest) -> Dict[str, Any]:
        reply = relay.process_input(payload.text, source=payload.source)
        return {"reply": reply}

    @app.post("/api/confirm")
    def post_confirm(payload: ConfirmRequest) -> Dict[str, Any]:
        reply = relay.confirm_pending(payload.action_id)
        return {"reply": reply}

    @app.post("/api/cancel")
    def post_cancel(payload: ConfirmRequest) -> Dict[str, Any]:
        reply = relay.cancel_pending(payload.action_id)
        return {"reply": reply}

    return app


_DASHBOARD_HTML = """<!doctype html>
<html lang=\"en\">
<head>
<meta charset=\"utf-8\" />
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
<title>Relay</title>
<style>
  :root { color-scheme: dark; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Inter', sans-serif;
         margin: 0; background: #0e0f12; color: #e7e9ee; }
  header { padding: 14px 20px; border-bottom: 1px solid #1f2227;
           display: flex; gap: 14px; align-items: center; }
  header h1 { font-size: 16px; margin: 0; font-weight: 600; letter-spacing: 0.4px; }
  header .muted { color: #8b909a; font-size: 12px; }
  main { display: grid; grid-template-columns: 1.1fr 1fr 1fr; gap: 18px;
          padding: 20px; }
  section { background: #131519; border: 1px solid #1f2227; border-radius: 12px;
            padding: 14px 16px; }
  section h2 { font-size: 13px; margin: 0 0 10px; color: #c4c8d0;
                text-transform: uppercase; letter-spacing: 0.6px; }
  .row { padding: 8px 0; border-bottom: 1px solid #1c1f24; font-size: 13px; }
  .row:last-child { border-bottom: none; }
  .meta { color: #7a808b; font-size: 11px; margin-top: 2px; }
  .pill { font-size: 10px; padding: 1px 6px; border-radius: 6px;
           background: #1d2128; color: #aab0bb; margin-right: 6px; }
  .pill.warn { background: #3a2a14; color: #f1c47e; }
  .pill.ok { background: #14321f; color: #7ee0a8; }
  .pill.err { background: #3a1717; color: #f08585; }
  form { display: flex; gap: 8px; padding: 14px 20px; border-top: 1px solid #1f2227;
          background: #0b0c0e; position: sticky; bottom: 0; }
  input[type=text] { flex: 1; background: #15171c; border: 1px solid #262931;
                       color: #e7e9ee; padding: 10px 12px; border-radius: 8px;
                       font-size: 14px; }
  button { background: #2c64ff; color: white; border: none; padding: 10px 16px;
            border-radius: 8px; font-size: 13px; cursor: pointer; }
  button.secondary { background: #2a2d34; color: #c4c8d0; }
  .reply { padding: 12px 20px; color: #b7bcc6; font-size: 13px;
           border-top: 1px solid #1f2227; min-height: 18px; }
  .actions { float: right; }
  .actions button { padding: 4px 10px; font-size: 11px; margin-left: 4px; }
  @media (max-width: 1080px) { main { grid-template-columns: 1fr; } }
</style>
</head>
<body>
<header>
  <h1>RELAY</h1>
  <span class=\"muted\">control center</span>
  <span class=\"muted\" id=\"updated\"></span>
</header>
<main>
  <section>
    <h2>Reminders</h2>
    <div id=\"reminders\"></div>
  </section>
  <section>
    <h2>Notes</h2>
    <div id=\"notes\"></div>
  </section>
  <section>
    <h2>Calendar</h2>
    <div id=\"calendar\"></div>
  </section>
  <section>
    <h2>Pending Actions</h2>
    <div id=\"pending\"></div>
  </section>
  <section style=\"grid-column: 1 / -1\">
    <h2>Activity</h2>
    <div id=\"logs\"></div>
  </section>
</main>
<div class=\"reply\" id=\"reply\"></div>
<form id=\"cmd\">
  <input id=\"cmdText\" type=\"text\" placeholder=\"Tell Relay something — e.g. 'remind me to submit the form at 6'\" autocomplete=\"off\" />
  <button type=\"submit\">Send</button>
  <button type=\"button\" class=\"secondary\" id=\"confirmBtn\">Confirm</button>
  <button type=\"button\" class=\"secondary\" id=\"cancelBtn\">Cancel</button>
</form>
<script>
async function fetchState() {
  const res = await fetch('/api/state');
  const data = await res.json();
  render(data);
  document.getElementById('updated').textContent =
    'updated ' + new Date().toLocaleTimeString();
}

function escapeHtml(s) {
  return (s || '').replace(/[&<>"']/g, c => ({
    '&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'
  }[c]));
}

function render(data) {
  const r = document.getElementById('reminders');
  r.innerHTML = (data.reminders || []).map(item => `
    <div class=\"row\">
      <div class=\"actions\">
        <button class=\"secondary\" onclick=\"complete('${item.id}')\">Done</button>
        <button class=\"secondary\" onclick=\"delReminder('${item.id}')\">Delete</button>
      </div>
      ${escapeHtml(item.text)}
      <div class=\"meta\">${item.remind_at ? 'at ' + item.remind_at : 'anytime'}</div>
    </div>`).join('') || '<div class=\"meta\">no active reminders</div>';

  const n = document.getElementById('notes');
  n.innerHTML = (data.notes || []).map(item => `
    <div class=\"row\">
      <div class=\"actions\">
        <button class=\"secondary\" onclick=\"delNote('${item.id}')\">Delete</button>
      </div>
      ${escapeHtml(item.content)}
      <div class=\"meta\">${item.created_at}</div>
    </div>`).join('') || '<div class=\"meta\">no notes yet</div>';

  const c = document.getElementById('calendar');
  c.innerHTML = (data.events || []).map(item => `
    <div class=\"row\">
      <div class=\"actions\">
        <button class=\"secondary\" onclick=\"delEvent('${item.id}')\">Delete</button>
      </div>
      ${escapeHtml(item.title)}
      <div class=\"meta\">${item.start_time || ''}</div>
    </div>`).join('') || '<div class=\"meta\">no upcoming events</div>';

  const p = document.getElementById('pending');
  p.innerHTML = (data.pending || []).map(item => `
    <div class=\"row\">
      <span class=\"pill warn\">${item.tool_name}</span>
      ${escapeHtml(item.preview || '(no preview)')}
      <div class=\"meta\">${item.id} · ${item.created_at}</div>
    </div>`).join('') || '<div class=\"meta\">nothing waiting</div>';

  const logs = document.getElementById('logs');
  logs.innerHTML = (data.logs || []).map(item => {
    const cls = item.kind && item.kind.includes('failed') ? 'err'
      : item.kind && item.kind.includes('succeeded') ? 'ok' : '';
    return `<div class=\"row\"><span class=\"pill ${cls}\">${item.kind}</span>
              ${escapeHtml(item.content || '')}
              <div class=\"meta\">${item.source || ''} · ${item.created_at}</div></div>`;
  }).join('') || '<div class=\"meta\">no activity yet</div>';
}

async function send(path, body) {
  const res = await fetch(path, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body || {}),
  });
  const data = await res.json();
  document.getElementById('reply').textContent = data.reply || '';
  fetchState();
}

document.getElementById('cmd').addEventListener('submit', e => {
  e.preventDefault();
  const text = document.getElementById('cmdText').value.trim();
  if (!text) return;
  send('/api/command', { text });
  document.getElementById('cmdText').value = '';
});
document.getElementById('confirmBtn').addEventListener('click', () => send('/api/confirm', {}));
document.getElementById('cancelBtn').addEventListener('click', () => send('/api/cancel', {}));

async function complete(id) {
  await fetch('/api/reminders/' + id + '/complete', { method: 'POST' });
  fetchState();
}
async function delReminder(id) {
  await fetch('/api/reminders/' + id, { method: 'DELETE' });
  fetchState();
}
async function delNote(id) {
  await fetch('/api/notes/' + id, { method: 'DELETE' });
  fetchState();
}
async function delEvent(id) {
  await fetch('/api/calendar/' + id, { method: 'DELETE' });
  fetchState();
}

fetchState();
setInterval(fetchState, 5000);
</script>
</body>
</html>
"""


__all__ = ["create_app"]
