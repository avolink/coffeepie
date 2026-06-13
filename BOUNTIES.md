# Coffee Pie Token (COFP) — Contribution & Bounty Program

> **Status: Under construction.** The COFP token has not yet been deployed to TRON mainnet. Bounty rewards will be live once the token is deployed and the bounty platform is operational. Until then, contributions are tracked for future reward allocation.

Welcome to the **Coffee Pie Token (COFP)** contribution program. This ecosystem is designed to reward high-efficiency, results-oriented, and self-managed contributions from developers, auditors, translators, moderators and tech support guiding volunteers, without traditional corporate bureaucracy or hourly tracking. 

We strictly enforce **Goodhart's Law** prevention: We do not reward lines of code (to prevent spaghetti code) or hours worked (to incentivize efficiency and optimization). Contributions are evaluated solely on **complexity, impact, and peer-reviewed quality**.

---

## 1. Core Mechanics & Reward Architecture

### T-Shirt Sizing Framework
Tasks are classified by architectural complexity and impact. Efficient contributors who make refactors and solve high-complexity problems quickly are rewarded for their skill, not their time.

### Peer-Review & Code Quality Alignment
* **The Auditor's Incentive:** Every submission requires an audit. Auditors receive a percentage of the task's base reward. If an auditor identifies a critical inefficiency or a bug before merging, a portion of the developer's reward is dynamically reallocated to the auditor as an optimization bonus.
* **Refactoring & Abstraction Bonuses:** Rewriting an existing module to reduce complexity while maintaining or improving performance (e.g., compressing 500 lines of messy code into 50 elegant lines) qualifies for custom optimization bounties.

### Governance and Liquidity Terms
* **Technical Voting Rights:** Holding COFP tokens in your wallet grants you voting weight regarding the technical direction and architecture of the network. If tokens are moved or sold on the open market (**Tron TRC-20**), technical voting rights are waived.
* **Contributor Token Options:** Contributors who earn COFP may: (a) sell on the TRON open market (TRC-20) — voting rights are permanently waived upon sale; (b) hold for long-term valuation appreciation and future dividends after IPO. Contributors **cannot** burn COFP for fiat — that right is exclusive to Trusted Providers (Datacenter Operators). Consumers (end users) never receive or interact with COFP; they use Coffee Pie® Credits (Cr) obtained by watching Ads or purchasing Credit Packages.
* **No Employment Relationship:** Participation is entirely voluntary, non-exclusive, and task-based. Contributors act as independent operators; there is no subordination or fixed scheduling.

---

## 2. Generic Bounty Categorization

| Size | Eligible Task Types | Criteria of Success | Base Reward |
| :---: | :--- | :--- | :---: |
| **S** *(Small)* | • Minor bug fixes (UI/UX)<br>• Single-page localization/translations<br>• Community moderation (1 week)<br>• Documentation updates | • Zero regression bugs<br>• High-quality, natural translation<br>• Spam-free channels & structured logs | **X COFP** |
| **M** *(Medium)* | • Implementing new Vanilla JS views<br>• Setting up specific Firebase Firestore endpoints<br>• Writing standard unit tests<br>• Basic asset design | • Clean, fully decoupled code<br>• Passing 100% of automated tests<br>• Adherence to architectural guidelines | **2X COFP** |
| **L** *(Large)* | • Refactoring critical backend/network modules<br>• Optimizing Proxmox LXC container configurations<br>• Setting up automated CI/CD deployment pipelines<br>• Designing robust local AI inference tooling integrations | • Medible reduction in system latency/overhead<br>• Fully documented edge cases<br>• Successful peer-review sign-off | **4X COFP** |
| **XL** *(Extra Large)*| • Designing network-wide interoperability standards<br>• Core security architecture auditing<br>• Resolving complex low-level hardware communication layers | • Consensus approval from the Technical Board<br>• Production-stable deployment | **8X COFP** |

---

## 3. High-Value Bounties (Critical Bug Bounty & Vulnerabilities)

This section is dedicated exclusively to the discovery and responsible disclosure of critical vulnerabilities that threaten the financial, structural, or operational stability of the network. 

*Note: Exploiting a bug on live environments disqualifies the contributor from receiving the reward. All high-value discoveries must be reported through our confidential disclosure channel.*

### Vulnerability Tiers & Classification

#### 🚨 Tier 1: Critical Severity (Zero-Day & Network Disruption)
* **Scope:** Zero-day exploits, vulnerabilities causing total service interruption, unauthorized modification of the core protocol, or smart contract logic flaws leading to loss of escrowed assets.
* **Impact:** Immediate threat to the entire ecosystem or financial integrity.
* **Reward Range:** 50'000 to 100'000 COFP

#### 🛡️ Tier 2: High Severity (Security & Data Breaches)
* **Scope:** Flaws allowing the bypass of identity verification (KYC/KYB frameworks), unauthorized access to internal databases (Firebase instances), or manipulation of the COFP token balance tracking.
* **Impact:** Potential data breach or financial leak affecting network validation.
* **Reward Range:** 30'000 COFP

#### ⚠️ Tier 3: Medium Severity (Operational Hazards)
* **Scope:** Vulnerabilities that permit distributed denial of service (DDoS) on individual nodes, localized state machine desynchronization, or partial API blockages.
* **Impact:** Degraded user experience or temporary loss of efficiency for specific infrastructure providers.
* **Reward Range:** 10'000 COFP

---

## 4. How to Submit & Claim
DO NOT make a pull request with the details of the vulnerability, which could cause malicious actors to exploit it before patching.
Write a private email to security@coffeepie.co with all the details and wait for one of our Admins or Moderator to put in contact with your to tankh for your contributtion and assign the bounty to you Coffee Pie Account.