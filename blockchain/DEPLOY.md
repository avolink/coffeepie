# COFP Token — TRC-20 Deployment Guide

## Prerequisites

- [TronLink wallet](https://www.tronlink.org/) browser extension (Chrome/Firefox)
- TRX in wallet for gas (~1'000 TRX covers deployment)
- Contract verified on [Tronscan](https://tronscan.io)

## Step 1 — Prepare the Wallet

1. Install TronLink, create or import a wallet
2. Fund it with TRX (for deployment gas + contract energy)
3. Keep the private key / mnemonic secure — this wallet will be the
   **contract owner** and the initial token holder

## Step 2 — Deploy via Remix IDE

1. Go to https://remix.ethereum.org
2. Create a new file `COFP_Token.sol` and paste the contract
3. Compile: Solidity tab → compiler `0.8.20` → click **Compile**
4. Deploy: Deploy tab → environment **Injected Provider (TronLink)**
5. Constructor arguments:

   | Arg | Value | Rationale |
   |---|---|---|
   | `_initialSupply` | `1'000'000` | 1M COFP seed liquidity |
   | `_targetInflationBasisPoints` | `200` | 2.00% annual inflation target |

6. Click **Transact**, confirm in TronLink

## Step 3 — Verify on Tronscan

1. After deployment, copy the contract address
2. Open https://tronscan.io, search the contract address
3. Go to Contract → Verify & Publish
4. Upload the same Solidity source with compiler 0.8.20
5. Set optimization: **No**

## Step 4 — Monetary Policy

COFP uses an **inflation-targeting** model. Instead of a fixed emission
number, the annual emission cap is a percentage of current total supply.
This auto-scales: growing supply → growing cap, shrinking supply → shrinking cap.

### Emission Formula

```
annualEmissionCap = totalSupply × targetInflationBasisPoints ÷ 10000
```

| Parameter | Value |
|---|---|
| `targetInflationBasisPoints` | 200 (2.00% annual inflation) |
| Allowed range | 100–500 (1%–5%), enforced at contract level |
| Cap behavior | Auto-recalculates every `mint()` call based on current supply |
| Year window | 365 days from deploy or last reset |

### Example

| Total Supply | 2% Cap | Max Mintable/Year |
|---|---|---|
| 1'000'000 | 20'000 | 20'000 COFP |
| 10'000'000 | 200'000 | 200'000 COFP |
| 100'000'000 | 2'000'000 | 2'000'000 COFP |

### Governance

1. `setTargetInflation(150)` → lowers to 1.5% (deflationary stance)
2. `setTargetInflation(300)` → raises to 3.0% (expansionary stance)
3. Community votes on Coffee Pie platform → owner executes on-chain
4. Contract enforces hard bounds: minimum 1%, maximum 5%

### Equilibrium Mechanism

```
Burning drives supply down → cap drops automatically → less new COFP
→ COFP appreciates → burning slows → supply stabilizes

Emission drives supply up → cap rises → more COFP available
→ providers/contributors rewarded → network grows → burning increases
```

### Central Bank Role

- **Algorithmic**: base emission = supply × target rate (automatic)
- **Community-governed**: target rate adjustable by vote within 1-5% band
- **Emergency**: `pause()` freezes all transfers, `unpause()` restores
- **Execution**: Coffee Pie backend mints to reward providers/contributors within cap

| Parameter | Value |
|---|---|
| Name | Coffee Pie |
| Symbol | COFP |
| Decimals | 6 |
| Standard | TRC-20 (TRON) |
| Initial Supply | 21'000'000 COFP |
| Burnable | Yes (by holder or approved spender) |
| Governance | Off-chain (Coffee Pie Platform) |
| Trading | BVC Stock Exchange (planned) |

## Step 5 — Backend Integration

The Coffee Pie backend interacts with the contract for:

1. **Provider settlement** — reads contract for provider wallet balances,
   burns tokens via `burnFrom()` when provider requests fiat withdrawal
2. **Contributor credit burning** — burns tokens via `burn()` when
   contributor exchanges COFP for Platform Credits (Cr), capped per account
3. **Distribution** — mints/distributes COFP to contributors and providers
   via regular `transfer()` calls

### TRON RPC Endpoints (for backend)

```
Mainnet: https://api.trongrid.io
Shasta Testnet: https://api.shasta.trongrid.io
```

### TRC-20 Contract Functions Used

```
balanceOf(address)         → read token balance
transfer(address, uint256) → distribute tokens
burn(uint256)              → contributor credit burning
burnFrom(address, uint256) → provider fiat settlement
transferOwnership(address) → admin rotation
```

## Step 6 — Post-Deployment Checklist

- [ ] Contract address recorded and backed up
- [ ] Verified on Tronscan
- [ ] TronLink wallet private key stored securely (cold storage recommended)
- [ ] Test burn + test mint on Shasta testnet before mainnet
- [ ] **Transfer ownership to Gnosis Safe multi-sig wallet** (MANDATORY before BVC listing — minimum 4/7 signers: Core Dev Lead, Legal Counsel, Community Representative, CFO, Cold Storage Key, External Auditor, Emergency Trustee)
- [ ] **Enable 48-hour timelock on all `onlyOwner` functions** — prevents single-key compromise from instantly draining the contract
- [ ] **Document signer succession plan** — each signer designates a successor who inherits their key on verified death/incapacity (notarized letter + 30-day waiting period). The 4/7 threshold tolerates up to 3 lost keys before the contract freezes, providing decades of operational safety
- [ ] Deploy monitoring: alert on every `mint()`, `burn()`, `pause()`, `transferOwnership()` event
- [ ] Add contract address to Coffee Pie backend `.env`
- [ ] Publish token info on https://coffeepie.co/token
