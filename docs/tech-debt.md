# 技術債

已知該改、但還沒改的地方。

## 格式

每條技術債一個 `##` 標題，底下三項：

- 現況：目前怎麼做的，缺口在哪。
- 影響：不還的話會有什麼風險或代價。
- 對策：理想的做法，以及大致怎麼改。

## 新增節點類型要改多個登記表

- 現況：新增一種節點類型，要同步改 5 個地方——`NodeType` enum、對應的 Content model class、`CONTENT_MODELS`、`CONTENT_PROMPTS`、`_RENDERERS`，分散在 schemas、agents、prompts、ui 四個檔。
- 影響：每加一種類型都要跨多檔改多處，成本高、容易漏改。（`tests/test_content_type_registry.py` 會抓到漏掉的那一處，但只能擋「漏」，免不了手動逐處修改。）
- 對策：把登記集中到一處，例如每種類型用一個物件或註冊機制同時帶上 model / prompt / renderer，新增時只動一個地方，其餘自動衍生。
