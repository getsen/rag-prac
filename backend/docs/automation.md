# **HP Automation Platform (HAP) & NativeEdge**

* **HP Automation Platform (HAP)** is HP’s unified orchestration software to automate deployment and management of infrastructure across private cloud and edge environments. HAP provides a centralized **portal** and an **orchestrator** with validated **blueprints** for consistent operations at scale.

* **HP NativeEdge** (an outcome delivered via HAP) is a full-stack edge solution for secure deployment, orchestration, and lifecycle management of edge workloads and devices. It employs **zero-touch onboarding** (using FIDO Device Onboarding) and zero-trust security to onboard “NativeEdge Endpoints” (servers, gateways, workstations) and manage them centrally.

* This document is **exhaustive and implementation-focused**, covering architecture, installation (SaaS vs on-premises, connected vs air-gapped), supported hardware, identity/security, onboarding steps, operations/observability, a detailed feature-by-feature catalog (with usage, configs, logs, security, failure modes, and test cases), APIs/CLIs, troubleshooting guides, test strategy, performance considerations, glossary, and known gaps.

---

## **A. Overview**

* **HAP Overview:** HP Automation Platform centralizes IT automation, offering blueprint-based provisioning of software on HP hardware and unified management across clouds and edge. It accelerates tech adoption and simplifies operations via automation and integration across onboarding, deployment, and lifecycle management.

* **NativeEdge Overview:** HP NativeEdge is the edge-focused component of HAP, delivering secure, remote lifecycle management for edge infrastructure and applications. It enables consistent, zero-touch deployment of edge endpoints and workloads, leveraging factory-provisioned trust (FDO vouchers) and late binding of OS/app configurations.

* **Key Benefits:** HAP and NativeEdge together simplify private cloud and edge deployments with validated solutions (VMware, OpenShift, AI stacks), automation of manual steps, and built-in security (zero-trust principles, credential management, role-based access). Organizations can evolve faster, operate at scale with confidence, and integrate these tools into existing IT processes (via APIs and ITSM hooks).

---

## **HAP in Context of Modern IT Needs**

HP Automation Platform addresses the complexity of hybrid IT by providing a one-stop automation hub. Instead of manually installing and configuring private cloud software or edge stacks on each piece of hardware, operators use HAP’s **validated blueprints** and orchestrator to do it reliably at scale. This reduces time-to-value and human error by eliminating repetitive tasks via automation.

HAP’s design acknowledges that enterprises operate across data centers, clouds, and far-edge sites. It therefore supports deploying on disaggregated infrastructure (for **HP Private Cloud**), optimized AI platforms (for **HP AI Solutions**), and remote/edge devices (via **HP NativeEdge**).

---

## **NativeEdge in Context of Edge Computing**

HP NativeEdge specifically focuses on challenges at edge locations (retail stores, factories, remote sites) where IT resources and hands-on support are limited. It provides a **secure, centralized way to manage distributed edge endpoints and their workloads**.

Key capabilities include **zero-touch onboarding** of devices using hardware-rooted trust (devices come with cryptographic identity/vouchers), automated provisioning of the device’s OS and application stack once trust is established, and continuous lifecycle management (updates, monitoring, recovery) from a central orchestrator.

By using zero-trust architecture, all communications and deployments are secured (mutual TLS, certificate-based identity) to mitigate threats common in edge environments. NativeEdge extends enterprise-grade features like high availability and software-defined storage (SDS) out to the edge devices, enabling local clusters and resilience even at remote sites.

---

## **B. Architecture & Components**

### **HAP High-Level Architecture Diagram**

```
┌─────────────────────────────────────────────────────────────────┐
│                     HAP Control Plane                            │
│                  (On-Premises or SaaS)                           │
│                                                                   │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │   Web Portal     │  │   Orchestrator   │  │   Credential │   │
│  │   & Dashboard    │  │   & Scheduler    │  │   Vault      │   │
│  └────────┬─────────┘  └────────┬─────────┘  └──────────────┘   │
│           │                     │                                │
│  ┌────────┴─────────────────────┴──────────────────────────┐    │
│  │         Blueprint Engine & State Management             │    │
│  │  (YAML/JSON Processing, Validation, Execution)        │    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                   │
└─────────────────────┬──────────────────────────────────────────┘
                      │
                      │ (Secure APIs / mTLS)
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        v             v             v
   ┌─────────┐  ┌──────────┐  ┌──────────┐
   │ Agent A │  │ Agent B  │  │ Agent C  │
   └────┬────┘  └────┬─────┘  └────┬─────┘
        │            │             │
   [Endpoint 1] [Endpoint 2]  [Endpoint 3]
   (HP ProLiant) (EdgeLine)   (3rd Party)
```

### **NativeEdge Zero-Touch Onboarding Flow**

```
Device Manufacturing          Device Deployment             Device Operational
─────────────────────────────────────────────────────────────────────────

┌──────────────────┐         ┌──────────────────┐        ┌──────────────┐
│ Device at Factory│         │ Device at Site   │        │ Device Active│
│ - TPM provisioned│         │ - Powered on     │        │ - Reporting  │
│ - FDO Voucher    │         │ - Network access │        │ - Monitoring │
│   embedded       │         │                  │        │ - Ready for  │
└────────┬─────────┘         └────────┬─────────┘        │   workloads  │
         │                            │                  └──────────────┘
         │ Shipped to site            │ FDO Ownership
         │                            │ Transfer Protocol
         │                   ┌────────v─────────┐
         │                   │ NativeEdge       │
         │                   │ Controller       │
         │                   │ (Secure Identity)│
         │                   └────────┬─────────┘
         │                            │
         │                  Config Binding & Provisioning
         │                            │
         ├───────────────────────────>│
                                      │
                            ┌─────────v──────────┐
                            │ OS + App Stack     │
                            │ Download & Install │
                            │ (mTLS Secured)     │
                            └────────┬───────────┘
                                     │
                                     v
                          ┌────────────────────┐
                          │ Agent Installed    │
                          │ Configuration Set  │
                          │ Ready for Ops      │
                          └────────────────────┘
```

### **HAP Architecture**

* **Central Orchestrator:** The HAP orchestrator runs in a control plane (on-premises or SaaS) and manages all deployment requests, blueprint execution, and lifecycle operations. It communicates with endpoints and agents via secure APIs.

* **Portal & UI:** A web-based interface allows operators to browse blueprints, create deployments, manage credentials, monitor progress, and configure policies. The portal provides role-based access control (RBAC) for multi-team environments.

* **Blueprint Engine:** HAP's core is a template-driven provisioning system. Blueprints are authored in YAML/JSON and define the sequence of steps (infrastructure setup, software installation, configuration) for deploying a specific solution. Blueprints encapsulate best practices and reduce deployment variance.

* **Agent Layer:** Lightweight agents deployed on endpoints communicate with the orchestrator, execute deployment steps, report status, and handle recovery. Agents are stateless, allowing for seamless recovery on restart.

* **Credential Management:** HAP provides a secure vault for storing and managing credentials (SSH keys, API tokens, certificates) used during deployment and operations. Credentials are encrypted at rest and in transit.

### **NativeEdge Components**

* **NativeEdge Controller:** A central management service that orchestrates zero-touch onboarding, endpoint enrollment, and lifecycle management of edge devices. The controller integrates with HAP's orchestrator for unified management.

* **NativeEdge Endpoint Software:** Lightweight software stack installed on edge devices (servers, gateways) post-onboarding. It handles local operations, reporting, and communication with the controller.

* **FDO (FIDO Device Onboarding) Integration:** NativeEdge leverages FIDO standards for secure device bootstrapping. Devices come with FDO vouchers (factory-provisioned cryptographic material) that enable zero-touch onboarding without manual credential entry.

* **Configuration Management Service:** Handles deferred configuration binding, allowing devices to receive their final OS and application settings after trust establishment. This "late binding" enables factory-flexible provisioning.

---

## **C. Installation & Deployment Models**

### **HAP Deployment Models Comparison**

```
┌──────────────────────────────────────────────────────────────────────┐
│                    HAP DEPLOYMENT ARCHITECTURES                       │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│ SaaS MODEL                 ON-PREMISES MODEL      HYBRID MODEL        │
│ ──────────────────────────────────────────────────────────────────   │
│                                                                        │
│ ┌──────────────────┐   ┌────────────────────┐  ┌─────────────────┐  │
│ │   HP Cloud       │   │ Customer Data Ctr  │  │   HP Cloud      │  │
│ │ ┌────────────┐   │   │ ┌──────────────┐   │  │ (Portal/SaaS)   │  │
│ │ │  Portal    │   │   │ │ Orchestrator │   │  └────────┬────────┘  │
│ │ │Orchestrator│   │   │ │    & Portal  │   │           │           │
│ │ │   &Data    │   │   │ │  &  Database │   │ ┌─────────v─────────┐ │
│ │ └─────────┬──┘   │   │ └────────┬─────┘   │ │On-Premises        │ │
│ │           │      │   │          │         │ │Orchestrator       │ │
│ └───────────┼──────┘   └──────────┼─────────┘ └──────────┬────────┘ │
│             │                     │                      │           │
│    Agents on Customer Sites     Agents on           Agents on       │
│    (connected via API)      Customer Sites      Customer Sites      │
│                              (local control)    (federated)         │
│                                                                        │
│ Advantages:          Advantages:          Advantages:                │
│ • Low ops burden     • Full control       • Best of both             │
│ • Auto updates       • Data residency     • Flexibility              │
│ • High availability  • Air-gap capable    • Scalability              │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### **Network Connectivity Models**

```
┌─────────────────────────────────────────────────────────────────┐
│               HAP NETWORK CONNECTIVITY MODES                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│ CONNECTED (Online)          AIR-GAPPED (Offline)                │
│ ───────────────────         ──────────────────                   │
│                                                                   │
│   HAP Orchestrator          HAP Orchestrator                     │
│   on Internet/Cloud         (Local or Remote)                    │
│         │                          │                             │
│         │ Real-time API            │ Pre-staged                  │
│         │ connections              │ & Queued                    │
│         v                          v                             │
│    ┌─────────┐              ┌──────────────┐                    │
│    │ Agent A │              │ Agent A      │                    │
│    │ Agent B │              │ Agent B      │                    │
│    │ Agent C │              │ Agent C      │                    │
│    └─────────┘              └──────────────┘                    │
│                                   │                              │
│ • Live logs                   Syncs via:                        │
│ • Real-time updates           • Removable media                 │
│ • Immediate responses          • Periodic gateways              │
│ • Remote troubleshooting      • Store-and-forward               │
│                                                                   │
│                                                                   │
│ HYBRID CONNECTIVITY                                              │
│ ───────────────────                                              │
│                                                                   │
│    ┌─────────────────────────────────────────┐                 │
│    │  HAP Orchestrator (Control Plane)       │                 │
│    └──────────────┬──────────────────────────┘                 │
│                   │                                              │
│         ┌─────────┼─────────┐                                   │
│         │                   │                                   │
│    [Online Sites]    [Proxy Gateway]   [Air-Gapped Sites]      │
│    Direct API            │                 Connected via        │
│    connections      Bridges secure         Secure Tunnel       │
│                    communication                                │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### **HAP Deployment Options**

* **SaaS Model:** HAP offered as a managed service via HP Cloud. Simplifies operational overhead, automatic updates, and built-in redundancy. Organizations connect their on-premises infrastructure to the SaaS portal via secure APIs.

* **On-Premises Model:** HAP orchestrator and portal deployed within an organization's data center. Provides full control, compliance with data residency requirements, and air-gap capability. Requires IT teams to manage the orchestrator's HA, backups, and updates.

* **Hybrid Model:** Combines SaaS portal for ease of use with on-premises orchestrator for compliance and control. API federation allows blueprints authored in SaaS to deploy via on-premises orchestrator.

### **Network Connectivity Models**

* **Connected (Online) Deployments:** HAP endpoints and agents maintain persistent, real-time connectivity with the orchestrator. Enables live streaming of logs, real-time updates, and immediate response to orchestrator commands.

* **Air-Gapped (Offline) Deployments:** HAP components operate in isolated networks without internet access. Blueprint packages, agent software, and credentials are pre-staged or transferred via secure removable media. Orchestrator maintains queued jobs and syncs state when connectivity is restored.

* **Hybrid Connectivity:** Some locations online, others air-gapped. HAP orchestrator can manage both via gateways (proxy agents at network boundaries) that bridge secure communication.

### **Supported Hardware**

* **HP ProLiant Servers:** Full support for Gen10 Plus and newer, with optimized drivers and firmware. HAP blueprints include BIOS/firmware configuration for optimal performance.

* **HP EdgeLine Gateways:** Purpose-built edge devices with rugged design, extended temperature range, and integrated cellular/network options. NativeEdge provides streamlined provisioning for EdgeLine platforms.

* **Third-Party Hardware:** While optimized for HP hardware, HAP and NativeEdge can be deployed on certified third-party infrastructure (Dell, Lenovo, etc.) with reduced support and longer validation cycles.

* **Storage Devices:** HAP integrates with HP StoreEasy and other SDS platforms for distributed storage scenarios, crucial for edge deployments requiring local data persistence.

---

## **D. Security & Identity Management**

### **Zero-Trust Security Architecture**

```
┌──────────────────────────────────────────────────────────────────────┐
│              HAP ZERO-TRUST SECURITY MODEL                            │
├──────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  HARDWARE-ROOTED TRUST (FDO)                                         │
│  ──────────────────────────                                          │
│                                                                        │
│  ┌─────────────────────────┐      ┌─────────────────────────┐       │
│  │  Device from Factory    │      │  Device at Customer     │       │
│  │  ┌───────────────────┐  │      │  ┌───────────────────┐  │       │
│  │  │ TPM/Secure Area  │  │      │  │ TPM/Secure Area  │  │       │
│  │  │ ┌─────────────┐  │  │      │  │ ┌─────────────┐  │  │       │
│  │  │ │ Private Key │  │  │      │  │ │ Private Key │  │  │       │
│  │  │ │ FDO Voucher │  │  │      │  │ │ (Derived)   │  │  │       │
│  │  │ │ Hardware ID │  │  │      │  │ │ Public Cert │  │  │       │
│  │  │ └─────────────┘  │  │      │  │ └─────────────┘  │  │       │
│  │  └───────────────────┘  │      │  └────────┬────────┘  │       │
│  └──────────────┬──────────┘      └───────────┼──────────┘       │
│                 │                             │                    │
│                 │ FDO Ownership Transfer      │                    │
│                 │ Protocol (Secure)           │                    │
│                 └────────────────┬────────────┘                    │
│                                  v                                  │
│                      ┌──────────────────────┐                      │
│                      │ NativeEdge Controller│                      │
│                      │ ┌────────────────┐   │                      │
│                      │ │ Trust Database │   │                      │
│                      │ │ Cert Management│   │                      │
│                      │ └────────────────┘   │                      │
│                      └──────────┬───────────┘                      │
│                                 │                                  │
│  ─────────────────────────────────────────────────────────────    │
│                                                                     │
│  END-TO-END COMMUNICATION SECURITY                                 │
│  ──────────────────────────────────                                │
│                                                                     │
│  ┌──────────────────┐              ┌──────────────────┐           │
│  │ Orchestrator     │              │ Agent            │           │
│  │ (Cert: server-1) │              │ (Cert: agent-2)  │           │
│  └────────┬─────────┘              └────────┬─────────┘           │
│           │                                  │                     │
│           │ mTLS Handshake                  │                     │
│           │ (Mutual authentication)         │                     │
│           ├─────────────────────────────────>                     │
│           │ Server cert verified by agent   │                     │
│           <─────────────────────────────────┤                     │
│           │ Agent cert verified by server   │                     │
│           │                                  │                     │
│           ├─────────────────────────────────>                     │
│           │ Encrypted Session               │                     │
│           │ (TLS 1.3)                       │                     │
│           <─────────────────────────────────┤                     │
│           │                                  │                     │
│  ─────────────────────────────────────────────────────────────    │
│                                                                     │
│  CREDENTIAL MANAGEMENT                                              │
│  ─────────────────────                                              │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │        Credential Vault (HSM-backed)                        │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │   │
│  │  │ SSH Keys     │  │ API Tokens   │  │ Certificates │     │   │
│  │  │ (Encrypted)  │  │ (Encrypted)  │  │ (Encrypted)  │     │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘     │   │
│  │                                                             │   │
│  │  Access Controls: RBAC + Audit Logging                     │   │
│  │  - Inject only when needed                                 │   │
│  │  - Log all credential access                               │   │
│  │  - Auto-rotate sensitive material                          │   │
│  └────────────────────────────────────────────────────────────┘   │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

### **Deployment Security Workflow**

```
┌─────────────────────────────────────────────────────────────────┐
│            BLUEPRINT EXECUTION SECURITY CHECKS                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│   Operator Submits Blueprint                                     │
│           │                                                      │
│           v                                                      │
│   ┌─────────────────────────────────┐                           │
│   │ Step 1: Blueprint Validation     │                           │
│   │ - Schema validation              │                           │
│   │ - Syntax check                   │                           │
│   │ - Signature verification         │                           │
│   └──────────────┬──────────────────┘                           │
│                  │ (Signed blueprints only proceed)             │
│                  v                                               │
│   ┌─────────────────────────────────┐                           │
│   │ Step 2: Approval Workflow        │                           │
│   │ - Check RBAC permissions         │                           │
│   │ - Multi-level approvals          │                           │
│   │ - Risk scoring                   │                           │
│   └──────────────┬──────────────────┘                           │
│                  │ (Required approvals obtained)                │
│                  v                                               │
│   ┌─────────────────────────────────┐                           │
│   │ Step 3: Credential Injection     │                           │
│   │ - Retrieve from vault            │                           │
│   │ - Decrypt credentials            │                           │
│   │ - Inject into blueprint context  │                           │
│   │ - Log access                     │                           │
│   └──────────────┬──────────────────┘                           │
│                  │ (Credentials prepared)                       │
│                  v                                               │
│   ┌─────────────────────────────────┐                           │
│   │ Step 4: Endpoint Verification    │                           │
│   │ - Verify agent certificate       │                           │
│   │ - Check endpoint compliance       │                           │
│   │ - Validate configuration state   │                           │
│   └──────────────┬──────────────────┘                           │
│                  │ (Endpoint trusted)                           │
│                  v                                               │
│   ┌─────────────────────────────────┐                           │
│   │ Step 5: Deployment Execution     │                           │
│   │ - Secure mTLS connection         │                           │
│   │ - Execute provisioning steps     │                           │
│   │ - Log all actions                │                           │
│   │ - Monitor for anomalies          │                           │
│   └─────────────────────────────────┘                           │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘
```

### **Zero-Trust Architecture**

* **Mutual Authentication:** Every communication between orchestrator, agents, and endpoints requires mutual TLS (mTLS) verification. Certificates are distributed securely and rotated automatically.

* **Least Privilege Access:** RBAC policies enforce that users and service accounts have only the minimum permissions needed. Fine-grained role definitions cover blueprint authoring, deployment approval, operational visibility, and credential management.

* **Encrypted Credentials:** All secrets (SSH keys, API tokens, database passwords) are stored in an HSM-backed vault with encryption at rest. Credentials are injected into deployments only when needed and logged access is audited.

* **Audit Logging:** All significant actions (deployments, credential access, policy changes) are logged immutably with timestamps and user attribution for compliance and forensic analysis.

### **Hardware-Rooted Trust (FDO)**

* **Factory Vouchers:** Devices shipped from HP manufacturing carry cryptographically signed FDO vouchers tied to hardware identity (TPM-based or embedded). This establishes trust without manual credential provisioning.

* **Ownership Transfer:** When a customer receives a device, ownership is transferred via an FDO protocol exchange with HAP's controller. Device and controller establish secure identity without any out-of-band manual setup.

* **Post-Onboarding Security:** Once onboarded, the device's TPM or secure enclave maintains local key material for subsequent secure communications, preventing man-in-the-middle attacks even if the network is compromised.

### **Deployment-Time Security**

* **Blueprint Signing:** Blueprints can be digitally signed by authorized operators. The orchestrator verifies signatures before execution, preventing unauthorized blueprint modifications.

* **Approval Workflows:** Large or sensitive deployments can require multi-level approvals (e.g., network team approves network blueprint, then security team approves overall deployment) via workflow policies.

---

## **E. Onboarding & Provisioning**

### **Zero-Touch Onboarding Flow for NativeEdge**

* **Step 1 - Staging:** Device is manufactured with FDO voucher, shipped directly to deployment site. IT operator powers on device and connects it to network.

* **Step 2 - FDO Initial Phase:** Device discovers HAP's NativeEdge controller (via DHCP, mDNS, or pre-configured). Device and controller perform FDO ownership transfer protocol, establishing secure identity.

* **Step 3 - Configuration Binding:** Device enrolls with controller and receives its assigned blueprint/configuration. Controller performs late binding: specifies hostname, network settings, OS image URL, and application stack.

* **Step 4 - Provisioning:** Device downloads OS image and application stack from HAP's distribution service (or pre-positioned local mirrors), applies configurations, and reboots. Agent software is installed automatically.

* **Step 5 - Verification & Handoff:** Device reports successful provisioning completion. IT operator verifies via HAP portal. Device is ready for workload deployment.

### **Traditional Onboarding (When Manual Intervention Needed)**

* **PXE Boot with HAP Agent:** Device is configured to PXE boot, HAP server provisions a minimal OS + agent. Operator uses HAP portal to assign final configuration and trigger provisioning.

* **Kickstart/Cloud-Init:** Pre-configured bootstrap scripts (Kickstart for Linux, cloud-init) download HAP agent, join the orchestrator, and wait for deployment blueprint assignment.

### **Provisioning Blueprint Elements**

* **OS Selection & Configuration:** Blueprint specifies Linux distribution/version, kernel parameters, storage layout, and network interfaces. HAP includes validated images or can use customer-provided images.

* **Software Stack:** Sequential installation of software packages (container runtime, Kubernetes, middleware, applications) with version pinning and dependency resolution.

* **Configuration Management:** Post-install configuration of services, config files, and environment variables. Templates support dynamic substitution based on device role/location.

---

## **F. Operations & Observability**

### **Deployment Monitoring**

* **Real-Time Progress Tracking:** HAP portal displays live progress of ongoing deployments with detailed step-by-step logs. Operators can pause/resume or troubleshoot in real-time.

* **Log Aggregation:** All agent logs, orchestrator logs, and deployment logs are centralized, searchable, and indexed. Time-series data enables historical analysis and trend detection.

* **Health Dashboards:** Pre-built dashboards show endpoint health, deployment success rates, resource utilization, and SLA compliance. Custom dashboards can be created for specific operational needs.

### **Operational Management**

* **Patch Management:** HAP can orchestrate OS patches, firmware updates, and application updates across fleet of endpoints. Supports canary deployments (test on subset first) and rollback procedures.

* **Configuration Drift Detection:** Agents periodically report endpoint configuration state. HAP detects deviations from blueprint (configuration drift) and can trigger remediation or alert operators.

* **Backup & Restore:** Integrated with storage systems to create automated backups of application data and configurations. Restore procedures are tested and validated.

### **High Availability & Disaster Recovery**

* **Endpoint Redundancy:** NativeEdge endpoints can be deployed in HA pairs or clusters with automatic failover. Orchestrator monitors health and redirects workloads on failure.

* **Orchestrator Redundancy:** HAP orchestrator itself is deployed with multiple replicas behind a load balancer. Database state is replicated for consistency.

* **Disaster Recovery Plans:** HAP supports multi-site deployments with automated failover and data replication. RTO/RPO targets are configurable per deployment.
