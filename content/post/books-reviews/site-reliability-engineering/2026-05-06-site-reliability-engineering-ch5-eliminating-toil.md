---
title: "📗〔讀書心得〕- SRE Ch5：消滅瑣事 (Toil) "
subtitle: ""
description: "探討 Google SRE 如何定義並系統性地消除 Toil（瑣事）。了解手動操作、重複性、可自動化等五大特徵，以及 50% 法則如何幫助團隊從被動救火轉向主動預防，實現可靠性與可擴展性的雙贏。"
date: 2026-05-06
author: "Yujie Zheng"
image: ""
tags: ["BookReview", "SiteReliabilityEngineering", "Automation", "GoogleSRE", "Toil" ]
categories: [ "books-reviews" ]
---
這篇文章將聚焦於《Site Reliability Engineering》中的：

- [Chapter 5 - Eliminating Toil](https://sre.google/sre-book/eliminating-toil/)

將深入探討 SRE 如何定義、衡量並消除 Toil，以及為何這種思維是現代軟體工程師與維運人員的必修課。

---

# 📗〔讀書心得〕- SRE Ch5：消滅瑣事 (Toil)

- [SRE 核心精神：為什麼消滅「瑣事 (Toil)」是 SRE 的最高價值？](#sre-核心精神為什麼消滅瑣事-toil是-sre-的最高價值)
- [核心概念：到底什麼是「瑣事 (Toil)」？](#核心概念到底什麼是瑣事-toil)
  - [1. 手動操作 (Manual)](#1-手動操作-manual)
  - [2. 重複性 (Repetitive)](#2-重複性-repetitive)
  - [3. 可自動化 (Automatable)](#3-可自動化-automatable)
  - [4. 戰術性而非戰略性 (Tactical, not Strategic)](#4-戰術性而非戰略性-tactical-not-strategic)
  - [5. 缺乏長期價值 (No Enduring Value)](#5-缺乏長期價值-no-enduring-value)
  - [Bonus: 隨服務規模線性增長 O(n) (Scales Linearly)](#bonus-隨服務規模線性增長-on-scales-linearly)
- [實務落地：Google SRE 的 50% 法則](#實務落地google-sre-的-50-法則)
- [SRE 核心概念：何謂真正的「工程」工作？](#sre-核心概念何謂真正的工程工作)
- [Toil 一定是壞事嗎？](#toil-一定是壞事嗎)
  - [對個人的影響：](#對個人的影響)
  - [對組織的影響：](#對組織的影響)
- [我的 TAKEAWAY](#我的-takeaway)
- [Extended Reference ＆ FYI](#extended-reference--fyi)

## SRE 核心精神：為什麼消滅「瑣事 (Toil)」是 SRE 的最高價值？

你是否也曾陷入這樣的循環：每天上班，處理不完的告警、手動重啟服務、執行重複的部署腳本、為新用戶手動設定權限⋯⋯？這些工作看似必要，卻讓你沒有時間思考如何改善系統，只能被動地「救火」。當系統規模擴大，這些瑣碎的工作也跟著線性增長，最終吞噬了你所有的時間與精力。

在 Google，他們為這類工作定義了一個專有名詞：**Toil**（瑣事）。

Site Reliability Engineering (SRE) 的核心理念之一，就是系統性地辨識並消滅 Toil。這不只是為了讓工程師工作得更開心，更是確保服務能夠**可靠地**（Reliability）、**可延展地**（Scalability）運行的關鍵。

> If a human operator needs to touch your system during normal operations, you have a bug. The definition of normal changes as your systems grow.
Carla Geisser, Google SRE
> 

## 核心概念：到底什麼是「瑣事 (Toil)」？

首先，我們必須釐清，Toil 並不等於「所有你不想做的工作」。有些任務雖然繁瑣，但具有長期價值（例如：重構老舊的設定檔），這就不是 Toil。有些工作是行政管理所需（例如：團隊會議、撰寫績效報告），這屬於 **Overhead**（行政開銷），也不是 Toil。

那麼，SRE 定義的 **Toil** 究竟是什麼？它通常具備以下五個特徵中的一個或多個：

### 1. 手動操作 (Manual)

- **定義**：這項工作需要人為介入執行。即使是運行一個自動化腳本，如果需要你親自登入主機、輸入指令並監看過程，這個「手動觸發」的動作本身就是 Toil。

### 2. 重複性 (Repetitive)

- **定義**：如果你需要一遍又一遍地做同樣的事情，這就是 Toil。第一次解決問題是「Engineering」，但第一百次做同樣的操作就是「Toil」。

### 3. 可自動化 (Automatable)

- **定義**：如果一台機器能和你做得一樣好，甚至更好，那這項工作就是 Toil。如果任務需要人類的專業判斷與創造力，那它就不是 Toil。

### 4. 戰術性而非戰略性 (Tactical, not Strategic)

- **定義**：Toil 通常是被動、中斷驅動的。你不是在規劃未來，而是在處理眼前立即發生的問題。處理 Pager 告警就是最典型的戰術性 Toil。

> 「Pager 告警」一詞源自 **早期工程師值班的傳呼機時代**，後來延伸為所有 **on-call 緊急告警** 的代稱。今天我們講「處理 Pager 告警」，其實就是在說「處理 on-call 時跳出來的緊急系統事件」。
> 

### 5. 缺乏長期價值 (No Enduring Value)

- **定義**：當你完成這項工作後，系統的狀態只是「恢復原狀」，並沒有變得更好。

### 6. 隨服務規模線性增長 O(n) (Scales Linearly)

- **定義**：如果你的工作量隨著用戶數、流量或伺服器數量成正比增加，那它就是 Toil。


---

## 實務落地：Google SRE 的 50% 法則

**理解了什麼是 Toil，下一步就是如何消滅它。**

Google SRE 團隊有一個著名的目標：**將 Toil 控制在每位工程師 50% 的工作時間以下**。剩下的 50% 應該投入在「工程」項目上，例如開發自動化工具、重構系統架構、提升系統效能等，這些工作能夠在未來減少更多的 Toil。

那麼，這個時間是如何計算的呢？

最基本的 **Toil** 來源是輪值（on-call）班表。一個典型的 SRE 團隊，成員需要輪流擔任主要（primary）與次要（secondary）的隨時待命角色。如果一個團隊有 4 個人，每個人在一個週期內需要擔任一週的待命，這意味著在每 4 週中，至少有 1 週的時間是用於處理待命與中斷性工作。因此，潛在的 **Toil** 時間下限為 1/4 = 25%。

根據 Google 內部 SRE 的季度問卷調查顯示，**Toil** 的主要來源是來自各種中斷性工作（interrupts），例如處理非緊急的服務相關訊息或電子郵件。其次才是緊急的隨時待命響應，接著是版本發布與部署（Releases and Pushes）。

調查結果也顯示，Google SRE 團隊平均花在 **Toil** 上的時間約為 33%。

---

## SRE 核心概念：何謂真正的「工程」工作？

了解完 「瑣事 (Toil)」後，來了解 「工程」工作的定義為何：

- **原創性與判斷力（Novelty & Judgment）**：工程工作是**新穎的**，沒有現成的標準答案。它需要運用專業知識做出判斷與決策，而非機械式地重複操作。
- **永久性的改善（Permanent Improvement）**：一次的工程投入，可以讓未來的問題不再發生，或是讓處理問題的效率大幅提升。它不是為了應付單次事件，而是為了從根本上解決問題。
- **策略驅動（Strategy Driven）**：工程工作通常是基於長期策略規劃。例如，為了應對未來用戶成長，你選擇重新設計一套軟體架構的設計或是系統架構的設計。
- **創造性與設計思維（Creativity & Design）**：它是一個設計導向的過程，目標是創造出更通用、更可擴展的解決方案。例如，開發一個通用的自動化**函式**庫，讓所有團隊都能使用，而非僅僅為了解決一個特定問題。

---

## Toil 一定是壞事嗎？

這是一個常見的誤解。**Toil** 在某些情況下並不總是負面的。適量且可預測的 **Toil** 任務，有時能給人一種成就感和快速完成的滿足感。它們通常風險低、壓力小，有些人甚至可能喜歡這類工作。

此外，書中提及，我們必須認清一個事實：**任何工程師角色，都無法完全避免 Toil**。少量的 **Toil** 是可以接受的，只要你不因此感到不滿，這就不是問題。

然而，一旦 **Toil** 的比例過高，就會變得有害。過多的 **Toil** 會帶來以下嚴重的負面影響：

### 對個人的影響：

- **職涯停滯（Career Stagnation）**：如果你的大部分時間都花在處理 **Toil** 上，你將沒有時間參與能展現你能力、提升你專業技能的專案。長期下來，你的職涯發展將會停滯不前。
- **士氣低落（Low Morale）**：雖然每個人的忍受程度不同，但每個人都有極限。過多的 **Toil** 會導致倦怠、厭煩和不滿。

### 對組織的影響：

- **角色混淆（Creates Confusion）**：SRE 團隊努力向內外部夥伴傳達我們是一個「工程組織」。當 SRE 團隊花過多時間在 **Toil** 上，這會混淆大家對 SRE 角色的認知，使外界誤以為 SRE 就是救火隊或系統管理員。
- **進度緩慢（Slows Progress）**：當 SRE 團隊忙於手動維護與救火，就沒有時間進行重要的自動化或**可靠性**專案。這會導致整個產品的開發速度變慢，因為 SRE 無法即時為新功能提供支援。
- **負面先例（Sets Precedent）**：如果你過於樂意承擔 **Toil**，你的開發同事可能會將原本屬於他們的維運工作轉嫁給你。這會形成一個惡性循環，讓其他團隊也開始期望 SRE 承擔這類工作。
- **人才流失（Promotes Attrition）**：即使個人不介意 **Toil**，你的現有或未來同事可能無法忍受。如果團隊文化中充滿 **Toil**，最優秀的工程師將會尋求更具挑戰性與回報的工作機會。
- **承諾違背（Breach of Faith）**：對於那些被 SRE 的「工程工作」願景所吸引而加入的新人，過多的 **Toil** 會讓他們感到被欺騙，嚴重影響團隊士氣。

---

## 我的 TAKEAWAY

- 消除 Toil 的過程，本質上是將團隊的思維模式從**被動反應**轉變為**主動預防**。它要求我們不再滿足於「讓系統暫時恢復運作」，而是要不斷問：「如何才能讓這個問題永遠不再發生？」
- 真正的「工程」工作的目標是：**用同樣的人力，去管理更大規模或更多的服務。** 它追求的是槓桿效應。
- 務實上，不是每間公司都有 Google 的資源、技術實力與工程文化，並且可以強制的設定少於 50 % toil 的目標，完全的 "Toil-Free" 是一個過於理想目標，但「持續減少 Toil」的趨勢對任何規模的組織都有益。
- 團隊必須具備足夠的工程能力。傳統的系統管理員往往習慣手動操作，缺乏打造穩健自動化工具的背景。這需要組織在人才培養上持續投資，例如 Python、Terraform、Ansible、prometheus、 …等工具。
- 最常見的困境是時間與資源的「死亡螺旋」：因 Toil 太多而沒有時間做自動化，結果導致 Toil 不斷增加。要打破這個循環，必須制定有力的決策，例如規定每個季度漸進地保留固定比例的時間或資源，專門用於技術債清償與 Toil 消除。

# Extended Reference ＆ FYI
1. https://sre.google/sre-book/eliminating-toil/

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
