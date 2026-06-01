from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlparse

from research.audio.labels import LABELS, canonical_label

DEFAULT_AUDIT_DIR = Path("data/audio/audits")
DEFAULT_DECISIONS = Path("data/audio/curation/audio_review_decisions.csv")
AUDIO_SUFFIXES = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}
DECISION_COLUMNS = [
    "audit",
    "path",
    "true_label",
    "predicted_label",
    "decision",
    "corrected_label",
    "target_split",
    "reviewer",
    "review_notes",
    "updated_at",
]
VALID_DECISIONS = {"accepted", "relabel", "reject", "unsure", "needs_review", ""}


@dataclass(frozen=True)
class ReviewAppConfig:
    audit_dir: Path
    decisions_path: Path
    repository_root: Path


def run_server(host: str, port: int, config: ReviewAppConfig) -> None:
    handler = _handler(config)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Audio review app: http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


def load_audit_rows(audit_path: Path) -> list[dict[str, str]]:
    with audit_path.open(newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def load_decisions(path: Path) -> dict[tuple[str, str], dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return {(row.get("audit", ""), row.get("path", "")): dict(row) for row in reader}


def save_decision(path: Path, decision: dict[str, str]) -> dict[str, str]:
    decision = _normalize_decision(decision)
    decisions = load_decisions(path)
    decisions[(decision["audit"], decision["path"])] = decision
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=DECISION_COLUMNS)
        writer.writeheader()
        writer.writerows(sorted(decisions.values(), key=lambda row: (row["audit"], row["path"])))
    return decision


def merge_decisions(rows: list[dict[str, str]], decisions: dict[tuple[str, str], dict[str, str]], audit_name: str) -> list[dict[str, str]]:
    merged = []
    for row in rows:
        output = dict(row)
        decision = decisions.get((audit_name, row.get("path", "")), {})
        output["review_decision"] = decision.get("decision", "")
        output["corrected_label"] = decision.get("corrected_label", "")
        output["target_split"] = decision.get("target_split", "")
        output["reviewer"] = decision.get("reviewer", "")
        output["review_notes"] = decision.get("review_notes", "")
        output["updated_at"] = decision.get("updated_at", "")
        merged.append(output)
    return merged


def filter_rows(rows: list[dict[str, str]], filters: dict[str, str]) -> list[dict[str, str]]:
    output = rows
    for key in ["split", "source", "true_label", "predicted_label", "error_type", "review_priority", "review_decision"]:
        value = filters.get(key, "")
        if value:
            output = [row for row in output if row.get(key, "") == value]
    query = filters.get("q", "").strip().lower()
    if query:
        output = [
            row
            for row in output
            if query in row.get("path", "").lower()
            or query in row.get("notes", "").lower()
            or query in row.get("source", "").lower()
        ]
    return output


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    total = len(rows)
    errors = sum(row.get("is_error") == "1" for row in rows)
    reviewed = sum(bool(row.get("review_decision")) for row in rows)
    by_error_type: dict[str, int] = {}
    by_label: dict[str, int] = {}
    for row in rows:
        by_error_type[row.get("error_type", "")] = by_error_type.get(row.get("error_type", ""), 0) + 1
        by_label[row.get("true_label", "")] = by_label.get(row.get("true_label", ""), 0) + 1
    return {
        "total": total,
        "errors": errors,
        "reviewed": reviewed,
        "by_error_type": by_error_type,
        "by_label": by_label,
    }


def _normalize_decision(decision: dict[str, str]) -> dict[str, str]:
    normalized = {column: str(decision.get(column, "")).strip() for column in DECISION_COLUMNS}
    if normalized["decision"] not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of {sorted(VALID_DECISIONS)}")
    if normalized["corrected_label"]:
        normalized["corrected_label"] = canonical_label(normalized["corrected_label"])
    if normalized["target_split"] not in {"", "train", "val", "test"}:
        raise ValueError("target_split must be train, val, test, or blank")
    if not normalized["updated_at"]:
        normalized["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return normalized


def _handler(config: ReviewAppConfig):
    class ReviewRequestHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path == "/":
                    self._send_html(_html())
                elif parsed.path == "/api/audits":
                    self._send_json(self._audits())
                elif parsed.path == "/api/rows":
                    self._send_json(self._rows(parsed.query))
                elif parsed.path == "/audio":
                    self._send_audio(parsed.query)
                else:
                    self.send_error(HTTPStatus.NOT_FOUND)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            try:
                if parsed.path != "/api/decision":
                    self.send_error(HTTPStatus.NOT_FOUND)
                    return
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                saved = save_decision(config.decisions_path, payload)
                self._send_json(saved)
            except Exception as exc:  # noqa: BLE001
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def log_message(self, format: str, *args) -> None:
            timestamp = time.strftime("%H:%M:%S")
            print(f"{timestamp} {self.address_string()} {format % args}")

        def _audits(self) -> dict[str, object]:
            audits = sorted((path.name for path in config.audit_dir.glob("*_error_audit.csv")), key=_audit_sort_order)
            return {"audits": audits, "decisions_path": str(config.decisions_path)}

        def _rows(self, query: str) -> dict[str, object]:
            params = {key: values[-1] for key, values in parse_qs(query).items()}
            audit_name = params.get("audit", "")
            if not audit_name:
                audits = self._audits()["audits"]
                audit_name = audits[0] if audits else ""
            audit_path = _resolve_audit(config.audit_dir, audit_name)
            rows = load_audit_rows(audit_path)
            merged = merge_decisions(rows, load_decisions(config.decisions_path), audit_path.name)
            filtered = filter_rows(merged, params)
            offset = max(0, int(params.get("offset", "0") or 0))
            limit = max(1, min(5000, int(params.get("limit", "5000") or 5000)))
            return {
                "audit": audit_path.name,
                "rows": filtered[offset : offset + limit],
                "summary": summarize_rows(filtered),
                "total_unfiltered": len(rows),
                "labels": LABELS,
                "offset": offset,
                "limit": limit,
            }

        def _send_html(self, html: str) -> None:
            body = html.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_audio(self, query: str) -> None:
            params = parse_qs(query)
            raw_path = unquote(params.get("path", [""])[-1])
            audio_path = _resolve_audio_path(raw_path, config.repository_root)
            content_type = mimetypes.guess_type(audio_path)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(audio_path.stat().st_size))
            self.end_headers()
            with audio_path.open("rb") as handle:
                while chunk := handle.read(1024 * 512):
                    self.wfile.write(chunk)

    return ReviewRequestHandler


def _resolve_audit(audit_dir: Path, audit_name: str) -> Path:
    audit_path = (audit_dir / Path(audit_name).name).resolve()
    audit_root = audit_dir.resolve()
    if audit_root not in audit_path.parents or not audit_path.exists() or audit_path.suffix != ".csv":
        raise ValueError(f"unknown audit: {audit_name}")
    return audit_path


def _resolve_audio_path(raw_path: str, repository_root: Path) -> Path:
    if not raw_path:
        raise ValueError("missing audio path")
    audio_path = Path(raw_path).expanduser()
    if not audio_path.is_absolute():
        audio_path = repository_root / audio_path
    audio_path = audio_path.resolve()
    if audio_path.suffix.lower() not in AUDIO_SUFFIXES:
        raise ValueError("unsupported audio file type")
    if not audio_path.exists():
        raise ValueError(f"audio file does not exist: {audio_path}")
    return audio_path


def _audit_sort_order(name: str) -> tuple[int, str]:
    if "_val_" in name:
        return (0, name)
    if "_train_full_" in name:
        return (1, name)
    if "_train_" in name:
        return (2, name)
    if "_test_" in name:
        return (3, name)
    return (4, name)


def _html() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Canopy Audio Review</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8f6;
      --panel: #ffffff;
      --ink: #17201b;
      --muted: #627067;
      --line: #d8ded7;
      --accent: #0b6b57;
      --warn: #a64f00;
      --bad: #b3261e;
      --good: #2f6b2f;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; color: var(--ink); background: var(--bg); }}
    button, input, select, textarea {{ font: inherit; }}
    button {{ border: 1px solid var(--line); background: var(--panel); color: var(--ink); border-radius: 6px; padding: 8px 10px; cursor: pointer; }}
    button.primary {{ background: var(--accent); color: white; border-color: var(--accent); }}
    button.icon {{ width: 36px; height: 36px; padding: 0; display: inline-grid; place-items: center; }}
    button:disabled {{ opacity: 0.5; cursor: not-allowed; }}
    header {{ height: 56px; display: flex; align-items: center; justify-content: space-between; padding: 0 18px; border-bottom: 1px solid var(--line); background: var(--panel); }}
    h1 {{ font-size: 18px; margin: 0; font-weight: 700; letter-spacing: 0; }}
    .app {{ display: grid; grid-template-columns: minmax(320px, 420px) 1fr; height: calc(100vh - 56px); min-height: 620px; }}
    aside {{ border-right: 1px solid var(--line); background: var(--panel); min-width: 0; display: flex; flex-direction: column; }}
    main {{ min-width: 0; overflow: auto; }}
    .filters {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; padding: 12px; border-bottom: 1px solid var(--line); }}
    .filters .wide {{ grid-column: 1 / -1; }}
    label {{ display: grid; gap: 4px; color: var(--muted); font-size: 12px; font-weight: 650; }}
    select, input, textarea {{ width: 100%; border: 1px solid var(--line); border-radius: 6px; padding: 8px 9px; background: white; color: var(--ink); }}
    textarea {{ resize: vertical; min-height: 78px; }}
    .summary {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 12px; border-bottom: 1px solid var(--line); }}
    .metric {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px; background: #fbfcfb; }}
    .metric b {{ display: block; font-size: 18px; }}
    .metric span {{ color: var(--muted); font-size: 12px; }}
    .list {{ overflow: auto; }}
    .row {{ width: 100%; text-align: left; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; padding: 10px 12px; display: grid; gap: 5px; background: white; }}
    .row.active {{ background: #eaf4f0; box-shadow: inset 3px 0 0 var(--accent); }}
    .row-top {{ display: flex; align-items: center; justify-content: space-between; gap: 8px; }}
    .row-title {{ font-weight: 700; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .row-sub {{ color: var(--muted); font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .badge {{ border-radius: 999px; padding: 3px 7px; font-size: 12px; font-weight: 700; white-space: nowrap; background: #eef1ef; color: var(--muted); }}
    .badge.p1 {{ background: #fde8e5; color: var(--bad); }}
    .badge.p2 {{ background: #fff1de; color: var(--warn); }}
    .badge.p3 {{ background: #e8eefc; color: #274b9f; }}
    .workspace {{ display: grid; grid-template-columns: minmax(0, 1fr) 340px; gap: 18px; padding: 18px; }}
    .section {{ background: var(--panel); border-bottom: 1px solid var(--line); }}
    .detail, .decision {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; padding: 14px; }}
    .detail h2 {{ margin: 0 0 8px; font-size: 22px; letter-spacing: 0; }}
    .path {{ color: var(--muted); word-break: break-all; font-size: 13px; margin-bottom: 12px; }}
    audio {{ width: 100%; margin: 8px 0 14px; }}
    .grid {{ display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; }}
    .field {{ border: 1px solid var(--line); border-radius: 6px; padding: 8px; min-width: 0; }}
    .field span {{ display: block; color: var(--muted); font-size: 12px; }}
    .field b {{ display: block; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .scores {{ display: grid; gap: 8px; margin-top: 14px; }}
    .score {{ display: grid; grid-template-columns: 120px 1fr 56px; gap: 10px; align-items: center; }}
    .bar {{ height: 10px; background: #edf0ee; border-radius: 999px; overflow: hidden; }}
    .fill {{ height: 100%; background: var(--accent); }}
    .score strong {{ overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    .decision {{ position: sticky; top: 18px; align-self: start; display: grid; gap: 10px; }}
    .decision h2 {{ margin: 0; font-size: 16px; }}
    .seg {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
    .seg button.selected {{ background: var(--accent); border-color: var(--accent); color: white; }}
    .nav {{ display: flex; gap: 8px; align-items: center; justify-content: space-between; }}
    .empty {{ padding: 24px; color: var(--muted); }}
    .save-state {{ min-height: 20px; color: var(--muted); font-size: 13px; }}
    @media (max-width: 900px) {{
      .app {{ grid-template-columns: 1fr; height: auto; }}
      aside {{ height: 48vh; border-right: 0; border-bottom: 1px solid var(--line); }}
      .workspace {{ grid-template-columns: 1fr; padding: 12px; }}
      .decision {{ position: static; }}
      .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Canopy Audio Review</h1>
    <div id="decisionPath"></div>
  </header>
  <div class="app">
    <aside>
      <div class="filters">
        <label class="wide">Audit <select id="audit"></select></label>
        <label>Priority <select id="review_priority"><option value="">All</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="9">9</option></select></label>
        <label>Error <select id="error_type"><option value="">All</option><option>background_false_positive</option><option>threat_false_negative</option><option>threat_confusion</option><option>correct</option></select></label>
        <label>True label <select id="true_label"><option value="">All</option></select></label>
        <label>Predicted <select id="predicted_label"><option value="">All</option></select></label>
        <label>Decision <select id="review_decision"><option value="">All</option><option>accepted</option><option>relabel</option><option>reject</option><option>unsure</option><option>needs_review</option></select></label>
        <label class="wide">Search <input id="q" type="search"></label>
      </div>
      <div class="summary">
        <div class="metric"><b id="metricTotal">0</b><span>clips</span></div>
        <div class="metric"><b id="metricErrors">0</b><span>errors</span></div>
        <div class="metric"><b id="metricReviewed">0</b><span>reviewed</span></div>
      </div>
      <div id="rows" class="list"></div>
    </aside>
    <main>
      <div id="empty" class="empty">No clip selected.</div>
      <div id="workspace" class="workspace" hidden>
        <section class="detail">
          <h2 id="clipTitle"></h2>
          <div id="clipPath" class="path"></div>
          <audio id="audio" controls preload="metadata"></audio>
          <div class="grid">
            <div class="field"><span>True</span><b id="trueLabel"></b></div>
            <div class="field"><span>Raw</span><b id="rawLabel"></b></div>
            <div class="field"><span>Thresholded</span><b id="thresholdedLabel"></b></div>
            <div class="field"><span>Error</span><b id="errorType"></b></div>
            <div class="field"><span>Source</span><b id="source"></b></div>
            <div class="field"><span>Split</span><b id="split"></b></div>
            <div class="field"><span>Score</span><b id="predictedScore"></b></div>
            <div class="field"><span>Margin</span><b id="margin"></b></div>
          </div>
          <div id="scores" class="scores"></div>
          <div class="field" style="margin-top:14px"><span>Notes</span><b id="notes"></b></div>
        </section>
        <section class="decision">
          <h2>Review</h2>
          <div class="seg" id="decisionButtons">
            <button data-decision="accepted">Accept</button>
            <button data-decision="relabel">Relabel</button>
            <button data-decision="reject">Reject</button>
            <button data-decision="unsure">Unsure</button>
          </div>
          <label>Corrected label <select id="corrected_label"></select></label>
          <label>Target split <select id="target_split"><option value="">Keep</option><option>train</option><option>val</option><option>test</option></select></label>
          <label>Reviewer <input id="reviewer"></label>
          <label>Review notes <textarea id="review_notes"></textarea></label>
          <button class="primary" id="save">Save</button>
          <div class="nav">
            <button id="prev" class="icon" title="Previous">‹</button>
            <span id="position"></span>
            <button id="next" class="icon" title="Next">›</button>
          </div>
          <div id="saveState" class="save-state"></div>
        </section>
      </div>
    </main>
  </div>
  <script>
    const labels = {json.dumps(LABELS)};
    const state = {{ audits: [], rows: [], selectedIndex: -1, selectedDecision: "" }};
    const $ = (id) => document.getElementById(id);
    const filters = ["review_priority", "error_type", "true_label", "predicted_label", "review_decision", "q"];
    async function api(path, options) {{
      const response = await fetch(path, options);
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || response.statusText);
      return data;
    }}
    function audioUrl(path) {{ return "/audio?path=" + encodeURIComponent(path); }}
    function basename(path) {{ return path.split(/[\\\\/]/).pop(); }}
    function setOptions(select, values, keepAll = true) {{
      select.innerHTML = keepAll ? '<option value="">All</option>' : "";
      values.forEach((value) => {{
        const option = document.createElement("option");
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}
    async function init() {{
      setOptions($("true_label"), labels);
      setOptions($("predicted_label"), labels);
      setOptions($("corrected_label"), ["", ...labels], false);
      const data = await api("/api/audits");
      state.audits = data.audits;
      $("decisionPath").textContent = data.decisions_path;
      setOptions($("audit"), state.audits, false);
      filters.forEach((id) => $(id).addEventListener("input", loadRows));
      $("audit").addEventListener("change", loadRows);
      $("prev").addEventListener("click", () => selectRow(Math.max(0, state.selectedIndex - 1)));
      $("next").addEventListener("click", () => selectRow(Math.min(state.rows.length - 1, state.selectedIndex + 1)));
      $("save").addEventListener("click", saveDecision);
      document.querySelectorAll("#decisionButtons button").forEach((button) => {{
        button.addEventListener("click", () => setDecision(button.dataset.decision));
      }});
      await loadRows();
    }}
    async function loadRows() {{
      const params = new URLSearchParams({{ audit: $("audit").value, limit: "5000" }});
      filters.forEach((id) => {{ if ($(id).value) params.set(id, $(id).value); }});
      const data = await api("/api/rows?" + params.toString());
      state.rows = data.rows;
      state.selectedIndex = state.rows.length ? 0 : -1;
      $("metricTotal").textContent = data.summary.total;
      $("metricErrors").textContent = data.summary.errors;
      $("metricReviewed").textContent = data.summary.reviewed;
      renderRows();
      selectRow(state.selectedIndex);
    }}
    function renderRows() {{
      const container = $("rows");
      container.innerHTML = "";
      state.rows.forEach((row, index) => {{
        const button = document.createElement("button");
        button.className = "row" + (index === state.selectedIndex ? " active" : "");
        button.innerHTML = `
          <div class="row-top">
            <div class="row-title">${{row.true_label}} → ${{row.predicted_label}}</div>
            <span class="badge p${{row.review_priority}}">${{row.review_priority}}</span>
          </div>
          <div class="row-sub">${{row.error_type}} · ${{row.source}} · ${{basename(row.path)}}</div>
          <div class="row-sub">${{row.review_decision || "unreviewed"}}</div>`;
        button.addEventListener("click", () => selectRow(index));
        container.appendChild(button);
      }});
    }}
    function selectRow(index) {{
      state.selectedIndex = index;
      renderRows();
      const row = state.rows[index];
      $("empty").hidden = Boolean(row);
      $("workspace").hidden = !row;
      if (!row) return;
      $("clipTitle").textContent = basename(row.path);
      $("clipPath").textContent = row.path;
      $("audio").src = audioUrl(row.path);
      $("trueLabel").textContent = row.true_label;
      $("rawLabel").textContent = row.raw_predicted_label;
      $("thresholdedLabel").textContent = row.thresholded_predicted_label;
      $("errorType").textContent = row.error_type;
      $("source").textContent = row.source;
      $("split").textContent = row.split;
      $("predictedScore").textContent = row.predicted_score;
      $("margin").textContent = row.margin;
      $("notes").textContent = row.notes || "";
      $("corrected_label").value = row.corrected_label || row.true_label;
      $("target_split").value = row.target_split || "";
      $("reviewer").value = row.reviewer || "";
      $("review_notes").value = row.review_notes || "";
      setDecision(row.review_decision || "");
      $("position").textContent = `${{index + 1}} / ${{state.rows.length}}`;
      $("prev").disabled = index <= 0;
      $("next").disabled = index >= state.rows.length - 1;
      renderScores(row);
    }}
    function renderScores(row) {{
      const container = $("scores");
      container.innerHTML = "";
      labels.map((label) => [label, Number(row["score_" + label] || 0)])
        .sort((a, b) => b[1] - a[1])
        .forEach(([label, value]) => {{
          const div = document.createElement("div");
          div.className = "score";
          div.innerHTML = `<strong>${{label}}</strong><div class="bar"><div class="fill" style="width:${{Math.max(0, Math.min(100, value * 100))}}%"></div></div><span>${{value.toFixed(3)}}</span>`;
          container.appendChild(div);
        }});
    }}
    function setDecision(decision) {{
      state.selectedDecision = decision;
      document.querySelectorAll("#decisionButtons button").forEach((button) => {{
        button.classList.toggle("selected", button.dataset.decision === decision);
      }});
    }}
    async function saveDecision() {{
      const row = state.rows[state.selectedIndex];
      if (!row) return;
      $("saveState").textContent = "Saving";
      const payload = {{
        audit: $("audit").value,
        path: row.path,
        true_label: row.true_label,
        predicted_label: row.predicted_label,
        decision: state.selectedDecision || "needs_review",
        corrected_label: $("corrected_label").value,
        target_split: $("target_split").value,
        reviewer: $("reviewer").value,
        review_notes: $("review_notes").value
      }};
      const saved = await api("/api/decision", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify(payload)
      }});
      Object.assign(row, {{
        review_decision: saved.decision,
        corrected_label: saved.corrected_label,
        target_split: saved.target_split,
        reviewer: saved.reviewer,
        review_notes: saved.review_notes,
        updated_at: saved.updated_at
      }});
      $("saveState").textContent = "Saved";
      renderRows();
    }}
    init().catch((error) => {{
      $("empty").hidden = false;
      $("empty").textContent = error.message;
    }});
  </script>
</body>
</html>"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a local web app for reviewing audio audit CSVs.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    args = parser.parse_args()
    config = ReviewAppConfig(
        audit_dir=args.audit_dir,
        decisions_path=args.decisions,
        repository_root=Path.cwd(),
    )
    run_server(args.host, args.port, config)


if __name__ == "__main__":
    main()
