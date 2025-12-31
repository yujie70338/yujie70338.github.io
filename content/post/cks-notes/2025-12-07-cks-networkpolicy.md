---
title: "〔CKS 筆記整理〕Kubernetes NetworkPolicy 深度解析：零信任隔離網路架構"
subtitle: ""
description: "本文將從 SRE 的維運視角，探討 NetworkPolicy 的運作機制與實戰策略。內容涵蓋：API Server 與 CNI 的職責分離、建構 Default Deny*零信任架構的標準流程，以及生產環境中常見的 DNS 解析斷線與 YAML 邏輯誤區。透過本文，你將學會如何建立穩定且安全的叢集網路防禦體系。"
date: 2025-12-07
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "NetworkPolicy", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes NetworkPolicy 深度解析：零信任隔離網路架構

## 摘要

Kubernetes 預設採用「扁平化網路（Flat Network）」模型，Cluster 內的所有 Pod 預設皆可互相連線。這種設計雖然便利，但在資安上卻是極大的風險，一旦單點遭到入侵，攻擊者便能輕易進行橫向移動（Lateral Movement）。本文將從 SRE 的維運視角，探討 NetworkPolicy 的運作機制與實戰策略。內容涵蓋：API Server 與 CNI 的職責分離、建構 **Default Deny** 零信任架構的標準流程，以及生產環境中常見的 **DNS 解析斷線**與 **YAML 邏輯誤區**。透過本文，你將學會如何建立穩定且安全的叢集網路防禦體系。

## 一、核心機制：API Server 與 CNI 的分工

在撰寫 NetworkPolicy 之前，必須先理解 Kubernetes 的網路安全架構，特別是「意圖」與「執行」的分離。

NetworkPolicy 本質上是一份 **Layer 3 (IP) 與 Layer 4 (Port) 的防火牆宣告**。

1. **宣告（API Server）**：當你執行 `kubectl apply` 時，API Server 僅負責接收並儲存這份規則到 etcd。API Server 本身**不具備**阻擋流量的能力。
2. **執行（CNI Agent）**：真正的流量過濾是由節點上的 **CNI (Container Network Interface)** 負責。CNI 的 Agent（如 `calico-node` 或 `cilium-agent`）會監聽 API Server 的規則變動，並將 YAML 轉換為底層 Linux Kernel 的 iptables 或 eBPF 規則來執行阻擋。

### CNI 選型比較：Flannel, Calico 與 Cilium

若底層 CNI 不支援 NetworkPolicy，即使部署了 YAML 檔案，防火牆也不會生效。

以下是常見 CNI 的支援度比較：

| CNI     | NetworkPolicy 支援 | 底層技術        | 核心特點                                   |
| ------- | ------------------ | --------------- | ------------------------------------------ |
| Flannel | ❌ 不支援          | Overlay Network | 僅提供基本連通性，無法阻擋流量 (Fail-Open) |
| Calico  | ✅ 完整支援        | iptables        | 業界標準，穩定性高，支援 L7 Policy         |
| Cilium  | ✅ 完整支援        | eBPF            | 高效能，深度可觀測性，支援 L7 (API/DNS)    |

## 二、實戰策略：建構零信任架構

為了強化安全性，標準作法是將預設行為從「允許所有（Allow All）」改為「拒絕所有（Default Deny）」，再依需求逐一放行。

### Step 1: 部署全域拒絕策略 (Default Deny)

在建立 Namespace 時，應立即套用此 Policy。它會選取所有 Pod，但未定義任何白名單，從而阻擋所有進出的流量。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: target-namespace # 請替換為目標 Namespace
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
  # 未定義 ingress 或 egress 規則，預設為全部阻擋
```

### Step 2: 放行基礎設施所需的流量 (DNS、API 與監控)

實施 `Default Deny Egress` 後，Pod 會立即失去連線能力。在生產環境中，必須優先放行以下三類基礎設施流量，避免服務崩潰：

#### 1. DNS 解析 (最關鍵)

所有網路連線的第一步通常是 DNS 查詢。必須放行通往 `kube-system` Namespace 中 CoreDNS 的流量 (UDP/TCP 53)。

#### 2. Kubernetes API 與 Cloud Metadata

- **K8s API**: Controller 或 Operator 需要連線 Cluster API (Port 443) 獲取狀態。
- **Metadata**: 在公有雲 (AWS/GCP) 上，Pod 可能需要存取 Metadata Server (`169.254.169.254`) 以獲取 IAM 權限。

#### 3. 監控數據 (Metrics/Logs)

若有安裝 Datadog、New Relic 或 OpenTelemetry Agent，需允許 Pod 將監控數據發送至 Agent 或外部端點。

**基礎設施流量放行範例：**

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-infra-egress
  namespace: target-namespace
spec:
  podSelector: {}
  policyTypes:
    - Egress
  egress:
    # 1. 放行 DNS
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53

    # 2. 放行 K8s API Server (通常位於 default namespace)
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: default
          podSelector:
            matchLabels:
              component: apiserver
              provider: kubernetes
      ports:
        - protocol: TCP
          port: 443

    # 3. 放行 Cloud Metadata (AWS/GCP)
    - to:
        - ipBlock:
            cidr: 169.254.169.254/32

    # 4. 放行監控系統 (例如 OpenTelemetry Collector)
    - to:
        - ipBlock:
            cidr: 10.0.0.0/8
      ports:
        - protocol: TCP
          port: 4317
```

### Step 3: 應用服務間的微隔離

完成基礎設施設定後，最後一步是處理應用程式之間的連線授權。

由於 Kubernetes Pod 的 IP 高度動態（重啟或擴縮容皆會改變 IP），使用 IP 規則維護成本極高。最佳實務是**全面使用 Label Selector**。

透過 `podSelector`，防火牆規則能與應用程式的標籤綁定。無論 Pod 如何重建或漂移，只要標籤不變，NetworkPolicy 就會自動生效。

**範例**：僅允許標籤為 `app: frontend` 的 Pod，連線至 `app: backend` 的 TCP 8080。

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: target-namespace
spec:
  podSelector:
    matchLabels:
      app: backend # 目標：保護 backend Pod
  policyTypes:
    - Ingress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend # 來源：只允許 frontend Pod
      ports:
        - protocol: TCP
          port: 8080
```

## 三、常見誤區：YAML List 的邏輯判斷

NetworkPolicy 的 YAML 語法中，最容易混淆的是 List (`-`) 的使用，這決定了條件是「且 (AND)」還是「或 (OR)」。這是在 Code Review 中最容易被忽略，卻能瞬間將嚴格的防火牆變成「大門敞開」的設定錯誤。

### 情境 A：嚴格模式 (AND) - 推薦用法

當所有條件寫在**同一個** `-` 列表項目下時，邏輯為 **AND**。流量來源必須**同時滿足**所有條件。

```yaml
ingress:
  - from:
      - namespaceSelector:
          matchLabels:
            project: my-project
        podSelector: # 注意：這裡沒有 "-"
          matchLabels:
            role: frontend
# 解讀：只有「來自 my-project Namespace」且「標籤為 frontend」的 Pod 可以連線。
# 這是最精確的微隔離寫法。
```

### 情境 B：寬鬆模式 (OR)

當條件被拆分到**不同**的 `-` 列表項目時，邏輯為 **OR**。流量來源只要**滿足其中之一**即可。

```yaml
ingress:
  - from:
      - namespaceSelector: # 第一個規則
          matchLabels:
            project: my-project
      - podSelector: # 第二個規則
          matchLabels:
            role: frontend
# 解讀：
# 1. 來自 my-project Namespace 的「所有」Pod 都可以連線 (無論它是什麼 Pod)。
# 2. 或者，來自當前 Namespace 且標籤為 frontend 的 Pod 也可以連線。
# 風險：這通常會意外開放過多的權限。
```

## 四、可觀測性與縱深防禦

### 1. 先觀察，再阻擋 (Log before Enforce)

**部署 Default Deny 最大的風險是誤擋正常流量**。在強制執行 (Enforce) 之前，**強烈建議**先開啟 CNI 的 Audit/Log 模式，觀察是否有預期外的流量被攔截，至少觀察 24 小時（或涵蓋完整的 CronJob 週期）後，確認日誌中沒有誤擋關鍵流量後，再關閉 Log 模式並推上 Production。

### **Cilium**

Cilium 提供原生的 `Policy Audit Mode`，這是最安全的測試方式。開啟後，Cilium 會記錄違反 Policy 的行為，但**不會真正丟棄封包**。

- **開啟方式**：修改 Cilium ConfigMap 或 Helm Values，設定 `policy-audit-mode: true`。
- **觀察指令**：

  ```shell
  # 觀察即時的丟包與審核紀錄
  kubectl exec -it -n kube-system <cilium-pod> -- cilium monitor

  # --type drop --type policy-verdict #--type drop: 用於觀察被防火牆丟棄的封包（Packet Drops）。
  # --type policy-verdict: 用於觀察 Policy 的決策過程。

  ```

- **視覺化**：若有安裝 Hubble UI，可以直接在網頁上看到紅色的連線（代表被 Deny）。

### **Calico**

標準的 Kubernetes NetworkPolicy 沒有 Log Action，但 Calico 提供了 CRD (`CalicoNetworkPolicy`) 來擴充這項功能。你可以建立一條專門用來 Log 的規則，放在 Deny 規則之前。

- **實作方式**：使用 `action: Log`。

  ```yaml
  apiVersion: projectcalico.org/v3
  kind: NetworkPolicy
  metadata:
    name: log-denied-traffic
    namespace: my-app
  spec:
    selector: all()
    types:
      - Ingress
    ingress:
      - action: Log
        source: {} # 記錄所有來源
  ```

- **觀察日誌**：Calico 通常會將日誌寫入節點的 `/var/log/syslog` 或核心日誌 (`dmesg`)，具體視系統配置而定。搜尋關鍵字 `CalicoPacketLog` 即可找到被記錄的封包。

### 2. 應用層防護 (Layer 7 Filtering) 的防護：

NetworkPolicy 的能力天花板在於它「看不懂」應用層協定（Layer 7）。它能告訴你 IP 和 Port 正確（Layer 3~4），但無法區分這個請求是無害的 `GET /products` 還是危險的 `DELETE /users`。

若需實現更精細的 Layer 7 控制，除了使用 NetworkPolicy 之外，通常還會加上 **Service Mesh (Istio, Linkerd)** 或 **進階 CNI (Cilium)** 來達成。

- **Service Mesh 方案**：利用 Sidecar Proxy (Envoy) 攔截流量，透過 `AuthorizationPolicy` 限制特定 Service Account 只能存取特定的 HTTP Method 或 Path。
- **縱深防禦體系 (Defense in Depth)**： 一個完整的雲原生防禦應包含三道防線：

$$\text{整體安全} = \text{Cloud Security Group (基礎設施)} + \text{NetworkPolicy (微隔離)} + \text{Service Mesh (應用層授權)}$$

### 3. 外部流量相依性管理：從 IPBlock 到 Egress Gateway

當 Pod 需要連線到 Cluster 外部（例如 AWS RDS、Stripe API、Google Maps API）時，NetworkPolicy 雖然提供了 `ipBlock`，但在現代微服務環境中，直接維護 IP 白名單往往造成維運的困難。

### **模擬範例：金流服務 Stripe 的 IP 災難**

假設你的服務需要連線至 `api.stripe.com` 處理刷卡。

1. **初階作法 (Bad)**：你 `dig api.stripe.com` 取得 IP，寫入 NetworkPolicy 的 `ipBlock`。
2. **災難發生**：Stripe 使用 CDN，其背後有成千上萬個動態 IP，且隨時會變動。某天早上，你的交易功能突然全掛，只因為 Stripe 切換了 CDN 節點，IP 變了，而你的防火牆還擋著。

### **解決方案：Egress Gateway 模式**

**最佳實務**是**不要**在 NetworkPolicy 層級與外部動態的 IP 搏鬥，而是將這項職責交給能使用 FQDN 的 Egress Gateway (如 Istio Egress Gateway 或 Cilium)。

1.  **NetworkPolicy 層 (L3/L4)**：
    只負責放行應用程式 Pod 連線到 **Egress Gateway Pod** 的 L3/L4 流量。這是一個內部且穩定的連線。

    ```yaml
    # 範例：只允許連線到 istio-egressgateway
    egress: - to: - namespaceSelector:
    matchLabels:
    kubernetes.io/metadata.name: istio-system
    podSelector:
    matchLabels:
    app: istio-egressgateway
    ports: - protocol: TCP
    port: 443

    ```

2.  **Egress Gateway 層 (L7)**：
    讓 Gateway 統一代理出口流量，並在此處使用 **FQDN (網域名稱)** 進行白名單過濾。
    - **ServiceEntry**：用於註冊 `.stripe.com` 為合法外部服務。
    - **Gateway Rule**：用於只允許通過 Gateway 存取已註冊的 Domain。

**結論**：透過這種分層架構，只需要維護「內部 Pod -> Gateway」的穩定路徑，而「Gateway -> 外部動態 IP」的複雜解析則交給專門的 Proxy 處理，一勞永逸解決 IP 變動導致的斷線問題。

# 額外補充

## Hubble UI

Hubble UI 是 Cilium 生態系中的網路可觀測性工具。

### 1. What is Hubble UI?

Hubble UI 是一個基於網頁的圖形化介面，它能將 Kubernetes 叢集內的網路流量「視覺化」。

- **服務地圖 (Service Map)**：它會自動畫出誰連線到誰（例如 Frontend -> Backend -> DB）。
- **流量審計 (Flow Audit)**：它能即時顯示每一個連線請求的結果。綠色線條代表允許 (Forwarded)，**紅色線條代表被防火牆阻擋 (Dropped)**。
- **除錯工具**：當 NetworkPolicy 設定錯誤導致服務不通時，您不用去撈 iptables log，直接看 Hubble UI 上哪條線變紅，點開就能看到是哪個 Policy 擋下的。

### 2. CNI 都可以使用嗎？

**不行，它是 Cilium 專屬的工具。**

- Hubble 的底層依賴 **eBPF** 技術來蒐集核心層級的網路數據，這是 **Cilium CNI** 的核心功能。
- 如果您使用 **Calico** 或 **Flannel**，是無法直接使用 Hubble UI 的。
  - **Calico** 的對應方案通常是付費版的 Calico Enterprise/Cloud 才有的 Flow Logs 介面，或是自行透過 Log 輸出搭配 Grafana/Elasticsearch。
  - **Istio** (Service Mesh) 也有類似的 Kiali Dashboard，但那是 Layer 7 的視角，**Hubble 則涵蓋了 L3/L4 到 L7**。

### 3. 如何使用？

步驟一：已經安裝了 Cilium CNI 之後，啟用 Hubble 與 UI ：

```shell
cilium hubble enable --ui

```

步驟二：開啟 UI 在您的本機電腦執行以下指令，它會自動建立 Port-forward 並打開瀏覽器：

```
cilium hubble ui

```

**步驟三：除錯操作**

1. 進入 UI 後，選擇您要觀察的 Namespace (例如 `target-namespace`)。
2. 畫面中央會出現服務拓樸圖。
3. 下方會有即時的流量列表。
4. 在篩選欄位輸入 `verdict=DROPPED`，畫面就會過濾出所有被 NetworkPolicy 阻擋的流量，讓您一目瞭然是誰在擋路。

## Cilium 的 L7 功能算是 Service Mesh 嗎？

是，**Cilium 不僅提供 Service Mesh 功能，更開啟了「Sidecarless」的架構革命。**

但從維運成本角度來看，我們必須區分它與傳統 Service Mesh（如 Istio、Linkerd）在實作上的巨大差異。

### 1. 功能面：完全符合定義

Service Mesh 的三大支柱，Cilium 透過 eBPF 與 Envoy 的結合完全覆蓋：

1. **安全性 (Security)**：`CiliumNetworkPolicy` 能依據 HTTP Method、Path 進行 L7 過濾，實現 API 等級的零信任。
2. **可觀測性 (Observability)**：Hubble 能解析 L7 協定 (HTTP, DNS, …)，提供黃金指標 (RPS, Latency, Error Rate)，無需應用程式埋點。
3. **流量管理 (Traffic Management)**：支援金絲雀部署 (Canary)、流量切分與重試機制 (Retries)。

### 2. 架構面：Sidecar vs. Sidecarless

- **傳統 Service Mesh (Istio 傳統模式)**
  - **架構**：Sidecar 模式。
  - **成本**：每個 Pod 都要注入一個 Envoy Container。假設你有 1000 個 Pod，就多了 1000 個 Sidecar，**資源消耗與延遲顯著增加**。
  - **痛點**：Sidecar 啟動順序、升級維護都是維運負擔。
- **Cilium Service Mesh**
  - **架構**：Sidecarless (Per-Node Proxy) 模式。
  - **機制**：利用 eBPF 在核心層攔截封包。當遇到需要 L7 處理的流量時，eBPF 將其轉送至節點上的**共用 Envoy 實例**，處理完再送回核心。
  - **優勢**：應用程式完全無感，無需注入 Sidecar，大幅降低資源開銷與維運複雜度。

### 3. Service Mesh 如何選擇 :

- **場景 A：你只需要 L7 防火牆與可觀測性 👉 選 Cilium 。**
  不需要為了這些功能去部署沉重的 Istio。Cilium 的 `CiliumNetworkPolicy` 配合 Hubble 已經能滿足 90% 的資安與監控需求，且效能更好。
- **場景 B：你需要極致複雜的流量治理 👉 Istio 生態系仍較成熟。** 如果你需要非常複雜的跨叢集路由、精細的熔斷機制 (Circuit Breaking) 或強制的 mTLS 驗證體系，Istio 目前的工具鏈（如 Kiali, Jaeger 整合）與資源仍較為豐富。

## Egress Gateway 範例補充：Istio Egress Gateway

**場景描述**： 要求所有連往外部（Internet）的流量，都必須統一經過一個「出口節點 (Egress Gateway)」。這通常是為了：

1. **固定來源 IP**：方便外部合作廠商（如銀行、支付閘道）將您的 Gateway IP 加入防火牆白名單。
2. **統一監控**：在 Gateway 處集中收集所有對外連線的日誌。

流量路徑為：`Pod (Sidecar) -> Egress Gateway -> 外部網路 (google.com)`。
若沒有設定，Pod 預設會直接連線外部；設定後，Sidecar 會攔截流量並強制轉送給 Gateway。

```yaml
# 1. istio 準備
apiVersion: v1
kind: Namespace
metadata:
  name: demo-istio
  labels:
    istio-injection: enabled
---
# 2. 定義外部服務 (ServiceEntry)
# 告訴 Istio 網格，google.com 是一個合法的外部服務
apiVersion: networking.istio.io/v1beta1
kind: ServiceEntry
metadata:
  name: google-ext
  namespace: demo-istio
spec:
  hosts:
    - google.com
  ports:
    - number: 443
      name: tls
      protocol: TLS
  resolution: DNS
  location: MESH_EXTERNAL
---
# 3. 定義 Gateway 資源
# 這是在 istio-egressgateway Pod 上開啟一個 port 443 的監聽器
apiVersion: networking.istio.io/v1beta1
kind: Gateway
metadata:
  name: istio-egressgateway
  namespace: demo-istio
spec:
  selector:
    istio: egressgateway
  servers:
    - port:
        number: 443
        name: tls
        protocol: TLS
      hosts:
        - google.com
      tls:
        mode: PASSTHROUGH # HTTPS 透傳，Gateway 不做解密
---
# 4. 定義流量路由 (VirtualService) - 核心邏輯
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: direct-google-through-egress-gateway
  namespace: demo-istio
spec:
  hosts:
    - google.com
  gateways:
    - mesh # 規則適用於應用程式 Pod (Sidecar)
    - istio-egressgateway # 規則適用於 Egress Gateway 本身
  tls:
    - match:
        # 步驟 A: 當 Sidecar (mesh) 收到往 google.com 的流量時...
        - gateways:
            - mesh
          port: 443
          sniHosts:
            - google.com
      route:
        # ...將流量轉送到 Egress Gateway Service
        - destination:
            host: istio-egressgateway.istio-system.svc.cluster.local
            subset: google
            port:
              number: 443
          weight: 100
    - match:
        # 步驟 B: 當 Egress Gateway 收到往 google.com 的流量時...
        - gateways:
            - istio-egressgateway
          port: 443
          sniHosts:
            - google.com
      route:
        # ...將流量真正送往外部網路
        - destination:
            host: google.com
            port:
              number: 443
          weight: 100
---
# 5. 定義 DestinationRule
# 為 Gateway 定義流量子集 (Subset)
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata:
  name: egressgateway-for-google
  namespace: demo-istio
spec:
  host: istio-egressgateway.istio-system.svc.cluster.local
  subsets:
    - name: google
```

## Egress Gateway 範例補充：Cilium Network Policy

**場景描述**：
您不希望維護複雜的 Istio Gateway 架構，也不需要統一的出口 IP，但您需要**嚴格的安全性**。您希望直接在 Pod 層級阻擋所有連線，只允許應用程式連線到特定的網域名稱（如 `google.com`）。

流量路徑為：`Pod -> Cilium eBPF Filter -> 外部網路`。

```yaml
# 1. 基礎設施準備
apiVersion: v1
kind: Namespace
metadata:
  name: demo-cilium
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
  namespace: demo-cilium
  labels:
    app: my-app
spec:
  replicas: 1
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      containers:
        - name: curl
          image: curlimages/curl
          command: ["/bin/sleep", "3650d"]
---
# 2. Cilium FQDN Policy - 核心邏輯
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: allow-only-google
  namespace: demo-cilium
spec:
  # 選取目標 Pod
  endpointSelector:
    matchLabels:
      app: my-app
  egress:
    # 規則 1: 必須允許 DNS 解析 (UDP 53)
    # 若沒這條，Pod 連 google.com 的 IP 都查不到，連線會直接失敗
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s:k8s-app: kube-dns
      toPorts:
        - ports:
            - port: "53"
              protocol: UDP
          rules:
            dns:
              - matchPattern: "*" # 允許查詢任何 Domain，但連線只允許下面定義的 FQDN

    # 規則 2: 基於 FQDN 的白名單
    # Cilium 會解析 google.com 對應的 IP 並動態放行
    - toFQDNs:
        - matchName: "google.com"
        - matchName: "*.google.com"
      toPorts:
        - ports:
            - port: "443"
              protocol: TCP
            - port: "80"
              protocol: TCP
```

# 參考連結

- [**Network Policies**](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [**Service Map & Hubble UI**](https://docs.cilium.io/en/stable/observability/hubble/hubble-ui/)
- [**Enable and enforce application layer policies**](https://docs.tigera.io/calico-cloud/network-policy/application-layer-policies/alp)

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
