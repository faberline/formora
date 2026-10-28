# 基準工具檢查紀錄

日期：2026-10-29，Asia/Taipei。
環境：macOS 26.5.2，arm64，Rust 1.96.1。

本紀錄保留 PR #15 初版工具的檢查結果。
下方數量與 CI 狀態屬於該次候選。
後續進度見[網格參考資料](mesh-primitives-reference.md)與[原生預覽](macos-preview.md)。

## 已執行

| 檢查 | 結果 |
|---|---|
| `cargo fmt --check` | 通過 |
| `cargo clippy --locked --all-targets -- -D warnings` | 通過 |
| `cargo test --locked` | 21 項整合測試通過，沒有跳過 |
| `cargo run --locked -- baseline check --root . --strict` | 結束碼 2。正確拒絕未完成的基準 |

嚴格檢查的結果：

```json
{
  "structurally_valid": true,
  "baseline_ready": false,
  "product_acceptance": "unrun",
  "sources": 8229,
  "features": 0,
  "pending_sources": 8229,
  "pending_features": 0,
  "uncovered_sources": 0,
  "incomplete_products": ["blender", "unreal"],
  "problems": []
}
```

測試涵蓋錯誤版本、浮動文件、缺少來源、來源被刪除、檔案摘要改變、
未完成來源採集、未審核案例、缺少測試條件及命令結束碼。

## 未完成

- Unreal 目前只採集首頁及下一層文件清單，尚未完整採集。
- 8,229 個文件與章節入口尚未逐項審核。
- 尚未完成產品功能與可執行測試案例的對照表。
- 尚未安裝或執行參考產品以取得實測證據。
- 尚未通過任何 Formora 產品功能驗收。
- 首輪遠端 CI 的 Linux 檢查通過。Windows checkout 改變文字來源的換行，導致摘要檢查失敗。macOS 檢查因而取消。
- 已加入 `.gitattributes`，禁止改變固定來源檔案的位元組。仍須以新 revision 的三平台 CI 結果確認修正。

本紀錄只支持工具檢查，不能用來關閉 0.0 或後續 milestones。
