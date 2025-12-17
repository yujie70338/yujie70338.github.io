---
title: "〔CKS 筆記整理〕Kubernetes Pod Security 演進與實戰指南：從 PSP 到 PSA"
subtitle: ""
description: "本文將帶您深入解析 Kubernetes Pod 安全性演進。內容涵蓋從 PSP 到 PSA 的轉變歷程、PSA 架構原理、Pod Security Standards (PSS) 安全標準解析，以及生產環境的遷移與配置實戰建議。"
date: 2025-12-09
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "Pod Security", "PSP", "PSA", "PSS", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes Pod Security 演進與實戰指南：從 PSP 到 PSA

## 摘要：

本文將帶您深入解析 Kubernetes Pod 安全性演進。內容涵蓋從 PSP 到 PSA 的轉變歷程、PSA 架構原理、Pod Security Standards (PSS) 安全標準解析，以及生產環境的遷移與配置實戰建議。

## 1. 歷史演進：從 PSP 到 PSA

理解 Kubernetes 安全機制的轉變，是維護舊叢集或規劃升級的基礎。

### 1.1 PodSecurityPolicy (PSP) - 已棄用的機制

**PodSecurityPolicy (PSP)** 曾是 Kubernetes 控制 Pod 權限（如 `privileged`、`hostPath`）的核心機制。然而，因設計上的數項缺陷，最終導致其被淘汰：

- **權限模型複雜**：PSP 的授權檢查機制反直覺，難以釐清 ServiceAccount 或 User 所需權限，導致配置易錯且難維護。
- **Fail-closed 風險**：一旦啟用 PSP Admission Controller 卻未配置對應策略，系統將預設拒絕所有 Pod 建立請求，極易造成服務中斷。
- **缺乏靈活粒度**：難以針對不同 `Namespace` 進行隔離與差異化配置。

**現狀**：PSP 已於 v1.21 棄用，並在 **v1.25 正式移除**。若叢集版本達 v1.25 以上，`PodSecurityPolicy` 物件即完全失效。

### 1.2 Pod Security Admission (PSA) - 現代標準

**Pod Security Admission (PSA)** 是 Kubernetes 內建的 Admission Controller，旨在成為 PSP 的現代化替代方案。

PSA 設計理念為「簡單至上」。它無需安裝 CRD 或綁定複雜 RBAC，僅需在 **Namespace** 上設定 **Label** 即可運作，負責強制執行 Pod Security Standards (PSS) 定義的安全等級。

**局限性**：PSA 僅具備驗證 (Validate) 能力，**無法修改 (Mutate)** Pod 配置；且控制粒度僅限於 **Namespace** 層級。若需對單一 Pod 進行細緻控制（如基於 Label），或需自動注入 SecurityContext，則須搭配 **Kyverno** 或 **OPA Gatekeeper** 等第三方工具。

## 2. 安全標準：Pod Security Standards (PSS)

PSS 是定義安全規範的「規則書」，PSA 則是執行規則的「守門員」。PSS 定義了三種安全等級，協助使用者快速分類工作負載：

### 等級定義與適用場景

| 等級           | 定義                                             | 適用場景                                               | 規則範例                                                                           |
| -------------- | ------------------------------------------------ | ------------------------------------------------------ | ---------------------------------------------------------------------------------- |
| **Privileged** | 完全不受限 (Unrestricted)。                      | 系統基礎設施組件 (如 CNI/CSI 驅動)，需存取 Host 資源。 | 允許 `privileged: true`、`hostNetwork: true`。                                     |
| **Baseline**   | 限制已知風險，允許常見配置。**建議作為預設值**。 | 絕大多數應用程式 (Web 服務、API、微服務)。             | 禁止特權容器、Host Network/PID/IPC、HostPath Volume。                              |
| **Restricted** | 最嚴格的安全強化 (Hardening)。                   | 高敏感應用、處理 PII 或需法規遵循場景。                | 強制 `runAsNonRoot: true`、`readOnlyRootFilesystem: true`、Drop ALL Capabilities。 |

### 實務部署策略

企業實施 PSS 時，建議採取分層策略：全域預設採用 **Baseline**，以阻擋容器逃逸風險並維持開發彈性；針對高敏感 **Namespace** 則強制啟用 **Restricted**。

實施 Restricted 的主要成本在於**開發流程調整**。例如：由於強制要求 `runAsNonRoot: true`，開發者須修改 Dockerfile 指定 UID，並確保應用程式在無 Root 權限下能正常讀寫。

**Restricted 合規 Dockerfile 範例：**

```dockerfile
# 選擇基礎映像檔
FROM alpine:3.19

# 1. 建立非 Root 使用者與群組 (如 UID 1000)
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

# 2. 設定工作目錄並賦權
WORKDIR /app
COPY . .
RUN chown -R appuser:appgroup /app

# 3. 切換至非 Root 使用者 (建議使用 UID)
USER 1000

# 4. 啟動應用程式
CMD ["./my-app"]

```

## 3. PSA 實戰配置與驗證

PSA 配置完全依賴 **Namespace Label**，操作上直觀簡單。

### 3.1 啟用方式

使用 `kubectl label` 即可啟用：

```shell
# 語法：pod-security.kubernetes.io/<mode>=<standard>
# 範例：將 my-app Namespace 設為強制執行 restricted 標準
kubectl label ns my-app pod-security.kubernetes.io/enforce=restricted

```

### 3.2 三種控制模式 (Modes)

PSA 提供三種模式，可同時並存於同一 Namespace，利於漸進式遷移：

- **Enforce**：直接拒絕 (Reject) 違規 Pod 的建立請求。
- **Audit**：允許建立，但將違規事件寫入 Audit Log。
- **Warn**：允許建立，但在 `kubectl` 操作時輸出警告訊息。

**遷移實戰 (Baseline -> Restricted)**

若計劃將 Namespace 升級至 Restricted，建議可以採用混合模式試運行，依據 log 逐步調整 Pod 。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
  labels:
    # 維持 Baseline 執法，確保底線安全
    pod-security.kubernetes.io/enforce: baseline

    # 對不符合 Restricted 的行為發出警告與審計日誌
    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/audit: restricted
```

### 3.3 負面測試 (Negative Testing)

驗證 PSA 是否生效的最佳方式是進行負面測試：在標記 `enforce: restricted` 的 Namespace 中部署 `privileged: true` 的 Pod。

-> 預期應收到包含 `violates PodSecurity` 的 `403 Forbidden` 錯誤。

## 4. 關鍵機制與實務注意事項

### 4.1 現存 Pod 不受影響

PSA 僅攔截**進入 API Server 的新請求** (Create/Update)。對現有運作中的違規 Pod，PSA 不會主動終止，直到該 Pod 被刪除重建或觸發更新時才會受檢。

### 4.2 Service Mesh (Istio) 兼容性

Restricted 模式會阻礙 Service Mesh (如 Istio) 的 Sidecar 注入，因為傳統注入機制常需 `NET_ADMIN` 權限修改 `iptables` 或以 Root 啟動，違反 Drop Capabilities 與 runAsNonRoot 規則。

**解決方案**：

1. **使用 CNI Plugin**：如 Istio CNI，將特權操作下沈至 Node 層級，使 Pod 無需 `NET_ADMIN`。
2. **調整策略**：若無法使用 CNI，該 Namespace 可能僅能維持 **Baseline** 等級。

### 4.3 readOnlyRootFilesystem 處理

Restricted 強制要求唯讀（read-only）根檔案系統。若應用程式需寫入臨時檔（如 app log 或 cache），應掛載 `emptyDir` Volume 至寫入路徑。

**YAML 配置範例**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-app
spec:
  containers:
    - name: app
      image: my-app:1.0
      securityContext:
        readOnlyRootFilesystem: true
      volumeMounts:
        - mountPath: /var/log/app
          name: log-volume
        - mountPath: /tmp
          name: tmp-volume
  volumes:
    - name: log-volume
      emptyDir: {}
    - name: tmp-volume
      emptyDir: {}
```

### 4.4 全域預設與豁免 (Exemptions)

若需設定全域預設策略或豁免特定對象（如 `kube-system`），需配置 `AdmissionConfiguration`。

```yaml
apiVersion: apiserver.config.k8s.io/v1
kind: AdmissionConfiguration
plugins:
  - name: PodSecurity
    configuration:
      apiVersion: pod-security.admission.config.k8s.io/v1beta1
      kind: PodSecurityConfiguration
      # 1. 全域預設值：未 Label 的 Namespace 預設套用 Baseline
      defaults:
        enforce: "baseline"
        enforce-version: "latest"
        audit: "restricted"
        audit-version: "latest"
        warn: "restricted"
        warn-version: "latest"
      # 2. 全域豁免清單
      exemptions:
        usernames:
          - "system:serviceaccount:kube-system:default"
        runtimeClasses:
          - "kata-containers"
        namespaces:
          - "kube-system"
          - "istio-system"
```

### 4.5 版本釘選 (Version Pinning)

生產環境中，PSS 的**版本釘選**是常被忽略卻關鍵的設定。

若 Label 未指定版本，PSA **預設使用 `latest`** 規則。隨著 Kubernetes 升級，PSS 標準（特別是 Restricted）可能更動，導致 pod 可能在叢集升級後突遭拒絕。建議可以明確指定版本號（如 `v1.29`），確保叢集升級後仍依舊版規則檢查，保留版本升級的緩衝時間。

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production-app
  labels:
    pod-security.kubernetes.io/enforce: restricted

    # 【關鍵】指定使用 v1.29 規則，避免隨叢集升級而變動
    pod-security.kubernetes.io/enforce-version: "v1.29"

    pod-security.kubernetes.io/warn: restricted
    pod-security.kubernetes.io/warn-version: "v1.29"
```

## 參考連結

- [**Pod Security Standards**](https://kubernetes.io/docs/concepts/security/pod-security-standards/)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
