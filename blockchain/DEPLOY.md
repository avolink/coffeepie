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
5. The constructor takes **no arguments** — 100M initial supply is minted to the deployer
6. Click **Transact**, confirm in TronLink

## Step 3 — Verify on Tronscan

1. After deployment, copy the contract address
2. Open https://tronscan.io, search the contract address
3. Go to Contract → Verify & Publish
4. Upload the same Solidity source with compiler 0.8.20
5. Set optimization: **No**

## Step 4 — Monetary Policy

COFP uses an **elastic-supply** model. There is no hard cap on total supply.

### Why Elastic Supply?

Coffee Pie is a computing utility network, not a speculative asset. Its token
represents **real compute resources served** — 1 COFP = 1 Coffee Pie® Slice
served for 1 minute (1 Slice·min). A Provider hosting 4 Slices for 60 minutes
earns 4 × 60 = 240 COFP.

**Supply grows with the network.** As more Providers join the QFDM Network and
serve more Slices, more COFP is minted to compensate them. As demand grows and
more consumers rent Slices, the token has real economic backing: every COFP in
circulation corresponds to compute time actually delivered.

**Initial supply: 100'000'000 COFP.** Minted to the deployer wallet at
construction. This bootstraps the ecosystem — early Contributors, Providers,
and supporters are rewarded from this pool before organic minting takes over.

**Supply is elastic, not inflationary.** Minting is mechanically tied to
real compute provision (1 COFP per Slice·min). The token supply grows only
when the network grows — it's a reflection of real economic activity, not
arbitrary dilution.

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

### Mint Mechanism

```
mint(address _to, uint256 _value) — onlyOwner
  └→ No supply cap — mints any amount
```

The `mint()` function creates new COFP tokens. It is the **only** way new
tokens enter circulation besides the initial 100M constructor mint.

| Scenario | Action |
|---|---|
| Provider serves 4 Slices for 1 hour | `mint()` creates 240 new COFP |
| Provider serves 1 Slice for 1 minute | `mint()` creates 1 new COFP |
| Contributor reward from initial pool | `transfer()` from owner wallet (no mint needed) |
| Initial pool runs low | `mint()` tops up the reward pool |

The mint function is NOT arbitrary inflation — it is mechanically tied to
compute provision at a fixed rate of 1 COFP per Slice·min. The owner can
only mint as fast as the QFDM Network consumes Slices.

### Supply Lifecycle

```
Deploy: 100M → owner wallet (initial bootstrap supply)
  ↓
Distribute: owner → providers, contributors, early supporters
  ↓
Circulate: tokens flow through the ecosystem
  ↓
Burn: providers burn for fiat settlement (supply decreases)
  ↓
Mint: owner mints new tokens to pay providers for new Slices served
  ↓
Grow: supply grows organically as the QFDM Network expands
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
| Initial Supply | 100'000'000 COFP |
| Max Supply | No cap (elastic — grows with network) |
| Burnable | Yes (by holder or approved spender) |
| Mintable | Yes (owner only, no supply cap) |
| Emission Rate | 1 COFP per Slice·min served by Providers |
| Governance | Off-chain (Coffee Pie Platform) |
| Trading | BVC Stock Exchange (planned) |

## Step 5 — Backend Integration

The Coffee Pie backend interacts with the contract for:

1. **Provider settlement** — reads contract for provider wallet balances,
   burns tokens via `burnFrom()` when provider requests fiat withdrawal
2. **Contributor credit burning** — burns tokens via `burn()` when
   contributor exchanges COFP for Platform Credits (Cr), capped per account
3. **Reward distribution** — transfers COFP to contributors and providers
   via `transfer()` calls; mints new tokens via `mint()` when the owner
   supply runs low and Providers need to be paid for Slices served

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
mint(address, uint256)     → emit new tokens for Providers (owner only)
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
