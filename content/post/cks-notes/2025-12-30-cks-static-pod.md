---
title: "〔CKS 筆記整理〕揭秘 Kubernetes Static Pods：Kubelet 如何啟動 Control plane 核心元件"
subtitle: ""
description: "本文將深入探討 Kubernetes 架構中一個特殊且關鍵的機制：Static Pods。"
date: 2025-12-30
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "StaticPods", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕揭秘 Kubernetes Static Pods：Kubelet 如何啟動 Control plane 核心元件

## **摘要**

本文將深入探討 Kubernetes 架構中一個特殊且關鍵的機制：Static Pods。這是理解叢集如何自我啟動（Bootstrapping）的核心概念，也是面對控制平面（Control Plane）故障時的重要維運知識。文章將剖析 Kubelet 如何繞過調度器直接管理容器、鏡像 Pod（Mirror Pod）的運作原理，以及當 API Server 失效時，如何透過底層工具進行除錯與修復。

介紹 Kubernetes 架構時，通常會強調一個原則：API Server 是叢集的唯一入口，所有請求都必須經過驗證、准入控制，最後由調度器（Scheduler）指派節點執行。這個說法在絕大多數情況下是正確的，但它無法解釋一個根本的邏輯矛盾：

> 如果 Kubernetes 的控制平面元件（如 API Server 本身）也是以 Pod 的形式運行，那麼在叢集尚未啟動、API Server 還不存在的時候，是誰負責「調度」這些核心組件？

這就是分散式系統中經典的「雞生蛋」問題，而 Kubernetes 給出的解答便是 **Static Pods**。

在實際維運經驗中，許多人對 Static Pod 的理解僅止於「它存在於節點的某個目錄裡」。然而，當發生叢集等級的異常，例如 etcd 毀損或是 API Server 無法啟動時，理解 Static Pod 的運作機制往往是快速恢復服務的關鍵。我們必須暫時拋開 kubectl 的便利，回到 Kubelet 的視角來看待這個機制。

### 繞過控制平面的特殊機制

Static Pod 是 Kubelet Daemon 的獨有功能。與一般 Pod 不同，Static Pod 不需要經過 API Server，也不受 Deployment 或 ReplicaSet 的控制。它的生命週期直接綁定在特定節點的 Kubelet 上。

其運作原理可以簡化為一種自動化機制，Kubelet 會定期執行以下流程：

1. **掃描 (Scan)**：
   Kubelet 定期掃描本地的特定目錄（預設為 `/etc/kubernetes/manifests`），或是監聽啟動參數中指定的 HTTP URL。
2. **偵測 (Detect)**：
   透過檔案監控機制（如 inotify），一旦偵測到目錄下出現符合 Kubernetes 規範的 YAML 或 JSON 檔案。
3. **執行 (Execute)**：
   繞過控制平面，直接呼叫底層的容器執行環境（CRI，如 containerd 或 CRI-O）來啟動容器。
4. **同步 (Sync)**：
   - **修改**：若檔案內容變更，Kubelet 會重啟 Pod 以套用變更。
   - **刪除**：若檔案被移除，Pod 會隨即被終止。

為了更清楚理解兩者的差異，我們可以參考下圖比較一般 Pod 與 Static Pod 的建立路徑：

```
+-------------------------------------------------------+
|                   一般 Pod (標準路徑)                  |
+-------------------------------------------------------+
User (kubectl)
      |
      v
 API Server  <----->  Scheduler (指派節點)
      |
      v
   Kubelet   (監聽 API Server)
      |
      v
 CRI (Container Runtime)

+-------------------------------------------------------+
|                Static Pod (Kubelet 捷徑)               |
+-------------------------------------------------------+
YAML File (/etc/kubernetes/manifests)
      |
      v
   Kubelet   (直接掃描檔案，繞過控制平面)
      |
      v
 CRI (Container Runtime)

```

這種機制不依賴網路與叢集狀態，因此成為啟動控制平面元件的最佳方案。在使用 kubeadm 部署叢集時，Kubelet 是第一個啟動的元件，隨後掃描清單並拉起 `kube-apiserver`、`kube-controller-manager` 和 `etcd`。等到這些 Static Pod 準備就緒，整個 Kubernetes 叢集才算正式運作。

### 鏡像 Pod （Mirror Pod）的角色與限制

Static Pod 最常造成的困惑來自於它的「分身」。雖然 Static Pod 不受 API Server 管轄，但為了讓管理員能透過 `kubectl get pods` 觀察叢集全貌，Kubelet 會嘗試向 API Server 註冊一個對應的 **Mirror Pod（鏡像 Pod）**。

- **命名規則**：通常為 `{Pod名稱}-{Node名稱}`，例如 `etcd-master-01`。
- **本質**：Mirror Pod 僅是 API Server 中的一個唯讀記錄，用於展示狀態，並非實際運行的容器控制者。

**常見的操作誤區：**

| 操作指令             | 預期行為 | 實際結果                        | 原因                                                                    |
| -------------------- | -------- | ------------------------------- | ----------------------------------------------------------------------- |
| `kubectl delete pod` | 刪除 Pod | Pod 顯示 Terminating 後瞬間重建 | 本地 YAML 檔案仍存在，Kubelet 發現 Mirror Pod 消失會立即重新註冊。      |
| `kubectl edit pod`   | 修改設定 | 修改無效                        | 真正的配置來源（Source of Truth）是節點上的 YAML 檔案，而非 etcd 紀錄。 |

### 當標準工具失效時的應對策略

由於 Static Pod 的特性，其管理方式與一般應用程式截然不同。當需要重啟故障的控制平面組件，或是因配置錯誤導致 API Server 無法啟動時，標準的 kubectl 指令將無法使用。此時需回歸 Linux 系統層面進行操作。

### 1. 刪除或停止 Pod

唯一有效的方法是將對應的 YAML 檔案從 manifest 目錄中**移走**或**刪除**。

### 2. 重啟 Pod

Kubernetes 沒有原生的重啟指令，對於 Static Pod，通常採用 **「移出再移入」（Move-out-Move-in）** 的策略：

- 先將 YAML 檔搬移至臨時目錄。
- 等待 Kubelet 清理掉舊容器。
- 再將檔案搬回原目錄，觸發 Kubelet 重新啟動服務。

### 3. 底層除錯

當 API Server 無法回應時，無法使用 `kubectl logs` 查看日誌。此時需透過 SSH 登入節點，使用容器層級工具進行診斷：

- **查看容器狀態**：使用 `crictl ps` 找出停止或異常的容器 ID。
- **查看容器日誌**：使用 `crictl logs <container-id>` 直接讀取崩潰訊息。
- **檢查 Kubelet 日誌**：若是 YAML 格式錯誤或權限問題，錯誤訊息會出現在 Kubelet 服務日誌中（`journalctl -u kubelet`）。

### 架構決策：DaemonSet 與 Static Pod 的差異

在設計系統架構時，容易混淆 Static Pod 與 DaemonSet 的用途，因為兩者都具備「在特定節點上運行」的特質。下表整理了兩者的核心差異：

| 特性         | Static Pod                     | DaemonSet                                    |
| ------------ | ------------------------------ | -------------------------------------------- |
| **管理者**   | Kubelet (本地節點)             | Controller Manager (控制平面)                |
| **依賴性**   | 不依賴 API Server              | 必須依賴 API Server 與 Scheduler             |
| **更新方式** | 修改節點上的檔案               | `kubectl apply`，支援 Rolling Update         |
| **適用場景** | 叢集核心組件 (etcd, apiserver) | 叢集附加組件 (CNI, Log Agent, Monitor Agent) |
| **儲存限制** | 僅能使用 hostPath 等本地儲存   | 支援 PVC 等所有儲存類型                      |

除非是為了部署像 `kube-proxy` 這類極度底層、或需要在 control-plane 啟動前就緒的組件，否則**不建議**在一般應用場景中使用 Static Pod。因為它缺乏集中式管理，無法進行滾動更新，也無法使用依賴 API Server 的進階功能（如 PersistentVolumeClaim）。

總結來說，Static Pod 是 Kubernetes 賦予 Kubelet 的特殊模式，是 control-plane 的 pod 自我啟動的基礎。

# Extended Reference ＆ FYI

- [**Create static Pods**](https://kubernetes.io/docs/tasks/configure-pod-container/static-pod/)

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
