---
title: "〔〔CKS 筆記整理〕強化防禦 Kubelet ：探討 Kubelet Port 10250 的潛藏風險和防護策略"
subtitle: ""
description: "本文將解析 Kubelet Port 10250 的功能與潛在風險。"
date: 2025-12-30
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "Kubelet", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕強化防禦 Kubelet ：探討 Kubelet Port 10250 的潛藏風險和防護策略

## 摘要

在建構 Kubernetes 叢集防禦時，我們往往聚焦於 API Server 的權限控制或網路防火牆，卻容易忽略運行於每個節點上的 Kubelet 服務。Port `10250` 是 Kubelet 的主要控制介面，若配置不當，可能允許未授權的使用者直接控制節點。本文將解析 Kubelet 的潛在風險，介紹如何透過「權限委派（Delegation）」機制加強驗證，並說明 Port `10250` `10255` 的安全疑慮與防護建議。

### Kubelet 基礎介紹

**Kubelet 是什麼？**
`Kubelet` 是運行在叢集中每個節點（Node）上的核心代理程式（Agent），其角色類似於該節點的管理員。它的主要職責是持續監控 API Server 分派下來的 Pod 規格（PodSpec），並確保容器 runtime（如 Docker 或 containerd）依照這些規格運行容器。為了接收來自 Control Plane 的指令（例如查看日誌、執行命令），它預設監聽 TCP 10250 埠口。

**為何 Kubelet 容易被利用？**
Kubelet 之所以成為攻擊目標，是因為它`擁有**管理節點資源的權限**`。為了管理容器生命週期，Kubelet 必須能夠控制底層的容器 runtime。如果沒有正確設定認證與授權機制，Port 10250 就可能成為一個安全缺口。若未明確定義 Kubelet 該信任誰，它可能會接受匿名連線，讓攻擊者有機會繞過 API Server 的權限限制，直接對節點下達指令。

### Port 10250 的潛在風險

要理解這個風險，我們需要了解指令的傳遞路徑。當使用者執行 `kubectl logs` 或 `kubectl exec` 時，API Server 負責驗證請求，但最終指令會轉發到目標節點的 Kubelet Port 10250。

若此端口缺乏適當防護，且攻擊者能夠接觸到這個網路介面，可能產生的風險主要分為三類：

1. **遠端代碼執行 (Remote Code Execution, RCE)**
   透過 `/run` API，未授權者可能在節點上的容器內執行任意指令。這可能被用來植入惡意程式或對內部網路進行掃描。
2. **敏感資訊外洩 (Information Leakage)**
   透過 `/pods` API，可以列出該節點上所有 Pod 的完整規格（Spec）。若開發者將 **資料庫密碼** 或 **API Key** 直接寫在環境變數（Environment Variables）裡，這些資訊將被直接讀取。
3. **應用程式日誌存取**
   透過 `/logs` 介面讀取應用程式的標準輸出，可能導致除錯資訊或使用者資料外洩。

### 核心防禦機制：權限委派 (Delegation)

為了有效管理大量節點的權限，Kubelet 採用 **「權限委派」** 模式。這代表 Kubelet 不自行維護使用者清單或決定權限，而是`將驗證工作交還給 Kubernetes API Server` 處理。

這套機制包含兩個步驟：

- **步驟 1: 認證委派 (Authentication Delegation)**
  當 Kubelet 收到請求（例如監控系統的抓取請求）時，它不會自己解析 Token，而是將 Token 轉發給 API Server 確認身分。API Server 驗證後回傳該 Token 代表的使用者身分。
- **步驟 2: 授權委派 (Authorization Delegation)**
  確認身分後，Kubelet 再次詢問 API Server，確認該使用者是否有權限執行特定動作（例如讀取節點狀態）。API Server 會依據 RBAC 規則回傳允許或拒絕。

透過這兩個步驟，Kubelet 的存取控制就能與整個叢集的安全策略保持一致。

### 實務配置指南

實務上，我們通常透過修改 `KubeletConfiguration` 來落實上述策略。以下是關鍵參數的說明與建議值：

| 設定分類       | 參數名稱                           | 建議值    | 說明                                                       |
| -------------- | ---------------------------------- | --------- | ---------------------------------------------------------- |
| **拒絕匿名**   | `authentication.anonymous.enabled` | `false`   | **基本設定**。強制所有請求必須攜帶憑證，拒絕不明連線。     |
| **認證機制**   | `authentication.webhook.enabled`   | `true`    | 啟用認證委派，將 Token 驗證工作轉交給 API Server 處理。    |
| **授權機制**   | `authorization.mode`               | `Webhook` | 啟用授權委派，依據 API Server 的 RBAC 規則來決定存取權限。 |
| **關閉唯讀埠** | `readOnlyPort`                     | `0`       | **關鍵設定**。關閉無需認證即可讀取 Pod 資訊的 Port 10255。 |

**設定檔範例 (`kubelet-config.yaml`)：**

```
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
authentication:
  anonymous:
    enabled: false          # [關鍵] 強制拒絕匿名連線
  webhook:
    enabled: true           # [關鍵] 啟用認證委派
  x509:
    clientCAFile: /etc/kubernetes/pki/ca.crt
authorization:
  mode: Webhook             # [關鍵] 啟用授權委派
readOnlyPort: 0             # [關鍵] 關閉不安全的唯讀埠口 (Port 10255)

```

### Port 10255 的安全疑慮

Port 10255 預設是 Kubelet 的「唯讀埠口（Read-Only Port）」。這是一個常見的誤區，許多人認為「唯讀」代表安全。然而，`Port 10255 完全無需認證，任何能連線到該埠口的人都能存取資訊`。

- **架構資訊**：可得知節點上運行了哪些服務與版本。
- **環境變數**：若 Pod Spec 中含有明碼的 Environment Variables（如密碼），可被直接讀取。

因此，為了落實安全原則，**建議將 `readOnlyPort` 設為 `0` 以完全關閉此埠口**。

### 進階設定與常見問題

除了基礎設定，建議啟用 API Server 的 `NodeRestriction` 功能，`限制 Kubelet 只能修改屬於自己的節點物件`，防止權限擴散。同時，開啟憑證自動輪替（Certificate Rotation）以定期更新金鑰。

### （補充）Metrics Server 運作異常的解決方式

啟用嚴格的權限驗證後，最常見的副作用是 Metrics Server 無法抓取數據（例如導致 `kubectl top nodes` 顯示錯誤）。

- **原因**：Metrics Server 過去可能依賴匿名或較為寬鬆的存取權限。加固後，Kubelet 拒絕了它的請求。
- **解決方法**：建立專屬的 RBAC 規則，明確賦予 Metrics Server 存取權限。

**解決方案範例 (ClusterRole)：**

```
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: system:aggregated-metrics-reader
rules:
- apiGroups: [""]
  resources: ["nodes/metrics", "nodes/stats", "nodes/proxy"]
  verbs: ["get", "list", "watch"]

```

### 結語

強化 Kubelet 安全性的核心在於：將認證與授權回歸 API Server 統一管理，並關閉不必要的埠口（如 Port 10255）。雖然這需要額外的配置，甚至可能在初期影響部分監控工具的運作，但透過正確的 RBAC 設定即可解決。這些措施能有效降低節點被未授權存取的風險，建立更穩固的叢集環境。

# Extended Reference ＆ FYI

- [Secure kubelet port 10250 #7965](https://github.com/kubernetes/kubernetes/issues/7965)
- [**Kubelet authentication/authorization**](https://kubernetes.io/docs/reference/access-authn-authz/kubelet-authn-authz/)
- [**Securing the Kubelet**](https://notes.kodekloud.com/docs/Kubernetes-and-Cloud-Native-Security-Associate-KCSA/Kubernetes-Cluster-Component-Security/Securing-the-Kubelet)
- [**kubelet**](https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet/)
- [**Set Kubelet Parameters Via A Configuration File**](https://kubernetes.io/docs/tasks/administer-cluster/kubelet-config-file/)
- [KubeletConfiguration API](https://kubernetes.io/docs/reference/config-api/kubelet-config.v1beta1/?utm_source=chatgpt.com)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
