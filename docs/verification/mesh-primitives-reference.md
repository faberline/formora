# 網格基本形狀參考資料

日期：2026-10-29，Asia/Taipei。
本次屬於 [issue #22](https://github.com/faberline/formora/issues/22)。
完整功能盤點仍由 [issue #14](https://github.com/faberline/formora/issues/14) 追蹤。

## 固定來源

參考版本是 Blender 5.2.3 LTS。
建置是 `e13b728c6880`，2026-10-22 01:31:22，Darwin Release。
本地執行檔的 SHA-256 是：

```text
de1e04556f03716d25682dd01cc776d94e512f7ff8673049a486c3e8b7f9b619
```

正式版本與手冊來源仍依 `baseline/lock.json`。
新增的手冊快照保留實際內容與摘要。
參考資料的 `url` 表示其上游來源。
它不表示產生的幾何 JSON 是從該網址下載。

## 本次內容

十種形狀共有 57 組固定輸入。
包含預設值、關閉 UV、位置與旋轉，以及各形狀的大小、細分、填面和半徑變體。
UV 是貼圖在面上的二維座標。
每份資料保留頂點、邊、有方向的面、法線、每個面角的 UV、平滑旗標和變換。

比較標準在 Formora 對應建模功能實作前固定。
局部與世界座標每軸的絕對誤差上限均為 0.000001 公尺。
法線及 UV 每個分量的絕對誤差上限為 0.000001。
拓撲、數量、面方向及 UV 層須相符。
拓撲是頂點、邊與面的連接關係。
頂點和面可以使用不同編號。

## 已執行的檢查

- 以兩個新的 Blender 程序各跑完 57 組輸入。
- 第二次輸出的面與邊編號有部分不同。不能宣稱檔案完全相同。
- 以一對一頂點對應和有方向的面循環比較。57 組均通過。
- 重跑後的最大座標、法線及 UV 誤差均為 0。
- 另外檢查平面、方塊及三角球的解析數量與大小。
- 兩種圓環體半徑表示法產生相同幾何。
- 錯誤版本與未允許的操作都以結束碼 1 拒絕，沒有產生輸出目錄。
- 在第二組操作故意使用錯誤參數。程序失敗後，部分輸出已移除。
- 以既有輸出目錄重跑時，程序拒絕執行。原有檔案的摘要全部保持相同。
- 十項比較工具測試通過。測試涵蓋重新編號、反轉面方向、破壞邊、UV、法線及座標，以及缺少 UV、非有限數值和重合頂點。
- 先以放大 100 倍的物件證明局部誤差可能被放大而漏過。修正後，逐點世界座標檢查會拒絕相同錯誤。
- 擷取紀錄同時固定輸入、工具、實際參數與每份網格的摘要。測試會核對這些關係。

[參考資料](../../baseline/reference/blender-5.2.3/README.md)包含輸入、完整結果和摘要的說明。
第一次輸出的每份 JSON 都由 `baseline/lock.json` 固定摘要。

## 重跑

輸出目錄必須是新的目錄。
以下是已使用的命令形式：

```sh
/Applications/Blender.app/Contents/MacOS/Blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tools/blender_mesh_reference.py -- --suite baseline/fixtures/mesh-primitives.json --output /private/tmp/formora-mesh-reference-new
python3 tools/compare_mesh_reference.py --suite baseline/fixtures/mesh-primitives.json --reference baseline/reference/blender-5.2.3/mesh-primitives --candidate /private/tmp/formora-mesh-reference-new
python3 -m unittest discover -s tools/tests -v
```

## 尚未驗收

Formora 尚未執行這批建模案例。
所有十項功能契約保持 `pending`。
來源清單仍有 8,219 項待審核。
共同選項、編輯模式插入、完整參數範圍和退化輸入仍需盤點。
渲染品質與效能需要另立標準。
Windows 和 Linux 的 Blender 參考執行未做。
基準嚴格檢查仍應以結束碼 2 表示未完成。
本次不關閉任何 milestone。
