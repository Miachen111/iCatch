# iCatch 拍遣隊 Prototype

本專案是 iRent 車況拍照、疑似車損與整潔判讀、營運事件及清潔整備任務的可操作原型。資料、訂單、任務和獎勵均為競賽示意；不連接正式 iRent 系統。

## 先讀這兩份文件

- [系統架構與分工](docs/architecture.md)：各人的工作邊界、資料流與開發順序。
- [共同模組契約](docs/contracts.md)：六視角代碼、A／B／C 的函式與回傳格式、D 提供給 E 的 API 草案。**組員先確認契約，再開始實作。**

## 預定技術

| 部分 | 預定工具 | 負責 |
| --- | --- | --- |
| 網頁 | Nuxt 4、Vue 3 | E；A 提供拍照引導元件 |
| 後端與事件規則 | Python、FastAPI | D |
| 影像與整潔判讀 | Python 函式 | A、B、C |
| 關聯資料 | Neon PostgreSQL；Python 端預計使用 SQLModel | D |
| 原照與標記圖 | Neon Object Storage | D 管理存取 |

目前只建立專案目錄和共同契約；**尚未建立 Nuxt、FastAPI、資料庫、儲存 bucket 或公開 Demo 網址**。Neon 提供 PostgreSQL 和檔案儲存；未來 Nuxt 與 FastAPI 仍需各自部署到能運行程式的服務。

## 目錄

```text
frontend/                 E 的 Nuxt 專案；A 的拍照元件由 A 與 E 協調放置
backend/app/services/     A、B、C 各自的 Python 判讀函式
backend/app/              D 的 API、資料模型及事件／任務規則（稍後建立）
docs/                     共用規格；更改介面前先討論
demo_data/                有使用權的小型示範資料與預期結果
```

## 協作方式

1. A、B、C、D、E 各自從 `main` 建分支，以 Pull Request 合併。不要直接覆寫別人的模組。
2. A、B、C 按 `docs/contracts.md` 實作；先在自己的電腦測試，再提交程式、依賴清單、設定與可重現的測試範例。不要直接操作 D 的資料庫。
3. D 先以符合契約的假判讀結果串起流程；接入真函式時，輸入與輸出格式應維持不變。
4. 真實 API 金鑰、連線字串、含個資的照片和沒有再散布權的資料不得提交。大型模型權重寫明取得方式，不直接塞入 Git 歷史。
5. PR 至少說明做了什麼、如何執行、使用哪張測試照、實際與預期結果。改變契約的 PR 要由受影響的模組負責人一起確認。

## 下一步

1. 全組審閱 `docs/contracts.md`，確認六視角、輸出狀態及「待人工」的處理方式。
2. A／B／C 開始各自的本機判讀函式；E 開始 Nuxt 畫面與假資料。
3. D 建 FastAPI 骨架，使用假結果串通照片、事件、任務與驗收。
4. D 測試 Neon PostgreSQL 和 Object Storage 的上傳／讀回，再建立線上測試版。

本 README 的啟動指令、環境變數範本及部署方式會在對應程式建立後補齊；現在沒有可執行服務。
