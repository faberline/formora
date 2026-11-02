# CPU headless 除錯

Headless 是不開視窗的模式。
這個模式也不需要 GPU。
它檢查場景資料，不宣告畫面、遊戲操作或 FPS 通過。

## 前置評估

場景讀取、操作核心與變換查詢原本就不依賴 GPU。
CPU 預覽幾何原本跟著 `preview` feature 建置，會一起引入視窗及 GPU 函式庫。
現在 `headless` feature 只額外使用 glam 與 bytemuck 進行 CPU 數學及頂點資料處理。
`preview` 也使用這個相同核心。
既有 `formora::preview::math` 路徑保持可用。

不必先完成 Renderer 快取，才能使用這個工具。
大型場景的 CPU 幾何準備仍可能很慢。
報告可以指出這個成本。它沒有保證即時速度。

## 建置與命令列

```sh
cargo build --locked --no-default-features --features headless
./target/debug/formora headless --scene CASE.scene.json
./target/debug/formora headless --scene CASE.scene.json --geometry --include-world
```

Windows 執行檔是 `target/debug/formora.exe`。
命令將 JSON 報告寫到 stdout。
檢查通過時 exit code 是 0。診斷失敗時是 1。命令用法錯誤時是 64。
它不開視窗、不建立 GPU adapter、不取得場景寫入鎖，也不改寫來源檔案。
即使另一個 MCP 程序持有寫入鎖，它也能讀取已儲存的場景快照。
它不會看到另一個程式尚未保存的記憶體狀態。

預設檢查場景結構、世界變換與相機。
`--geometry` 會另準備與預覽相同的 CPU 頂點資料。
這是 f32 預覽投影，不是原生 f64 幾何的替代品。
`--include-world` 會列出每個物件的 row-major 世界矩陣。
這種矩陣每列是一個陣列，平移位於最後一欄。
預設只輸出世界變換的雜湊，避免大量輸出。
`--width`、`--height` 指定相機投影尺寸。預設為 1280、800，且必須非零。
這些尺寸不會配置像素或 GPU 記憶體。

## 讀取結果

`passed` 只代表已要求的檢查通過。
`checks` 各有 `passed`、`failed`、`skipped` 或 `not_requested` 狀態。
前置階段失敗後，依賴它的檢查會標示 `skipped`。
未要求 `--geometry` 時，它會標示 `not_requested`。
不能把這兩種狀態當成幾何已通過。
CLI 的 `load` 失敗也可能包含讀入時的場景驗證錯誤。

報告包含原生資產計數、場景與世界變換的 SHA-256，以及可選的幾何計數、界限及雜湊。
資產計數不重複計算實例。預覽頂點計數則包含各實例與可見標記。
場景雜湊來自已載入場景的標準 JSON 序列化，不是輸入檔案的原始位元組雜湊。
世界變換與頂點雜湊使用固定欄位順序及 little-endian 浮點位元。
雜湊不包含耗時。相同來源、平台及輸入可重現它們。
雜湊相同不能代替跨平台精度或畫面驗收。

各階段 `elapsed_ms` 是該段 CPU 操作的實際耗時。
最外層 `elapsed_ms` 也包含報告中的雜湊與資料準備。
它們不包含 CLI 讀檔、JSON 解析或 stdout 輸出。
這些都不是 GPU 時間或完整遊戲 frame 時間。

## Rust 與 MCP

```rust
let request = formora::headless::DebugRequest {
    geometry: true,
    include_world: true,
    ..Default::default()
};
let report = formora::headless::diagnose(&scene, &request);
```

Rust API 直接讀取 host 的記憶體 Scene。
它不開檔案、不持有 Session，也不修改 Scene。
`formora::geometry` 提供共用的 CPU 變換、幾何與 picking 函式。
這個 feature 不會連入 wgpu、winit、arboard、pollster 或 png。

啟動同一個 CPU-only 執行檔的 `mcp --scene PATH`，即可呼叫 `scene_debug`。
引數為 `geometry`、`include_world`、`width`、`height`，預設值與 CLI 相同。
MCP 仍沿用原本的 Session 與寫入鎖。
診斷工具本身唯讀，不保存、不改 revision，也不加入 undo。
診斷失敗會回傳 `isError: true`，文字內容是同一份 JSON 報告。
大型案例可只查預設階段，再加開 geometry，並為 MCP client 設定足夠的等待時間。

## 驗證邊界

[記憶體測試](../tests/headless.rs)驗證變換、界限、同 revision 修改、穩定雜湊及失敗階段。
[CI 程序測試](../tools/headless_smoke.py)使用命令列與官方 MCP client。
它核對來源檔案未被診斷改動，並保留實際程序等待、exit code 與失敗報告。
[CPU CI](../.github/workflows/headless.yml)取消 DISPLAY／WAYLAND_DISPLAY，且檢查依賴樹沒有 GPU 或視窗函式庫。
GPU 擷取仍使用既有 `render` 命令或 [Renderer API](renderer-api.md)，需另做驗證。
