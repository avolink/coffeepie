# COFP Token — Coffee Pie Utility Token (TRC-20)

The COFP Token (symbol: COFP) is the native utility token of the Coffee Pie ecosystem, deployed on the TRON blockchain under the TRC-20 standard for ultra-low fees and fast settlement. It serves as the economic backbone connecting three stakeholder groups: Contributors, Providers, and Investors.

> **Status:** Design and configuration phase. Not yet deployed to TRON mainnet. This mini-project may be revised or replaced if a better solution emerges before deployment.

---

## Token Purpose

COFP is not just a "bookkeeping tool" — it is a full utility token with governance rights, platform credit conversion, and provider settlement. It aligns incentives across the entire Coffee Pie ecosystem.

---

## Holder Classes

### 1. Contributors (Community)
Developers, translators, auditors, pentesters, and community supporters earn COFP by contributing to the Coffee Pie ecosystem.

**Rights:**
- Vote on technical decisions (development stack, deprecation policies, implementation priorities)
- Burn tokens for **Platform Credits (Cr)** to consume computing power on the QFDM Network
- **Burning cap:** 100,000 COFP per wallet per month (enforced by Coffee Pie backend, not the smart contract)

**On secondary sale:** Selling earned COFP on the open market is permitted, but the seller permanently loses all voting rights. The buyer receives an Investor-class token with economic rights only (dividends, valuation) — no governance vote.

### 2. Providers (Datacenter Operators)
Datacenter operators earn COFP by supplying computing resources to the QFDM Network.

**Rights:**
- Vote on regional pricing (average slice cost, electricity rates, labor costs)
- Burn tokens for **fiat currency** transferred to registered bank accounts within 24–72 hours
- **No burning cap** — providers are selling real resources and need unrestricted cash flow

**On secondary sale:** If a provider transfers COFP to a secondary wallet and sells on the open market, those tokens lose all voting and burning-for-fiat rights. The buyer receives an Investor-class token.

### 3. Investors (Public Markets)
Investors acquire COFP through public markets (target: BVC — Bolsa de Valores de Colombia).

**Rights:**
- Proportional dividends and valuation appreciation
- Binary governance choice: reinvest profits vs. distribute dividends
- No voting rights in technical or operational decisions

---

## Platform Credits (Cr)

COFP tokens are convertible into **Platform Credits (Cr)** via a one-way burning mechanism: holders may irreversibly retire their tokens (and all associated economic rights) in exchange for immediately spendable credits — analogous to a company repurchasing shares with service obligations instead of cash.

---

## Governance

The COFP smart contract is governed by a **Gnosis Safe multi-signature wallet** (minimum 4 of 7 signers) with a **48-hour timelock** on all administrative functions. This is mandatory before any stock exchange listing — no single individual may hold unilateral control over minting, pausing, or ownership transfer.

**Signers:**
- Core Development Lead
- Legal Counsel
- Community Representative
- CFO
- Cold Storage Key Holder
- External Auditor
- Emergency Trustee

---

## Monetization Model

COFP is backed by five transparent revenue streams:
1. Licenses and royalties for Codec Terminal rentals from manufacturers to third parties
2. Sale of highly segmented advertising spaces to advertisers
3. Alliances with public sector, educational entities, libraries, and NGOs
4. Manufacturer services: maintenance, repair, restore, recycling and final disposal
5. Direct consumers who prefer ad-free access or need high-end computing resources

---

## Files

| File | Description |
|------|-------------|
| `COFP_Token.sol` | Smart contract (Solidity, TRC-20) |
| `DEPLOY.md` | Deployment guide for TRON mainnet |

---

## Long-Term Vision

- **2035 Target:** Initial Public Offering (IPO) on BVC or tokenization (TRC-20)
- No single individual or entity will hold controlling stakes
- Success measured by positive impact on society and the environment, not just profit
- Guided by stoic and ethical principles

---

*Learn more about becoming a Cloud Provider: https://coffeepie.co/proveedores-nube*
