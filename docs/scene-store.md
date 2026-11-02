# 核心持有的場景

`SceneStore` 是選用的場景容器。
核心持有完整 `Scene`，並驗證每次更新。
外部程式只能取得唯讀場景。
這樣可省去未變模型資料的逐幀比對。
原有 `Scene` 介面仍按目前實值檢查資料。

## 建立及更新

```rust
use formora::scene::{Scene, Transform};
use formora::scene_store::{SceneStore, SceneUpdate};
use std::collections::BTreeMap;

fn move_object(store: &mut SceneStore, id: &str, transform: Transform)
    -> formora::scene::Result<bool>
{
    store.apply(SceneUpdate {
        transforms: BTreeMap::from([(id.to_owned(), transform)]),
        ..SceneUpdate::default()
    })
}

fn load(scene: Scene) -> formora::scene::Result<SceneStore> {
    SceneStore::new(scene)
}
```

`new` 完整驗證輸入。
`replace_all` 也完整驗證新場景。
失敗時保留舊場景及所有標記。
`scene()` 傳回 `&Scene`。
`into_scene()` 消耗容器，取回原場景。
容器不提供可寫的場景參照。

`SceneUpdate` 支援以下欄位：

| 欄位 | 行為 |
|---|---|
| `entities`、`mesh_assets`、`materials` | `BTreeMap<String, Option<T>>`。`Some` 新增或替換。`None` 移除。 |
| `transforms` | 按 ID 替換完整 `Transform`。包含精度與 delta。先處理 entity 替換，再處理此欄。目標不存在時失敗。 |
| 其他所有 `Scene` 欄位 | `Option<原型別>`。外層 `None` 保留原值。`active_camera` 等可空欄位使用兩層 `Option`。 |

整批更新只會全部成功或全部失敗。
移除材質時，也須更新同批中的使用者。
父節點、相機、註記及製作上下文仍須符合原有規則。
被更新的模型會完整驗證，即使沒有物件使用它。
未變模型可重用核心已持有的驗證證據。
程序配方與頂點權重仍執行原完整檢查。
只改 transform 時，不會複製所有模型以便還原。
核心移動舊值到私有還原表。

## 值標記

`ValueStamp` 是核心產生的不可建構標記。
比較兩個標記，可知道核心是否接受過該值的更新。
它不是可傳入的驗證許可。

| 方法 | 對象 |
|---|---|
| `stamp()` | 整個容器 |
| `entity_stamp(id)` | 一個 entity |
| `mesh_stamp(id)` | 一個模型資產 |
| `material_stamp(id)` | 一個材質 |
| `settings_stamp()` | 模型、entity、材質以外的場景欄位 |

缺少的 ID 傳回 `None`。
空批次傳回 `Ok(false)`，保留標記。
成功的非空批次傳回 `Ok(true)`。
核心保守更新所提交欄位的標記，即使新舊值相同。
失敗批次保留所有標記。
`revision` 是一般資料；核心不自動增加或信任它。

Host 可保存標記，判斷固定分區是否需要重建。
不必逐幀複製整個固定場景。
固定與動態分區可各自使用容器。
Host 須同步共享材質及父節點。
相機與有序全域燈光須來自當前完整場景。
分區結果仍須與完整場景的原有驗證及畫面參考比較。
標記不會自動完成跨容器同步。

## 準備畫面

`GeometryCache::vertices_store(&SceneStore)` 不需要 GPU。
啟用 `headless` 後可使用此方法。

啟用 `preview` 後，可使用：

```rust
# use formora::{preview::Renderer, scene_store::SceneStore};
# fn prepare(renderer: &Renderer, store: &SceneStore) -> formora::scene::Result<()> {
let first = renderer.prepare_store(store)?;
let next = renderer.prepare_store_from(&first, store)?;
# let _ = next;
# Ok(())
# }
```

後者沿用舊快照的 CPU 快取分支。
它仍檢查 Renderer 所有權。
兩者都保留原有世界變換、材質、角點及 GPU f32 檢查。
舊快照保持不變。
有效的 f64 場景可能無法轉成有效 GPU f32 資料。
此時準備會失敗。
Host 須保留上個成功快照，修復資料後再準備。
失敗不能算作呈現成功。

## 驗證範圍

CI 的獨立 consumer 會比較 raw、容器及 layer 的 PNG 像素。
它也測試同 revision 修改、原子失敗、GPU 轉換失敗與修復及舊快照。
CPU 測試保留無效未使用模型、父鏈及材質規則。

固定效能案例使用 32 個資產，每個含 2048 個三角形。
先暖機 3 次，再交替量測 8 組完整更新及準備。
每組按位比較輸出。
容器路徑與 raw 路徑的中位時間比須不大於 0.25。
冷啟動及原始樣本都保留。
舊有三項效能門檻維持原值。
這項案例不能替代 FF 原工作量、實體解析度或完整每幀門檻。
更新、驗證、投影、上傳、回讀及 resize 成本仍須計入實際幀。
