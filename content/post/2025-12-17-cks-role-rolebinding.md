---
title: "〔CKS 筆記整理〕Kubernetes RBAC 權限管理解析：Role, ClusterRole 與綁定機制全攻略"
subtitle: ""
description: "本文將深入剖析 RBAC 的核心元件，並模擬生產環境中標準的設定與實務建議。"
date: 2025-12-17
author: "Yujie Zheng"
image: ""
tags: ["K8S","Kubernetes","RBAC","Role","Rolebinding","CKS"]
categories: ["Tech"]
---

# 〔CKS 筆記整理〕Kubernetes RBAC 權限管理解析：Role, ClusterRole 與綁定機制全攻略

在 Kubernetes 的安全模型中，如果說 Authentication (認證) 決定了「你是誰」，那麼 RBAC (Role-Based Access Control) 就決定了「你能做什麼」。

RBAC 是 Kubernetes Security 的基礎機制，它解決的核心問題可以用一句話概括：「**誰 (Subject)** 在 **哪裡 (Scope)** 可以對 **什麼 (Resource)** 做 **什麼動作 (Verb)**？」

本文將深入剖析 RBAC 的核心元件，並模擬生產環境中標準的設定與實務建議。

## 1. 定義權限：Role 與 ClusterRole (策略定義)

在 RBAC 的架構中，我們首先需要定義具體的權限內容。Kubernetes 提供了兩種物件來達成此目的。

### 1.1 Role (Namespace Level)

- **定義**：Role 是一個 **Namespaced** (隸屬於特定 Namespace) 的物件。
- **作用範圍**：僅能定義在該 Namespace 內的權限規則。
- **適用場景**：應用程式專屬的權限，例如「允許讀取 `dev` Namespace 的 Pods」。

### 1.2 ClusterRole (Cluster Level)

- **定義**：ClusterRole 是一個 **Non-namespaced** (不分 Namespace) 的物件。
- **作用範圍**：整個 Cluster。
- **適用場景**：
    1. **管理 Cluster-level 資源**：如 Nodes, PersistentVolumes (這些資源本質上不屬於任何 Namespace)。
    2. **非資源端點 (Non-resource endpoints)**：如 `/healthz`, `/metrics`。
    3. **定義通用權限範本 (Template)**：這是提升管理效率的關鍵功能。

### 1.3 Role 與 ClusterRole 比較表

| 特性 | Role | ClusterRole |
| --- | --- | --- |
| **作用範圍 (Scope)** | 特定 Namespace | 整個 Cluster |
| **隸屬 Namespace** | 是 (Namespaced) | 否 (Cluster-wide) |
| **資源類型** | 僅能控制該 Namespace 內的資源 | 可控制 Cluster-level 資源 (Nodes) 與 Namespaced 資源 |
| **典型用途** | 應用程式權限 (如 Pod Reader) | 系統管理員權限、權限範本 (Template) |
| **跨 Namespace 重用** | 不可 (需在每個 NS 重複建立) | 可 (定義一次，處處引用) |

> 實務建議：建立可重用的權限模版
最佳實踐是建立一個共用的 ClusterRole (例如 app-viewer)，然後在各個 Namespace 透過 RoleBinding 引用它。這讓權限管理變成了「中央定義，地方引用」的模式，提升維護性。
> 

## 2. 分發權限：RoleBinding 與 ClusterRoleBinding (綁定機制)

定義好權限策略後，我們需要透過「綁定 (Binding)」將規則授予具體的使用者或服務。

### 2.1 RoleBinding (區域綁定)

- **功能**：將權限授予給 **特定 Namespace 下** 的使用者或 ServiceAccount。
- **關鍵特性**：
    - 它可以引用 `Role`。
    - 它也可以引用 `ClusterRole` (**重點！**)。

**實務應用：使用 ClusterRole 作為範本**

- **場景**：我們希望給予 Bob `view` (讀取) 的權限，但只限制在 `dev` Namespace。
- **實作**：建立一個 RoleBinding 在 `dev` 空間，並引用全域的 `view` ClusterRole。
- **結果**：Bob 雖然擁有標準的讀取權限，但其權限範圍將被嚴格限制在 `dev` Namespace 內。

### 2.2 ClusterRoleBinding (全域綁定)

- **功能**：將權限授予給 **整個 Cluster** 的使用者。
- **風險**：這賦予了極高的權限範圍。一旦綁定，該使用者在「所有 Namespace」都將擁有該權限，若配置不當，容易造成嚴重的安全隱患。
- **適用場景**：
    - 監控系統 (如 Prometheus) 需要讀取所有 Node 和 Pod 的 metrics。
    - CI/CD 系統需要權限在任何地方部署應用。
    - Cluster Admin (cluster-admin)。

## 3. 經典配置範例

經典的配置模式：**定義一次 ClusterRole，在 Namespace 中重複使用**。

### 步驟 1: 定義通用的 ClusterRole (範本)

我們建立一個全域的讀取者角色，允許查看 Pod 和 Log。

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader-global
rules:
- apiGroups: [""] # "" 代表 Core Group (Pod 屬於此群組)
  resources: ["pods", "pods/log"] # 允許看 Pod 和 Log
  verbs: ["get", "list", "watch"]

```

定義好全域範本後，我們可以透過 RoleBinding 將其**限縮**在 specific Namespace 內，而非直接綁定至全域。這樣做的好處是，我們只需要維護一份規則，但可以靈活地分發給不同專案。

### 步驟 2: 在特定 Namespace 綁定 (限制範圍)

接著，我們將這個全域定義的角色，限制在 `development` Namespace 內賦予給 Alice。

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-in-dev
  namespace: development # <--- 關鍵：權限被限制在 development
subjects:
- kind: User
  name: alice # 給 Alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole # <--- 引用上面的全域範本
  name: pod-reader-global
  apiGroup: rbac.authorization.k8s.io

```

## 4. 進階實務細節

即使配置了上述物件，工程實務中仍有幾個細節容易被忽略。

### 4.1 ServiceAccount 的重要性 (應用程式使用)

RBAC 的主體 (Subject) 不僅包含人類使用者 (User)，也涵蓋了在叢集內運行的應用程式 (Workloads)。

- **User**：給真人使用 (由外部 IdP 管理，如 AWS IAM, Google OIDC)。
- **ServiceAccount (SA)**：給 Pod 內的應用程式使用 (K8s 原生物件)。

**最佳實踐**：每個應用程式都應該有自己專屬的 ServiceAccount，並只綁定最小權限。**建議避免讓 Pod 使用 default ServiceAccount**。雖然預設情況下 default SA 沒有權限，但若有人不小心給予了 default SA 權限，所有未指定 SA 的 Pod 都會繼承該權限，這將產生不必要的安全風險。

### 4.2 權限驗證工具：kubectl auth can-i

當開發者詢問：「為什麼我的 Pod 不能讀 Secret？」或「我有權限刪除 Deployment 嗎？」，與其逐行檢查 YAML，不如直接詢問 API Server。

```shell
# 檢查我自己能不能刪除 pod
kubectl auth can-i delete pod

# (管理員專用) 模擬身分檢查
# 檢查 system:serviceaccount:dev:my-app 這個 SA 在 dev 空間能不能讀取 secret
kubectl auth can-i get secret --as=system:serviceaccount:dev:my-app -n dev

```

### 4.3 API Groups 的常見配置錯誤

撰寫 Rules 時，最常發生的錯誤是寫錯 `apiGroups`。

- **Core Group ("")**：Pod, Service, Node, ConfigMap, Secret, PersistentVolume。
- **Apps Group ("apps")**：Deployment, DaemonSet, StatefulSet, ReplicaSet。
- **Batch Group ("batch")**：Job, CronJob。
- **Networking ("networking.k8s.io")**：Ingress, NetworkPolicy。

**錯誤範例**：

```yaml
- apiGroups: [""]
  resources: ["deployments"] # <--- 錯誤：Deployment 不在 Core Group
  verbs: ["get"]

```

這條規則將無法生效，因為 Deployment 屬於 `apps` 群組。正確寫法應為 `apiGroups: ["apps"]`。

> 查詢技巧：若不確定資源屬於哪個群組，可以使用以下指令查詢：
> 
> 
> ```yaml
> # 查詢 deployment 屬於哪個 API Group
> kubectl api-resources | grep deployment
> 
> ```
> 

### 4.4 規模化管理的關鍵：綁定 Group 而非 User

在上述範例中，我們將權限直接綁定給了 `User: alice`，但在大規模生產環境中，這不是最佳做法。

- **管理挑戰**：當團隊擴張，人員流動頻繁時，如果直接綁定 User，SRE 需要不斷修改 RoleBinding YAML 來新增或移除使用者。
- **建議做法**：在正式環境中，可以**綁定 Group**，減少維運的成本。
    - 例如綁定給 `Group: dev-team-leads`。
- **運作機制**：
    - **Group 哪裡來的？** Kubernetes 內部並沒有 `Group` 資源物件。Group 字串通常來自外部認證系統 (如 OIDC Token 中的 `groups` 欄位) 或客戶端證書的 Organization (O) 欄位。
    - 人員管理交由外部 IdP (OIDC, LDAP, Active Directory) 處理。
    - 當 Alice 加入該群組，她自動獲得權限；當 Alice 離開時，只需在 IdP 端移除，她自動失去權限。
    - **優勢**：K8s YAML 完全不用修改，實現權限與人員管理的解耦。

## 5. 總結最佳實務 (Best Practices)

掌握 Kubernetes RBAC 的精髓，不僅在於理解 API 物件的運作，更在於建立一套可持續維護的安全習慣。首要原則即是堅守「最小權限原則 (`Least Privilege`)」。在賦予權限時，我們應始終思考「完成這項任務所需的最小範圍是什麼？」。如果一個應用程式只需要讀取 Pod，就絕對不要給予修改的權限；如果它只在特定 Namespace 運作，就絕不應該使用 `ClusterRoleBinding` 將權限擴及整個 Cluster。這不僅是為了防範惡意攻擊，更是為了降低人為誤操作帶來的衝擊。

此外，善用「ClusterRole 定義範本，RoleBinding 限制範圍」的標準模式，能有效避免 YAML 配置的過多的重複與混亂。在追求方便的同時，我們必須嚴格禁止在生產環境中使用萬用字元 (`*`)。雖然在 `resources` 或 `verbs` 使用 `*` 較為便捷，但這代表賦予了不受限制的權限，容易成為潛在的安全漏洞。

最後，權限管理並非一次性的設定，而是一個持續的維運過程。妥善的權限設計能讓團隊協作更順暢，同時大幅降低人為失誤的風險。

---

<small><em>This Content is Authored by the writer, with AI-assisted proofreading and SEO optimization.</em></small>