# 網格建立情境與邊界案例

日期：2026-10-29，Asia/Taipei。
本次屬於 [issue #28](https://github.com/faberline/formora/issues/28)。
使用已固定的 Blender 5.2.3 LTS / `e13b728c6880`。
本次只測量上游行為，Formora 執行仍為 `unrun`。

## 本次固定的案例

新增 131 組輸入，保留先前 57 組輸入與原始資料。
兩個新的上游程序各執行全部 131 組。
所有有限數值的比較誤差都是零。

| 類別 | 驗證內容 |
|---|---|
| 位置與對齊 | 世界、游標、視角，以及明確覆寫位置與旋轉 |
| 縮放 | 負縮放及其中一軸為零的建立參數 |
| 編輯與插入 | 建立後可編輯，以及插入既有網格 |
| UV | 產生、停用、建立第一層、保留兩個既有層及目前使用的層 |
| 既有資料 | 幾何、物件變換、UV、材質綁定與頂點、邊、面的原有歸屬 |
| 選取 | 頂點、邊及面各自的選取結果 |
| 下界 | 零尺寸、零半徑、零深度、圓錐兩端相等及圓環體特殊半徑 |

Torus 沒有 `scale` 與 `enter_editmode` 建立參數。
本次沒有對它傳入不存在的選項。
Torus 在既有網格中的插入仍有實際案例。

共用功能各有個別契約：位置與對齊、編輯插入、預設 UV。
預設 UV 契約也連結首批資料中的 20 組新物件案例。
十種形狀的原有契約都連結本次相對應的情境。
所有契約仍待完整內容審核。

## 明確的上游未定義值

零半徑 Circle 的 NGON 與 TRIFAN 填面會產生 NaN UV。
分別有 14 與 42 個未定義分量。
NaN 不是有限數值，不能用數值誤差宣稱通過。

原始分類保留為 `{"reference_nonfinite":"nan"}`。
其他位置與屬性仍須是有效資料。
意外出現於其他案例的未定義 UV 會令擷取失敗。

在 Formora 建模功能實作前，這兩組案例固定以下規則：

- 保留來源的幾何與拓撲。
- 只有來源未定義的 UV 分量使用有限零值。
- 操作回報 `degenerate_default_uv` 診斷。
- 其他有限數值仍使用原本的 `1e-6` 誤差上限。

比較兩份上游資料時，須使用 `--upstream-repeat`。
它只確認未定義分類能重現，不是 Formora 數值驗收。
沒有此旗標時，保留 NaN 標記的候選不能通過。
沒有有限來源 UV 的這兩組，UV 誤差欄位是 `null`，不是零誤差。
有限零值缺少診斷，也不能通過。
這個規則只適用於已列出的兩組案例。

## 比較器的修正

比較器現在檢查材質、目前 UV 層、選取範圍及原有／新增頂點歸屬。
這些資料仍依頂點及有方向的面對應，不要求相同編號。

零尺寸 Suzanne 的 507 個頂點完全重合。
重新編號測試先觸發舊搜尋上限。
修正後，面角 UV 的一對一對應先縮小候選範圍。
仍須通過完整邊、面方向、面角及屬性檢查。
搜尋上限與數值誤差沒有放寬，也沒有把頂點焊接為同一點。
UV 對應使用可重配的一對一匹配，避免排序或貪心選擇漏掉有效對應。

## 檔案與重跑

[資料與授權說明](../../baseline/reference/blender-5.2.3/README.md)適用於本次參考資料。

- `baseline/fixtures/mesh-creation-contexts.json`：固定輸入及未定義 UV 規則。
- `baseline/fixtures/mesh-creation-seed.json`：既有網格、變換、材質角色及兩種初始 UV 配置。
- `baseline/reference/blender-5.2.3/mesh-contexts/`：完整輸出、摘要及第二次比對。
- `baseline/sources/blender-5.2-object-types.html`：共用選項的官方手冊快照。

第一份輸出的每份 JSON 都由 `baseline/lock.json` 固定摘要。
新擷取器重用未修改的第一版擷取器。
兩份工具的摘要都保留在 manifest 中。
目前 32 項 Python 測試通過。
上游模式會依輸入及第二次捕捉核對。產品只須提供相同編輯能力，不要求舊式 GUI 模式。

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender_mesh_context_reference.py -- --suite baseline/fixtures/mesh-creation-contexts.json --output /private/tmp/formora-mesh-context-new
python3 tools/compare_mesh_reference.py --suite baseline/fixtures/mesh-creation-contexts.json --reference baseline/reference/blender-5.2.3/mesh-contexts --candidate /private/tmp/formora-mesh-context-new --upstream-repeat
python3 -m unittest discover -s tools/tests -v
```

## 尚未完成

完整上限、效能、參數組管理與一般物件型別切換仍需契約。
共用選項頁面與完整產品仍未完成盤點。
目前 13 項功能契約及 9,036 項來源待審核。
Formora 建模、其他平台上游執行與完整功能驗收都未因此通過。
嚴格基準檢查仍應返回 2。
本次不關閉任何 milestone。
