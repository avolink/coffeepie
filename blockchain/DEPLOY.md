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
5. The constructor takes **no arguments** — supply is fixed at deploy time
6. Click **Transact**, confirm in TronLink

## Step 3 — Verify on Tronscan

1. After deployment, copy the contract address
2. Open https://tronscan.io, search the contract address
3. Go to Contract → Verify & Publish
4. Upload the same Solidity source with compiler 0.8.20
5. Set optimization: **No**

## Step 4 — Monetary Policy

COFP uses a **fixed-supply** model. The total supply is hard-capped at
100'000'000 COFP (represented internally as 100'000'000 × 10^18 sub-units
with 18 decimal places — the maximum TRC-20 precision).

### Why Fixed Supply?

Coffee Pie is a company, not a central bank. Its token represents equity
and service value in the QFDM ecosystem, not a national currency.

**No inflation.** The supply never grows beyond 100M COFP. This preserves
purchasing power for all token holders and eliminates the community-governed
inflation debate — there is no "target rate" to argue over, no emission
schedule to game, no dilution of early supporters.

**No deflation.** Burning reduces supply (tokens irreversibly retired for
fiat settlement, platform credits, or other utility), but the owner can
restore supply via `remint()` up to the original 100M cap. This prevents
a runaway deflationary spiral where all tokens eventually vanish.

### Decimals: Maximum Precision (18 decimal places)

| Property | Value |
|---|---|
| `decimals` | 18 |
| 1 COFP (display) | 10^18 sub-units |
| Minimum unit | 0.000000000000000001 COFP |

COFP uses the TRC-20 standard maximum of 18 decimal places — the same
precision as ETH (1 ETH = 10^18 wei). Users think in whole tokens for
everyday use (rewards, voting, settlement), while the sub-unit precision
handles any fractional scenario at any scale:

- Micro-rewards for sub-second compute sessions (fraction of a vCPU-second)
- Proportional dividend payouts across millions of micro-holders
- AI inference micro-transactions (pay per token generated)
- Dust-level precision for IoT sensor data streaming credits

The 18-decimal architecture ensures the token remains viable at
**planetary scale** — if one day COFP represents fractional ownership
in individual compute cycles across billions of codec terminals, the
sub-unit granularity will be there from day one.

### Remint Mechanism

```
remint(address _to, uint256 _value) — onlyOwner
  └→ Only succeeds if totalSupply + _value <= MAX_SUPPLY
```

| Scenario | Action |
|---|---|
| Tokens burned for fiat settlement | `remint()` restores supply for new rewards |
| Tokens burned for platform credits | `remint()` keeps reward pool full |
| Supply at 100M (no burns) | `remint()` reverts — nothing to restore |
| Supply below 100M | `remint()` fills the gap to reward providers/contributors |

The remint function is NOT inflation — it only replaces what was burned.
The network can never exceed 100M COFP in circulation.

### Supply Lifecycle

```
Deploy: 100M → owner wallet
  ↓
Distribute: owner → providers, contributors, early supporters
  ↓
Burn: providers burn for fiat, contributors burn for credits
  ↓  (supply drops below 100M)
Remint: owner restores burned supply → redistribute to new providers/contributors
  ↓
Repeat: supply oscillates between 100M and (100M - burned), never exceeds 100M
```

### Emergency

- `pause()` freezes all transfers — emergency circuit breaker
- `unpause()` restores transfers — community vote required before execution
- `transferOwnership()` must go to Gnosis Safe multi-sig (see Step 6)

| Parameter | Value |
|---|---|
| Name | Coffee Pie |
| Symbol | COFP |
| Decimals | 18 |
| Standard | TRC-20 (TRON) |
| Max Supply | 100'000'000 COFP |
| Burnable | Yes (by holder or approved spender) |
| Remintable | Yes (owner only, up to MAX_SUPPLY) |
| Inflation | 0% (fixed supply) |
| Governance | Off-chain (Coffee Pie Platform) |
| Trading | BVC Stock Exchange (planned) |

## Step 5 — Backend Integration

The Coffee Pie backend interacts with the contract for:

1. **Provider settlement** — reads contract for provider wallet balances,
   burns tokens via `burnFrom()` when provider requests fiat withdrawal
2. **Contributor credit burning** — burns tokens via `burn()` when
   contributor exchanges COFP for Platform Credits (Cr), capped per account
3. **Reward distribution** — transfers COFP to contributors and providers
   via `transfer()` calls; remints via `remint()` when the owner supply
   runs low and burned tokens need to be restored

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
remint(address, uint256)   → restore burned supply (owner only)
transferOwnership(address) → admin rotation
```

## Step 6 — Post-Deployment Checklist

- [ ] Contract address recorded and backed up
- [ ] Verified on Tronscan
- [ ] TronLink wallet private key stored securely (cold storage recommended)
- [ ] Test burn + test remint on Shasta testnet before mainnet
- [ ] **Transfer ownership to Gnosis Safe multi-sig wallet** (MANDATORY before BVC listing — minimum 4/7 signers: Core Dev Lead, Legal Counsel, Community Representative, CFO, Cold Storage Key, External Auditor, Emergency Trustee)
- [ ] **Enable 48-hour timelock on all `onlyOwner` functions** — prevents single-key compromise from instantly draining the contract
- [ ] **Document signer succession plan** — each signer designates a successor who inherits their key on verified death/incapacity (notarized letter + 30-day waiting period). The 4/7 threshold tolerates up to 3 lost keys before the contract freezes, providing decades of operational safety
- [ ] Deploy monitoring: alert on every `remint()`, `burn()`, `pause()`, `transferOwnership()` event
- [ ] Add contract address to Coffee Pie backend `.env`
- [ ] Publish token info on https://coffeepie.co/token
