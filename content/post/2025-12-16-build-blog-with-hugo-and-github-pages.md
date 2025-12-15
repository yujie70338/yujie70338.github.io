---
title: "🚀 從零開始：用 Hugo + GitHub Pages 打造你的個人部落格"
date: 2025-12-16T00:00:00+08:00
description: "完整教學：使用 Hugo 靜態網站生成器與 GitHub Pages 免費部署，從安裝、設定到發布，step by step 帶你建立專屬的技術部落格。包含 hugo server 開發技巧與常見問題排解。"
author: "Yujie Zheng"
categories: [ "life" ]
tags: [ "Hugo", "GitHub Pages", "Blog", "Static Site" ]
image: "/img/post-bg-unix-linux.jpg"
---

# 前言

想要擁有一個完全屬於自己的部落格嗎？不想被平台限制版面、不想看到廣告、想要完全掌控內容的呈現方式？那麼使用 **Hugo + GitHub Pages** 就是你的最佳選擇！

Hugo 是目前最快的靜態網站生成器之一，而 GitHub Pages 提供免費的靜態網站託管服務。這個組合不僅完全免費，還能享有：

- ✅ **極快的建置速度**：Hugo 能在毫秒內生成數百頁內容
- ✅ **零成本部署**：GitHub Pages 提供免費託管與自動部署
- ✅ **完全掌控**：從版面到功能，完全客製化
- ✅ **版本控制**：使用 Git 管理所有內容，安全又方便
- ✅ **SEO 友善**：靜態網頁載入快速，搜尋引擎友善

這篇文章會帶你從零開始，step by step 建立屬於你的技術部落格！

---

# Step 1：環境準備

## 1.1 安裝必要工具

首先，確認你的電腦已安裝以下工具：

### 安裝 Hugo（macOS）

```bash
# 使用 Homebrew 安裝 Hugo
brew install hugo

# 確認安裝成功
hugo version
# 應顯示類似：hugo v0.152.2+extended+withdeploy darwin/arm64
```

### 確認 Git 已安裝

```bash
git --version
# 應顯示類似：git version 2.x.x
```

如果沒有 Git，請先安裝：
```bash
brew install git
```

---

# Step 2：建立 Hugo 網站

## 2.1 建立新網站

```bash
# 建立專案目錄
mkdir my-blog
cd my-blog

# 初始化 Hugo 網站
hugo new site . --force
```

此時你會看到以下目錄結構：
```
my-blog/
├── archetypes/    # 文章模板
├── content/       # 所有文章內容
├── layouts/       # 自訂版面
├── static/        # 靜態資源（圖片、CSS、JS）
├── themes/        # 主題目錄
└── hugo.toml      # 網站設定檔
```

## 2.2 選擇並安裝主題

Hugo 提供豐富的主題選擇。這裡以 [hugo-theme-cleanwhite](https://github.com/zhaohuabing/hugo-theme-cleanwhite) 為例：

```bash
# 使用 git submodule 安裝主題（推薦）
git init
git submodule add https://github.com/zhaohuabing/hugo-theme-cleanwhite.git themes/hugo-theme-cleanwhite
```

> **為什麼用 submodule？** 這樣可以保持主題獨立更新，又不會汙染你的專案。

## 2.3 複製範例內容

```bash
# 複製主題的範例內容到專案根目錄
cp -r themes/hugo-theme-cleanwhite/exampleSite/* .
```

這會複製以下內容：
- `hugo.toml`：網站設定範例
- `content/`：文章範例
- `static/`：靜態資源範例

---

# Step 3：客製化網站設定

編輯 `hugo.toml` 檔案，設定你的網站資訊：

```toml
baseurl = "https://your-username.github.io/"
title = "我的技術部落格"
theme = "hugo-theme-cleanwhite"
languageCode = "zh-tw"

[params]
  header_image = "img/home-bg.jpg"
  SEOTitle = "我的技術部落格"
  description = "分享技術、記錄成長的地方"
  keyword = "技術部落格, 程式設計, DevOps"
  
  # Sidebar 設定
  sidebar_about_description = "熱愛技術的工程師，持續學習與分享"
  sidebar_avatar = "img/avatar.jpg"
  
  # 社群連結
  [params.social]
    github = "https://github.com/your-username"
    linkedin = "https://linkedin.com/in/your-profile"
```

---

# Step 4：建立第一篇文章

## 4.1 使用指令建立文章

```bash
hugo new post/my-first-post.md
```

這會在 `content/post/` 目錄下建立新文章。

## 4.2 編輯文章內容

打開 `content/post/my-first-post.md`，編輯 front matter 和內容：

```markdown
---
title: "我的第一篇部落格文章"
date: 2025-12-16
description: "使用 Hugo 建立的第一篇文章"
author: "Your Name"
categories: [ "tech" ]
tags: [ "Hugo", "Blog" ]
image: "/img/post-bg.jpg"
---

# Hello, World!

這是我的第一篇部落格文章，使用 Hugo + GitHub Pages 建置。

## 為什麼選擇 Hugo？

- 快速
- 靈活
- 免費

讓我們開始這段旅程吧！
```

---

# Step 5：本地預覽與開發

## 5.1 啟動開發伺服器

```bash
hugo server
```

成功啟動後，你會看到：
```
Web Server is available at http://localhost:1313/
```

在瀏覽器開啟 http://localhost:1313/ 就能即時預覽你的網站！

## 5.2 Hugo Server 開發技巧

### 即時重載（Live Reload）
Hugo server 預設啟用即時重載，當你修改任何檔案時，瀏覽器會自動重新整理。

### 顯示草稿文章
```bash
hugo server -D
```
`-D` 參數會顯示標記為 `draft: true` 的文章。

### 指定不同 Port
```bash
hugo server --port 1314
```

### 停用快速渲染模式（完整重建）
```bash
hugo server --disableFastRender
```
當快取造成問題時，使用此選項強制完整重建。

### 清除快取並重建
```bash
# 停止 server（Ctrl+C）
rm -rf public/ resources/
hugo server
```

---

# Step 6：設定 .gitignore

建立 `.gitignore` 檔案，排除不需要版控的檔案：

```bash
touch .gitignore
```

內容如下：

```gitignore
# Hugo build artifacts
/public/
/resources/
/resources/_gen/
hugo_stats.json
.hugo_build.lock

# OS files
.DS_Store
*.swp

# Editor
.vscode/
.idea/
```

---

# Step 7：建立 GitHub Repository

## 7.1 在 GitHub 建立 Repository

1. 前往 [GitHub](https://github.com/)
2. 點擊右上角的 `+` → `New repository`
3. **Repository 名稱必須是**：`your-username.github.io`
   （例如：`john.github.io`）
4. 設定為 **Public**
5. **不要**勾選 "Initialize this repository with a README"
6. 點擊 `Create repository`

## 7.2 推送本地專案到 GitHub

```bash
# 初始化 Git（如果還沒做）
git init

# 加入所有檔案
git add .

# 提交
git commit -m "Initial commit: Hugo site"

# 設定遠端 repository
git remote add origin https://github.com/your-username/your-username.github.io.git

# 推送到 GitHub
git branch -M main
git push -u origin main
```

---

# Step 8：設定 GitHub Actions 自動部署

## 8.1 建立 GitHub Actions Workflow

建立 `.github/workflows/hugo-deploy.yml`：

```bash
mkdir -p .github/workflows
touch .github/workflows/hugo-deploy.yml
```

編輯 `hugo-deploy.yml`，加入以下內容：

```yaml
name: Deploy Hugo site to Pages

on:
  push:
    branches: ["main"]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false

defaults:
  run:
    shell: bash

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          submodules: recursive
          fetch-depth: 0

      - name: Setup Hugo
        uses: peaceiris/actions-hugo@v3
        with:
          hugo-version: 'latest'
          extended: true

      - name: Build with Hugo
        run: hugo --minify

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./public

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

## 8.2 提交並推送 Workflow

```bash
git add .github/workflows/hugo-deploy.yml
git commit -m "Add GitHub Actions workflow"
git push
```

---

# Step 9：設定 GitHub Pages

**這一步非常重要！** 否則網站會顯示 README 而不是你的部落格。

1. 前往你的 GitHub Repository
2. 點擊 `Settings`
3. 在左側選單找到 `Pages`
4. 在 **"Build and deployment"** 區塊：
   - **Source** 選擇：`GitHub Actions` ✅
   - **不要**選擇 "Deploy from a branch" ❌
5. 儲存設定

## 9.1 確認部署狀態

1. 前往 Repository 的 `Actions` 頁面
2. 你會看到 workflow 正在執行
3. 等待綠色勾勾（✓）出現，表示部署成功

---

# Step 10：訪問你的網站

部署成功後，你的網站會在：

```
https://your-username.github.io/
```

🎉 **恭喜！你的個人部落格已經上線了！**

---

# 常見問題與技巧

## Q1：如何新增文章？

```bash
# 建立新文章
hugo new post/2025-12-16-my-new-article.md

# 編輯文章內容
vim content/post/2025-12-16-my-new-article.md

# 本地預覽
hugo server

# 推送到 GitHub（自動部署）
git add .
git commit -m "Add new article"
git push
```

## Q2：主題不見了怎麼辦？

如果 clone 專案後主題消失，執行：

```bash
git submodule update --init --recursive
```

## Q3：如何清除快取？

當遇到顯示異常時：

```bash
rm -rf public/ resources/
hugo server
```

## Q4：如何客製化主題？

不要直接修改 `themes/` 目錄！而是在專案根目錄建立對應的檔案：

```bash
# 覆寫 sidebar
cp themes/hugo-theme-cleanwhite/layouts/partials/sidebar.html layouts/partials/sidebar.html

# 然後編輯 layouts/partials/sidebar.html
```

## Q5：GitHub Pages 顯示 404？

檢查以下項目：
1. Repository 名稱是否為 `username.github.io`
2. Pages 設定是否選擇 `GitHub Actions`
3. Workflow 是否執行成功（檢查 Actions 頁面）
4. `hugo.toml` 中的 `baseurl` 是否正確

## Q6：如何使用自訂網域？

1. 在 GitHub Pages 設定中加入 Custom domain
2. 在 DNS 設定 CNAME 記錄指向 `username.github.io`
3. 更新 `hugo.toml` 的 `baseurl`

---

# 實用指令速查表

```bash
# 建立新網站
hugo new site my-site

# 安裝主題（submodule）
git submodule add <theme-url> themes/<theme-name>

# 建立新文章
hugo new post/article-name.md

# 啟動開發伺服器
hugo server

# 啟動伺服器（含草稿）
hugo server -D

# 建置網站
hugo

# 清除快取
rm -rf public/ resources/

# 更新 submodule
git submodule update --remote --merge
```

---

# 總結

使用 Hugo + GitHub Pages 建立部落格的優勢：

1. **完全免費**：不需要任何費用
2. **快速部署**：推送即部署，幾分鐘就上線
3. **高效能**：靜態網站載入飛快
4. **易於維護**：Markdown 寫作，Git 版本控制
5. **完全掌控**：客製化程度高，沒有平台限制

現在你已經擁有一個完全屬於自己的技術部落格了！接下來就是持續創作優質內容，分享你的知識與經驗。

Happy blogging! 🎉

---

# 參考資源

1. [Hugo 官方文件](https://gohugo.io/documentation/)
2. [GitHub Pages 文件](https://docs.github.com/en/pages)
3. [Hugo Themes 主題庫](https://themes.gohugo.io/)
4. [Hugo 部署到 GitHub Pages 官方指南](https://gohugo.io/host-and-deploy/host-on-github-pages/)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
