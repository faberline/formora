# Agent 操作介面

CLI 和 MCP 共用 Rust 指令核心。
兩種介面的成功修改都會先儲存，再回傳結果。
一次只允許一個程序寫入場景。
其他程序仍可讀取已儲存的場景。

## 建立與查詢

以下命令適用於 macOS 的開發環境。
先在 repository 根目錄建置。

```sh
cargo build --locked
./target/debug/formora scene init --scene /private/tmp/formora-room.scene.json --demo-room
./target/debug/formora scene inspect --scene /private/tmp/formora-room.scene.json
./target/debug/formora scene schema
```

`init` 不會覆寫既有場景。
`inspect` 不修改場景。
`schema` 輸出操作資料的 JSON Schema，也就是可由程式讀取的欄位規則。

## 修改

先查詢目前的 `revision`，也就是場景版本號。
把版本號放入 `expected_revision`。
以下請求假設場景版本號是 1。

```json
{
  "expected_revision": 1,
  "commands": [
    {"operation": "set_door_duration", "id": "front_door", "duration_seconds": 2.0},
    {"operation": "trigger_door", "id": "front_door", "open": true},
    {"operation": "advance", "seconds": 1.0}
  ]
}
```

把請求存為 `request.json`，再執行：

```sh
./target/debug/formora scene apply --scene /private/tmp/formora-room.scene.json --request request.json
```

成功後，門的進度是 0.5，場景版本號是 2。
也可使用 `--request -` 從標準輸入讀取 JSON。
單次 `apply` 的程序結束後，復原紀錄不會保留。

## 持續操作

```sh
./target/debug/formora scene serve --scene /private/tmp/formora-room.scene.json
```

每一行是一個 JSON 請求。每個回應也只佔一行。
此程序保留復原紀錄，直到程序結束。

```json
{"id":"inspect","name":"scene_inspect","arguments":{}}
{"id":"door","name":"scene_inspect","arguments":{"entity":"door_panel"}}
{"id":"undo","name":"scene_undo","arguments":{"expected_revision":2}}
```

最後一個請求只有在此程序已成功修改過場景時，才有可復原的紀錄。
復原後的版本號仍會增加。

## MCP

```sh
./target/debug/formora mcp --scene /private/tmp/formora-room.scene.json
```

讓外部 MCP client 啟動此程序，並連接其標準輸入與標準輸出。
MCP 是 agent 用來發現和呼叫工具的協定。
此介面支援 `2025-11-25`、`2025-06-18` 和 `2025-03-26` 版本。
參考 [MCP 生命週期](https://modelcontextprotocol.io/specification/2025-11-25/basic/lifecycle)、
[工具](https://modelcontextprotocol.io/specification/2025-11-25/server/tools)與
[標準輸入輸出傳輸](https://modelcontextprotocol.io/specification/2025-11-25/basic/transports)。

工具如下：

| 工具 | 用途 |
|---|---|
| `scene_inspect` | 查詢整個場景或單一物件 |
| `scene_apply` | 檢查版本號，再執行並儲存一批指令 |
| `scene_undo` | 復原此程序中的上一批操作，並儲存結果 |

初始化完成前不能呼叫工具。
工具失敗時，MCP 回傳 `isError: true`。
無效指令、過期版本號及儲存失敗都不會提交記憶體中的修改。
MCP 的標準輸出只放協定訊息。
啟動失敗的說明寫入標準錯誤。

## 外部 client 測試

在獨立的 Python 環境安裝測試依賴後執行：

```sh
python3 -m pip install -r tools/requirements-mcp.txt
python3 tools/mcp_smoke.py target/debug/formora
```

測試使用官方 Python MCP SDK 2.3.0。
它會檢查初始化、工具發現、欄位規則、查詢、修改、版本衝突、復原和重開。
測試只使用新建的暫存場景。

目前沒有成果視窗與點擊試玩介面。
這些功能由 [預覽與實機驗收工作](https://github.com/faberline/formora/issues/18)處理。
此介面的測試通過不能作為 milestone 0.1 的完整驗收。
