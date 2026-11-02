# 重用幾何準備

Renderer 會重用已準備的 CPU 頂點與未變的 GPU vertex buffer。
它不以 `Scene.revision` 或來源物件位址判斷場景是否改變。
每次 draw／capture 仍先驗證完整 Scene。
相機、光源與幾何共用同一次求得的世界變換。

每個使用中的 asset 只解析一次法線、三角形與材質槽。
各 entity 的頂點依實際幾何、世界矩陣及材質資料重用。
實例是共用同一 asset 的不同物件。
物件位置不同時，各實例仍有自己的世界座標頂點。
父變換與父反向矩陣都會影響快取鍵。
座標、著錄法線、世界矩陣與材質也核對浮點位元，包含正零與負零。
編輯模式的相機朝向標記會保守重建。

相同 revision 的修改仍會生效。
相機或光源的更新不需要重建一般靜態幾何，但仍更新繪圖資料。
無效 Scene 會失敗，不會偷偷顯示舊快取並回報成功。
幾何準備失敗後，下一個有效 Scene 可以恢復。

## CPU API

```rust
let mut cache = formora::geometry::GeometryCache::default();
let vertices = cache.vertices(&scene)?;
```

啟用 `headless` feature 即可使用，不需要 GPU。
`preview::math::GeometryCache` 也是同一個型別。
方法回傳 `Arc<Vec<Vertex>>`，也就是可共用的唯讀頂點快照。
呼叫者若用 `Arc::make_mut` 修改自己的副本，不會改到快取。
頂點內容與未快取的 `geometry::vertices` 逐位元相同。

這項快取會保留 asset 副本、解析後三角形、各物件頂點及合併頂點。
它使用更多 CPU 記憶體，來避免反覆運算。
冷路徑仍需要準備資料。改變的幾何仍可能需要重建合併陣列與 GPU buffer。
它沒有 GPU instancing、部分 buffer 更新或跨 Renderer 共用。
同一 Renderer 的繪圖與擷取須依序呼叫。

## 明確的 GPU 快照

大量靜態物件仍可能讓每幀驗證與世界變換很慢。
可先建立不可變的 GPU 快照，再只更新相機：

```rust
let prepared = renderer.prepare(&scene)?;
let camera = formora::geometry::camera_view(&scene, renderer.width, renderer.height)?;
renderer.draw_prepared(&prepared, &camera)?;
renderer.capture_prepared(&prepared, &camera, path)?;
```

`prepare` 完整驗證目前 Scene，也接受相同 revision 的新資料。
它回傳 `preview::PreparedScene`。
快照保留當時的頂點、材質、光源與註記。
它只可用於建立它的 Renderer，跨 Renderer 會失敗。
`camera()` 取得準備當時的相機，`vertex_count()` 取得頂點數。

`draw_prepared` 不接收或追蹤後來的 Scene。
修改幾何、材質、光源、註記或編輯標記後，必須再次呼叫 `prepare`。
不能用舊快照宣稱新的 Scene 已經顯示。
新快照不會改寫舊快照的 GPU 資料。
即使快照已存在，沒有視窗的 Renderer 仍不能 `draw_prepared`。

`camera_view` 只抽出並驗證相機及其父變換鏈。
它也保留父反向矩陣。
它不驗證其他物件，也不能代替完整 Scene 驗證。
原有 `geometry::camera` 仍會驗證完整 Scene。
viewport 尺寸改變後，須用新尺寸重新計算相機。
手動提供的 Camera 須有有限且可轉成 f32 的位置與投影資料。

原有 `draw(&Scene)` 與 `capture(&Scene)` 保持直接使用完整目前資料。
它們會驗證 Scene，沒有要求使用端採用快照。
準備與重新準備的成本須另外記錄，並計入需要更新的完整 frame。
純 `draw_prepared` 時間不能冒充整體互動效能。

## 固定檢查

[記憶體測試](../tests/preview_cache.rs)以未快取路徑比較完整頂點位元。
案例包含冷／暖路徑、共用資產、同 revision 修改、父變換、父反向矩陣、F32 變換、負與零縮放、著錄法線、選取、隱藏、多邊形、註記、ID 重用及失敗後恢復。
GPU CI 仍使用原有外部 consumer 的影像與錯誤檢查。

Linux CI 另跑固定的合成 CPU 比較。
它使用 256 個共用 189 面網格的物件，輸出 145152 個頂點。
先暖機，再保留八組同程序成對量測。
兩條路徑都包含相同 Scene 驗證與世界變換求值。
快取路徑的中位數必須不超過原路徑的 25%。
另外保留首次 cache 準備的時間。
這些是 CPU 準備資料的量測，不含 GPU、視窗呈現或完整遊戲 frame。
FF Modern 的完整 frame 與 1000 村民門檻，以及 Vortex 的完整城市互動標準，仍須由使用端各自驗證。
合成比較通過不能代替它們。
