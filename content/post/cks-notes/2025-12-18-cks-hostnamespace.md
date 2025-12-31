---
title: "〔CKS 筆記整理〕Kubernetes 特權後門：揭秘 Host Namespaces 帶來的容器安全隱患與防禦策略"
subtitle: ""
description: "本文將深入探討 service account 預設行為的風險，並提供阻斷此攻擊路徑的範例設定。"
date: 2025-12-18
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "ServiceAccount", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes 特權後門：揭秘 Host Namespaces 帶來的容器安全隱患與防禦策略

在 Kubernetes 的安全模型中，開發者與維運人員通常會將目光集中在 `securityContext` 中的 `privileged: true` 設定。然而，在 Pod 的 `spec` 層級中，隱藏著三個以 `host` 開頭的設定，它們的危險程度絲毫不亞於特權模式，卻經常被忽視。

這三個設定分別是：`hostNetwork`、`hostPID` 與 `hostIPC`。

本文將探討 Kubernetes Host Namespaces (hostNetwork, hostPID, hostIPC) 作為經常被忽略的重大安全風險，它們實質上是 特權後門 (privilege backdoors)。我們將解釋 Linux Namespaces (Network, PID, IPC) 如何實現容器隔離，以及為何啟用 host\* 設定可以繞過這些關鍵邊界。

## 1. 基礎觀念：什麼是 Namespace？

要深入理解「Host Namespace」的風險，我們必須回歸容器的本質。

容器（Container）並非虛擬機（VM），其本質是 Linux 系統上的一個普通行程（Process）。之所以使用者在容器內看不到系統上的其他行程，是因為 Linux Kernel 使用了 **Namespaces（命名空間）** 技術在系統資源上建立隔離機制，使在不同 namespace 下的進程只能看到它們各自的 資源視圖（isolated view of system resources）。

常見的 Namespaces 包括：

- **Network Namespace**：讓容器擁有獨立的 IP 位址、路由表和網卡，使其看不到宿主機（Node）的網路介面。
- **PID Namespace**：讓容器擁有獨立的行程編號（PID）空間，使其看不到宿主機上的其他執行程式。
- **IPC Namespace**：讓容器擁有獨立的行程間通訊資源（如 Message Queues、Shared Memory）。

在預設情況下，這些 Namespace 就像一道道牆，將容器內的環境與底層 Node 隔開，確保了容器的隔離性。

## 2. Host Namespaces：打破容器隔離的特權後門

當你在 Pod 的 YAML 設定中開啟 `hostNetwork: true`、`hostPID: true` 或 `hostIPC: true` 時，等於是在告訴 Kubernetes：

**「請把這道牆打掉，讓這個容器直接使用底層 Node 的空間。」**

這就是為什麼我們將其稱為「特權後門」。雖然容器表面上看起來還是在獨立運行，但實際上它的一隻腳已經跨進了宿主機的核心區域，打破了容器最基本的信任邊界。

## 3. 三大危險設定解析

這三個設定位於 YAML 的 `spec` 根層級，而非 `securityContext` 內，這也是它們容易在程式碼審查中被忽略的原因。

### 3.1 hostNetwork: true (網路層破口)

**行為描述：**
啟用後，該 Pod 不再獲取 Cluster 內部的獨立 IP，而是直接共用 Node 的 IP 位址與網路介面。

**實際現象：**
在容器內執行 `ifconfig` 或 `ip addr` 時，看到的不再是虛擬網卡，而是實體機的 `eth0` 或 `ensX`。若容器監聽 port 80，就等同於 Node 本身在監聽 port 80。

**主要安全風險**
這是雲端環境中最常見的攻擊路徑之一。

1. **網路監聽與橫向流量接觸**：Pod 直接置於 Node 的網路命名空間，可監聽或存取該 Node 上的所有網路流量，可能繞過 Kubernetes 內建的網路隔離與 NetworkPolicy。這樣的行為可被利用作為流量嗅探或橫向移動的起點。
2. **存取雲端執行個體中繼資料服務（Instance Metadata Service）**：典型雲端平台（例如 AWS）在 `169.254.169.254` 提供 Metadata Service 供執行個體查詢臨時 IAM 憑證與其他敏感資訊。正常 Pod 的來源 IP 是 Pod IP，受限較多。而啟用 hostNetwork 的 Pod 來源 IP 是 Node IP，雲端會識別為 Node 本身請求 Metadata Service，因此可能返回與該 Node 相關的高權限憑證。
3. **雲端權限外洩的連鎖衝擊**：如果取得 Node 的高權限 IAM Credentials，攻擊者可能操作該節點甚至整個專案/叢集層的資源，比僅控制單一容器更具破壞性，導致雲端環境全面失陷。這是許多雲端 Kubernetes 安全評估中常見的高風險警告點。

### 3.2 hostPID: true (行程層破口)

**行為描述：**
容器與 Node 共用 PID 命名空間。

**實際現象：**
在容器內執行 `ps aux`，可以看到 Node 上正在運行的「所有」程式，包含 `kubelet`、`containerd`、系統 Daemon，甚至其他 Pod 的行程。

**主要安全風險**

1. **敏感資訊揭露**：容器可列出 Node 所有行程及其參數，可能暴露明文密碼、憑證或敏感資訊。
2. **拒絕服務（DoS）**：如果容器能操作 PID（例如 kill），可終止關鍵行程（如 kubelet），導致該節點變成 NotReady 甚至失效。
3. **行程附著與提權**：若容器具有類似 SYS_PTRACE 能力，可利用 ptrace 等機制附著到高權限行程，如 kubelet，進行執行任意程式碼或提權。

### 3.3 hostIPC: true (通訊層破口)

**行為描述：**
設定 hostIPC: true 後，該 Pod 與 Node（節點）共用 IPC 命名空間，容器可以使用宿主機的行程間通訊機制（例如 共享記憶體／Shared Memory、信號量／Semaphores、訊息佇列／Message Queues）。這樣做會讓容器能直接讀寫宿主機的 IPC 資源。

**主要安全風險**

1. **共用 IPC 會暴露敏感資料**：容器可存取宿主機及其他 Pod 的共享記憶體區塊，可能讀取或修改敏感資料。這等同於把宿主機的通訊機制暴露給容器。
2. **干擾或破壞 IPC 資源**：攻擊者可寫入垃圾資料或不正當的訊號量值，破壞共享記憶體內容或操作序列，進而導致依賴 IPC 的應用（例如資料庫、HPC 程式）錯誤或崩潰。

## 4. 風險總結與防禦策略

在威脅模型 (Threat Model) 中，我們必須將這三個 `host*` 設定視為與 `privileged: true` 同等級的最高風險。

| 設定名稱        | 核心影響       | 關鍵攻擊路徑                                   |
| --------------- | -------------- | ---------------------------------------------- |
| **hostNetwork** | 網路身分混淆   | 竊取雲端 IAM 憑證 (Metadata Service)、封包監聽 |
| **hostPID**     | 行程可見與控制 | 殺死 Kubelet (DoS)、行程注入、敏感參數洩露     |
| **hostIPC**     | 記憶體干擾     | 破壞資料庫或高敏應用記憶體區塊                 |

## 防禦策略

### 1. 預設拒絕共享 Host Namespace 與 Host 資源

在所有生產環境 Namespace 中預設禁止 `hostNetwork`、`hostPID`、`hostIPC` 等欄位設定為 `true`。

除非有明確且必要的理由，不應允許 Pod 共用節點的命名空間或資源。這是最簡單也最有效的隔離原則。

### 2. 採用 Kubernetes Pod Security Standards（PSS）

使用 Kubernetes 內建的 Pod Security Standards（PSS）來統一 Namespace 的安全等級。

**套用 Baseline 或 Restricted Profile：**

- **Baseline**：禁止已知高風險權限設定（例如 HostNamespace）。
- **Restricted**：在 Baseline 基礎上更嚴格限制（例如禁止特權容器、root 使用者等）。

確保 namespace 有適當的安全標籤，例如至少為 `baseline` 等級，並在必要時提升為 `restricted`。

這能在資源建立階段**自動拒絕**不符合政策的 Pod 部署請求。

### 3. 例外需求的白名單與隔離管理

只有極少數受信任的系統元件（例如某些系統監控 Agent 或 CNI plugin）才可能需要這類高權限設定。

對這些例外請求實施嚴格白名單、RBAC 控制，並考慮放在**專用 Namespace** 中，並透過 NetworkPolicy 限制其網路存取範圍。

避免將例外設定散佈在一般應用 Namespace，減少誤用風險。

### 快速檢測：你的叢集安全嗎？

你可以使用以下 `kubectl` 指令，快速找出叢集中所有開啟 `hostNetwork` 的 Pod：

```
kubectl get pods -A -o jsonpath='{range .items[?(@.spec.hostNetwork==true)]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}'

```

### 高風險 YAML 範例 (應被阻擋)

以下是一個典型的危險配置範例。請注意，即使 `containers` 下方的 `securityContext` 看起來很乾淨，只要 `spec` 層級開啟了這些設定，該 Pod 就足以讓駭客接管節點。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: dangerous-pod
spec:
  # 危險區域：這三行讓容器突破隔離牆
  hostNetwork: true
  hostPID: true
  hostIPC: true
  containers:
    - name: attacker
      image: hacker-tool
      # 即使這裡沒有 privileged: true，上述設定依然極度危險
```

## 5. 結論

Kubernetes 的安全性不僅取決於外部防火牆，更取決於每個 Pod 的配置細節。`hostNetwork`、`hostPID` 與 `hostIPC` 是三把雙面刃，它們雖然提供了便利的除錯與監控能力，但也同時敞開了通往節點核心的大門。

作為叢集管理員，我們必須在「便利性」與「安全性」之間找到平衡點。當你選擇打破這層隔離時，必須清楚意識到這等同於放棄了容器最基本的安全保障。請務必透過 Pod Security Standards (PSS) 或 Policy-as-Code 工具（如 OPA Gatekeeper、Kyverno）來自動化攔截這些危險配置，落實真正的「最小權限原則」(Least Privilege)。

## 參考連結

- [**Pod Security Standards**](https://kubernetes.io/docs/concepts/security/pod-security-standards/)
- [**Process Injection: Ptrace System Calls**](https://attack.mitre.org/techniques/T1631/001/)
- [**Code injection in running process using ptrace**](https://medium.com/@jain.sm/code-injection-in-running-process-using-ptrace-d3ea7191a4be)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
