# quant-knowledge-dashboard

量化文獻自動歸檔系統的監控儀表板。Hermes Agent（DeepSeek profile）每天 08:00 與 20:00 掃描部落格與論文來源，把文章整理進 Obsidian vault 的「量化交易」資料夾；這個頁面顯示歸檔進度。

> 這是早期版本（2026-05），功能已併入 [Balaena Mission Control](https://github.com/anson1eechun/balaena-quant) 的 KB Explorer。

## 顯示內容

- 系統狀態：上次掃描時間、下次掃描時間（依 08:00 / 20:00 排程推算）、已處理 URL 數
- vault 統計：各分類文章數（不含 MOC 檔），每類最近 5 篇
- 追蹤中的部落格：呼叫 `blogwatcher-cli blogs` 取得
- `GET /api/status`：上述資料的 JSON

## 執行

```bash
python3 dashboard_server.py   # http://localhost:8899
```

只用 Python 標準庫，前端從 CDN 載入 Plotly。

## 注意

- 伺服器綁在 `0.0.0.0:8899`，同網段的人都看得到 vault 的分類與文章標題。只在自己的機器上用，或改成 `127.0.0.1`。
- vault、追蹤檔、blogwatcher、cron job ID 都寫死在檔案開頭，換環境要改。
