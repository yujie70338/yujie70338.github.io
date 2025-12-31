---
title: "〔CKS 筆記整理〕揭秘 Kubernetes Pod ：Pause 容器、共享網路與資源管理"
subtitle: ""
description: "本文旨在探討 Kubernetes Pod 的設計核心。"
date: 2025-12-30
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "Pod", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕揭秘 Kubernetes Pod ：Pause 容器、共享網路與資源管理

## 摘要

本文旨在探討 Kubernetes Pod 的設計核心。文章將深入淺出地解說共享網路命名空間的機制、Pause Container 的功能，以及 Sidecar 模式在啟動順序與資源管理上的挑戰，整理對 Pod 生命週期管理的觀念。

對於初學者而言，Pod 常被簡單定義為「一個或多個容器的集合」，但這個定義並未完全解釋其設計目的。Pod 的核心概念，其實是為了在雲端環境中模擬一台「邏輯主機（Logical Host）」。這決定了應用程式之間的通訊模式，以及多個容器在同一環境下運作時，因緊密耦合（Tightly Coupled）所產生的影響。

## **共享網路：優勢與限制**

當多個容器運行在同一個 Pod 時，它們的關係類似於在同一台虛擬機（VM）上運行的多個處理程序（Process）。這種關係建立在「共享網路命名空間（Shared Network Namespace）」之上，意即 Pod 內的所有容器都共用同一個 Cluster IP 位址與 Port 空間。

這樣的架構設計帶來了以下優勢：

- **低延遲通訊**：容器間可透過 `localhost` 直接通訊，繞過 NAT 與路由設定。
- **簡化發現機制**：無需依賴服務發現（Service Discovery）或外部 DNS。
- **信任域內**：視為內部網路，通常無需複雜的認證機制即可互連。

然而，這也帶來了實務上的限制。開發者必須像在單機環境一樣，妥善規劃 Port 的使用。若兩個容器嘗試監聽同一個 Port（例如都佔用 80 Port），將導致 `Address already in use` 錯誤，並使容器啟動失敗。此外，在設定監聽介面（Bind Interface）時，需根據用途嚴格區分（例如）：

| 用途               | 建議綁定介面            | 典型範例             | 說明                                                                     |
| ------------------ | ----------------------- | -------------------- | ------------------------------------------------------------------------ |
| **僅供內部使用**   | `127.0.0.1` (Localhost) | Cloud SQL Auth Proxy | 僅允許同 Pod 內的主程式連線，避免將管理介面暴露給外部，安全性較高。      |
| **需接收外部流量** | `0.0.0.0` (Any)         | Envoy / Nginx Proxy  | 必須監聽所有介面，才能接收來自 Pod 外部（如 Service 或 Ingress）的流量。 |

## 共享儲存：**檔案系統的運用**

除了網路，**檔案系統的共享**是「邏輯主機」概念的另一大支柱。在傳統伺服器上，不同的處理程序可以讀寫同一個目錄下的檔案；在 Pod 中，我們則透過 **`Volume`** 來實現這項功能。

最常見的例子是 `emptyDir`。當多個容器掛載同一個 `emptyDir` Volume 時，它們就像是存取本機上的同一個暫存資料夾。

- **運作模式**：容器 A 將日誌寫入 `/var/log/app.log`（掛載點），容器 B（Sidecar）可以直接讀取該路徑下的檔案並轉送至 Log Server。
- **實務意義**：如果沒有共享儲存，Sidecar 就難以取得主程式產生的靜態檔案或日誌。這進一步強化了 Pod 的設計哲學：容器之間不只共享 IP，也能共享儲存空間。

## 基礎設施的錨點：Pause Container

為了維持共享環境的穩定，Kubernetes 引入了一個輕量級元件：Pause Container（或稱 Infra Container）。

當 Kubelet 啟動 Pod 時，最先啟動的並非應用程式，而是這個沙箱容器。Pause Container 的主要職責是建立並持有 Linux Namespaces（包含 Network、IPC 與 UTS 等）。隨後啟動的業務容器與輔助容器，則是透過加入這個已建立的命名空間來運作。

這是一種將「網路環境」與「應用程式生命週期」解耦的設計。即使主程式因錯誤而重啟，只要 Pause Container 仍在運行，Pod 的 IP 位址就不會改變，既有的路由規則也能維持，大幅降低了應用程式復原時的網路波動。

如果你有權限登入 Kubernetes 的 Worker Node，可以試試看使用以下指令找到這個關鍵元件：

```
sudo crictl ps | grep pause
```

## Sidecar 模式與啟動順序

基於 pod 的特性，Sidecar Pattern 常被用來處理輔助性任務，例如將 Service Mesh 的代理伺服器或日誌收集器獨立為 Sidecar 容器，讓主程式的容器專注於核心業務。然而，容器的啟動順序一直是實務上的痛點，特別是在 Kubernetes v1.29 版本前後有顯著差異：

| 版本           | 啟動行為                         | 潛在風險 (Race Condition)                                            | 最佳實務                                                                 |
| -------------- | -------------------------------- | -------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **v1.28 以前** | **無順序保證**<br>容器平行啟動   | 主程式比 Sidecar 先啟動，導致連線資料庫失敗，引發 CrashLoopBackOff。 | 在主程式啟動腳本中加入 `sleep` 或迴圈偵測邏輯，等待 Sidecar 就緒。       |
| **v1.29 以後** | **原生支援 Sidecar**<br>依序啟動 | 問題已解決。平台確保 Sidecar 完全就緒後，才啟動主程式。              | 使用 `initContainers` 並設定 `restartPolicy: Always`，定義原生 Sidecar。 |

## 資源共享與管理

除了網路與啟動順序，資源管理也是不可忽視的一環。Pod 的資源需求是內部所有容器的總和。若未妥善設定資源限制（Resource Limits），單一 Sidecar 容器（如日誌代理程式）若發生記憶體洩漏，可能會耗盡節點資源，或觸發 Pod 層級的驅逐機制，導致主程式一同被終止。因此，為每個容器設定獨立的資源配額是維持穩定性的關鍵。

此外，進階的使用者可以透過設定 `shareProcessNamespace: true` 來打破容器間的 PID 隔離。這允許在 Sidecar 中使用 `ps` 指令觀察主程式的狀態。

可以嘗試在測試環境開啟了 shareProcessNamespace: true，你可以進入 Sidecar 容器驗證是否能看到其他容器的 Process：

```
# 在 Sidecar 中也能看到主程式的 Process
kubectl exec -it <pod-name> -c sidecar -- ps aux
```

然而，啟用此功能需特別留意**安全風險**，請僅在 labs 或 測試環境中開啟。由於 Linux 的環境變數可透過 `/proc/{PID}/environ` 讀取，若應用程式將機敏資訊（如密碼或金鑰）儲存於環境變數中，共享 PID Namespace 將導致這些資訊對 Pod 內的所有容器可見。除非是為了短期除錯，否則不建議在生產環境中長期開啟此選項，以避免潛在的資訊外洩或隔離性破壞。

總結來說，理解 Pod 作為邏輯主機的機制，從共享網路的低延遲優勢，到 Pause Container 提供的穩定基礎，以及 Sidecar 模式的運作細節，有助於更準確地利用 pod 的特性，在享受 Kubernetes 便利性的同時，也確保服務運行的穩定性。

# Extended Reference ＆ FYI

- [shareProcessNamespace | Share Process Namespace between Containers in a Pod](https://kubernetes.io/docs/tasks/configure-pod-container/share-process-namespace/)
- [Pod Lifecycle](https://kubernetes.io/docs/concepts/workloads/pods/pod-lifecycle/)
- https://jimmysong.io/zh/book/kubernetes-handbook/pod/pause-container/

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
