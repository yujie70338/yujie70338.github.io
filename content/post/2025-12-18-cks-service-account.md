---
title: "〔CKS 筆記整理〕Kubernetes ServiceAccount 預設自動掛載的資安隱患：從預設風險到 Projected Token 與 NetworkPolicy 縱深防禦"
subtitle: ""
description: "本文將深入探討 service account 預設行為的風險，並提供阻斷此攻擊路徑的範例設定。"
date: 2025-12-18
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "ServiceAccount", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes ServiceAccount 預設自動掛載的資安隱患：從預設風險到 Projected Token 與 NetworkPolicy 縱深防禦

在 Kubernetes 的運作機制中，ServiceAccount (SA) 扮演著 Pod 在叢集內的「身分證」角色。然而，Kubernetes 的預設行為會自動將這張身分證掛載到每一個容器中。這種便利性在現代資安觀點來看，形成了一個顯著的攻擊面，常被攻擊者利用於叢集內的橫向移動 (Lateral Movement)。

本文將深入探討 service account 預設行為的風險，並提供阻斷此攻擊路徑的範例設定。

## 1. 核心機制與潛在風險

要防禦攻擊，首先必須理解攻擊者如何利用現有機制。

### 1.1 預設行為 (The Default Behavior)

當您建立一個 Pod 卻未指定 ServiceAccount 時，Kubernetes 會自動指派該 Namespace 下的 `default` SA 給這個 Pod。

此時，Kubelet 會執行一個關鍵動作：自動將該 SA 對應的 Secret (Token) 掛載到容器的 `/var/run/secrets/kubernetes.io/serviceaccount` 目錄下。這意味著，即使是一個與 Kubernetes 業務邏輯無關的靜態網頁容器，預設都擁有能夠與 API Server 溝通的憑證。

### 1.2 攻擊路徑：橫向移動 (Lateral Movement)

這是雲端原生環境中，攻擊者最常利用的路徑之一：

1. **入侵 (Initial Access)**：攻擊者利用 Web 應用程式的漏洞（如 RCE 或任意檔案讀取）成功進入容器內部。
2. **讀取憑證 (Credential Theft)**：攻擊者讀取 `/var/run/secrets/kubernetes.io/serviceaccount/token` 檔案，獲取 JWT Token。
3. **探測 (Discovery)**：使用該 Token 對 API Server 發起請求（例如 `curl https://$KUBERNETES_SERVICE_HOST/api/v1/pods`），嘗試探測叢集結構。
4. **權限擴散 (Expansion)**：若該 ServiceAccount 權限設定過當（例如被錯誤綁定 `cluster-admin` 或過度寬鬆的 RBAC），攻擊者即可利用此 Token 控制整個叢集。

## 2. 設定層級與優先權邏輯

為了關閉此預設行為，我們使用 `automountServiceAccountToken: false` 設定。這個參數可以在兩個層級進行設定，我們接下來來了解它的覆蓋邏輯。

### 2.1 層級一：ServiceAccount (推薦預設值)

將 `automountServiceAccountToken: false` 設定在 service account 上後，所有使用此 SA 的 Pod 預設都不會掛載 Token，除非 Pod 明確要求。

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: backend-sa
  namespace: default
automountServiceAccountToken: false ## <--- 關鍵設定：影響所有使用此 SA 的 Pod
```

### 2.2 層級二：Pod Spec (例外覆蓋)

Pod 層級的設定擁有最高優先權，可以覆蓋 ServiceAccount 層級的設定。這通常用於除錯，或是針對必須與 API Server 互動的特殊需求（例如 Kubernetes Controllers、Prometheus 監控組件、CI/CD Runners 或 Service Mesh）。

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: debug-pod
spec:
  serviceAccountName: backend-sa ## 即使 SA 層級設為 False...
  automountServiceAccountToken: true ## <--- 這裡指定 True，最終結果就是 True
  containers:
    - name: app
      image: my-app
```

## 3. 影響評估 (Impact Analysis)

不過在開始動手修改正式區環境，記得要先進行更改後的風險評估。以下是不同應用類型的影響評估與錯誤徵兆：

| 應用類型           | 典型範例                                                | 影響評估                                                                    | 錯誤徵兆                                    |
| ------------------ | ------------------------------------------------------- | --------------------------------------------------------------------------- | ------------------------------------------- |
| **純業務應用**     | Nginx, Java Spring Boot (REST API), Frontend            | **無影響**。這類應用只處理業務邏輯，不需與 K8s API Server 溝通。            | (運作正常)                                  |
| **K8s 客戶端工具** | 在 Pod 內跑 `kubectl` 的運維腳本                        | **功能失效**。`kubectl` 預設依賴該 Token 進行認證。                         | `error: no configuration has been provided` |
| **K8s SDK 應用**   | Prometheus, Jenkins Agent, Operators (Go/Python Client) | **啟動失敗**。SDK 初始化 `InClusterConfig()` 時會因為找不到憑證檔案而報錯。 | `unable to load in-cluster configuration`   |

### 3.1 如何確認 Token 是否正在被使用？

Kubernetes 並沒有內建針對應用行為的 "Dry Run" 模式

我們可以透過 **API Server 稽核日誌 (Audit Logs)** 來進行「被動式 Dry Run」：

1. **啟用 Audit Log**：確保 K8s Control Plane 已開啟 Audit Log 功能。
2. **搜尋存取紀錄**：搜尋例如 `system:serviceaccount:<namespace>:<sa-name>` 的紀錄。
3. **判斷依據**：
   - **有紀錄**：代表該應用程式**正在使用** Token 呼叫 API。
   - **無紀錄**（持續觀察 24h+）：代表該應用程式可能不需要 Token，可以進一步規劃關閉 automountServiceAccountToken。

### 3.2 金絲雀部署 (Canary Rollout)

值得注意的是，修改 ServiceAccount 的 `automountServiceAccountToken` 設定**不會**觸發 Pod 自動重啟。這為我們提供了一個安全緩衝：

1. **修改 SA 設定**：將 automount 設為 `false`。此時現有的 Pod 仍掛載著舊 Token，不受影響。
2. **金絲雀驗證**：手動刪除**一個** Pod 讓其重建（或重啟 Deployment 的 rollout）。
3. **觀察**：檢查新啟動的 Pod 是否運作正常。
4. **全面套用**：確認無誤後，再逐步重啟其餘 Pods。

## 4. 驗證與測試 (Verification)

確認評估無誤並設定完畢後，我們需要驗證憑證是否真的從容器中消失。

#### 驗證情境 A：安全狀態 (Token 已移除)

當設定生效後，Secret Volume 不會被掛載到容器中。

```shell
## 進入容器檢查
kubectl exec my-secure-pod -- ls /var/run/secrets/kubernetes.io/serviceaccount/
```

**預期結果：**

```text
ls: /var/run/secrets/kubernetes.io/serviceaccount/: No such file or directory
```

攻擊者即便進入容器，也找不到任何憑證，無法進行後續的權限濫用。

## 5. 最佳實踐的補充說明

### 5.1 基礎安全設定 (Basic Configuration)

#### 維持 default ServiceAccount 的預設狀態

許多第三方的 Helm Chart（如 Monitoring stack 或 Ingress Controller）在部署時，若開發者未指定 SA，會預設使用 `default` SA 且程式邏輯可能依賴 Token。如果您直接修改 `default` SA 的 `automountServiceAccountToken` 為 `false`，這類應用可能會無預警故障。因此，最佳策略是**保持 `default` SA 原樣**（或者保持 True 但不綁定任何 RBAC 權限），但強制要求您的其他業務需求(應用程式)的 Pod 使用「專用」的 SA。

#### 為應用程式建立專用 ServiceAccount

權限隔離的基礎在於專款專用。請為每個應用程式建立獨立的 ServiceAccount：

1. 建立 `webapp-sa`，並設定 `automountServiceAccountToken: false`。
2. 在 Deployment YAML 中明確指定 `serviceAccountName: webapp-sa`。

#### 透過策略引擎強制執行 (Policy Enforcement)

在開發流程中，總是依賴開發者自己記得寫 `false` 是不切實際的。因此，在生產環境中，可以使用 OPA Gatekeeper 或 Kyverno 等工具來強制執行策略。

例如，設定一條 Kyverno 規則：「如果 Namespace 不在白名單內，且 Pod 沒有明確設定 `automountServiceAccountToken: false`，則拒絕該建立請求。」

### 5.2 Projected Volume

#### 採用 Projected Service Account Tokens (實作範例)

若您的應用（如 Prometheus）真的需要 Token 來存取 API Server，建議不要使用傳統的 Secret 掛載方式，可以採用更現代的 **Projected Volume**。

**什麼是 Projected Volume？**
它允許將多個 Volume 來源映射到同一個目錄下。針對 Service Account Token，它不再使用靜態 Secret，而是要求 Kubelet 向 API Server 請求一個具有「時效性」且「可輪替」的新 Token。

**傳統方式 vs Projected Volume**

| 特性                    | 傳統 Secret 掛載 (Legacy)         | Projected Service Account Token (推薦)            |
| ----------------------- | --------------------------------- | ------------------------------------------------- |
| **時效性**              | **永久有效** (除非刪除 SA)        | **有期限** (可自訂，預設 1 小時)                  |
| **輪替機制 (Rotation)** | 手動 (需刪除 Secret 重建)         | **自動** (Kubelet 自動更新並通知 Pod)             |
| **適用範圍 (Audience)** | 無限制 (任何 API Server 請求皆可) | **可限制** (僅限特定接收者使用，Audience Binding) |
| **安全性**              | 低 (一旦洩漏需全域輪替)           | **高** (洩漏影響範圍有限且短暫)                   |

**Projected Volume 設定步驟範例 (Step-by-Step)**

若要啟用此機制，請遵循以下標準設定流程：

**步驟 1：定義 Volume (在 Pod Spec 中)**
在 `volumes` 區塊中，我們使用 `projected` 類型。

```yaml
volumes:
  - name: my-secure-token-vol
    projected:
      sources:
        - serviceAccountToken:
            path: token ## 檔案名稱
            expirationSeconds: 3600 ## Token 壽命 1 小時
            audience: my-app-backend ## (選填) 限制 Token 的適用對象，防止被誤用
```

**步驟 2：掛載 Volume (在 Container Spec 中)**
將上述 Volume 掛載到容器內的指定路徑。

```yaml
containers:
  - name: my-app
    image: my-image
    volumeMounts:
      - name: my-secure-token-vol
        mountPath: /var/run/secrets/tokens
        readOnly: true
```

**步驟 3：應用程式適配 (關鍵注意事項)**
由於 Token 會自動輪替 (Rotation)，[Kubelet 會在 Token 過期前（約壽命的 80% 時）](<https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#:~:text=The%20kubelet%20proactively%20requests%20rotation%20for%20the%20token%20if%20it%20is%20older%20than%2080%25%20of%20its%20total%20time%2Dto%2Dlive%20(TTL)%2C%20or%20if%20the%20token%20is%20older%20than%2024%20hours>)自動更新檔案。

- **開發者注意**：應用程式不能只在啟動時讀取一次 Token。必須實作 **定期重讀** 或 **監控檔案變更** 的邏輯。大多數現代 K8s Client SDK (Go, Python, Java) 已內建此功能，無需修改程式碼；但若是自寫的 Shell Script，則需特別處理。

**完整 YAML 範例**

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secure-pod
spec:
  serviceAccountName: backend-sa
  automountServiceAccountToken: false ## 關閉預設的不安全掛載
  containers:
    - name: app
      image: curlimages/curl
      ## 模擬應用程式定期讀取 Token
      command:
        [
          "sh",
          "-c",
          "while true; do cat /var/run/secrets/tokens/token; sleep 60; done",
        ]
      volumeMounts:
        - mountPath: /var/run/secrets/tokens
          name: token-vol
          readOnly: true
  volumes:
    - name: token-vol
      projected:
        sources:
          - serviceAccountToken:
              path: token
              expirationSeconds: 600 ## 10分鐘後過期，便於測試輪替
              audience: api-server
```

#### 實施網路層級存取控制 (NetworkPolicy)

**NetworkPolicy** 是防止 Token 被濫用的最後一道防線。其原理很簡單：即使攻擊者手握有效的 Token，如果我們從網路層直接封鎖該 Pod 對 Kubernetes API Server 的連線能力，該 Token 將因網路不可達而失效，從而阻斷了攻擊路徑。

設定範例（針對不需要與 API Server 溝通的純業務 Pod，實施 Egress 限制）：

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-api-access
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: webapp ## 針對特定應用
  policyTypes:
    - Egress
  egress:
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns ## 僅允許連線到 DNS
      ports:
        - port: 53
          protocol: UDP
        - port: 53
          protocol: TCP
  ## 注意：未列出的目的地（如 K8s API Server IP）預設皆為 Deny
```

因此，透過 ServiceAccount 的「身份管理」加上 NetworkPolicy 的「網路隔離」，我們可以大幅降低 Kubernetes 叢集因單一容器淪陷而導致權限擴散的風險。

## 6. 總結：構建零信任的防線

Kubernetes 的安全性並非來自單一的設定，而是來自層層堆疊的防禦縱深。透過檢視 ServiceAccount 的預設行為，我們發現「便利性」往往潛藏著資安風險。

總結來說，要構建一個穩固的環境，我們可以採取以下三道防線：

1. **身分管理 (Identity Management)**：徹底檢查並關閉不必要的 `automountServiceAccountToken`，並確保業務 Pod 使用專用的 ServiceAccount。
2. **現代化認證 (Modern Auth)**：對於必須存取 API 的服務，捨棄永久有效的 Secret，使用具備時效性與 Audience 限制的 **Projected Volume**。
3. **網路隔離 (Network Isolation)**：假設 Token 終將被竊取，利用 **NetworkPolicy** 封死通往 API Server 的網路路徑，作為最後的保險。

## 參考連結

- [The kubelet proactively requests rotation for the token if it is older than 80% of its total time-to-live (TTL), or if the token is older than 24 hours](<https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#:~:text=The%20kubelet%20proactively%20requests%20rotation%20for%20the%20token%20if%20it%20is%20older%20than%2080%25%20of%20its%20total%20time%2Dto%2Dlive%20(TTL)%2C%20or%20if%20the%20token%20is%20older%20than%2024%20hours>)
- [What is Lateral Movement?](https://www.checkpoint.com/tw/cyber-hub/cyber-security/what-is-lateral-movement/)
- [Lateral Movement Explained](https://www.crowdstrike.com/en-us/cybersecurity-101/cyberattacks/lateral-movement/)
- [Opt out of API credential automounting](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/#opt-out-of-api-credential-automounting:~:text=Opt%20out%20of%20API%20credential%20automounting)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
