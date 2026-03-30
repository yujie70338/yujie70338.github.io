---
title: "〔筆記整理〕訊息佇列選型：RabbitMQ vs Kafka 深度解析"
subtitle: ""
description: "深入比較 RabbitMQ 與 Kafka 的底層設計、吞吐量、交付保證與使用場景，協助微服務架構下的技術選型決策。"
date: 2026-03-30
author: "Yujie Zheng"
image: ""
tags: ["MessageQueue", "RabbitMQ", "Kafka", "DistributedSystems", "MicroServices"]
categories: [ "tech" ]
---

# 〔筆記整理〕RabbitMQ vs Kafka 

- [〔筆記整理〕RabbitMQ vs Kafka](#筆記整理rabbitmq-vs-kafka)
  - [前言](#前言)
  - [RabbitMQ 是什麼？](#rabbitmq-是什麼)
  - [Kafka 是什麼？](#kafka-是什麼)
  - [核心差異深入比較](#核心差異深入比較)
    - [順序保證](#順序保證)
    - [吞吐量與延遲](#吞吐量與延遲)
    - [交付保證](#交付保證)
  - [應用場景選擇](#應用場景選擇)
  - [總結](#總結)
- [Extended Reference ＆ FYI](#extended-reference--fyi)

## 前言

**【技術筆記】RabbitMQ 與 Kafka 的比較**

> 準備 system design 時的學習隨手整理。

在分散式系統與微服務架構中，服務之間的通訊是一大挑戰。當我們使用傳統的直接呼叫（如 HTTP 請求）時，若下游服務遇到流量突波或當機，上游服務就可能被迫等待、超時，甚至遺失請求。

為了解決 **系統耦合、單點故障與無法應對流量突波** 的問題，訊息佇列（Message Queue）應運而生。透過在服務之間加入「緩衝區」，生產者（Producer）只需將訊息丟入佇列即可立即返回，消費者（Consumer）則依照自身處理能力擷取訊息，實現系統解耦並有效吸收突發流量。

RabbitMQ 與 Apache Kafka 是這個領域最受歡迎的兩大解決方案，但它們的底層設計與解決的核心問題截然不同。

## RabbitMQ 是什麼？

RabbitMQ 是一款傳統的訊息代理（Message Broker），設計核心在於確保訊息能被準確、靈活地路由並交付至指定目的地。
- 推播模型（Push-based）：RabbitMQ 會主動將訊息推播給消費者。
- 以 Broker 為重心的架構：RabbitMQ 的 Broker 承擔了極大的系統責任。它負責根據設定的規則處理複雜的訊息路由、追蹤訊息是否已成功交付，並自動管理重試機制與死信佇列（Dead letter queue）。相對地，消費者端只需單純地接收與處理訊息即可。
- 消費後即刪除（Message Deletion）：一旦消費者確認（ACK）成功處理了訊息，RabbitMQ 就會將該訊息從佇列中刪除
。

## Kafka 是什麼？

Apache Kafka 是一個分散式事件串流平台（Event Streaming Platform），底層本質上是「分散式僅附加日誌（Distributed append-only log）」的實現。
- 拉取模型（Pull-based）：消費者會依照自己的節奏，批次從 Kafka 中主動拉取訊息。
- 以消費者為重心的架構：與 RabbitMQ 相反，Kafka 的 Broker 責任非常輕量，只負責將訊息循序寫入日誌中。消費者必須自己負責追蹤並記錄讀取的位置（稱為 Offset）。
- 持久化與可重播性（Persistence and Replayable）：訊息被讀取後 **不會被刪除**，而是會根據設定的保留策略（例如保留數小時、數天或無限期）持久化儲存在磁碟中。這讓多個不同的系統可以獨立讀取同一個資料流，或者隨時回到歷史紀錄的任何時間點重新處理資料。

## 核心差異深入比較

### 順序保證

RabbitMQ 提供嚴格的佇列順序保證；若只有單一消費者，可獲得完美的全域順序（Global Ordering）。然而一旦增加多個並行消費者提升吞吐，順序保證就被犧牲。

Kafka 將主題（Topic）切分為多個 **分割區（Partitions）**，只保證分割區內的順序（Per-partition Ordering）。透過指定 Partition Key（例如同一用戶 ID），可讓該用戶所有事件進入同一分割區依序處理，兼顧多分割區的並行吞吐能力。

### 吞吐量與延遲

| 指標 | RabbitMQ | Kafka |
|------|----------|-------|
| 延遲 | 約 1–5 ms | 約 5–50 ms |
| 吞吐量 | 約 4,000–10,000 msg/s | 超過 1,000,000 msg/s |
| 特點 | 低延遲，Broker 複雜路由負擔高 | 高吞吐，批次追加寫入降低每筆負擔 |

### 交付保證

兩者皆支援 **最多一次（At most once）**與 **最少一次（At least once）** 交付。Kafka 額外支援 **精確一次（Exactly once）**，但有使用限制，通常僅適用於輸入輸出皆在同一 Kafka 叢集的封閉交易場景。

> 實務上，無論選擇哪套系統，仍建議在消費者端實作 **冪等性（Idempotent）** 以應對潛在的重複訊息。

## 應用場景選擇

**選擇 RabbitMQ 的場景：**
因為 RabbitMQ 具備低延遲、強大靈活的路由能力，且架構以任務導向為主，所以以下場景會選擇它：
- **背景任務與工作佇列（Task Queue）**：發送電子郵件、處理付款、圖片轉檔等任務，處理完畢即刪除。
- **微服務間請求-回應**：需要低於 5ms 的極低延遲，且以服務解耦為主要目標。
- **複雜路由邏輯**：需要 Broker 根據訊息內容智慧派發至特定佇列或消費者。

**選擇 Kafka 的場景：**
因為 Kafka 具備極致的百萬級吞吐量、資料持久化能力以及支援多方獨立消費，所以以下場景會選擇它：
- **多系統共用事件主幹（Event Stream）**：同一事件（如訂單成立）需被通知、分析、詐欺偵測、帳單等多個系統獨立消費。
- **歷史資料重播（Replayability）**：需要回到過去任意時間點重新處理資料，例如災難復原或重訓機器學習模型。
- **巨量資料管道**：每秒百萬級的日誌聚合（Log Aggregation）、IoT 感測器資料或用戶點擊流（Clickstream）分析。

## 總結

RabbitMQ 與 Kafka 並非競爭關係，而是針對不同問題的解方。選擇時應先回答幾個核心問題：吞吐量是否達到每秒百萬級？是否需要多個下游系統獨立消費同一份資料？是否需要資料回播能力？。

# Extended Reference ＆ FYI

1. [RabbitMQ vs Kafka: A Practical Guide - Medium](https://medium.com/@taycode/rabbitmq-vs-kafka-a-practical-guide-61b82c096cf7)
2. [Kafka vs RabbitMQ - DataCamp](https://www.datacamp.com/blog/kafka-vs-rabbitmq)
3. [Choosing RabbitMQ or Kafka - Confluent](https://www.confluent.io/compare/rabbitmq-vs-apache-kafka/#at-a-glance-choosing-rabbitmq-or-kafka)
4. [YouTube: RabbitMQ vs Kafka 比較影片](https://www.youtube.com/watch?v=1HOVtQ-_fcE)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
