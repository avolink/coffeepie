# COFP Token — Coffee Pie Utility Token (TRC-20)

The COFP Token (symbol: COFP) is the native utility token of the Coffee Pie ecosystem, deployed on the TRON blockchain under the TRC-20 standard for ultra-low fees and fast settlement. It serves as the economic backbone connecting three stakeholder groups: Contributors, Providers, and Investors.

> **Status:** Design and configuration phase. Not yet deployed to TRON mainnet. This mini-project may be revised or replaced if a better solution emerges before deployment.

---

## Token Purpose

COFP is not just a "bookkeeping tool" — it is a full utility token with governance rights and provider fiat settlement. It aligns incentives across the entire Coffee Pie ecosystem. **Token unit: 1 COFP = 1 Coffee Pie® Slice served for 1 minute** (1 Slice·min). Earnings scale linearly: a Provider hosting 4 Slices for 60 minutes earns 4 × 60 = 240 COFP. COFP has an elastic supply — tokens are minted at a fixed rate of 1 COFP per Slice·min as Providers serve real compute resources on the QFDM Network. There is no supply cap; the supply grows with the network. Initial bootstrap supply: 100'000'000 COFP. This is a supply-side token — consumers (end users) never hold or interact with COFP. Consumers operate entirely with Coffee Pie® Credits (Cr).

---

## Holder Classes

### 1. Contributors (Community)
Developers, translators, auditors, pentesters, and community supporters earn COFP by contributing to the Coffee Pie ecosystem.

**Rights:**
- Vote on technical decisions (development stack, deprecation policies, implementation priorities)
- **Wallet holding limit:** 10% of the total COFP supply per wallet, enforced by the Coffee Pie backend
- May sell earned COFP on the TRON open market (TRC-20) — proceeds are the contributor's to keep
- May hold COFP for long-term valuation appreciation and future dividends after IPO
- May burn COFP for Credits at a rate of 10 Cr per COFP
- **Cannot burn COFP for fiat** — that right is exclusive to Trusted Providers

**On secondary sale:** Selling earned COFP on the open market is permitted, but the seller permanently loses all voting rights. The buyer receives an Investor-class token with economic rights only (dividends, valuation) — no governance vote.

### 2. Providers (Datacenter Operators)
Datacenter operators earn COFP by supplying computing resources to the QFDM Network.

**Rights:**
- Vote on regional pricing (average slice cost, electricity rates, labor costs)
- Burn tokens for **fiat currency** transferred to registered bank accounts within 24–72 hours (Trusted Providers only)
- **No burning cap** — providers are selling real resources and need unrestricted cash flow

**On secondary sale:** If a provider transfers COFP to a secondary wallet and sells on the open market, those tokens lose all voting and burning-for-fiat rights. The buyer receives an Investor-class token.

### 3. Investors (Public Markets)
Investors acquire COFP through public markets (target: BVC — Bolsa de Valores de Colombia).

**Rights:**
- Proportional dividends and valuation appreciation
- Binary governance choice: reinvest profits vs. distribute dividends
- No voting rights in technical or operational decisions

---

## Two-Currency Model

Coffee Pie® operates two strictly separate currencies:

**COFP** (TRC-20 on TRON) is the **supply-side token**: only Providers and Contributors earn it. Only Trusted Providers may burn COFP for fiat cash flow (internal ledger operation, transferred to their registered bank account within 24–72 hours). This is not a public token redemption.

**Credits (Cr)** are the **demand-side consumer currency**: end users (consumers) obtain Cr exclusively by:
1. Watching Ads (paid by Advertisers)
2. Purchasing Credit Packages at `coffeepie.co/precios`

Consumers never hold, earn, or interact with COFP directly. Credits are the only currency consumers spend to rent computing Slices.

**Parking Fee:** dormant Slices (powered off or suspended) still reserve storage on a provider's node, so they are billed in Credits at **10 Cr per dormant Slice per hour**. The first 9 dormant Slices per account are free; the fee applies from the 10th dormant Slice and up. See `PROVIDERS.md` for the provider-side settlement.

---

## Governance

**Current state (alpha):** The COFP smart contract currently uses a single `owner` address for administrative functions (`mint`, `pause`, `transferOwnership`). This is appropriate for the pre-deployment design and configuration phase.

**Target state (pre-IPO):** Before any stock exchange listing or mainnet deployment, contract ownership MUST be transferred to a **Gnosis Safe multi-signature wallet** (minimum 4 of 7 signers) with a **48-hour timelock** on all administrative functions. This ensures no single individual holds unilateral control over minting, pausing, or ownership transfer.

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
1. QFDM Royalty Fees for Codec Terminal rentals from manufacturers to third parties
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

- **2035 Target:** Initial Public Offering (IPO) on BVC and tokenization (TRC-20)
- No single individual or entity will hold controlling stakes
- Success measured by positive impact on society and the environment, not just profit
- Guided by stoic and ethical principles

---

*Learn more about becoming a Cloud Provider: https://coffeepie.co/proveedores-nube*
