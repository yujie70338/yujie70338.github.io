---
title: "〔CKS 筆記整理〕Kubernetes API Server Audit Log：資安鑑識與追蹤人為誤操作的最後防線"
subtitle: ""
description: "本文將從架構設計的角度，探討如何平衡稽核需求與 API Server 的效能，說明如何避免因配置不當導致 Master Node 故障，並建立一套符合最小權限原則的 Audit Logging 策略。"
date: 2025-12-07
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "Auditlogging", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes API Server Audit Log：資安鑑識與追蹤人為誤操作的最後防線

## 摘要

Audit Logging 是 Kubernetes API Server 的核心功能，用於記錄所有對 Cluster 的操作請求。這不僅是滿足資安合規的基本要求，更是 SRE 在追蹤資源變更（如 Deployment 被意外刪除）時的關鍵依據。本文將從架構設計的角度，探討如何平衡稽核需求與 API Server 的效能，說明如何避免因配置不當導致 Master Node 故障，並建立一套符合最小權限原則的 Audit Logging 策略。

## 前言：為什麼需要 Audit Logging？

當系統發生異常時，工程師通常會優先檢查 Pod Logs 或 Metrics。但在處理資安事件或人為誤操作時，問題往往不在應用程式本身，而在於釐清「是誰、在什麼時候、對什麼資源、做了什麼操作」。此時，kube-apiserver 的 Audit Logging 就提供了必要的鑑識資料。

更關鍵的是，**Pod Logs 是動態且易逝的**。攻擊者在入侵後，往往會嘗試清除容器內的 Application Logs，或是直接刪除 Pod 來掩蓋惡意活動軌跡。相較之下，Audit Logging 獨立於工作負載之外，客觀地記錄了 API 層級的所有互動。即使攻擊者抹除了容器內的痕跡，其「刪除資源」或「修改配置」的動作本身仍會被永久保留，成為防止抵賴 (`Non-repudiation`) 與保留證據的最後防線。

Audit Logging 能夠完整記錄對 Cluster 發起的所有請求，包含四個核心維度：**`Who` (來源 Identity)、`What` (操作內容)、`When` (時間點) 與 `Where` (來源 IP)**。然而，要在 Production 環境開啟這項功能，需要謹慎配置。若設定不當，可能會 Serialization 開銷過大而影響 API Server 的整體效能，甚至造成 Disk 空間耗盡使 master node outage。

## 架構權衡：Observability 與效能的平衡

Audit Logging 的配置核心在於選擇合適的記錄等級 (Level)。這不僅是參數設定，更是對系統負載與儲存成本的權衡。

Kubernetes 提供了四種記錄等級：

| Level | 記錄內容 | 典型用途 | 效能衝擊 |
|-------|---------|---------|---------|
| None | 不記錄任何資訊 | 排除高頻、無意義的系統雜訊 | 最低 |
| Metadata | 請求的標頭資訊 (User, Verb, Resource) | 大多數 API 操作的預設值 | 低 |
| Request | Metadata + Request Body | 記錄變更操作,如修改 Deployment | 中等 |
| RequestResponse | Metadata + Request Body + Response Body | 極度敏感資源的除錯或鑑識 | 最高 (高風險) |

**注意**：若對 Cluster 內大量 Object 的 LIST 操作開啟 `RequestResponse`，API Server 必須對所有 Object 進行 Serialization 並寫入 Log。這會導致 CPU 使用率飆升與巨大的 Disk I/O 壓力，嚴重時可能造成 API Server 回應延遲。因此，高詳細度的記錄等級應`僅針對少數敏感操作`開啟。

### 進階優化：利用 `omitStages` 削減日誌體積

除了 Level 之外，另一個鮮為人知但至關重要的優化參數是 `omitStages`。要理解它，必須先知道 Kubernetes API 請求的生命週期會經歷四個階段 (Stages)：

1. **RequestReceived**：Audit Handler 剛收到請求，尚未處理。
2. **ResponseStarted**：Header 已發送，但 Body 還沒送完 (通常用於長時間連接如 Watch)。
3. **ResponseComplete**：回應已完成，這是資訊最完整的時候。
4. **Panic**：處理請求時發生系統崩潰。

預設情況下，API Server 可能會針對同一個請求記錄多個階段的 Event（例如記一筆 RequestReceived，處理完再記一筆 ResponseComplete）。這會導致日誌量加倍，且浪費 I/O。

**實務建議**：
在絕大多數的鑑識場景中，我們只關心「最終結果」。因此，建議在策略中設定 `omitStages` 來忽略 `RequestReceived`。這能直接將日誌條目數量減半，且不會遺漏關鍵資訊。

```yaml
# 優化範例：只記錄結果，不記錄過程
- level: Metadata
  omitStages:
    - "RequestReceived"
  verbs: ["get", "list", "watch"]

```

## 如何啟用：API Server 參數配置

Audit Logging 並非預設開啟，必須在 Control Plane 的 `kube-apiserver` 啟動參數中進行配置。

在大多數使用 `kubeadm` 部署的 Cluster 中，您需要修改 `/etc/kubernetes/manifests/kube-apiserver.yaml`。

**參數範例說明：**

```yaml
spec:
  containers:
  - command:
    - kube-apiserver
    # 1. 指定策略檔案路徑 (必須先建立此檔案)
    - --audit-policy-file=/etc/kubernetes/audit-policy.yaml

    # 2. 指定日誌輸出路徑 (Log Backend: File)
    - --audit-log-path=/var/log/kubernetes/audit.log

    # 3. 配置 Log Rotation (防止 Disk 寫滿)
    - --audit-log-maxage=30       # 檔案保留 30 天
    - --audit-log-maxbackup=10    # 最多保留 10 個舊檔案
    - --audit-log-maxsize=100     # 每個檔案最大 100MB (到達上限即輪替)

```

**注意事項**：啟用前請確保 `/etc/kubernetes/audit-policy.yaml` 已經存在於 Master Node 上，且該路徑有正確掛載 (hostPath volume mount) 到 API Server Pod 內，否則 API Server 將無法啟動。

## 進階架構：整合 SIEM 與 Webhook Backend

在企業級環境中，單純將 Log 寫入本地檔案往往不夠，我們需要將 `Audit Log` 即時傳送到 `SIEM` (如 Splunk, Elasticsearch, Datadog) 或資安監控工具 (如 Falco)。

Kubernetes 提供了 **Webhook Backend** 模式，讓 API Server 將 Log 以 JSON 格式 POST 到外部 HTTP Endpoint。

### 步驟 1：準備 Webhook 設定檔

Webhook 設定檔是一個標準的 `kubeconfig` 格式檔案，用於定義接收端點的位置與驗證資訊。
假設您已經架設了一個 Log Collector (例如 Fluentd 或 Vector) 在 `https://192.168.1.100:8888` 接收日誌。

建立檔案 `/etc/kubernetes/audit-webhook.yaml`：

```yaml
apiVersion: v1
kind: Config
preferences: {}
clusters:
- name: audit-cluster
  cluster:
    server: https://192.168.1.100:8888  # Log Collector 的位址
    # 若接收端使用自簽憑證，需提供 CA；若信任系統 CA 則可省略
    # certificate-authority: /etc/kubernetes/pki/ca.crt
contexts:
- name: webhook
  context:
    cluster: audit-cluster
    user: kube-apiserver
current-context: webhook
users:
- name: kube-apiserver
  user:
    # 若需要驗證，可在此配置 client-certificate 或 token
    # token: "SECRET-TOKEN"

```

### 步驟 2：修改 API Server 參數與效能調優

Webhook Backend 最致命的風險在於：**如果接收端變慢，可能會拖慢 API Server**。因此，SRE 必須謹慎配置 Batching (批次處理) 參數。

修改 `kube-apiserver.yaml`，加入以下範例參數：

```yaml
    # 指定 Webhook 設定檔路徑
    - --audit-webhook-config-file=/etc/kubernetes/audit-webhook.yaml

    # 效能關鍵：批次發送配置 (Batching)
    - --audit-webhook-mode=batch    # 啟用批次模式 (預設為 batch，切勿設為 blocking)

    - --audit-webhook-batch-buffer-size=10000  # 記憶體中緩衝的最大事件數
    - --audit-webhook-batch-max-size=400       # 單次 HTTP POST 的最大事件數
    - --audit-webhook-batch-max-wait=30s       # 若未達 max-size，最長等待多久發送一次

    # 斷線保護
    - --audit-webhook-initial-backoff=10s      # 第一次失敗後的重試等待時間

```

**最佳實踐**：
不要讓 API Server 直接連線到位於公網的雲端 SIEM。建議在 Cluster 內部或同一 VPC 內架設一個輕量級的中介 Collector (如 Fluent Bit, Vector)，由它負責接收 Webhook 並緩衝，再異步轉發給後端的 Splunk 或 ELK。這樣能確保即便 SIEM 維護或斷線，API Server 也不會受到影響（Backpressure）。

### 步驟 3：中介層 Log Reduction 策略

直接將 API Server 的 Audit Log 送進雲端 SIEM (如 Splunk, Datadog) 是非常昂貴的，因為 Kubernetes Audit Log 的 JSON 結構非常冗長。

**操作策略**：

1. **過濾無用欄位**：
Kubernetes 的物件常包含 `managedFields`，這個欄位紀錄了每個欄位是由哪個 controller 修改的，體積巨大但對資安鑑識幾乎無用。務必在中間層將其刪除 (`drop`)。
    - *Vector VRL 範例*: `del(.requestObject.metadata.managedFields)`
2. **雜訊過濾 (Deduplication)**：
針對重複性極高的 `get` / `watch` 請求，可以在中間層進行取樣 (Sampling) 或聚合，只傳送異常或變更類的日誌。
3. **緩衝與重試 (Buffering)**：
中間層可以作為 Buffer。當 SIEM 維護或斷線時，Vector/Fluent Bit 可以將日誌暫存在本地 Disk，防止資料遺失，也避免阻塞 API Server。

## 儲存策略：避免 Disk 空間耗盡

如果您選擇使用 File Backend (寫入本地檔案)，則需考量儲存安全。在 Production 環境中，若未限制 Log 檔案的增長，可能會導致 Master Node Disk 寫滿，進而影響 API Server 運作。

因此，配置**Log Rotation (日誌輪替)** 是必要的。如上節參數所示，設定 `--audit-log-maxsize` 與 `--audit-log-maxage` 能確保 Log 佔用的 Disk 空間在可控範圍內。

## 資安鑑識重點：關鍵資源監控

在設定稽核策略時，應基於資安風險來選擇重點監控的對象。主要關注攻擊者可能進行 `Lateral Movement` (橫向移動) 或 `Privilege Escalation` (提權) 的路徑：

1. **ServiceAccounts (SA)**：SA Token 是 Pod 的身分識別憑證。針對 `TokenRequest` 或高權限 SA 的變更操作，建議啟用 `RequestResponse` 等級，以完整記錄憑證的獲取過程。
2. **Pod/Exec**：當有人`試圖進入 Container 執行命令`時，通常`涉及除錯或潛在入侵行為`。應開啟詳細記錄，以`還原使用者在 Container 內執行的具體指令`。

**重要原則**：對於 **Secrets** 資源，**僅能記錄 Metadata**。絕對不能對 Secrets 的 `get` 或 `list` 操作啟用 RequestResponse，否則敏感資訊（如 DB 密碼、API Key）將會以明文形式寫入 Audit Log，導致 Log 本身成為資安漏洞。

## 實戰配置：策略撰寫邏輯與 YAML 範例

Kubernetes Audit Policy 遵循「First match wins (第一條匹配生效)」原則。因此，**規則的順序配置非常關鍵**。

以下是一個符合最佳實踐的 `/etc/kubernetes/audit-policy.yaml` 範例：

```yaml
apiVersion: audit.k8s.io/v1
kind: Policy
# 全域省略 RequestReceived 階段，直接減少 50% 雜訊
omitStages:
  - "RequestReceived"

rules:
  # 1. 排除雜訊 (Drop Noise)
  # 不記錄 kube-system 內的高頻讀取操作，也不記錄 node 狀態回報
  - level: None
    verbs: ["get", "watch", "list"]
    namespaces: ["kube-system"]
  - level: None
    users: ["system:node-problem-detector", "system:kube-proxy"]

  # 2. 保護隱私 (Protect Secrets)
  # 強制 Secrets 只記錄 Metadata，防止內容外洩
  - level: Metadata
    resources:
    - group: ""
      resources: ["secrets"]

  # 3. 鎖定關鍵 (Capture Critical)
  # 記錄 Pod Exec/Attach 的完整請求與回應 (鑑識指令)
  - level: RequestResponse
    resources:
    - group: ""
      resources: ["pods/exec", "pods/attach"]

  # 記錄對 SA 的 token 請求
  - level: RequestResponse
    resources:
    - group: ""
      resources: ["serviceaccounts/token"]

  # 4. 記錄變更 (Capture Changes)
  # 對於所有資源的寫入操作 (create, update, patch, delete)，記錄 Request Body
  - level: Request
    verbs: ["create", "update", "patch", "delete"]

  # 5. 預設兜底 (Catch-all)
  # 其他所有操作 (通常是唯讀) 只記錄 Metadata
  - level: Metadata

```

這套策略能大幅減少 Log 量，同時確保關鍵的資安事件（如 Exec 進入容器、修改資源配置）都被完整保留，提升後續分析效率。

## 結語

Observability 需要在運算資源與儲存成本之間取得平衡，隨著 Cluster 規模擴大與業務邏輯變更，昨天的最佳配置可能成為今天的效能瓶頸。我們必須時刻意識到：每一條 Log 都有其代價。優秀的稽核策略並不在於記錄了多少，而在於能否在關鍵時刻——無論是資安鑑識或故障排查——提供精準的答案。透過精細化的 Policy 設計、穩健的 Webhook 架構以及中間層的 Log Reduction，建立一套既能提供足夠鑑識線索且合理節費，又不會影響系統穩定性的 Audit Policy。

# 參考連結

- [https://www.upwind.io/glossary/using-kubernetes-audit-logs-for-devsecops#:~:text=Request%3A Log metadata and the,%2C request%2C and response bodies](https://www.upwind.io/glossary/using-kubernetes-audit-logs-for-devsecops#:~:text=Request%3A%20Log%20metadata%20and%20the,%2C%20request%2C%20and%20response%20bodies).

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
