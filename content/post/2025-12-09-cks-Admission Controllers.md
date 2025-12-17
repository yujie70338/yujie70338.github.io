---
title: "〔CKS 筆記整理〕Kubernetes Admission Control 完全攻略：從原理到 OPA Gatekeeper 生產環境實戰"
subtitle: ""
description: "本文將帶您深入剖析 Admission Control 的 Core Process、Policy Engine 的實作方式，以及在 Production Environment 中的模擬範例。"
date: 2025-12-09
author: "Yujie Zheng"
image: ""
tags: ["K8S", "Kubernetes", "AdmissionControl", "CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes Admission Control 完全攻略：從原理到 OPA Gatekeeper 生產環境實戰

在 Kubernetes 的 Security Model 中，許多人誤以為只要設定好 Authentication (身分認證) 和 RBAC (權限控制)，Cluster 就安全了。然而，真正決定一個 Object 能否被寫入 etcd 的關鍵檢查點，是 **Admission Controllers**。即便 User 通過了 Authentication 且擁有 RBAC 寫入權限，如果 Request 內容不符合 Admission Control 的規則，API Server 依然會拒絕該請求。

本文將帶您深入剖析 Admission Control 的 Core Process、Policy Engine 的實作方式，以及在 Production Environment 中的模擬範例。

## 1. **核心流程**：先 Mutate，再 Validate

Kubernetes 對於 Request 的處理順序有著嚴格的邏輯設計，理解這個順序是設計 Webhook 的基礎。整個流程遵循著一個基本原則：**先 Mutate (變更)，再 Validate (驗證)**。

### Phase 1: Mutation Phase (變更階段)

當一個 Request 進入 API Server 並通過 Schema 驗證前，首先會觸發變更階段。

- **對應物件**：`MutatingWebhookConfiguration`
- **目的**：修改 Request 的內容 (Patch)。
- **邏輯理由**：此順序的必要性在於，若等到驗證完才修改物件，修改後的內容可能再次違反規則，導致邏輯矛盾。因此，系統必須先完成所有的 Mutation，確認最終狀態後再進行檢查。
- **實務應用**：
  - **Istio Sidecar Injector**：在 Pod 被持久化之前，自動將 `istio-proxy` 的容器定義注入到 Pod 中。
  - **StorageClass Defaulting**：當使用者建立 PVC 但未指定 StorageClass 時，系統會在此階段自動填入 (Populate) 預設值。

### Phase 2: Validation Phase (驗證階段)

當所有 Mutation 都完成，且通過了 Schema 結構驗證後，請求就會進入驗證階段。

- **對應物件**：`ValidatingWebhookConfiguration`
- **目的**：進行最終的決策 (Accept or Reject)。
- **邏輯理由**：在這個階段，系統檢查物件的最終狀態是否合法，我們無法再對物件進行任何修改。
- **實務應用**：
  - **ResourceQuota**：檢查 Namespace 配額是否足夠。
  - **OPA Gatekeeper**：檢查 Pod 是否包含了必要的 Label、映像檔來源是否合法等。

## 2. Policy Engine 整合：OPA Gatekeeper

隨著 Cluster 規模擴大，單靠原生的檢查機制往往不足以應對複雜的合規需求。這時，我們通常會引入 **Open Policy Agent (OPA)** 這類通用的策略引擎，實現「策略即程式碼 (Policy as Code)」。

**Gatekeeper 與 OPA 的關係**：OPA 是一個通用的策略引擎，而 **Gatekeeper** 是 OPA 在 Kubernetes 上的 Controller 實作。Gatekeeper 透過 CRD (Custom Resource Definition) 讓 OPA 能以 Kubernetes 原生的方式進行管理與整合，解決了原生 OPA 難以與 Kubernetes API 互動的問題。

具體的架構是建立一個 `ValidatingWebhookConfiguration` 作為橋樑。當 API Server 收到 CREATE 或 UPDATE 請求時，會根據設定將請求暫停，並將內容轉發給 OPA Service 的 `/validate` 端點。OPA 接著會執行預先定義的 Rego Policy 進行評估。如果 OPA 回傳 `Allow: true`，API Server 才會將資料寫入 etcd；反之則會回傳錯誤訊息給使用者，達到強制執行的效果。

在選擇 **Open Policy Agent (OPA)** 作為策略引擎時，會需要使用 Rego 語言來撰寫策略。Rego 的優點在於極度靈活，能夠處理非常複雜的邏輯，例如比對 Ingress Hostname 是否與現有服務衝突。然而，其學習曲線也相對較高。如果您的需求相對單純，例如僅需檢查 Label 或 Annotation，使用 YAML 編寫策略的 **Kyverno** 會是更容易上手的替代方案。但若您的目標是跨平台統一策略管理（涵蓋 K8s, Terraform, Envoy 等），OPA 仍然是目前業界最常見的選擇。

## 3. 生產環境配置最佳實踐：Webhook 設定

在生產環境中配置 Webhook 時，最重要的參數之一是 `failurePolicy`。這個參數決定了：「當 Webhook Service (如 OPA) 故障或回應超時的時候，API Server 該怎麼辦？」

這裡存在著安全性與可用性的權衡。若設定為 **Ignore (Fail-open)**，代表當 Webhook 故障時允許請求通過，這能確保服務的高可用性，但也意味著在維修期間，違規的資源可能繞過檢查進入叢集。相反地，若設定為 **Fail (Fail-closed)**，則採取嚴格阻擋策略，直接拒絕請求。這雖然安全性最高，但也帶來風險：一旦 Webhook Service 出問題，與該 Webhook 相關的部署作業可能會受影響。

因此，建議在生產環境中，將 `failurePolicy` 設為 `Fail`，並搭配以下兩種機制來確保安全性與可用性：

1. **排除規則 (Exclude Rules)**：排除特定 Namespace 或資源類型，避免影響關鍵服務。
2. **監控與警報**：監控 Webhook Service 的健康狀態，並在故障時觸發警報。

以防範**死鎖 (Deadlock)** 的發生。

試想一個場景：您的 OPA Pod 故障了，而您將 `failurePolicy` 設為 `Fail`，且沒有設定排除規則。此時 Kubernetes 嘗試重啟 OPA Pod，這會產生一個新的 Pod 建立請求；API Server 收到請求後，發現需要經過 Webhook 檢查，於是嘗試呼叫 OPA；但 OPA 尚未啟動，呼叫失敗；根據 `Fail` 策略，API Server 拒絕了 OPA Pod 的建立請求。結果就是：OPA 因為需要通過自己的檢查才能啟動，導致無法成功啟動。

在啟用嚴格模式 (`Fail`) 時，建議務必配合 **NamespaceSelector** 與 **ObjectSelector** 進行精確過濾。

除了透過 `namespaceSelector` 進行粗粒度的排除（例如排除 `kube-system`），實務上也可以同時使用 **`objectSelector`**。在想檢查帶有特定 Label 的 Pod 的情境，或想明確豁免某些自動生成的 Pod（例如大量且頻繁變動的 CI/CD Runner）的情境，使用 `objectSelector` 可以大幅減少 Webhook 的負載，避免不必要的網路呼叫，這也是防止誤擋關鍵資源的第二道防線。

以下是一個安全的配置範本，展示了如何結合 `namespaceSelector` 與 `objectSelector`：

```yaml
apiVersion: admissionregistration.k8s.io/v1
kind: ValidatingWebhookConfiguration
metadata:
  name: policy-enforcement-webhook
webhooks:
  - name: validate.policy.example.com
    admissionReviewVersions: ["v1"]

    # 現代 K8s Best Practice，確保 Webhook 無副作用
    sideEffects: None

    # 避免讓 API Server 等待過久導致累積大量的 pending requests，產生效能的雪崩效應
    timeoutSeconds: 5

    # 嚴格模式：Webhook 連不上就拒絕請求
    failurePolicy: Fail

    clientConfig:
      service:
        name: my-webhook-service
        namespace: security-tools
        path: "/validate"
      # 必須注入 CA Bundle，通常由 cert-manager 自動處理
      caBundle: "Ci0tLS0tQk..."

    rules:
      - operations: ["CREATE", "UPDATE"]
        apiGroups: ["*"]
        apiVersions: ["*"]
        resources: ["pods", "deployments", "services"]

    # ========================================================
    # 關鍵設定 1：排除 kube-system 與 Webhook 自身的 Namespace
    # ========================================================
    namespaceSelector:
      matchExpressions:
        # 使用 K8s 自動注入的 Label: kubernetes.io/metadata.name
        # 邏輯：選取名稱 "不是" 以下列表的 Namespace
        - key: kubernetes.io/metadata.name
          operator: NotIn
          values:
            - "kube-system" # 排除系統核心組件，避免影響叢集運作
            - "security-tools" # 排除 OPA 自己，防止重啟時發生死鎖

    # ========================================================
    # 關鍵設定 2：使用 ObjectSelector 進行精準過濾
    # ========================================================
    # 場景：豁免帶有特定標籤的 Pod (如緊急救援 Pod 或 CI Runner)
    # 這能減少 Webhook Load，避免不必要的網路呼叫
    objectSelector:
      matchExpressions:
        - key: app.kubernetes.io/exclude-webhook
          operator: NotIn
          values:
            - "true"
```

## 4. K8S 原生機制：ImagePolicyWebhook 與 Cloud Provider 的限制

除了通用的 Webhook 機制，Kubernetes 還有一個專門針對 Image Compliance 的傳統機制，稱為 `ImagePolicyWebhook`。它專注於檢查 Image 的屬性，例如是否擁有 Cosign Signature、是否來自內部的 Harbor Registry，或是掃描後是否存在 Critical Vulnerability。

值得注意的是，`ImagePolicyWebhook` 與前述的 `ValidatingWebhookConfiguration` 在架構上有顯著差異。前者屬於 API Server 的 Startup Flag 配置 (Flag-based)，需要透過 `--admission-control-config-file` 來掛載 Config File。這在自建的 K8s Cluster 中或許不是問題( 需修改 /_etc/kubernetes/manifests/kube-apiserver.yaml_)，但在 Managed K8s Service (如 EKS, AKS, GKE) 中，Cloud Provider 通常不允許 User 修改 Master Node (即雲端環境中不會有 Control Plane 的權限)。

因此，在 Cloud Environment 中，我們幾乎無法使用原生的 `ImagePolicyWebhook`。現代化的替代方案是全面轉向基於 K8s Object (CRD) 動態配置的工具，如 OPA Gatekeeper 或 Kyverno。這也是為什麼在討論定義 Validation 或 Mutation Rule 的標準 K8s Object 時，標準答案通常是 `ValidatingWebhookConfiguration` 與 `MutatingWebhookConfiguration`，而非那些依賴 Static Config 的傳統機制。

## 5. 實戰演練：使用 OPA Gatekeeper 實作 Mutation 與 Validation

Gatekeeper 不僅是 Validating Webhook，近年也引入了 **Mutation** 功能 (Alpha/Beta)，讓我們能透過 CRD 進行變更。

**情境模擬**：
接下來，我們將模擬一間公司的合規需求。公司規定所有新建立的 Namespace 都必須自動標示安全等級為 Baseline，以確保預設的安全性；同時，為了確保成本可追蹤，所有部署的 Pod 都必須包含 `billing` 標籤，否則應予以拒絕。

我們將透過以下步驟實現此需求：

1. **Mutate (變更)**：自動將所有新建立的 Namespace 加上 PSS 標籤 `pod-security.kubernetes.io/enforce: baseline`。
2. **Validate (驗證)**：強制所有 Pod 必須包含 `billing` Label。

### Step 1: 安裝 OPA Gatekeeper

在 Production Environment 中，我們強烈建議使用 **Helm** 進行安裝，以便於日後的版本升級與參數管理。

**方法 A：使用 Helm 安裝 (推薦)**

```shell
# 1. 新增 Gatekeeper Helm Repo
helm repo add gatekeeper https://open-policy-agent.github.io/gatekeeper/charts

# 2. 更新 Repo 資訊
helm repo update

# 3. 安裝 Gatekeeper (預設會開啟 Mutation 功能)
# 安裝至 gatekeeper-system namespace
helm install gatekeeper gatekeeper/gatekeeper \
    --namespace gatekeeper-system \
    --create-namespace

```

**方法 B：使用 Prebuilt Manifest (快速測試)**

若您只是想在本機 (如 Minikube) 快速驗證，可以直接使用 Manifest 安裝。

```shell
kubectl apply -f https://raw.githubusercontent.com/open-policy-agent/gatekeeper/master/deploy/gatekeeper.yaml

```

安裝完成後，請檢查 `gatekeeper-controller-manager` Deployment 是否已成功啟動。

### Step 2: 實作 Mutation (使用 AssignMetadata CRD)

我們希望在 Namespace 建立時，自動注入 Pod Security Standards (PSS) 的標籤。因為我們要修改的是 Object 的 **Metadata** (Labels)，所以必須使用 `AssignMetadata` CRD，而非 `Assign`。

```yaml
# 1-mutation-namespace-pss.yaml
apiVersion: mutations.gatekeeper.sh/v1beta1
kind: AssignMetadata
metadata:
  name: force-pss-baseline
spec:
  match:
    scope: Cluster
    kinds:
      - apiGroups: [""]
        kinds: ["Namespace"]
    # 排除 kube-system 以避免影響系統組件 (可選)
    excludedNamespaces: ["kube-system"]

  # Location: 指定要修改的 Metadata 路徑
  # 注意：因為 key 包含斜線 '/'，必須使用引號包起來
  location: metadata.labels."pod-security.kubernetes.io/enforce"

  parameters:
    assign:
      value: "baseline"
```

執行：`kubectl apply -f 1-mutation-namespace-pss.yaml`

### Step 3: 實作 Validation (使用 ConstraintTemplate 與 Constraint)

Mutation 完成後，進入 Validation 階段。我們需要定義邏輯 (Template) 與參數 (Constraint) 來檢查 Pod Label。

**3.1 定義邏輯 (ConstraintTemplate)**

這是「規則的定義檔」，使用 Rego 語言撰寫。我們定義一個通用的 `K8sRequiredLabels` 模板。

```yaml
# 2-template.yaml
apiVersion: templates.gatekeeper.sh/v1
kind: ConstraintTemplate
metadata:
  name: k8srequiredlabels
spec:
  crd:
    spec:
      names:
        kind: K8sRequiredLabels
      validation:
        openAPIV3Schema:
          properties:
            labels:
              type: array
              items:
                type: string
  targets:
    - target: admission.k8s.gatekeeper.sh
      rego: |
        package k8srequiredlabels

        # 定義 violation 規則：若此規則成立 (return true)，則代表違反策略
        # 回傳值包含 msg (錯誤訊息) 與 details (額外資訊)
        violation[{"msg": msg, "details": {"missing_labels": missing}}] {

          # 1. 取得 Request 物件中現有的 Labels 集合
          # input.review.object 是被驗證的 Kubernetes 物件
          provided := {label | input.review.object.metadata.labels[label]}

          # 2. 取得 Constraint 參數中要求的 Labels 集合
          # input.parameters 是來自 Constraint YAML 的參數
          required := {label | label := input.parameters.labels[_]}

          # 3. 計算缺少的 Labels (集合相減)
          missing := required - provided

          # 4. 如果缺少的數量大於 0，則違反規則成立
          count(missing) > 0

          # 5. 格式化錯誤訊息
          msg := sprintf("you must provide labels: %v", [missing])
        }
```

執行：`kubectl apply -f 2-template.yaml`

**3.2 Dry Run**

在直接強制執行 (Enforce) 之前，最保險的部署方式是先開啟 **Dry Run** 模式。這允許我們觀察現有環境中有多少違規資源，而不實際阻擋請求。

```
# 3-constraint.yaml
apiVersion: constraints.gatekeeper.sh/v1beta1
kind: K8sRequiredLabels
metadata:
  name: require-billing-label
spec:
  # Dry Run 設定：只記錄違規，不拒絕請求
  # 若確認無誤後，可移除此行或改為 "deny" (預設值)
  enforcementAction: dryrun

  match:
    kinds:
      - apiGroups: [""]
        kinds: ["Pod"]
    namespaces: ["default"]
  parameters:
    labels: ["billing"]

```

執行：`kubectl apply -f 3-constraint.yaml`

_註：在 `dryrun` 模式下，違規資訊會顯示在 Constraint 物件的 `status.violations` 欄位中。確認無誤後，可將 `enforcementAction` 移除或改為 `deny` 以正式啟用阻擋功能。_

### Step 4: 驗證 (Verification)

現在，我們同時具備了 Namespace Mutation 和 Pod Validation 能力。讓我們來測試這兩個機制。

**驗證 Mutation (Namespace Label 自動注入)**

1. 建立一個乾淨的 Namespace：

   ```shell
   kubectl create ns project-alpha

   ```

2. 檢查 Label 是否被自動加上：

   ```shell
   kubectl get ns project-alpha -o jsonpath='{.metadata.labels}'

   ```

   **預期結果**：您應該會看到 `"pod-security.kubernetes.io/enforce":"baseline"` 出現在輸出中，證明 Mutation 成功。

**驗證 Validation (Pod Label 強制檢查)**

_假設您已將 enforcementAction 改回 deny_

1. 嘗試建立一個不合規的 Pod (缺少 billing label)：

   ```shell
   kubectl run test-pod --image=nginx --restart=Never
   ```

   **預期結果**：被 Gatekeeper 拒絕。

   > Error from server (Forbidden): admission webhook "validation.gatekeeper.sh" denied the request: [require-billing-label] you must provide labels: {"billing"}

2. 建立合規的 Pod：

   ```shell
   kubectl run test-pod --image=nginx --restart=Never --labels=billing=finance
   ```

   **預期結果**：Pod 成功建立。

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>
