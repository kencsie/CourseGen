ROADMAP_GENERATION_PROMPT = """
你是一位精通知識圖譜與教學設計的專家。請基於檢索資訊，為使用者生成一份「技能依賴樹狀圖」。

你的任務為以下：
1. **生成 Graphviz (DOT) 程式碼**：用於視覺化技能的依賴關係（從基礎到進階）。

輸出要求：
Graphviz 區塊必須語法正確，確保節點名稱沒有非法字符（建議用引號包起來）。
線條方向必須代表「先備知識 -> 進階技能」的流向。

請嚴格參考以下的 One-Shot 範例格式進行輸出：

### 範例輸入
**問題**：我是 Celeste 新手，目標是通關 7C (The Summit C-Side)，請給我學習路徑。
**檢索資訊**：(略... 關於 Celeste 的基礎操作、衝刺機制、牆壁彈跳 Wallbounces、以及 7C 的關卡結構設計...)

### 範例輸出
```graphviz
digraph G {{
    // 設定圖表方向為從左到右
    rankdir=LR;
    node [shape=box, style=rounded, fontname="Helvetica"];

    // 節點定義
    Start [label="登山新手", shape=ellipse];
    Basics [label="基礎操作\n(跳躍/抓牆/衝刺)"];
    Physics [label="動量物理學\n(慣性/重力)"];
    
    // 進階技巧
    Wall_Kick [label="牆面跳躍\n(Wall Kick vs Climb Jump)"];
    Wallbounce [label="牆壁彈跳\n(Wallbounce)"];
    Diamond_Mgmt [label="水晶連鎖\n(Dash Refill)"];
    
    // 心理與實戰
    Consistency [label="肌肉記憶與穩定度"];
    Room_3 [label="7C 最後房間\n(長程無檢查點)"];
    Victory [label="7C 登頂", shape=circle, style=filled, fillcolor="gold"];

    // 依賴關係
    Start -> Basics;
    Basics -> Physics [label="理解移動"];
    Basics -> Wall_Kick;
    
    // 關鍵技術依賴
    Basics -> Wallbounce [label="衝刺+跳躍組合"];
    Wall_Kick -> Wallbounce [label="時機掌控"];
    Physics -> Diamond_Mgmt [label="空中控制"];
    
    // 7C 特定需求
    Wallbounce -> Room_3 [label="核心機制(必須)"];
    Diamond_Mgmt -> Room_3 [label="空中續航"];
    Consistency -> Room_3 [label="容錯率為0"];
    
    Room_3 -> Victory;
}}
(範例結束，請依此格式回答)

真實問題： {question}
檢索資訊： {retrieved_doc}
"""
