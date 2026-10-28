# 功能對齊基準

GitHub milestones 是路線圖的主要來源。
目前的實作入口是 [0.0 追蹤 issue](https://github.com/faberline/formora/issues/1)。

## 固定來源

基準採 Blender 5.2.3 LTS 與 Unreal Engine 5.8.4 正式版。
查核日期是 2026-10-29，時區是 Asia/Taipei。

- [Blender 正式版本](https://www.blender.org/releases/)
- [Blender 5.2.3 下載摘要](https://download.blender.org/release/Blender5.2/blender-5.2.3.sha256)
- [Blender 5.2 手冊](https://docs.blender.org/manual/en/5.2/)
- [Unreal Engine 5.8 正式發布](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [Unreal Engine 5.8.4 正式 Hotfix](https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775)
- [Unreal Engine 5.8 手冊](https://dev.epicgames.com/documentation/unreal-engine?application_version=5.8)

Unreal 的完整產品版本是 5.8.4，文件版本是 5.8。
Blender 的完整產品版本是 5.2.3，文件版本是 5.2。
[參考建置實測](verification/reference-builds.md)保留兩套實際程序回報的版本與執行檔摘要。
這些探測只證明版本。它們不能代替功能或 GPU 驗收。

`baseline/lock.json` 的格式版本是 2。
`version` 固定三段完整產品版本。
`documentation_version` 固定兩段手冊版本。
`reference_build` 固定建置 ID 與已登記摘要的證據路徑。
來源清單、功能對照表及測試契約仍使用格式版本 1。

`baseline/lock.json` 固定來源及本地檔案的 SHA-256。
SHA-256 是檔案內容摘要，可用來檢查檔案是否改變。
它不能證明文件內容完整，也不能代替來源審核。

`baseline/inventory.json` 是來源清單。
`baseline/catalog.json` 是功能對照表。
`baseline/cases/` 放逐項驗收契約。
來源清單須保留固定 manifest 內的全部來源。
刪除來源不會縮小驗收範圍，而會使檢查失敗。

## 檢查方式

檢查資料格式與檔案摘要：

```sh
cargo run --locked -- baseline check --root .
```

要求來源覆蓋與測試契約全部齊備：

```sh
cargo run --locked -- baseline check --root . --strict
```

命令輸出 JSON。結束碼 0 表示所要求的檢查通過。
結束碼 1 表示資料無效。
結束碼 2 表示格式有效，但基準尚未齊備。
結束碼 64 表示命令用法錯誤。

`baseline_ready` 只表示來源與契約的登記條件齊備。
它不是獨立內容審核，也不是產品驗收。
`product_acceptance` 保持 `unrun`，因為此工具不執行產品測試。
CI 的通過只表示契約檢查通過。
`unverified_builds` 列出缺少版本探測證據的產品。
有缺少項目時，嚴格檢查不能通過。

## 逐項審核

來源先保持 `pending`，意思是尚未審核。
不能用文件標題數量代替功能覆蓋率。
一頁文件可能包含多個功能。每個功能都須有個別案例。

納入來源時，須把狀態改為 `include`，並填入功能 ID。
來源和功能必須互相引用。
排除來源時，須使用既定排除範圍並寫明理由。
不能把尚未支援的功能改成排除項目。

每項功能須指定 0.1 至 0.9 的實作版本。
測試契約須包含初始資料、操作、預期結果及證據要求。
數值結果須指定適用的誤差範圍。
品質與效能案例還須固定參考硬體、量測方法和通過標準。

`complete_products` 只能在完整盤點該產品後填入。
自動採集完成不代表盤點完成。
所有契約都須經內容審核，才能標記 `accepted`。
0.0 還須經 Codex 獨立內容審核，才可關閉。

## 來源採集

以下命令只採集固定版本的來源資料。
它不會接受任何產品功能。
輸出目錄必須是新的目錄，以保護固定基準。

```sh
python3 tools/collect_baseline.py --output /private/tmp/formora-source-review --date 2026-10-29 --unreal-depth 1
```

Blender 來源使用官方 Sphinx 索引。
Sphinx 索引列出文件頁面與章節位置。
Unreal 來源使用官方頁面的文件清單。
採集深度 1 只讀取首頁及下一層清單，不是完整盤點。
未取得的文件保留在採集失敗紀錄中。
來源採集不啟動參考產品。它產生的草稿不包含版本探測證據。
不要用採集草稿覆寫現有的建置 pin 或功能契約。

使用已稽核的固定 metadata 續跑：

```sh
python3 tools/collect_baseline.py --output /private/tmp/formora-source-review-next --date 2026-10-29 --unreal-depth 6 --unreal-seed baseline/sources/unreal-5.8-documents-depth5.json
```

metadata 記錄文件版本、摘要與子連結。
已取得的文件會重用。失敗頁面會重新嘗試。
工具會拒絕重複 URL、錯誤版本與無效摘要。
每秒最多開始一個請求。伺服器回報 429 時，工具會遵守 `Retry-After` 的等待時間。
沒有提供有效等待時間時，工具使用 60 秒。
[來源採集紀錄](verification/unreal-source-collection.md)保留原始資料、去重稽核及續跑結果。

目前 0.0 未完成。其餘 milestones 也未通過產品驗收。

## 首批網格案例

[網格基本形狀紀錄](verification/mesh-primitives-reference.md)保留十種形狀的 57 組參考輸入與結果。
參考結果來自實際 Blender 5.2.3 執行檔。
Formora 尚未執行這些對齊測試。
十項功能的契約仍為 `pending`。
這批案例不代表完整參數範圍、共同選項或 0.0 已完成。
