# 完整參考建置

日期：2026-10-29，Asia/Taipei。
環境：macOS 26.5.2，arm64。
本次屬於 [issue #26](https://github.com/faberline/formora/issues/26) 與 [issue #12](https://github.com/faberline/formora/issues/12)。
本紀錄保留 PR #27 的候選狀態。後續案例進度見[網格建立情境](mesh-creation-contexts.md)。

## 固定版本

| 產品 | 完整版本 | 文件版本 | 實際建置 ID |
|---|---|---|---|
| Blender | 5.2.3 LTS | 5.2 | `e13b728c6880` |
| Unreal Engine | 5.8.4 | 5.8 | `5.8.4-58902052+++UE5+Release-5.8` |

兩套產品都以實際執行程序回報版本。
Blender 使用原廠空白場景並停用自動腳本。
Unreal 使用新建的暫存專案及 Python commandlet。
commandlet 是不開啟編輯視窗的工具模式。
Unreal 同時使用 NullRHI，意思是不做 GPU 渲染。

Unreal 回報的完整版本與安裝目錄的 `Build.version` 相符。
[官方 5.8.4 Hotfix 公告](https://forums.unrealengine.com/t/5-8-4-hotfix-released/2842775)的首篇發布時間是 2026-10-20T13:25:52.767Z。
`baseline/sources/unreal-5.8.4-release.json` 保留選取的官方主題資料與回應摘要。
Blender 執行檔摘要與先前 57 組網格參考資料的執行檔摘要相同。

## 保存的證據

- `baseline/reference/builds/blender-5.2.3/`：版本、建置、執行檔摘要、命令、程序結果及選取的輸出。
- `baseline/reference/builds/unreal-5.8.4/`：相同資料，另含實際 `Build.version` 內容及 NullRHI 標記。
- `baseline/reference/builds/negative-checks.json`：錯誤建置與既有輸出的拒絕結果。

`report.json` 只記錄版本探測通過。
其中 `feature_tests`、`gpu_tests` 與 `product_acceptance` 都是 `unrun`。
`process.json` 保留程序結束碼與完整輸出的 SHA-256。
`stdout-excerpt.log` 是選取的版本、結束摘要及警告行。
它不是完整原始輸出。
固定檔案的 `url` 指向核對版本用的官方來源。
它不表示這些執行紀錄是從該網址下載。

Unreal 程序結束碼是 0，回報 0 個錯誤及 4 個警告。
警告來自最小專案沒有啟用 ACL 動畫壓縮設定資產。
本次沒有測試動畫壓縮。
這個最小專案不作為完整功能驗收的樣板，也不縮小內建功能範圍。

## 拒絕與檢查

故意指定錯誤建置時，Blender 上游程序結束碼是 1。
Unreal 上游程序結束碼是 255。
兩個捕捉命令都返回 1，沒有發布輸出目錄。
失敗診斷保留在另建的暫存目錄。

對既有輸出目錄再執行時，工具返回 2。
原有版本報告摘要沒有改變。

Rust 檢查新增七項測試。
它會拒絕不完整版本、預覽版本、錯誤手冊版本、舊 lock 格式、缺少版本探測、不符的建置及沒有固定摘要的證據。
缺少探測的產品會列在 `unverified_builds`。
探測證據不能宣稱完整產品驗收通過。

## 重跑

輸出目錄必須是新的目錄。
執行檔須符合 `baseline/lock.json` 的預先固定版本及建置。

```sh
python3 tools/probe_reference_build.py --product blender --executable /Applications/Blender.app/Contents/MacOS/Blender --output /private/tmp/formora-blender-build-new
python3 tools/probe_reference_build.py --product unreal --executable '/Users/Shared/Epic Games/UE_5.8/Engine/Binaries/Mac/UnrealEditor-Cmd' --engine-root '/Users/Shared/Epic Games/UE_5.8/Engine' --output /private/tmp/formora-unreal-build-new
```

每次 Unreal 探測都建立新的專案、使用暫存快取，並停用自動追蹤伺服器。
參考腳本只供上游測試使用。
Formora 產品核心仍由 Rust 實作。

## 尚未驗收

目前只確認 macOS 上的參考版本。
Windows、Linux 的參考程序及執行檔尚未測量。
版本探測不能代替建模、渲染、動畫、物理或遊戲功能測試。
9,037 項來源與十項功能契約仍待審核。
嚴格基準檢查仍應返回 2。
本次不關閉任何 milestone。
