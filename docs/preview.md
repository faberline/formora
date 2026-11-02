# 成果預覽

預覽直接使用 Rust 場景資料。
它顯示方塊、平面、材質、點光源和鏡頭。
父物件的變換也會套用到子物件。
目前是基本預覽。完整渲染功能屬於 0.3。

外部 Rust 程式可用[公開 Renderer API](renderer-api.md)管理自己的視窗。

## 建置與啟動

```sh
cargo build --locked --features preview
./target/debug/formora scene init --scene /private/tmp/formora-room.scene.json --demo-room
./target/debug/formora preview --scene /private/tmp/formora-room.scene.json
```

`init` 不會覆寫既有場景。
預覽需要可用的原生 GPU。
沒有 GPU 時會失敗，不會產生假的成功畫面。

讓 agent 與人同時操作同一份場景：

```sh
./target/debug/formora mcp --scene /private/tmp/formora-room.scene.json --preview
```

讓外部 MCP client 啟動這個命令。
MCP 和視窗共用同一個寫入 session。
session 是持有場景及寫入鎖的工作階段。
它不會另開第二個寫入程序。

## 觀看與回饋

| 操作 | 結果 |
|---|---|
| 點門 | 開門或關門 |
| Space | 播放或暫停 |
| R | 回到已儲存的場景狀態 |
| Shift＋點物件 | 在該位置建立註記 |
| 輸入文字，再按 Enter | 儲存註記 |
| Command＋V，或 Control＋V | 貼上註記文字 |
| Esc | 取消註記；沒有註記草稿時則關閉預覽 |
| S | 輸出目前畫面的 PNG |

註記會儲存物件 ID、世界座標和文字。
紅色標記顯示該世界座標。
Agent 可用 `scene_inspect` 讀取註記。
空白註記不會儲存。

`--capture` 可指定 PNG 路徑。
程式會在第一幀輸出一次，之後按 S 可更新該檔案。
沒有指定路徑時，S 會寫入系統暫存目錄的 `formora-preview.png`。

播放只改變記憶體中的執行狀態。
它不會每一幀都寫檔，也不會填滿復原紀錄。
Agent 修改開門時間時，播放中的門會保留目前位置。
Agent 明確觸發開門或關門時，預覽會接受新的目標。

## 輸出圖片

```sh
./target/debug/formora render --scene /private/tmp/formora-room.scene.json --output /private/tmp/formora-room.png
```

此命令使用同一個 GPU 渲染器。
它輸出已儲存場景的畫面。
它不讀取另一個預覽程序中尚未儲存的播放狀態。

## macOS 開發用 App

```sh
python3 tools/build_macos_app.py --binary target/debug/formora --output /private/tmp/Formora.app
```

這會建立可由 macOS 辨識的開發用 `.app`。
它不是正式發布安裝包。

## 驗證範圍

[實測紀錄](verification/macos-preview.md)保留畫面與資料。
目前已驗證 macOS Metal、原生點選、播放、註記、MCP 更新及重開。
中文註記的標準貼上已通過。
實體中文輸入法仍未驗證。
Windows 和 Linux 的原生視窗與 GPU 實機測試仍未執行。
這些結果不代表 Blender 或 Unreal 的完整功能已對齊。
