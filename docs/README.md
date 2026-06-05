# docs/ — 文件結構與維護規則

這份檔是 docs/ 的「地圖」：每個檔（資料夾）放什麼、什麼時候要動它。
新增任何文件前，先確認它在下面的分類裡有位置。

## 1. 檔案介紹

```
CourseGen/
├── CLAUDE.md                 # 程式碼地圖、Steering Loop、文件索引
├── docs/
│   ├── README.md             # docs 地圖與維護規則
│   ├── design-docs/          # 設計信念與ADR（架構決策紀錄）
│   │   ├── core-beliefs.md
│   │   └── 00xx-*.md
│   ├── exec-plans/           # 進行中與完成的計劃
│   │   ├── active/
│   │   └── completed/
│   ├── generated/            # 程式自動生成的圖與文件
│   └── pic/                  # README 截圖（15 張）
└── tests/                    # invariant 的自動化驗證
```

## 2. 更新時機

| 路徑 | 什麼時候動它 |
|---|---|
| `CLAUDE.md` | Steering Loop 流程或文件索引改變 |
| `docs/README.md` | docs 結構或維護規則改變 |
| `docs/design-docs/core-beliefs.md` | 通用信念被人類決策改變 |
| `docs/design-docs/00xx-*.md` | 不改舊的；有新決策推翻舊決策時，新增一份 |
| `docs/exec-plans/` | 開新任務（放 active）→ 完成後歸檔（移 completed） |
| `docs/generated/` | 由生成腳本更新 |
| `docs/pic/` | UI 改版、要換截圖時 |
| `tests/` | 浮現一條 invariant 就補一條測試 |
