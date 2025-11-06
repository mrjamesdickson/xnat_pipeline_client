from __future__ import annotations
import argparse, http.server, socketserver, json, pathlib, time, os

from . import __version__ as PKG_VERSION

INDEX_HTML = """<!doctype html>
<html><head>
<meta charset='utf-8'/>
<title>XNAT Pipelines Dashboard</title>
<style>
body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Arial,sans-serif;margin:20px}
h1{margin:0 0 12px 0}
.card{border:1px solid #ddd;padding:12px;margin:10px 0;border-radius:8px}
.meta{color:#444;font-size:12px;margin-bottom:6px}
pre{background:#111;color:#eee;padding:10px;border-radius:6px;overflow:auto;max-height:200px}
.status{font-weight:bold}
.grid{display:grid;grid-template-columns: 1fr 1fr; gap: 12px;}
</style>
</head><body>
<h1>XNAT Pipelines – Local Runs</h1>
<div id='summary'></div>
<div id='runs' class='grid'></div>
<script>
async function fetchJSON(url){ const r = await fetch(url + '?_=' + Date.now()); return await r.json(); }
function esc(s){ return (s||'').toString().replace(/[&<>]/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c])) }
function card(run){
  return `<div class='card'>
    <div class='meta'>${esc(run.dir)} • ${new Date(run.time*1000).toLocaleString()}</div>
    <div class='status'>${esc(run.status)}</div>
    <div>Cmd: <code>${esc(run.cmd.join(' '))}</code></div>
    <div>Context: <code>${esc(JSON.stringify(run.context))}</code></div>
    <div>Image: <code>${esc(run.image)}</code></div>
    <div>Log tail:</div>
    <pre>${esc(run.log_tail||'')}</pre>
  </div>`
}
async function refresh(){
  const data = await fetchJSON('status.json');
  document.getElementById('summary').textContent = `total=${data.total} running=${data.running} complete=${data.complete} failed=${data.failed}`;
  document.getElementById('runs').innerHTML = data.runs.map(card).join('');
}
setInterval(refresh, 1500);
refresh();
</script>
</body></html>"""

def scan_runs(root: pathlib.Path, tail=800):
    runs = []
    for d in sorted(root.glob('run_*')):
        run = {"dir": d.name, "time": d.stat().st_mtime, "status":"Unknown", "image":"", "context":{}, "cmd":[]}
        try:
            manifest = json.loads((d/'run.json').read_text())
            run.update({
                "time": manifest.get("time", run["time"]),
                "image": manifest.get("image",""),
                "context": manifest.get("context",{}),
                "cmd": manifest.get("cmd", []),
            })
        except Exception:
            pass
        # infer status from process.pid file presence or log lines
        status = "Unknown"
        log_tail = ""
        try:
            log = (d/"run.log").read_text(errors="ignore")
            log_tail = log[-tail:]
            if "DRY RUN" in log.splitlines()[0:1]:
                status = "Prepared"
            elif "CMD:" in log:
                status = "Running"
            if "error" in log.lower() or "traceback" in log.lower():
                status = "Failed"
            if "Complete" in log or "completed" in log.lower():
                status = "Complete"
        except Exception:
            pass
        run["status"] = status
        run["log_tail"] = log_tail
        runs.append(run)
    # tally
    counts = {"total": len(runs), "running":0, "complete":0, "failed":0}
    for r in runs:
        s = r["status"].lower()
        if s == "running": counts["running"] += 1
        elif s in ("complete","completed","succeeded","done"): counts["complete"] += 1
        elif s in ("failed","error","aborted"): counts["failed"] += 1
    return runs, counts

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, directory=None, **kwargs):
        super().__init__(*args, directory=directory, **kwargs)

def main():
    ap = argparse.ArgumentParser(prog="xnat-pipelines-dashboard")
    ap.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {PKG_VERSION}",
        help="Show the installed xnat-pipelines version and exit",
    )
    ap.add_argument("--runs", default="./xnat_local_runs")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()

    runs_root = pathlib.Path(args.runs).absolute()
    runs_root.mkdir(parents=True, exist_ok=True)

    class DashboardHandler(Handler):
        def do_GET(self):
            if self.path.startswith("/status.json"):
                runs, counts = scan_runs(runs_root)
                payload = {**counts, "runs": runs}
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if self.path in ("/","/index.html"):
                data = INDEX_HTML.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return super().do_GET()

    with socketserver.TCPServer(("", args.port), DashboardHandler) as httpd:
        print(f"Dashboard on http://localhost:{args.port}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    main()
