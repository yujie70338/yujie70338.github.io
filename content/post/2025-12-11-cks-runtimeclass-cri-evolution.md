---
title: "〔CKS 筆記整理〕Kubernetes RuntimeClass：從 CRI 演進到選擇各場景 RuntimeClass 實作"
subtitle: ""
description: "這篇文章將帶您回顧 Kubernetes CRI 的演進歷史，理解為何我們需要 RuntimeClass，並深入解析如何在生產環境中正確配置與管理多租戶與多元業務場景。"
date: 2025-12-11
author: "Yujie Zheng"
image: ""
tags: ["K8S","Kubernetes","RuntimeClass","CRI","gVisor","Kata","containerd","CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes RuntimeClass：從 CRI 演進到選擇各場景 RuntimeClass 實作

隨著 Kubernetes 在企業中的滲透率越來越高，我們對於「容器執行環境 (Container Runtime)」的需求也從單純的「跑起來就好」，演變為對`安全性`、`隔離性`與`特殊硬體支援`的極致追求。

在早期的 Kubernetes 中，我們習慣了一種預設模式：所有 Pod 都共享宿主機的核心 (Shared Kernel)，並由同一個 Runtime (通常是 Docker 或 runc) 負責執行。這種「一體適用 (One size fits all)」的模式雖然簡單高效，但在面對多租戶隔離或高敏感資料處理時，卻顯得功能不足。

這篇文章將帶您回顧 Kubernetes CRI 的演進歷史，理解為何我們需要 **RuntimeClass**，並深入解析如何在生產環境中正確配置與管理**多租戶與因應各種業務場景**。

## 1. Kubernetes CRI 演進史：從單體到解耦

要真正理解 RuntimeClass 的配置邏輯（特別是為什麼要去改 containerd 的設定檔），我們必須先回顧 Kubernetes 如何與底層容器溝通的歷史。這是一部從「Hardcoded到「Interface」的演進過程。

### 1.1 早期架構：Docker 獨大 (Pre-v1.5)

在 Kubernetes v1.5 之前的早期版本，並沒有所謂的 CRI (Container Runtime Interface)。當時 Kubelet 的程式碼中直接包含了處理 Docker 的邏輯，Kubelet 直接呼叫 Docker API 來建立容器。

這種設計導致了兩個嚴重問題：

- **耦合過深**：每次 Docker 更新 API，Kubernetes 就必須跟著修改程式碼並重新編譯。
- **擴充困難**：當 CoreOS 推出了 rkt 容器引擎時，K8s 為了支援它，被迫在 Kubelet 裡寫了一堆 `if runtime == 'rkt'` 的邏輯，導致 Kubelet 變得極度臃腫且難以維護。

### 1.2 CRI 的誕生與 RuntimeClass 的引入

為了切斷 Kubelet 與特定 Runtime 的強耦合，Kubernetes 在 v1.5 提出了 **CRI (Container Runtime Interface)**。Kubelet 轉變為一個 gRPC Client，只負責發送標準指令（如 `CreateContainer`），任何廠商只要實作了 CRI 的 gRPC Server (稱為 CRI Shim)，就能被 Kubernetes 使用。

隨著 CRI 生態成熟，除了標準的 `runc`，市場上出現了強調安全隔離的 **`gVisor` (Google)** 和 **Kata `Containers` (基於 VM)**。為了讓使用者能在同一個叢集中混合使用這些不同的 Runtime，Kubernetes 在 v1.12 引入了 **RuntimeClass** API 物件。這讓 Kubelet 透過 CRI 傳遞請求時，能夠帶上一個 `runtime_handler` 字串，明確告知底層：「這個 Pod 請幫我用 gVisor 啟動」。

### 1.3 棄用 Dockershim

Kubernetes 在 v1.24 正式移除了 **Dockershim**（那個為了相容 Docker 而存在的轉接頭）。

現在的架構變得更加簡潔：我們直接使用 **containerd** 或 **CRI-O** 作為 CRI Runtime。

- **路徑變更**：Kubelet -> containerd (內建 CRI plugin) -> runc/gVisor。
- **維運影響**：因為少了一層 Docker Daemon，我們在除錯時不再使用 `docker ps`，而是使用 `crictl ps`   指令；Log 路徑與 Socket 位置也都回歸 CRI 標準。

## 2. 核心概念：為什麼需要 RuntimeClass？

理解了歷史背景後，我們回到 RuntimeClass 本身。它是 Kubernetes 用來選擇容器執行環境的標準 API 物件。

### 2.1 架構定位

- **層級**：RuntimeClass 屬於 **Cluster-Level** 資源，不分 Namespace。
- **作用範圍**：設定於 PodSpec 的最頂層 (`spec.runtimeClassName`)。

其核心架構考量在於：**一個 Pod 內的所有 Container (包含 Sidecar) 必須共享同一個 Network、IPC 和 PID Namespace (Sandbox)**。因此，我們無法讓同一個 Pod裡的 Container A 跑在 gVisor，而 Container B 跑在 runc，它們必須共用同一個隔離邊界。

### 2.2 依據業務場景選擇 Runtime

在現代叢集中，我們通常會依據**業務需求**來選擇不同的 Runtime：

1. **一般微服務 (Native/runc)**：
標準容器。行程直接跑在 Host Kernel 上，利用 cgroups/namespaces 隔離。
    - *優點*：效能最好，啟動速度快 (毫秒級)。
    - *適用場景*：90% 的一般應用、內部微服務、高吞吐量 API。
2. **多租戶與敏感數據 (Sandboxed/gVisor)**：
Google 開發的 gVisor 在 User Space 模擬 Kernel Syscall，攔截並過濾系統呼叫。
    - *優點*：隔離性強，攻擊面小，防止容器逃逸。
    - *適用場景*：多租戶環境 (SaaS)、執行未受信任程式碼 (如 Serverless Function, User Upload Scripts)。
3. **強隔離與硬體虛擬化 (MicroVM/Kata Containers)**：
每個 Pod 跑在一個極輕量的虛擬機 (QEMU/Firecracker) 裡，擁有獨立的 Kernel。
    - *優點*：隔離性最強 (硬體級虛擬化)，完全阻隔租戶間的影響。
    - *適用場景*：金融級安全需求、完全隔離的租戶環境、需要特定 Kernel 版本的應用。
4. **AI 與高效能運算 (Hardware Accelerated/NVIDIA)**：
專為 GPU 存取優化的 Runtime (如 `nvidia-container-runtime`)。
    - *優點*：優化 GPU Pass-through 與 CUDA 驅動的掛載流程，確保容器能直接且高效地存取底層硬體加速器。
    - *適用場景*：AI 模型訓練/推論、HPC 科學運算。

## 3. 實戰配置流程 (Configuration Workflow)

接下來進到實作的部分，要讓 RuntimeClass 運作，僅僅在 Pod YAML 寫一行 `spec.runtimeClassName` 是不夠的。這涉及到 CRI (Containerd)、K8s API 與 Pod 三層的配合。

### 步驟一：底層 CRI 配置 (Node 層級)

這是最容易被忽略的一步。您必須先在 Node 的 `containerd` 設定檔中註冊 Runtime Handler。

> 強烈建議不要「手寫」整個檔案，容易漏掉關鍵設定（如 SystemdCgroup = true），進而容易導致 Kubelet 無法啟動。
> 

**標準做法**：
先執行指令生成完整的預設設定檔，再針對 `runtimes` 區塊進行修改。

```shell
containerd config default > /etc/containerd/config.toml

vim /etc/containerd/config.toml
```

**配置範例 (TOML 片段)**：

```text
[plugins."io.containerd.grpc.v1.cri".containerd.runtimes]
  # 定義一個名為 "runsc" (gVisor) 的 handler
  # 這裡的 key "runsc" 將對應到 RuntimeClass 物件中的 handler 欄位
  [plugins."io.containerd.grpc.v1.cri".containerd.runtimes.runsc]
    runtime_type = "io.containerd.runsc.v1"

```

設定完成後，重啟 containerd 服務。

```json
sudo systemctl restart containerd
```

### 步驟二：定義 RuntimeClass 物件 (Cluster 層級)

告訴 K8s 有這個 Runtime 存在，並映射到 CRI 的 Handler。

**基本配置 (gVisor 範例)**：

```shell
# 幫已完成步驟一的 Node 打上標籤
kubectl label node worker-node-01 sandbox.gvisor.io=true

# check 
kubectl get nodes --show-labels
```

```yaml
apiVersion: node.k8s.io/v1
kind: RuntimeClass
metadata:
  name: gvisor  # 這是開發者在 Pod YAML 裡引用的名稱
handler: runsc  # 對應到底層 CRI config 裡的 handler 名稱

# 關鍵設定：自動排程
scheduling:
  nodeSelector:
    sandbox.gvisor.io: "true"  
    # 強制 Pod 只能排程到有標籤 (sandbox.gvisor.io: "true") 的節點

# Pod Overhead (資源開銷設定)
# 對於 Kata Containers 或 gVisor 這類 Runtime，啟動每個 Pod 都會額外消耗記憶體（例如 QEMU VM 本身可能需要 100MB+）。如果 K8s Scheduler 不知道這筆開銷，可能會將過多的 Pod 排程到節點上，導致節點 OOM。
# 這會讓 K8s Scheduler 在計算資源時，自動扣除這部分的量，確保節點穩定。
overhead:
  podFixed:
    memory: "120Mi"
    cpu: "250m"

```

### 步驟三：Pod 使用 (Application 層級)

開發者只需在 Pod spec 指定 `runtimeClassName`，不必處理底層 CRI 的細節：

```yaml
apiVersion: v1
kind: Pod
metadata:
    name: sensitive-app
spec:
    runtimeClassName: gvisor
    containers:
    - name: app
        image: my-app:latest
        resources:
            requests:
                cpu: "250m"
                memory: "128Mi"
            limits:
                cpu: "500m"
                memory: "256Mi"
```
---

## 4. 常見 QA

1. **Pod 處於 Failed 狀態**：
     - 原因：Pod 指定了 `runtimeClassName`，但節點上的 CRI 未註冊對應 handler。
     - 排查：檢查 `/etc/containerd/config.toml` 與 `kubectl get runtimeclass`，確認名稱一致。
2. **Pod 卡在 Pending**：
     - 原因：RuntimeClass 設定了 `scheduling.nodeSelector`，叢集中沒有任何符合標籤的節點。
     - 排查：檢查節點標籤，並使用 `kubectl label nodes` 為安裝了該 Runtime 的節點打標籤。


## 5. 總結

RuntimeClass 是 Kubernetes 應對複雜運算需求與多租戶場景的重要拼圖。透過理解 CRI 的演進與 RuntimeClass 的配置邏輯，維運團隊可以提供一個既安全又靈活的基礎設施平台，讓一般應用跑在高效的 runc 上，同時讓敏感應用或 AI 工作負載無縫地運行在 gVisor、Kata 或 NVIDIA 的專屬環境中。

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>