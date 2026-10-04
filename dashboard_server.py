#!/usr/bin/env python3
"""
量化交易知識庫 — 監控儀表板伺服器
提供 JSON API 和 HTML 儀表板，監控自動歸檔系統狀態。

啟動：python3 dashboard_server.py
存取：http://localhost:8899
"""

import http.server
import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

PORT = 8899
VAULT = Path("/home/anson/Documents/Obsidian Vault")
QUANT_DIR = VAULT / "量化交易"
TRACKING = Path("/home/anson/.hermes/profiles/deepseek/data/quant_processed_urls.json")
BLOGWATCHER = "/home/anson/.hermes/profiles/deepseek/home/.local/bin/blogwatcher-cli"
SCANNER = "/home/anson/.hermes/profiles/deepseek/scripts/quant_scanner.py"
CRON_JOB_ID = "2276931868d9"
TZ = timezone(timedelta(hours=8))  # Asia/Taipei


def get_tracking_data():
    """讀取追蹤檔"""
    if TRACKING.exists():
        with open(TRACKING) as f:
            return json.load(f)
    return {"processed_urls": [], "last_scan": None}


def get_blogwatcher_blogs():
    """取得已追蹤的部落格清單"""
    try:
        result = subprocess.run(
            [BLOGWATCHER, "blogs"], capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip()
    except Exception:
        return "（無法連線 blogwatcher-cli）"


def get_obsidian_articles():
    """掃描 Obsidian 中各分類的文章清單"""
    categories = {}
    if not QUANT_DIR.exists():
        return categories

    for subdir in sorted(QUANT_DIR.iterdir()):
        if subdir.is_dir() and not subdir.name.startswith("."):
            md_files = list(subdir.rglob("*.md"))
            # 排除 MOC 檔案
            articles = [f for f in md_files if "MOC" not in f.name]
            if articles:
                cat_name = subdir.name
                categories[cat_name] = {
                    "path": str(subdir.relative_to(VAULT)),
                    "count": len(articles),
                    "articles": sorted(
                        [{"name": a.stem, "path": str(a.relative_to(VAULT))} for a in articles],
                        key=lambda x: x["name"],
                        reverse=True,
                    )[:20],  # 只取最近 20 篇
                }
    return categories


def get_system_status():
    """組合所有狀態資訊"""
    tracking = get_tracking_data()
    categories = get_obsidian_articles()

    total_articles = sum(c["count"] for c in categories.values())
    total_processed = len(tracking.get("processed_urls", []))

    # 計算下次掃描時間
    now = datetime.now(TZ)
    # cron: 0 8,20 * * * → 每天 08:00 和 20:00
    today_8am = now.replace(hour=8, minute=0, second=0, microsecond=0)
    today_8pm = now.replace(hour=20, minute=0, second=0, microsecond=0)
    if now < today_8am:
        next_scan = today_8am
    elif now < today_8pm:
        next_scan = today_8pm
    else:
        next_scan = today_8am + timedelta(days=1)

    return {
        "timestamp": now.isoformat(),
        "system": {
            "status": "running",
            "model": "DeepSeek V4 Flash",
            "cron_job_id": CRON_JOB_ID,
            "cron_schedule": "每日 08:00 / 20:00",
            "last_scan": tracking.get("last_scan"),
            "next_scan": next_scan.isoformat(),
            "total_processed_urls": total_processed,
        },
        "vault": {
            "total_articles": total_articles,
            "total_categories": len(categories),
            "vault_path": str(VAULT),
        },
        "categories": {
            k: {"count": v["count"], "path": v["path"]} for k, v in categories.items()
        },
        "recent_articles": {
            k: v["articles"][:5] for k, v in categories.items()
        },
        "tracked_blogs": get_blogwatcher_blogs(),
    }


# ── HTML 儀表板 ──────────────────────────────────────────

HTML_DASHBOARD = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>📊 量化交易知識庫 — 監控儀表板</title>
<script src="https://cdn.plot.ly/plotly-3.0.1.min.js"></script>
<style>
  :root {
    --bg: #0d1117;
    --card: #161b22;
    --border: #30363d;
    --text: #c9d1d9;
    --muted: #8b949e;
    --accent: #58a6ff;
    --green: #3fb950;
    --orange: #d2991d;
    --red: #f85149;
    --purple: #a371f7;
  }
  * { margin:0; padding:0; box-sizing:border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    line-height: 1.5;
    padding: 20px;
  }
  .header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 24px; padding-bottom: 16px; border-bottom: 1px solid var(--border);
  }
  .header h1 { font-size: 1.5rem; color: var(--accent); }
  .header .status-dot {
    display: inline-block; width: 10px; height: 10px; border-radius: 50%;
    background: var(--green); margin-right: 6px;
    animation: pulse 2s infinite;
  }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
  .last-update { color: var(--muted); font-size: 0.8rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
  @media (max-width: 768px) { .grid-2 { grid-template-columns: 1fr; } }
  .card {
    background: var(--card); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px;
  }
  .card h2 { font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 12px; }
  .stat { font-size: 2rem; font-weight: 600; }
  .stat.green { color: var(--green); }
  .stat.blue { color: var(--accent); }
  .stat.purple { color: var(--purple); }
  .stat.orange { color: var(--orange); }
  .stat-row { display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.85rem; }
  .stat-row .label { color: var(--muted); }
  .bar { background: var(--border); border-radius: 4px; height: 8px; margin-top: 4px; overflow: hidden; }
  .bar-fill { height: 100%; border-radius: 4px; background: var(--accent); transition: width 0.5s ease; }
  .article-list { list-style: none; max-height: 300px; overflow-y: auto; }
  .article-list li { padding: 6px 0; border-bottom: 1px solid var(--border); font-size: 0.8rem; }
  .article-list li:last-child { border-bottom: none; }
  .article-list a { color: var(--accent); text-decoration: none; }
  .article-list a:hover { text-decoration: underline; }
  .article-list .date { color: var(--muted); font-size: 0.7rem; }
  .blog-output {
    background: #0d1117; border: 1px solid var(--border); border-radius: 4px;
    padding: 12px; font-family: 'Fira Code', monospace; font-size: 0.75rem;
    max-height: 200px; overflow-y: auto; white-space: pre-wrap; color: var(--muted);
  }
  .btn {
    background: var(--accent); color: #fff; border: none; padding: 8px 16px;
    border-radius: 6px; cursor: pointer; font-size: 0.85rem;
  }
  .btn:hover { opacity: 0.85; }
  .btn-sm { padding: 4px 12px; font-size: 0.75rem; }
  .toolbar { display: flex; gap: 8px; align-items: center; }
  .empty-state { text-align: center; padding: 40px; color: var(--muted); }
  .empty-state .icon { font-size: 3rem; margin-bottom: 12px; }
  .chart-container { height: 300px; }
  .error-badge { background: var(--red); color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 0.7rem; }
</style>
</head>
<body>

<div class="header">
  <div>
    <h1><span class="status-dot"></span>量化交易知識庫監控儀表板</h1>
  </div>
  <div class="toolbar">
    <span class="last-update" id="lastUpdate">載入中...</span>
    <button class="btn btn-sm" onclick="refresh()">🔄 重新整理</button>
  </div>
</div>

<!-- 系統狀態卡 -->
<div class="grid" id="systemCards"></div>

<!-- 長條圖 + 來源 -->
<div class="grid-2" style="margin-top: 16px;">
  <div class="card">
    <h2>📂 分類分布</h2>
    <div class="chart-container" id="categoryChart"></div>
  </div>
  <div class="card">
    <h2>📡 追蹤來源</h2>
    <div class="blog-output" id="trackedBlogs">載入中...</div>
  </div>
</div>

<!-- 最近文章 -->
<div class="card" style="margin-top: 16px;">
  <h2>🆕 最近歸檔文章</h2>
  <div id="recentArticles"><div class="empty-state"><div class="icon">📭</div>尚無歸檔文章</div></div>
</div>

<script>
async function refresh() {
  try {
    const resp = await fetch('/api/status');
    const data = await resp.json();
    render(data);
    document.getElementById('lastUpdate').textContent =
      '更新於 ' + new Date(data.timestamp).toLocaleString('zh-TW');
  } catch(e) {
    document.getElementById('lastUpdate').textContent = '⚠️ 連線失敗';
  }
}

function render(data) {
  const s = data.system;
  const v = data.vault;

  // ── 系統狀態卡 ──
  document.getElementById('systemCards').innerHTML = `
    <div class="card">
      <h2>⚙️ 系統狀態</h2>
      <div class="stat green">${s.status === 'running' ? '● 運行中' : '○ 已停止'}</div>
      <div class="stat-row"><span class="label">模型</span><span>${s.model}</span></div>
      <div class="stat-row"><span class="label">排程</span><span>${s.cron_schedule}</span></div>
      <div class="stat-row"><span class="label">Cron Job</span><span style="font-family:monospace;font-size:0.7rem">${s.cron_job_id}</span></div>
    </div>
    <div class="card">
      <h2>📊 處理統計</h2>
      <div class="stat blue">${s.total_processed_urls}</div>
      <div class="stat-row"><span class="label">已處理文章 URL</span></div>
      <div class="stat-row"><span class="label">Vault 總筆記</span><span>${v.total_articles} 篇</span></div>
      <div class="stat-row"><span class="label">分類數</span><span>${v.total_categories} 個</span></div>
    </div>
    <div class="card">
      <h2>🕐 掃描時間</h2>
      <div style="margin-bottom:8px">
        <div class="stat-row"><span class="label">上次掃描</span><span>${s.last_scan ? new Date(s.last_scan).toLocaleString('zh-TW') : '尚未執行'}</span></div>
        <div class="stat-row"><span class="label">下次掃描</span><span>${new Date(s.next_scan).toLocaleString('zh-TW')}</span></div>
      </div>
      <div style="font-size:0.75rem;color:var(--muted)">
        距離下次掃描：<span id="countdown">計算中...</span>
      </div>
    </div>
  `;

  // 倒數計時
  const next = new Date(s.next_scan).getTime();
  function updateCountdown() {
    const now = Date.now();
    const diff = next - now;
    if (diff <= 0) {
      document.getElementById('countdown').textContent = '掃描中...';
      return;
    }
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    document.getElementById('countdown').textContent = `${h} 小時 ${m} 分鐘`;
  }
  updateCountdown();
  setInterval(updateCountdown, 30000);

  // ── 分類長條圖 ──
  const cats = data.categories;
  const catNames = Object.keys(cats);
  const catCounts = catNames.map(k => cats[k].count);
  const catColors = catNames.map((_,i) => {
    const palette = ['#58a6ff','#3fb950','#d2991d','#f85149','#a371f7','#79c0ff','#56d364','#e3b341','#ff7b72'];
    return palette[i % palette.length];
  });

  Plotly.newPlot('categoryChart', [{
    type: 'bar',
    x: catCounts,
    y: catNames,
    orientation: 'h',
    marker: { color: catColors, opacity: 0.8 },
    text: catCounts.map(c => c + ' 篇'),
    textposition: 'outside',
    textfont: { color: '#c9d1d9', size: 11 },
  }], {
    margin: { l: 140, r: 40, t: 10, b: 10 },
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { color: '#8b949e', size: 11 },
    xaxis: { showgrid: false, zeroline: false, showticklabels: false },
    yaxis: { showgrid: false, zeroline: false, autorange: 'reversed' },
  }, { responsive: true, displayModeBar: false });

  // ── 追蹤來源 ──
  document.getElementById('trackedBlogs').textContent =
    data.tracked_blogs || '（尚無追蹤來源，請透過 blogwatcher-cli add 新增）';

  // ── 最近文章 ──
  const recent = data.recent_articles;
  let html = '';
  let hasArticles = false;
  for (const [cat, articles] of Object.entries(recent)) {
    if (articles.length === 0) continue;
    hasArticles = true;
    html += `<div style="margin-bottom:12px"><strong style="color:var(--accent)">${cat}</strong>`;
    html += '<ul class="article-list">';
    for (const a of articles) {
      html += `<li>📄 ${a.name}</li>`;
    }
    html += '</ul></div>';
  }
  if (!hasArticles) {
    html = '<div class="empty-state"><div class="icon">📭</div><p>尚無歸檔文章</p><p style="font-size:0.8rem">使用 <code>blogwatcher-cli add</code> 新增追蹤來源後，系統會自動擷取並歸檔</p></div>';
  }
  document.getElementById('recentArticles').innerHTML = html;
}

// 初次載入 + 定時更新
refresh();
setInterval(refresh, 60000);
</script>
</body>
</html>"""


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            status = get_system_status()
            self.wfile.write(json.dumps(status, ensure_ascii=False, indent=2).encode())
        elif self.path == "/" or self.path == "/index.html":
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(HTML_DASHBOARD.encode())
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def log_message(self, format, *args):
        # 簡化日誌
        pass


def main():
    print(f"📊 量化交易知識庫儀表板")
    print(f"   → http://localhost:{PORT}")
    print(f"   API → http://localhost:{PORT}/api/status")
    print(f"   按 Ctrl+C 停止伺服器\n")

    server = http.server.HTTPServer(("0.0.0.0", PORT), DashboardHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n伺服器已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
