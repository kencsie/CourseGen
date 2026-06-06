# docs/ — 文件結構與維護規則

這份檔是 docs/ 的「地圖」：每個檔（資料夾）放什麼、什麼時候要動它。
新增任何文件前，先確認它在下面的分類裡有位置。

## 1. 檔案介紹

```
CourseGen/
├── README.md                 # 對外說明：功能、架構概覽、使用方式
├── CLAUDE.md                 # 程式碼地圖、Steering Loop、文件索引
├── docs/
│   ├── README.md             # docs 地圖與維護規則
│   ├── design-docs/          # 決策紀錄
│   │   ├── README.md         # 決策紀錄的模板與規則
│   │   └── YYYY-MM-DD-*.md   # 各項設計決策
│   ├── exec-plans/           # 進行中與完成的計劃
│   │   ├── README.md         # 計劃模板與維護規則
│   │   ├── active/
│   │   └── completed/
│   ├── tech-debt.md          # 已知技術債清單
│   └── pic/                  # README 截圖（15 張）
└── tests/                    # invariant 的自動化驗證
```

## 2. 更新時機

| 路徑 | 什麼時候動它 |
|---|---|
| `README.md` | 功能、架構或使用方式改變 |
| `CLAUDE.md` | Steering Loop 流程或文件索引改變 |
| `docs/README.md` | docs 結構或維護規則改變 |
| `docs/design-docs/` | 設計決定新增或變更時 |
| `docs/exec-plans/` | 開新任務（放 active）→ 完成後歸檔（移 completed） |
| `docs/tech-debt.md` | 發現新技術債，或還掉舊的時 |
| `docs/pic/` | UI 改版、要換截圖時 |
| `tests/` | 浮現一條 invariant 就補一條測試 |
