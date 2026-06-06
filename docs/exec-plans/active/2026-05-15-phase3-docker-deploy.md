# Phase 3：容器化部署（Docker + HTTPS）
- 狀態：active
- 期間：2026-05-15 →
- 證明：—

## 背景
Phase 1、2、2.5 已合併，但 app 仍跑在本機 uv run streamlit、Postgres 為手動 ad-hoc container、無 reverse proxy、無 HTTPS。要部署到 VPS，須先把 app + db + caddy 打包成 `docker compose up -d` 可一次拉起的 stack。

## 計劃
1. Dockerfile（python:3.12-slim + uv，多階段以最大化 layer cache）—— 用 slim 而非 alpine，因 psycopg2-binary 沒有 musl wheel、alpine 需 source build。
2. docker-compose.yml（db / app / caddy 三個 service，db 不對外 expose port）—— db 只走內部網路、host 完全摸不到 PG；`${DB_PASSWORD:?}` 沒設就 fail-fast，避免裸跑預設密碼。
3. Caddyfile（reverse proxy + ACME 自動 HTTPS + WebSocket matcher）—— Caddy 自動申請與續約憑證、零維護，並明寫 websocket 升級讓 Streamlit 即時互動不斷線。
4. .streamlit/config.toml、.dockerignore、.env.production.example —— 固定 server 設定、縮小 build context、提供部署範本。
5. PG 資料遷移 SOP（pg_dump → restore 進新 volume，寫進 README 而非腳本）—— 一次性操作不值得腳本化。
6. README 加 Deployment 章節（dev / VPS self-host / 本機 compose 試跑三種模式）—— 讓使用者照步驟即可上線。

## 驗證
（待完成）

## 成果
（待完成）
