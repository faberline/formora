# macOS 預覽實測

日期：2026-10-29，Asia/Taipei。
硬體：Apple M1 Max，Metal。
環境：macOS 26.5.2，arm64，Rust 1.96.1。
外部 client：官方 Python MCP SDK 2.3.0。

## 實際流程

1. 外部 MCP client 啟動開發用 App，並開啟同一個預覽 session。
2. Agent 透過 `scene_apply` 調整鏡頭，讓門位於畫面中央。
3. 以原生視窗點選門。畫面顯示門開啟及關閉。
4. 以 Shift＋點選建立位置標記。輸入英文註記並儲存。
5. Agent 透過 MCP 讀到註記，將開門時間從 1 秒改成 4 秒。
6. 原生視窗顯示新的 4 秒設定。播放、暫停、R 重設及 S 截圖均通過。
7. 以標準貼上輸入中文註記。MCP 及儲存資料保留完整文字。
8. 空白註記顯示「Type a note, then press Enter.」，不提交資料。
9. Agent 儲存門開 25% 的場景。關閉程序，再以同一執行檔重開。
10. 重開後，原生畫面仍顯示門開 25%、4 秒設定及位置標記。

原生 UI 測試使用 Computer Use 的視窗索引點選。
直接座標點選介面回報 `noWindowsAvailable`，沒有把該失敗算作通過。
視窗索引點選實際觸發了程式的滑鼠選取與門互動。

中文直接文字注入沒有產生註記。
改用原生貼上後通過。
這不證明所有中文輸入法都可使用。

## 保存的證據

- [重開前畫面](../evidence/macos-preview/before-reopen.png)
- [重開後畫面](../evidence/macos-preview/after-reopen.png)
- [已儲存場景](../evidence/macos-preview/reviewed.scene.json)
- [檔案摘要與測試環境](../evidence/macos-preview/manifest.json)

兩份 PNG 的位元組完全相同。
SHA-256 是：

```text
165e3a147d9615c940325751a68a441d42562ebfd7624d25c6472a186814742f
```

場景保留版本號 7、門進度 0.25、開門時間 4 秒及三則註記。
證據 manifest 記錄實際執行檔摘要及來源檔案摘要。

## 自動檢查

- 全部功能開啟時，1 項單元測試及 55 項整合測試通過。
- 格式與 Clippy 檢查通過。
- 播放同步測試先證明相同值的關門指令會被忽略，再驗證修正。
- 鎖的測試先證明繼承的描述符會延後釋放，再驗證明確解鎖。
- CI 會編譯及測試預覽功能。遠端 CI 結果須依目前 PR 的實際 revision 查證。

## 尚未完成

0.0 的逐項功能對照仍未完成。
原生預覽的 Windows 與 Linux 實機測試仍未執行。
完整建模、動畫、物理及渲染能力仍屬後續 milestones。
本紀錄不關閉任何 milestone。
