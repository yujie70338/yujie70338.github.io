---
title: "〔CKS 筆記整理〕Kubernetes SecurityContext：從原理到實戰，全面強化容器防護"
subtitle: ""
description: "本文將深入探討 Kubernetes SecurityContext 的核心概念與實務配置，協助你建立穩固的基礎設施防護。"
date: 2025-12-17
author: "Yujie Zheng"
image: ""
tags: ["K8S","Kubernetes","SecurityContext","CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes SecurityContext：從原理到實戰，全面強化容器防護

在 Kubernetes 的世界裡，我們往往專注於服務的高可用性與自動擴展，卻容易忽略最基礎的執行單元——Container 本身的權限邊界。

`SecurityContext` 是 Kubernetes 中落實「最小權限原則」的關鍵機制。如果設定不當，可能會使容器的隔離層級不足，增加系統風險。本文將深入探討 Kubernetes SecurityContext 的核心概念與實務配置，協助你建立穩固的基礎設施防護。

## 把 Node 當作共享公寓：為什麼你需要 SecurityContext？

要理解 SecurityContext，我們可以把 Kubernetes Node 想像成一棟「共享公寓」，而 Pod 則是剛搬進來的「房客」。

在**預設情況 (Default)** 下，這位房客擁有極高的權限 (Root)，他可以在牆上隨意鑽孔 (Write Files)，甚至試圖破壞隔間牆去窺探隔壁房間 (Container Escape)。

`SecurityContext` 的存在，就像是一份嚴格的「租屋公約」。它用來告訴底層的 Container Runtime (如 containerd) 與 Linux Kernel，這個 Process 必須在特定的限制條件下啟動：

1. **身分限制**：限制使用者身分 (Non-Root)。
2. **結構保護**：限制檔案系統的寫入 (ReadOnly Filesystem)。
3. **權限剝奪**：移除不必要的系統權限 (Drop Capabilities)。

這是 Container 安全的基石。如果這一層防線失守，應用程式一旦被入侵，攻擊者便更容易取得主機的控制權。

## 常見誤區：Privileged 與 RBAC 是兩回事

在學習 Kubernetes 時，初學者常混淆「系統權限」與「API 權限」。我們必須釐清這兩者的差異：

| 比較項目 | Linux 系統層級 (Privileged) | K8s API 層級 (RBAC) |
| ------ | --- | --- |
| **關鍵設定** | `privileged: true` | `ServiceAccount` + `RoleBinding` |
| **影響範圍** | **Container <-> Kernel** | **Pod <-> API Server** |
| **技術細節** | 關閉 Cgroups/Namespace 保護，擁有與 Host Root 近似的權限。 | 決定 Pod 是否能讀取 Secret、列出 Pod 或刪除資源。 |
| **誤解** | 開啟後自動獲得 K8s Admin 權限 (錯)。 | 給了 Admin 權限就能直接操作 Host (錯)。 |

### 間接攻擊鏈

雖然 `privileged` 不直接給予 API 權限，但它可能成為攻擊者的跳板。

典型的攻擊路徑如下：

```text
[攻擊者入侵 Pod]
      ⬇
(1) 特權啟動：利用 privileged 權限掛載宿主機根目錄 (mount / /host)
      ⬇
(2) 竊取憑證：讀取 Kubelet 設定檔 (/host/etc/kubernetes/kubelet.conf)
      ⬇
(3) 偽造身分：使用竊取的 Kubelet 憑證欺騙 API Server
      ⬇
(4) 權限外洩：讀取該節點上所有 Pod 的 Secret (包含其他 Namespace)

```

## 進程隔離：防禦漏洞的三個關鍵

限制容器內 Process 的行為，是減緩應用程式漏洞影響範圍的有效手段。

### 1. 禁止提權

**設定值**：`allowPrivilegeEscalation: false`

這是效益極高的設定。當設為 `false` 時，Runtime 會設定 Kernel 的 `no_new_privs` 標誌位。這意味著即使攻擊者在容器內嘗試利用帶有 SUID 的程式（如 `sudo` 或 `su`）進行提權，也會被系統阻擋。這對於防禦特定的 Kernel 提權漏洞相當有效。

### 2. 精細化權限控制 (Capabilities)

Linux 的 Root 權限其實是由多個 Capabilities 組成的集合。Docker 預設開啟了許多 Web App 不需要的部分權限。

建議的策略是採用`「白名單」模式`：先在 YAML 中宣告 `drop: ["ALL"]`，再根據業務需求逐一加回。例如，只有當服務需要綁定 Port 80 時，才加入 `NET_BIND_SERVICE`。

### 3. 強制使用非 Root 身分

**設定值**：`runAsNonRoot: true`

這是一個保護機制，確保服務不會意外地以 Root 身分執行。Kubelet 在啟動前會檢查 Image 的使用者設定，如果是 UID 0 就會拒絕啟動，避免配置疏失。

## 檔案系統層級的防禦

基礎設施視為不可變 (Immutable)，在容器內部的具體實踐就是 **唯讀(read-only)根目錄 (readOnlyRootFilesystem)**。

將根目錄掛載為 Read-Only 有兩個主要價值：

- **防植入**：攻擊者無法下載惡意腳本或工具到系統目錄。
- **防篡改**：無法修改 `/etc/passwd`、`/bin/sh` 等系統關鍵檔案。

**實務解法**：
若應用程式需要寫入 Log 或 Cache，不應開放原本的檔案系統權限，而是應該掛載 `emptyDir` 到 `/tmp` 或 `/var/log` 等特定路徑。這樣既滿足了寫入需求，又維持了系統層級的唯讀狀態。

## 經常被遺忘的防護：Seccomp

Seccomp (Secure Computing Mode) 是現代 K8s 防禦的重要環節。Linux 核心提供了 300 多個 System Calls，但絕大多數的微服務只需要用到其中的幾十個。

自 Kubernetes v1.19 起，建議至少啟用 `RuntimeDefault` 的 Seccomp Profile。這會阻擋像 `reboot`、`swapon` 這類對應用程式無用但具風險的呼叫，為系統增加一層防護。

*(註：部分 Kubernetes 發行版或雲端平台可能已有預設策略，建議先檢查現狀。)*

## YAML 配置細節：Pod 與 Container 層級

在撰寫 YAML 時，需注意設定生效的層級：

| 設定層級 | 關鍵欄位 | 特性與注意事項 |
| --- | --- | --- |
| **Pod 層級** | `fsGroup`, `sysctls` | 適用於 Pod 內所有容器共享的環境設定。 |
| **Container 層級** | `capabilities`, `privileged` | 針對個別 Process 的隔離設定。 |

### 特別提醒：fsGroup 的效能影響

當設定 `fsGroup` 來處理 Volume 權限時，K8s 預設行為是在 Pod 啟動時，**遞迴修改 (Recursively chown)** Volume 內所有檔案的權限。

若 Volume 內包含大量小檔案，這個動作可能會消耗大量 I/O 並導致 Pod 啟動時間過長。
**解法**：在 v1.20+ 版本中使用 `fsGroupChangePolicy: "OnRootMismatch"`，讓 K8s 只有在根目錄權限不符時才進行修改，提升啟動效率。

## 最佳實務：標準配置範例

以下是一個符合 **Pod Security Standards (Restricted)** 等級的參考配置：

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  # [Pod Level] 共享環境設定
  securityContext:
    runAsNonRoot: true
    # 為什麼是 10001？這只是慣用的非 Root ID，重點在於它不是 0
    runAsUser: 10001
    runAsGroup: 10001
    fsGroup: 10001
    fsGroupChangePolicy: "OnRootMismatch" # 避免大量檔案造成啟動延遲
    seccompProfile:
      type: RuntimeDefault # 關鍵的 Syscall 過濾

  containers:
  - name: app
    image: my-app:1.0.0
    # [Container Level] 進程隔離設定
    securityContext:
      allowPrivilegeEscalation: false # 禁止 SUID 提權
      readOnlyRootFilesystem: true    # 落實不可變更
      capabilities:
        drop: ["ALL"]                 # 權限最小化
        add: ["NET_BIND_SERVICE"]     # 僅開放必要權限
    volumeMounts:
    - name: tmp
      mountPath: /tmp
  volumes:
  - name: tmp
    emptyDir: {}

```

## 實務上的維運挑戰

嚴格的安全設定雖然提升了防護力，但也可能改變日常的維運習慣，特別是在除錯與遷移階段。

### 1. 除錯困難 (Debugging)

當移除了 Shell、禁用了 Root 且檔案系統唯讀，傳統的 `kubectl exec` 可能無法正常運作。
**解法**：建議使用 **Ephemeral Containers**。

```shell
# 使用 kubectl debug 掛載一個帶有工具箱的容器到目標 Pod
kubectl debug -it secure-app --image=busybox --target=app

```

這允許管理員在不破壞原有安全限制的情況下，臨時掛載工具進行排查。

### 2. 漸進式遷移策略

直接對現有服務套用嚴格規範可能會導致服務中斷。建議採取漸進式步驟：

1. **盤點**：先掃描現狀，了解目前服務的權限配置。
2. **警告模式**：利用 Pod Security Admission (PSA) 的 `warn` 模式，先觀察日誌中哪些 Pod 違反規則，而不直接阻擋。
3. **分批執行**：確認無誤後，再將模式改為 `enforce`。

## 結語

SecurityContext 的配置細節雖然繁瑣，但它是保護 Kubernetes 集群的重要投資。透過合理的權限控制與隔離機制，我們能為應用程式建立更穩固的運行環境。在追求功能交付的同時，逐步完善這些基礎安全設定，將能大幅降低潛在的系統風險。

## 參考連結

- [**Restrict a Container's Syscalls with seccomp**](https://kubernetes.io/docs/tutorials/security/seccomp/)
- [**Kubernetes 1.20: Granular Control of Volume Permission Changes**](https://kubernetes.io/blog/2020/12/14/kubernetes-release-1.20-fsgroupchangepolicy-fsgrouppolicy/)
- [**为Pods配置卷权限和所有权更改策略**](https://weiliang-ms.github.io/wl-awesome/2.%E5%AE%B9%E5%99%A8/k8s/security/%E5%AE%89%E5%85%A8%E4%B8%8A%E4%B8%8B%E6%96%87/02%E4%B8%BAPods%E9%85%8D%E7%BD%AE%E5%8D%B7%E6%9D%83%E9%99%90%E5%92%8C%E6%89%80%E6%9C%89%E6%9D%83%E6%9B%B4%E6%94%B9%E7%AD%96%E7%95%A5.html)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>