# 重用相同資產的驗證

動態場景仍會逐次檢查目前資料。
`Scene::validate` 仍執行原有完整驗證。
沒有公開的「跳過驗證」旗標。

GeometryCache 可以重用自己先前成功驗證的明確網格。
它會比較完整 MeshAsset 結構與數值。
頂點、三角面／多邊形 UV、角法線、角 RGBA 與面法線也比較浮點位元。
正零與負零的變動會重新驗證。
這不依賴 revision 或記憶體位址。

只有這次仍被物件使用，而且沒有 recipe 或 vertex_weights 的相同資產可重用。
有生成配方、頂點權重、新資料、改動或未使用的資產仍執行原驗證。
場景 context、物件、父子關聯、材質及其引用、相機、光源、門與其他狀態每次仍檢查。
無效輸入會失敗；不能用舊畫面回報成功。
原本有效的頂點快照不會被失敗輸入修改。

每次準備只讀同一份不可變 Scene。
資產驗證、世界變換、相機、光源與頂點在同一次呼叫內使用它。
Renderer 仍接受相同 revision 的村民、HUD、幾何、材質、光與相機修改。
GPU PreparedScene 仍是不可變快照；需要時必須重新 prepare。
這個變更沒有新增動態分層 API 或 GPU instancing。

CPU API 不變：

```rust
let mut cache = formora::geometry::GeometryCache::default();
let vertices = cache.vertices(&scene)?;
```

Renderer 的 prepare／draw／capture 自動使用這條路徑。
直接 `geometry::vertices`、`geometry::world_transforms`、`geometry::camera` 與 headless 診斷仍保留完整參考驗證。
使用端不必宣告資料沒有改變。

[記憶體測試](../tests/preview_cache.rs)核對與完整驗證相同的錯誤及恢復。
測試包含暖快取後改成 NaN、無效 UV／法線／顏色、遺失頂點、材質、父節點與非使用資產。
生成配方及頂點權重也有回退案例。
頂點仍與直接參考路徑逐位元相同。

CI 保留原 256 實例比較與 25% 門檻。
另一個固定比較使用 32 個獨立資產，各有 2048 面。
暖機三次後保留八組配對樣本，並交替測量順序。
控制組額外呼叫完整 `Scene::validate`，再做暖幾何準備。
比較組只呼叫一次含驗證重用的準備。
中位數比值須不超過 75%。
這個控制組有額外驗證，不等於舊版來源的性能。
它也不是 GPU 或完整遊戲 frame。
完整 frame 仍須計入村民、介面、事件與需要的幾何更新成本。
FF Modern 的凍結場景、6.5 ms draw、13.45 ms 完整 frame 與人數門檻均保留。
