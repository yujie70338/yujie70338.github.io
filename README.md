# yujie70338.github.io

個人部落格網站，使用 Hugo 靜態網站生成器建構。

## 專案初始化步驟

### 1. 安裝 Hugo

```bash
brew install hugo
hugo version
git --version
```

### 2. 建立新的 Hugo 網站

```bash
hugo new site . --force
```

### 3. 新增主題（使用 git submodule）

```bash
git submodule add https://github.com/zhaohuabing/hugo-theme-cleanwhite.git themes/hugo-theme-cleanwhite
```

### 4. 複製範例網站內容

```bash
cp -r themes/hugo-theme-cleanwhite/exampleSite/* .
```

這個指令會複製以下內容到網站根目錄：
- `config.toml`（範例設定檔）
- `content/`（文章範例）
- `static/`（靜態資源）
- `layouts/`
- `data/`

### 5. 設定網站

編輯 `hugo.toml` 檔案，設定網站標題、網域、描述等資訊：

```bash
vim hugo.toml 
```

### 6. 設定 GitHub Actions 自動部署

建立 GitHub Actions 工作流程設定檔：

```bash
mkdir -p .github/workflows
```

參考 GitHub Pages 部署文件：[https://gohugo.io/host-and-deploy/host-on-github-pages/](https://gohugo.io/host-and-deploy/host-on-github-pages/)

### 7. 設定 .gitignore

建立 `.gitignore` 檔案，排除不需要版控的檔案：

```bash
touch .gitignore
```

內容如下：

```gitignore
############################
# Hugo build artifacts
############################
/public/
/resources/
/resources/_gen/
hugo_stats.json
/assets/jsconfig.json
.hugo_build.lock

############################
# Hugo executables (local)
############################
hugo.exe
hugo.linux
hugo.darwin

############################
# Node / Frontend
############################
node_modules/
dist/
coverage/
.grunt/
build/Release
bower_components/
package-lock.json

############################
# Build / Output directories
############################
bin/
bin-debug/
bin-release/
[Bb]in/
[Oo]bj/

############################
# Logs & runtime
############################
logs/
*.log
pids/
*.pid
*.seed

############################
# Locks (generic)
############################
*.lock
.lock-wscript

############################
# OS / Editor / Backup
############################
.DS_Store
*.swp
*.markdown~
*.md~

############################
# Apache / Server
############################
.htpasswd

############################
# Coverage / Instrumentation
############################
lib-cov/

############################
# Settings / IDE
############################
.settings/

############################
# Executables / packages
############################
*.swf
*.air
*.ipa
*.apk

############################
# AWS publish artifacts
############################
.aws-credentials.json
.awspublish*

```

## 如何複製此專案

如果你要 clone 這個專案到本機，請使用以下指令：

### 方法一：直接複製並初始化 submodule

```bash
git clone --recurse-submodules https://github.com/yujie70338/yujie70338.github.io.git
cd yujie70338.github.io
```

### 方法二：先 clone 再初始化 submodule

```bash
git clone https://github.com/yujie70338/yujie70338.github.io.git
cd yujie70338.github.io
git submodule update --init --recursive
```

> ⚠️ **重要**：因為主題是使用 git submodule 管理，所以必須執行 `git submodule update --init --recursive` 來下載主題檔案，否則 `themes/hugo-theme-cleanwhite/` 目錄會是空的，網站無法正常運作。

## 本機開發

### 啟動開發伺服器

```bash
hugo server
```

然後在瀏覽器開啟 [http://localhost:1313](http://localhost:1313)

### 建立新文章

```bash
hugo new post/my-new-post.md
```

### 建構網站

```bash
hugo
```

生成的檔案會放在 `public/` 目錄中。

## 部署

推送到 GitHub 的 main 分支後，GitHub Actions 會自動建構並部署到 GitHub Pages。
