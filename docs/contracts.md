# A／B／C 與 D 的模組契約（討論版 v0.1）

本文件是介面的共同依據。`README.md` 介紹專案；之後由 D 在 Python 中建立與本文件一致的 Pydantic 模型，再由 FastAPI 對前端提供 API。改欄位或狀態代碼須先通知會受影響的組員。

## 共通約定

- 六個視角代碼固定為 `front_left`（左前）、`front_right`（右前）、`rear_left`（左後）、`rear_right`（右後）、`interior_front`（前車內）、`interior_rear`（後車內）。不可在資料中混用中文、序號及其他縮寫。
- 函式收的是**後端可讀的本地暫存檔路徑**，不是公開照片網址或 Neon object key。D 負責從上傳或儲存空間取得本地檔案，再交判讀函式。三位組員可直接用自己的本地照片測試。
- 回傳必須是結構化資料，**不可只回傳一行文字或直接印在終端**。輸出例子見 `docs/examples/`；具體以後續共用 Python 型別定稿。
- 訂單 ID、車輛 ID、照片 ID、拍攝時間、照片用途和 Storage key 由 D 的系統管理。A／B／C 不直接寫資料庫或上傳 Object Storage。
- 演算法失敗或逾時應讓 D 得到可處理的失敗結果；不可把失敗默認成合格、無車損或乾淨。未預期的例外由 D 記錄並轉人工。
- 示範照片只用有權使用的資料；大批評估照片、模型權重與密鑰不可隨意提交 GitHub。

## A：拍照品質

建議位置：`backend/app/services/quality.py`

```python
check_quality(photo_path: str, expected_view: str) -> QualityResult
```

`status` 必須是：

- `accepted`：可進入正常照片記錄與車況判讀，`reason_code` 為 `null`。
- `retake`：品質不合格，回一個最優先的原因與使用者提示；不進 B／C。
- `manual_review`：無法可靠判斷，先要求補拍；仍不確定則交人工，不當作 `accepted`。

必要欄位：`status`、`reason_code`（可空）、`message`。可用原因代碼先定 `blur`、`dark`、`overexposed`、`too_near`、`too_far`、`cropped`、`no_vehicle`、`uncertain`；其他原因代碼需先更新契約。對前／後車內照不套用車外「車輛主體入鏡」檢查。

## B：取還車疑似車損

建議位置：`backend/app/services/damage.py`

```python
compare_damage(before_photo_path: str, after_photo_path: str, view: str) -> DamageResult
```

只對四個車外視角執行；D 提供同車、同部位的取車與還車照片。`status` 必須是：

- `no_change`：在**可比較區域**未見明顯變化，不能宣稱整車保證無損。
- `suspected_change`：疑似新增變化；附標記圖，D 建待官方覆核事件。
- `uncomparable`：無基準照、角度差太大、對齊失敗或其他不確定；附原因，轉人工，不當作 `no_change`。

必要欄位：`status`、`reason`（可空）、`marked_image_path`（可空）。`marked_image_path` 是 B 在本地產生的檔案路徑；由 D 負責上傳與記錄。人工確認有無新增車損不由 B 自動定責。

## C：車內外整潔

建議位置：`backend/app/services/cleanliness.py`

```python
classify_cleanliness(photo_path: str, view: str) -> CleanlinessResult
```

車內與車外使用各自的三級準則；整備後的照片也呼叫同一函式。`level` 必須是 `clean`、`normal`、`urgent_dirty` 或 `unknown`。必要欄位：`level`、`evidence`（字串列表）、`needs_review`（布林值）、`reason`（可空）。

- `unknown`：無法判讀或模型服務失敗，必須 `needs_review=true`，不可當作 `clean`。
- `urgent_dirty`：提供照片中**可見**的依據；D 建清潔事件，是否收費另依企業規則與人工確認。
- `needs_review=true`：提醒 D 走人工覆核；即使暫有分級，沒有人工確認前不得視為已完成驗收或自動收費。

## D 的整合規則

1. A 合格照才走正常存檔與 B／C；拍攝失敗或有疑慮保留檢查紀錄，通知 E 重拍或轉人工。
2. 車外照可由 B 做前後比對、由 C 做整潔分級；車內照僅送 C。正式處理須確認照片與車輛、訂單、視角的綁定。
3. 同車多張可靠結果中任一 `urgent_dirty`，可建立清潔事件並附對應證據；`unknown` 另列人工覆核，不能被其他乾淨照覆蓋。
4. 任一 `suspected_change` 或尚待排除的 `uncomparable` 車損疑慮，整車不進群包任務池；疑似車損與髒污並存，統一由官方處理。
5. 本次租客自行補救沿原訂單、無群包獎勵；其他合格會員接單另建任務，排除本次租客承接同一事件的獎勵任務。
6. 驗收未通過不核發獎勵；清潔結案不代表其他停租原因已解除。全部停租原因解除後才恢復出租。

## D 提供給 E 的 API（草案，FastAPI 階段定稿）

| 操作 | 暫定入口 | 回傳重點 |
| --- | --- | --- |
| 上傳與品質檢查 | `POST /api/photos` | A 的狀態、重拍原因、合格照 ID |
| 完成還車判讀 | `POST /api/orders/{order_id}/analyze` | B／C 結果及建立的事件 |
| 查看事件 | `GET /api/events`、`GET /api/events/{event_id}` | 照片、模型依據、狀態與可執行動作 |
| 人工覆核 | `POST /api/events/{event_id}/review` | 覆核結果與更新後狀態 |
| 任務池及接單 | `GET /api/tasks`、`POST /api/tasks/{task_id}/accept` | 任務與資格／拒絕原因 |
| 整備留證及驗收 | `POST /api/tasks/{task_id}/evidence`、`POST /api/tasks/{task_id}/inspect` | 前後照片、C 的複檢、結案／退回及示意獎勵 |
| 展示重置 | `POST /api/demo/reset` | 固定示範資料重新建立（僅展示環境） |

這些是**前後端協作草案**，不是已經可以呼叫的服務。D 在建立 FastAPI 時將定義具體請求／回應模型、身份權限與錯誤碼；E 可先按這些資料形狀做假畫面。
