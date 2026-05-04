---
title: "📝〔筆記整理〕uv run 完整指南與使用筆記"
subtitle: ""
description: "深入介紹 Astral 開發的 uv run 工具：自動虛擬環境管理、PEP 723 單一腳本依賴支援，以及比 python3 更高效的現代 Python 開發工作流程筆記整理。"
date: 2026-05-04
author: "Yujie Zheng"
image: ""
tags: ["Python", "Uv", "PackageManagement", "PEP723", "DeveloperTools"]
categories: ["tech"]
---

# 📝〔筆記整理〕uv run 完整指南與使用筆記

- [📝〔筆記整理〕uv run 完整指南與使用筆記](#筆記整理uv-run-完整指南與使用筆記)
  - [前言](#前言)
  - [什麼是 uv run？](#什麼是-uv-run)
  - [為何 uv run 比 `python3` 更好？](#為何-uv-run-比-python3-更好)
  - [`uv run` 的推出時間與解決的問題](#uv-run-的推出時間與解決的問題)
  - [`uv run` 如何符合 PEP 723？](#uv-run-如何符合-pep-723)
  - [列出一些自己之後可以複習的官方文件或部落格](#列出一些自己之後可以複習的官方文件或部落格)
    - [官方文件](#官方文件)
- [Extended Reference ＆ FYI](#extended-reference--fyi)

## 前言

`uv run` 是由 Astral 公司開發的高效能 Python 套件與專案管理工具 `uv` 中的一個核心指令。它提供了一種更現代化、自動化的方式來執行 Python 專案中的指令或腳本，旨在簡化開發流程並解決傳統 `python3` 指令所面臨的諸多問題。

## 什麼是 uv run？

`uv run` 是一個指令，用於在 `uv` 所管理的專案環境中執行命令或 Python 腳本。它的核心功能是自動處理虛擬環境和依賴項，讓開發者無需手動啟用環境或安裝套件即可執行程式碼。

**主要行為模式**：

- **在專案內**：如果你在一個包含 `pyproject.toml` 的 `uv` 專案目錄中執行 `uv run <command>`，它會自動檢查並確保 `.venv` 虛擬環境是最新的，然後在該環境中執行你的指令。
- **在專案外**：如果目前目錄不是一個 `uv` 專案，`uv run` 會直接使用 `uv` 本身所在的 Python 環境來執行指令。
- **執行單一腳本**：當執行一個符合特定規範（PEP 723）的單一 Python 腳本時，`uv run` 會自動解析腳本內嵌的依賴宣告，在一個臨時的隔離環境中安裝它們，然後執行腳本。

## 為何 uv run 比 `python3` 更好？

相較於直接使用 `python3 some_script.py`，`uv run` 提供了顯著的優勢，主要體現在環境和依賴管理的自動化上：

1. **自動化虛擬環境管理**：`uv run` 無需手動啟用（`source .venv/bin/activate`）或停用虛擬環境。它會自動偵測並使用專案對應的 `.venv`，省去了繁瑣的步驟並避免了在錯誤環境中執行程式碼的風險。
2. **確保依賴項同步**：在執行指令前，`uv run` 會自動檢查 `pyproject.toml` 或 `uv.lock` 鎖定檔，並同步安裝所有必要的依賴項，確保你的執行環境始終處於最新且一致的狀態。這解決了手動執行 `pip install -r requirements.txt` 可能遺漏或版本不一致的問題。
3. **支援可攜式單一腳本 (PEP 723)**：`uv run` 的殺手級功能之一是它對 PEP 723 的原生支援。這讓你可以將腳本的依賴項直接寫在 `.py` 檔案的註解中。分享或執行這個腳本時，接收者只需要安裝 `uv` 並執行 `uv run <script_name>.py`，`uv` 就會自動建立臨時環境並安裝所需套件，實現真正的「單檔即可執行」，無需再附帶 `requirements.txt`。
4. **臨時依賴項**：你可以使用 `-with` 參數在執行時臨時加入依賴項，例如 `uv run --with requests demo.py`。這個依賴僅在當次執行中有效，執行完畢後會自動清理，非常適合測試或執行一次性任務，而不會污染專案的固定依賴。

## `uv run` 的推出時間與解決的問題

`uv` 最初於 2024 年 2 月發布，當時主要作為 `pip` 和 `pip-tools` 的高速替代品。包含 `uv run` 在內的專案管理、工具管理等一系列擴展功能則是在 2024 年 8 月的一次重大更新中推出的，將 `uv` 從一個安裝器擴展為一個全方位的 Python 開發工具鏈。

`uv run` 主要解決了 Python 開發中的幾個長期痛點：

- **複雜的環境管理**：解決了開發者需要手動建立、啟用、切換和記憶虛擬環境的麻煩。
- **依賴項不同步**：避免了因忘記安裝或更新依賴而導致的 `ModuleNotFoundError` 錯誤。
- **腳本分享困難**：傳統上分享一個 Python 腳本需要同時提供 `requirements.txt` 檔案，並指導使用者如何建立環境和安裝。`uv run` 搭配 PEP 723 大大簡化了這個過程。
- **工具鏈零散**：它將 `pip`（套件安裝）、`venv`（虛擬環境）、`pipx`（工具執行）等多個工具的功能整合到一個統一的指令中，簡化了工作流程。

## `uv run` 如何符合 PEP 723？

PEP 723 是一個 Python 增強提案，它定義了一種標準化的方式，將腳本的依賴項和其他 Metadata（如需要的 Python 版本）直接嵌入到 `.py` 檔案的註解中。

`uv run` 完全支援此規範。當你執行一個 Python 腳本時，`uv` 會掃描檔案開頭是否包含 PEP 723 格式的區塊。

**範例**：

一個 `main.py` 可以這樣寫：

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests<3",
#     "rich",
# ]
# ///
import requests
from rich.pretty import pprint

resp = requests.get("https://peps.python.org/api/peps.json")
data = resp.json()
pprint([(k, v["title"]) for k, v in data.items()][:10])
```

當你執行 `uv run main.py` 時：

1. `uv` 讀取到 `/// script` 區塊內的 Metadata。
2. 它會辨識出此腳本需要 `requests` 和 `rich` 這兩個套件。
3. 接著，`uv` 會在一個臨時的、隔離的虛擬環境中自動安裝這些依賴項。
4. 安裝完成後，`uv` 在這個準備好的環境中執行該腳本。

這個過程對使用者來說是完全無感的，不需要再去做虛擬環境的管理。

## 列出一些自己之後可以複習的官方文件或部落格

### 官方文件

官方文件是學習 `uv` 最準確的管道，內容詳盡且與最新版本同步：

- [[Getting started | uv]](https://docs.astral.sh/uv/getting-started/)：安裝步驟、基礎專案概念與 `uv` 的核心哲學。
- [[Features | uv]](https://docs.astral.sh/uv/getting-started/features/)：此頁面將 `uv` 的功能模組化（如：Python 版本管理、專案管理、指令稿執行、工具安裝），是快速了解 `uv` 全貌的最佳地圖。
- [[Running scripts | uv]](https://docs.astral.sh/uv/guides/scripts/)：解釋 `uv run` 如何執行單一腳本與 PEP 723 的整合。
- [[Locking and syncing | uv]](https://docs.astral.sh/uv/concepts/projects/sync/)：理解 `uv` 如何確保開發環境的可重現性（reproducibility），對於理解為何 `uv run` 比 `python3` 更可靠至關重要。
- [[PEP 723 – Inline script metadata]](https://peps.python.org/pep-0723/)：「腳本內嵌依賴」的標準規範， PEP 的原始定義文件。
- https://zsl0621.cc/python/best-python-project-manager

# Extended Reference ＆ FYI

- [1] https://docs.astral.sh/uv/getting-started/
- [2] https://docs.astral.sh/uv/getting-started/features/
- [3] https://docs.astral.sh/uv/guides/scripts/#using-a-shebang-to-create-an-executable-file
- [4] https://docs.astral.sh/uv/concepts/projects/sync/#partial-installations
- [5] https://peps.python.org/pep-0723/
- https://zsl0621.cc/python/best-python-project-manager

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
