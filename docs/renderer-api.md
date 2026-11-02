# 外部 Rust Renderer

此介面讓外部程式使用現有的基本 GPU 預覽器。
外部程式負責視窗、事件迴圈、輸入及遊戲狀態。
Renderer 只讀取傳入的 `Scene`。
它不需要 `Session`、`Editor` 或檔案寫入鎖。

## 來源與依賴

Formora 尚未發布 crates.io SDK。
固定 Git commit，不要依賴移動中的分支。
在依賴設定中啟用 `features = ["preview"]`。
未啟用此 feature 時，`formora::preview` 不存在。

目前根 `Cargo.lock` 固定 `winit 0.30.13`、`wgpu 26.0.1`。
`Cargo.toml` 的 winit 相容範圍從 0.30.12 開始。
外部程式必須解析成相同的 winit 型別，才能傳入 `Arc<Window>`。
本例明確使用 `winit = "=0.30.13"`。
Rust 最低版本為 1.85。

```rust
use formora::preview::Renderer;
use formora::scene::Scene;
use std::{path::Path, sync::Arc};
use winit::window::Window;

async fn setup(window: Arc<Window>) -> formora::scene::Result<Renderer> {
    let size = window.inner_size();
    Renderer::new(Some(window), size.width, size.height).await
}

fn redraw(renderer: &mut Renderer, scene: &Scene) -> formora::scene::Result<()> {
    renderer.draw(scene)
}

fn capture(renderer: &Renderer, scene: &Scene) -> formora::scene::Result<()> {
    renderer.capture(scene, Path::new("frame.png"))
}
```

在 winit `ApplicationHandler::resumed` 中建立 `Arc<Window>`。
先取得非零實體像素尺寸，再建立 Renderer。
將 `Resized` 事件的非零實體尺寸傳給 `resize`。
在 `RedrawRequested` 事件呼叫 `draw`。
依平台規則在主執行緒執行事件迴圈。
視窗最小化時，host 應暫停繪圖。
Renderer 持有視窗的 Arc。結束時先釋放 Renderer，再釋放 host 的視窗。
本介面沒有新增 suspend/resume 或裝置重建協定。

## 四個方法

| 方法 | 實際行為 |
|---|---|
| `async new(Option<Arc<Window>>, u32, u32) -> Result<Renderer>` | `Some` 建立視窗 surface；`None` 建立離線 GPU renderer。零尺寸回傳錯誤。需要可用 adapter。 |
| `resize(&mut self, u32, u32)` | 重建深度緩衝並更新 surface。任一尺寸為零時維持原尺寸。 |
| `draw(&mut self, &Scene) -> Result<()>` | 將目前 Scene 畫到視窗。無視窗時回傳錯誤。每次讀取傳入資料，不依賴 revision 變化。 |
| `capture(&self, &Scene, &Path) -> Result<()>` | 另畫離線影像，等待 GPU 回讀，再寫入 RGBA PNG。使用 renderer 的目前尺寸。 |

`width`、`height` 及 `adapter` 是現有公開欄位。
只讀取尺寸欄位。修改尺寸須呼叫 `resize`，否則 GPU 資源會與欄位不一致。
各方法的 `Result` 使用 `formora::scene::SceneError`。
裝置限制、配置及記憶體耗盡等 wgpu 錯誤仍可能造成 panic。
不要把任意使用者尺寸直接傳入 GPU。

`draw` 遇到 Lost／Outdated 時會重設 surface，並略過這一幀。
Timeout／Other 也可能略過一幀。
上述情況仍回傳 `Ok(())`，所以它不是呈現成功的收據。
其他 surface 錯誤會回傳錯誤。

`capture` 不是桌面截圖，也不是前一個已呈現 frame 的讀回。
它會再次讀取指定 Scene 並繪圖。
它會覆寫既有檔案。它不是原子保存。
無效 Scene 在寫檔前會被拒絕，但磁碟寫入失敗仍可能留下部分檔案。
父目錄必須存在。GPU 讀回會阻塞呼叫執行緒。

## Host 狀態

host 可在記憶體中建立或更新 `Scene`，先呼叫 `Scene::validate()`，再交給 Renderer。
相同 revision 的新幾何、材質與相機仍會生效。
渲染不會推進時間、執行命令或改寫 Scene。
正式遊戲的時間、選取、建造、存檔及識別碼映射仍由 host 負責。
不要將可編輯 Scene 的 revision 當成遊戲狀態版本。

每次繪圖仍重算世界變換與頂點，並建立 GPU 緩衝。
目前沒有 prepare/cache、局部更新或 draw-call 效能保證。
大型城市必須另做效能驗收。
材質、光照與幾何的支援範圍沿用[基本預覽](preview.md)。
本次沒有加入紋理、骨架、動畫或 per-corner RGBA 繪圖支援。
資料精度見[操作精度](operation-precision.md)。

## 外部 consumer 檢查

[獨立 crate](../tools/renderer-consumer/Cargo.toml)只使用公開 API。
[程式](../tools/renderer-consumer/src/main.rs)自行管理 winit 視窗，沒有呼叫 `preview::run`。

```sh
cargo check --locked --no-default-features --lib
cargo clippy --locked --manifest-path tools/renderer-consumer/Cargo.toml --all-targets -- -D warnings
```

功能測試由 [CI](../.github/workflows/renderer-consumer.yml) 執行。
CI 在四種 runner 編譯外部 consumer。
Linux 另以軟體 Vulkan 及 Xvfb 測試 GPU 擷取與 host-owned 視窗。
Xvfb 是虛擬顯示器，不代表實體桌面或硬體 GPU 驗收。
沒有 adapter、無法建立視窗或檢查失敗時，測試必須失敗。
CI 保留 PNG、adapter 名稱及程序輸出。

測試重用同一 Renderer，分別更新幾何、材質與相機，並保持 Scene revision 不變。
它比較重複擷取、各次影像差異、非對齊寬度、resize、零尺寸、無視窗 draw、無效場景與輸出錯誤。
FF Modern 與 Vortex 的實際遊戲視窗及互動流程須各自保留實測證據。
編譯、虛擬視窗與單張圖片不能代替完整遊戲驗收。
