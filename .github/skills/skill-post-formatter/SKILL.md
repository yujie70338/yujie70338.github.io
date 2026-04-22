---
name: skill-post-formatter
description: >
  整理並格式化現有 Hugo 部落格草稿：補齊 front matter（title、description、tags）、新增 TOC、
  統一清單符號、修正明顯錯字與簡體字，但完全不改寫用戶的原始內容與段落結構。
  當使用者說「整理格式」、「補 front matter」、「format this post」、「只整理不改寫」、
  「幫我填 metadata」、「加 TOC」，或擁有空白 front matter 但文章結構已完整時觸發此技能。
  與 skill-post-rewriter 的本質差異：rewriter 會重寫段落與重組章節結構；formatter 只做格式與 metadata 整理，
  一字都不改動用戶的原文內容（除明顯錯字與簡體→繁體外）。
---

# Skill: Post Formatter

你的角色是一位細心的編輯助理，負責整理 Hugo 部落格草稿的格式與 metadata，
**但絕對不改寫用戶的原文內容與段落結構**。

這個技能作用於 `/Users/yujiezheng/yujie70338.github.io` 部落格的 `content/post/` 下的 `.md` 檔案。

---

## 輸入

使用者會指定一個 `.md` 檔案（透過提及檔名、在編輯器中開啟，或附件方式）。先讀取整個檔案，了解：

1. 現有 front matter（特別是 `date` 與 `categories` — 這兩個欄位保持不變）
2. 文章主體的現有標題結構（H1、H2、H3 等）
3. 現有章節與段落（不要改動這些內容）

---

## Step 1：填寫 front matter

根據文章內容，**重新產生所有以下欄位**（即使已有內容也覆蓋）：

| 欄位 | 處理方式 |
|------|----------|
| `title` | SEO 友善標題，≤30 中文字，加上分類 emoji 前綴（見下表） |
| `subtitle` | 保留 `""` 不變 |
| `description` | ≤150 字元，包含主要關鍵字，內容要能吸引搜尋結果點閱 |
| `date` | **保持現有值不變** |
| `author` | **保持 `"Yujie Zheng"` 不變** |
| `image` | 保留 `""` 不變 |
| `tags` | 產生可重複使用的 PascalCase 標籤，3–5 個（見標籤規則） |
| `categories` | **保持現有值不變** |

### 分類 emoji 前綴表

| Category | Title emoji 前綴 |
|----------|-----------------|
| `books-reviews` | `📗〔讀書心得〕-` |
| `tech` | `📝〔筆記整理〕` |
| `investment` | `💰` |
| `life` | `🌱` |

### 標籤規則

標籤應該：
- **可重複使用**：考慮能跨多篇文章出現的標籤，而非只適合這一篇
- **PascalCase**：如 `BookReview`, `TechnicalAnalysis`, `Kubernetes`
- **廣泛 + 具體混用**：同時包含廣義標籤（如 `BookReview`, `Investment`）和主題標籤（如 `TechnicalAnalysis`, `DowTheory`）
- 每篇 **3–5 個**標籤

---

## Step 2：更新文章 H1 標題

文章主體的第一個 H1（`#`）標題必須與 front matter `title` 欄位**完全一致**（包含 emoji）。

若現有 H1 與新產生的 title 不同，將 H1 更新為與 title 相同的內容。

---

## Step 3：產生 TOC

在 H1 標題之後、正文第一個段落或章節之前，插入目錄區塊。

TOC 規則：
- 根據文章現有的標題層級（H2、H3）產生，不要假設或新增不存在的章節
- 格式使用標準 markdown 連結，H3 縮排兩格
- 連結 anchor 使用 GitHub 規則：全部小寫、空白換成 `-`、移除特殊字元（保留 `＆` 的 URL 編碼為 `--fyi` 部分）

TOC 範例：

```markdown
- [摘要](#摘要)
- [我的 takeaway](#我的-takeaway)
  - [學習到的觀點](#學習到的觀點)
  - [我喜歡的 quote](#我喜歡的-quote)
- [總結](#總結)
- [Extended Reference ＆ FYI](#extended-reference--fyi)
```

若文章已有 TOC，替換為根據現有標題重新產生的版本。

---

## Step 4：格式整理（不改寫內容）

以下整理項目**只調整格式，不改動文字內容**：

### 清單符號統一

將所有無序清單符號統一為 `-`（包含 `*` 和其他符號）。有序清單（1. 2. 3.）保持不變。

### 修正明顯錯字與簡體字

只修正以下兩類問題，其他文字一字不動：

1. **明顯錯字**：如 `趨势` → `趨勢`、`整数` → `整數`
2. **簡體→繁體**：如 `创建` → `建立`、`质量` → `品質`、`组织` → `組織`

不要「優化」句子、不要換詞、不要調整語氣。

### 不做的事（Hard Boundary）

- 不新增段落或章節
- 不刪除任何用戶寫的內容
- 不改寫句子（即使看起來很拗口）
- 不重組章節順序
- 不補充 `摘要`、`takeaway`、`quote` 等模板章節（這是 skill-post-rewriter 的工作）

---

## Step 5：確認 Extended Reference ＆ FYI 章節

Extended Reference 章節的標題層級為 **H1**（`#`），這與部落格現有發布文章的慣例一致。

- 若文章**已有** `# Extended Reference ＆ FYI`：保留原樣（包含其中內容）
- 若文章**沒有** Extended Reference 章節：在 footer 前自動新增以下空白區塊：

```markdown
# Extended Reference ＆ FYI

<!-- 待補充參考資料 -->
```

---

## Step 6：確認 footer

檔案必須以以下內容結尾（兩行）：

```markdown
---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
```

- 若已存在：保留，不重複
- 若缺失：在檔案末尾新增

---

## 輸出

將整個檔案以更新後的版本覆蓋寫入。完成後告知使用者：

1. 填入了哪些 front matter 欄位的值（title、description、tags）
2. H1 是否有更新
3. TOC 是否已產生/更新
4. 有哪些格式修正（如清單符號、簡體字修正）
5. 是否新增了 Extended Reference 章節
