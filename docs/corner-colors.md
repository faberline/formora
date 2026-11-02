# 每個角的顏色

`Triangle.corner_colors` 保存三個角的顏色。
顏色順序與 `vertices` 相同。
每個顏色是 `[red, green, blue, alpha]`。
所有值都必須有限，且介於 0 和 1。
錯誤長度、NaN、無窮大與超出範圍的值會被拒絕。

```json
{
  "vertices": ["a", "b", "c"],
  "uv_layers": {},
  "corner_normals": null,
  "corner_colors": [[0.25, 0.5, 0.75, 1], [0.125, 0.75, 0.375, 1], [0, 0, 1, 1]],
  "material_slot": null
}
```

這是 straight linear RGBA。
RGB 不預先乘以 alpha，也不自動做 gamma 轉換。
顏色直接取代該角的材質 `base_color`。
`roughness` 與 `metallic` 仍使用原材質的規則。
選取高亮仍可蓋過表面顏色。

省略 `corner_colors`，或設為 `null`，會使用原材質顏色。
省略時，儲存結果也不加入這個鍵。
舊場景的序列化、雜湊與顯示路徑保持原行為。
新資料仍使用 Scene schema version 1；舊版本工具會拒絕不認識的新鍵。
Rust 的 `Triangle` 與 `Polygon` struct literal 要新增 `corner_colors: None`。
這個 source API 變更需要使用端重新編譯。

`Polygon.corner_colors` 使用相同 RGBA，但長度須等於多邊形的角數。
預覽切分依原角索引取色。
焊接後保留與 UV、角法線相同的角映射。
被移除的角不再使用；保留角的顏色不取平均。

原生 Scene JSON 使用 f64 保存值。
CPU 預覽把各角值轉為 f32，並傳入既有頂點色欄位。
GPU 在三角面內插值。
原 shader 與 alpha blending 保持原設定。
這沒有新增透明面的排序能力。

顏色屬於 mesh asset 的面。
如果兩個 instance 需要不同的烘焙顏色，使用端須建立不同的 asset 變體。
只在最終顏色相同時共用資產。
Formora 不解讀來源 tint weight 或遊戲規則。
使用端可先依自己的來源 shader，逐角算出 final RGB，再使用 alpha 1。

使用 `scene_apply` 的 `set_mesh_asset` 更新角顏色。
CLI、MCP 與 Rust 使用相同的資料與驗證。
CPU headless 的 geometry 雜湊包含最終 f32 角顏色。
即使 revision 不變，直接更新的 Scene 與 GeometryCache 也會讀取實際顏色。
PreparedScene 是不可變快照；改色後須重新 `prepare`。
相同快照仍可保留原顏色。

靜態 USD 投影目前不支援這個欄位。
匯出含角顏色的資產會明確失敗，且不覆寫既有輸出。
不要移除欄位來宣告色彩匯出通過。

驗證分為三部分：

- [記憶體測試](../tests/corner_colors.rs)檢查資料、映射、快取與雜湊。
- [CPU CI](../tools/headless_smoke.py)檢查 CLI／MCP、保存、程序結束與重開。
- [外部 GPU consumer](../tools/renderer-consumer/src/main.rs)檢查 live／prepared 像素相同、RGB 插值與舊快照。

真實 consumer 仍須用固定 commit 驗收自己的全部資產。
靜態繪製速度通過，不能代替角顏色驗收。
