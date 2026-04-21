"""
Visualize browser-use agent trajectories in a local web UI.

Usage:
    python scripts/visualize_trajectory.py --result_dir outputs/test
    python scripts/visualize_trajectory.py --result_dir outputs/test --port 8765
"""

import argparse
import base64
import html
import http.server
import io
import json
import os
import sys
import urllib.parse

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SCUBA Trajectory Viewer</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:system-ui,-apple-system,sans-serif;background:#0f172a;color:#e2e8f0;min-height:100vh}
a{color:#60a5fa;text-decoration:none}a:hover{text-decoration:underline}
.container{max-width:1400px;margin:0 auto;padding:1rem}
h1{font-size:1.4rem;padding:.75rem 0;border-bottom:1px solid #334155;margin-bottom:1rem}
.summary-bar{display:flex;gap:1rem;flex-wrap:wrap;margin-bottom:1rem}
.badge{padding:.35rem .75rem;border-radius:.375rem;font-size:.85rem;font-weight:600}
.badge-pass{background:#065f46;color:#6ee7b7}.badge-fail{background:#7f1d1d;color:#fca5a5}
.badge-info{background:#1e3a5f;color:#93c5fd}
.task-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:.75rem;margin-bottom:1.5rem}
.task-card{background:#1e293b;border:1px solid #334155;border-radius:.5rem;padding:.75rem;cursor:pointer;transition:border-color .15s}
.task-card:hover{border-color:#60a5fa}.task-card.active{border-color:#3b82f6;background:#1e3a5f}
.task-card h3{font-size:.9rem;margin-bottom:.25rem;word-break:break-all}
.task-card .meta{font-size:.75rem;color:#94a3b8}
.task-card .score{float:right;font-weight:700;font-size:.9rem}
.score-pass{color:#6ee7b7}.score-fail{color:#fca5a5}
.viewer{display:none;background:#1e293b;border:1px solid #334155;border-radius:.5rem;overflow:hidden}
.viewer.active{display:block}
.viewer-header{padding:.75rem 1rem;background:#0f172a;border-bottom:1px solid #334155;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.5rem}
.viewer-header h2{font-size:1rem}
.nav-controls{display:flex;align-items:center;gap:.5rem}
.nav-controls button{background:#334155;color:#e2e8f0;border:none;padding:.4rem .8rem;border-radius:.25rem;cursor:pointer;font-size:.85rem}
.nav-controls button:hover{background:#475569}
.nav-controls button:disabled{opacity:.4;cursor:default}
.step-counter{font-size:.85rem;min-width:6rem;text-align:center}
.viewer-body{display:flex;gap:0;min-height:500px}
.screenshot-pane{flex:1;min-width:0;background:#000;display:flex;align-items:center;justify-content:center;padding:.5rem}
.screenshot-pane img{max-width:100%;max-height:70vh;object-fit:contain;border-radius:.25rem}
.details-pane{width:420px;min-width:320px;overflow-y:auto;max-height:75vh;padding:1rem;border-left:1px solid #334155;font-size:.82rem;line-height:1.5}
.detail-section{margin-bottom:1rem}
.detail-section h4{color:#94a3b8;font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:.25rem}
.detail-section pre{white-space:pre-wrap;word-break:break-word;background:#0f172a;padding:.5rem;border-radius:.25rem;max-height:200px;overflow-y:auto}
.detail-section .tag{display:inline-block;background:#334155;padding:.15rem .5rem;border-radius:.25rem;margin:.1rem .2rem;font-size:.75rem}
.tag-error{background:#7f1d1d;color:#fca5a5}
.rubric-table{width:100%;border-collapse:collapse;font-size:.8rem}
.rubric-table th,.rubric-table td{text-align:left;padding:.3rem .5rem;border-bottom:1px solid #334155}
.rubric-table th{color:#94a3b8;font-weight:500}
.prompt-box{background:#0f172a;padding:.75rem;border-radius:.25rem;font-size:.82rem;line-height:1.5;margin-bottom:1rem;max-height:120px;overflow-y:auto;white-space:pre-wrap;word-break:break-word}
.close-btn{background:none;border:none;color:#94a3b8;font-size:1.2rem;cursor:pointer;padding:.2rem .5rem}
.close-btn:hover{color:#e2e8f0}
@media(max-width:900px){.viewer-body{flex-direction:column}.details-pane{width:100%;max-height:none;border-left:none;border-top:1px solid #334155}}
</style>
</head>
<body>
<div class="container">
<h1>SCUBA Trajectory Viewer</h1>
<div class="summary-bar">
  <span class="badge badge-info" id="total-badge"></span>
  <span class="badge badge-pass" id="pass-badge"></span>
  <span class="badge badge-fail" id="fail-badge"></span>
</div>
<div class="task-grid" id="task-grid"></div>
<div class="viewer" id="viewer">
  <div class="viewer-header">
    <h2 id="viewer-title"></h2>
    <div style="display:flex;align-items:center;gap:1rem">
      <div class="nav-controls">
        <button id="btn-prev" onclick="changeStep(-1)">&larr; Prev</button>
        <span class="step-counter" id="step-counter">0 / 0</span>
        <button id="btn-next" onclick="changeStep(1)">Next &rarr;</button>
      </div>
      <button class="close-btn" onclick="closeViewer()">&times;</button>
    </div>
  </div>
  <div id="prompt-box" class="prompt-box" style="margin:0 1rem;margin-top:.75rem"></div>
  <div class="viewer-body">
    <div class="screenshot-pane"><img id="screenshot" src="" alt="screenshot"></div>
    <div class="details-pane" id="details-pane"></div>
  </div>
</div>
</div>
<script>
const DATA = __DATA_PLACEHOLDER__;
let currentTask = null, currentStep = 0;

function init() {
  const grid = document.getElementById('task-grid');
  let pass=0, fail=0;
  DATA.tasks.forEach(t => {
    if (t.score >= 1) pass++; else fail++;
    const card = document.createElement('div');
    card.className = 'task-card';
    card.id = 'card-' + t.task_id;
    card.innerHTML = '<span class="score ' + (t.score>=1?'score-pass':'score-fail') + '">' +
      (t.score>=1?'PASS':'FAIL') + '</span><h3>' + t.task_id + '</h3>' +
      '<div class="meta">' + t.num_steps + ' steps &middot; ' + t.time_min.toFixed(1) + ' min</div>';
    card.onclick = () => openTask(t.task_id);
    grid.appendChild(card);
  });
  document.getElementById('total-badge').textContent = DATA.tasks.length + ' tasks';
  document.getElementById('pass-badge').textContent = pass + ' passed';
  document.getElementById('fail-badge').textContent = fail + ' failed';
}

function openTask(taskId) {
  document.querySelectorAll('.task-card').forEach(c => c.classList.remove('active'));
  document.getElementById('card-' + taskId).classList.add('active');
  currentTask = DATA.tasks.find(t => t.task_id === taskId);
  currentStep = 0;
  document.getElementById('viewer').classList.add('active');
  document.getElementById('viewer-title').textContent = taskId;
  document.getElementById('prompt-box').textContent = currentTask.prompt;
  renderStep();
  document.getElementById('viewer').scrollIntoView({behavior:'smooth'});
}

function closeViewer() {
  document.getElementById('viewer').classList.remove('active');
  document.querySelectorAll('.task-card').forEach(c => c.classList.remove('active'));
  currentTask = null;
}

function changeStep(delta) {
  if (!currentTask) return;
  currentStep = Math.max(0, Math.min(currentStep + delta, currentTask.steps.length - 1));
  renderStep();
}

function renderStep() {
  const steps = currentTask.steps;
  const total = steps.length;
  document.getElementById('step-counter').textContent = (currentStep+1) + ' / ' + total;
  document.getElementById('btn-prev').disabled = currentStep === 0;
  document.getElementById('btn-next').disabled = currentStep >= total - 1;

  const s = steps[currentStep];
  const img = document.getElementById('screenshot');
  img.src = s.screenshot || '';
  img.style.display = s.screenshot ? 'block' : 'none';

  const pane = document.getElementById('details-pane');
  let h = '';

  if (s.plan) h += sec('Plan', pre(s.plan));
  if (s.eval_prev) h += sec('Eval Previous Goal', pre(s.eval_prev));
  if (s.memory) h += sec('Memory', pre(s.memory));
  if (s.next_goal) h += sec('Next Goal', pre(s.next_goal));
  if (s.actions && s.actions.length)
    h += sec('Actions', s.actions.map(a => '<span class="tag">' + esc(a) + '</span>').join(' '));
  if (s.results && s.results.length)
    h += sec('Results', s.results.map(r => '<span class="tag">' + esc(r) + '</span>').join(' '));
  if (s.errors && s.errors.length)
    h += sec('Errors', s.errors.map(e => '<span class="tag tag-error">' + esc(e) + '</span>').join(' '));

  if (currentStep === total - 1 && currentTask.rubric) {
    let rt = '<table class="rubric-table"><tr><th>Milestone</th><th>Weight</th><th>Result</th></tr>';
    currentTask.rubric.forEach(r => {
      rt += '<tr><td>'+esc(r.milestone)+'</td><td>'+r.weight+'</td><td>'+(r.is_success?'✓':'✗')+'</td></tr>';
    });
    rt += '</table>';
    h += sec('Evaluation Rubric', rt);
  }
  pane.innerHTML = h;
}

function sec(title, body) { return '<div class="detail-section"><h4>'+title+'</h4>'+body+'</div>'; }
function pre(t) { return '<pre>'+esc(t)+'</pre>'; }
function esc(t) { const d=document.createElement('div');d.textContent=t;return d.innerHTML; }

document.addEventListener('keydown', e => {
  if (e.key==='ArrowRight') changeStep(1);
  else if (e.key==='ArrowLeft') changeStep(-1);
  else if (e.key==='Escape') closeViewer();
});

init();
</script>
</body>
</html>"""


def parse_trajectory(traj_path, perf_path):
    with open(traj_path) as f:
        traj = json.load(f)
    perf = {}
    if os.path.exists(perf_path):
        with open(perf_path) as f:
            perf = json.load(f)

    task_id = os.path.basename(traj_path).replace(".json", "")
    prompt = traj.get("task_prompt", "")
    is_successful = traj.get("is_successful", False)
    score = perf.get("evaluation_result", {}).get("Score", 0)
    time_min = perf.get("time (min)", 0)
    rubric = perf.get("evaluation_result", {}).get("Rubric", [])

    steps_data = traj.get("steps", {})
    steps = []
    for step_key in sorted(steps_data.keys(), key=lambda x: int(x)):
        if step_key == "0":
            continue
        step = steps_data[step_key]
        parsed = {}

        if "get_plan" in step:
            parsed["plan"] = step["get_plan"].get("plan", "")

        if "input_messages" in step:
            contents = step["input_messages"].get("contents", [])
            state_info = contents[-1] if contents else {}
            if isinstance(state_info.get("content"), str) and len(contents) > 1:
                state_info = contents[-2]

            if isinstance(state_info.get("content"), list):
                for c in state_info["content"]:
                    if c.get("type") == "image_url":
                        parsed["screenshot"] = c["image_url"]["url"]

        if "output_messages" in step:
            try:
                tool_calls = step["output_messages"]["tool_call_message"]["tool_calls"]
                args = tool_calls[0]["args"]
                cs = args.get("current_state", {})
                parsed["eval_prev"] = cs.get("evaluation_previous_goal", "")
                parsed["memory"] = cs.get("memory", "")
                parsed["next_goal"] = cs.get("next_goal", "")
                action_list = args.get("action", [])
                parsed["actions"] = []
                for ad in action_list:
                    for fn, params in ad.items():
                        if params:
                            ps = ", ".join(f"{k}={repr(v)}" for k, v in params.items())
                            parsed["actions"].append(f"{fn}({ps})")
                        else:
                            parsed["actions"].append(f"{fn}()")
            except (KeyError, IndexError, TypeError):
                pass

        if "controller_messages" in step:
            cm = step["controller_messages"]
            parsed["results"] = [r["content"] for r in cm.get("action_result", []) if r and r.get("content")]
            parsed["errors"] = [e["content"] for e in cm.get("action_error", []) if e and e.get("content")]

        steps.append(parsed)

    return {
        "task_id": task_id,
        "prompt": prompt,
        "score": score,
        "time_min": time_min,
        "num_steps": len(steps),
        "rubric": rubric,
        "steps": steps,
    }


def build_html(result_dir):
    traj_dir = os.path.join(result_dir, "trajectory")
    perf_dir = os.path.join(result_dir, "performance")

    if not os.path.isdir(traj_dir):
        print(f"Error: {traj_dir} not found")
        sys.exit(1)

    tasks = []
    for fname in sorted(os.listdir(traj_dir)):
        if not fname.endswith(".json"):
            continue
        traj_path = os.path.join(traj_dir, fname)
        perf_path = os.path.join(perf_dir, fname)
        try:
            tasks.append(parse_trajectory(traj_path, perf_path))
        except Exception as e:
            print(f"  Warning: skipping {fname}: {e}")

    data = {"tasks": tasks}
    data_json = json.dumps(data, ensure_ascii=False)
    return TEMPLATE.replace("__DATA_PLACEHOLDER__", data_json)


def main():
    parser = argparse.ArgumentParser(description="Visualize SCUBA BU trajectories")
    parser.add_argument("--result_dir", type=str, required=True,
                        help="Path to result directory (e.g. outputs/test)")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--save", type=str, default=None,
                        help="Save HTML to file instead of serving")
    args = parser.parse_args()

    print(f"Loading trajectories from {args.result_dir}...")
    html_content = build_html(args.result_dir)
    html_bytes = html_content.encode("utf-8")

    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Saved to {args.save}")
        return

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html_bytes)))
            self.end_headers()
            self.wfile.write(html_bytes)

        def log_message(self, format, *a):
            pass

    server = http.server.HTTPServer(("localhost", args.port), Handler)
    url = f"http://localhost:{args.port}"
    print(f"Serving at {url}")
    print("Press Ctrl+C to stop.\n")

    import webbrowser
    webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
