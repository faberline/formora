# 功能對齊基準

GitHub milestones 是路線圖的主要來源。
目前的實作入口是 [0.0 追蹤 issue](https://github.com/faberline/formora/issues/1)。

## 固定來源

基準採 Blender 5.2.3 LTS 與 Unreal Engine 5.8 正式版。
查核日期是 2026-10-29，時區是 Asia/Taipei。

- [Blender 正式版本](https://www.blender.org/releases/)
- [Blender 5.2.3 下載摘要](https://download.blender.org/release/Blender5.2/blender-5.2.3.sha256)
- [Blender 5.2 手冊](https://docs.blender.org/manual/en/5.2/)
- [Unreal Engine 5.8 正式發布](https://www.unrealengine.com/news/unreal-engine-5-8-is-now-available)
- [Unreal Engine 5.8 手冊](https://dev.epicgames.com/documentation/unreal-engine?application_version=5.8)

Unreal 的 5.8 是官方發布及文件的版本名稱。
參考執行測試還須記錄實際執行檔的完整版本與建置資訊。
目前沒有安裝包或上游執行結果的驗收證據。

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

目前 0.0 未完成。其餘 milestones 也未通過產品驗收。
