// Copyright (c) 2026 Coffee Pie Contributors
// SPDX-License-Identifier: BSD-3-Clause

//! QFDM placement policy — the decision core of the DC-selection broker.
//!
//! This crate is **pure logic, no I/O**. Given a user's [`ServiceClass`] and the
//! live set of candidate datacenters (each with a verified [`Tier`], current free
//! capacity, and the *client-measured* ping), it decides where a slice should land
//! and who may be preempted. The broker feeds it data (from heartbeats + the
//! provider registry + the client's ping probes) and acts on the result.
//!
//! ## Model: graceful degradation, not rigid bands
//! Each class has a **preference order over all tiers** (best-first for premium,
//! cheapest-first for free). A slice lands on its most-preferred tier that is
//! *available within a comparable latency band* — so demand is never denied just
//! because its ideal tier is scarce, and supply/demand self-regulate (providers
//! build higher tiers because premium gravitates there; nobody is stranded when
//! it's scarce). See `SCHEDULING.md`.
//!
//! ## Tier is internal — consumers never see it
//! `Tier` is a supply-side signal used only here. Consumers are shown **region +
//! ping**, never the tier or node identity. Don't surface `Tier` in any
//! consumer-facing API. (See the AGENTS.md decision.)

use serde::{Deserialize, Serialize};

/// Provider infrastructure tier (supply side). Assigned/verified by Coffee Pie at
/// onboarding — **never self-reported** (a higher tier earns a higher settlement
/// margin, see `PROVIDERS.md`, so self-declaration would be a fraud vector) and
/// **never exposed to consumers**.
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub enum Tier {
    I,
    II,
    III,
    IV,
    V,
}

/// User service class (demand side), derived from the account's plan / credit
/// package: free (ads) → small/medium packages → large packages → government (B2G).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "snake_case")]
pub enum ServiceClass {
    /// Free tier (ad-funded). Prefers the cheapest tiers; preemptible.
    Free,
    /// Small / medium credit packages.
    Standard,
    /// Large credit packages.
    Priority,
    /// Government (B2G) and large dedicated buyers.
    Sovereign,
}

impl ServiceClass {
    /// Preference over **all** tiers, best-first for this class. The scheduler
    /// places a slice on the most-preferred tier available within a comparable
    /// latency band (graceful degradation: premium degrades V→IV→III→…; free
    /// climbs only as a last resort). Governance-tunable — this is the default.
    pub fn tier_preference(self) -> &'static [Tier] {
        use Tier::*;
        match self {
            // Premium classes want the best hardware, degrading downward.
            ServiceClass::Sovereign => &[V, IV, III, II, I],
            ServiceClass::Priority => &[V, IV, III, II, I],
            // Standard's sweet spot is III/IV, then spare V, then down.
            ServiceClass::Standard => &[IV, III, V, II, I],
            // Free prefers the cheapest capacity; high tiers are a last resort
            // (and it's preemptible, so it won't squat expensive nodes).
            ServiceClass::Free => &[I, II, III, IV, V],
        }
    }

    /// Free sessions run on backup/peak capacity and may be evicted.
    pub fn is_preemptible(self) -> bool {
        matches!(self, ServiceClass::Free)
    }

    /// Higher = more important. Used for preemption decisions.
    pub fn priority_rank(self) -> u8 {
        match self {
            ServiceClass::Free => 0,
            ServiceClass::Standard => 1,
            ServiceClass::Priority => 2,
            ServiceClass::Sovereign => 3,
        }
    }
}

/// May a `requester` slice evict a running `occupant` slice to free capacity?
/// Only a preemptible occupant can be evicted, and only by a strictly higher class.
pub fn can_preempt(requester: ServiceClass, occupant: ServiceClass) -> bool {
    occupant.is_preemptible() && requester.priority_rank() > occupant.priority_rank()
}

/// Width of a "comparable latency" band, in ms. Pings within the same band are
/// treated as equivalent — tier preference decides between them; across bands the
/// lower ping always wins (latency is the AGENTS.md #1 priority). Governance/region
/// tunable: smaller = latency dominates more; larger = tier preference dominates more.
pub const LATENCY_BUCKET_MS: u32 = 25;

/// A datacenter under consideration, carrying the data only the broker has:
/// the verified `tier` (registry), live `free_slices` (heartbeats), and the
/// user→DC `ping_ms` (measured client-side — the AGENTS.md #1 priority signal).
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DcCandidate {
    pub dc_id: String,
    pub tier: Tier,
    pub free_slices: u32,
    pub ping_ms: u32,
}

/// Rank candidate DCs for a `class` request needing `slices_needed`, best first.
///
/// Sort key: **`(latency band, tier preference, exact ping)`**.
/// - *Across* latency bands, lower ping always wins — a nearer node beats a farther
///   one regardless of tier (latency #1).
/// - *Within* a band (pings within [`LATENCY_BUCKET_MS`]), the class's tier
///   preference decides — premium gets the best hardware among comparably-close
///   nodes; free gets the cheapest.
///
/// Graceful degradation falls out for free: a class is never filtered out of a tier,
/// so premium degrades downward and is placed as long as *any* node has capacity.
/// An empty result means no node has free capacity at all — the caller may then
/// consider [`can_preempt`]-based eviction or queueing.
pub fn rank_candidates<'a>(
    class: ServiceClass,
    slices_needed: u32,
    candidates: &'a [DcCandidate],
) -> Vec<&'a DcCandidate> {
    let pref = class.tier_preference();
    let tier_rank = |t: Tier| pref.iter().position(|&p| p == t).unwrap_or(usize::MAX);

    let mut hits: Vec<&DcCandidate> =
        candidates.iter().filter(|c| c.free_slices >= slices_needed).collect();

    hits.sort_by(|a, b| {
        (a.ping_ms / LATENCY_BUCKET_MS)
            .cmp(&(b.ping_ms / LATENCY_BUCKET_MS))
            .then_with(|| tier_rank(a.tier).cmp(&tier_rank(b.tier)))
            .then_with(|| a.ping_ms.cmp(&b.ping_ms))
    });
    hits
}

#[cfg(test)]
mod tests {
    use super::*;

    fn dc(id: &str, tier: Tier, free_slices: u32, ping_ms: u32) -> DcCandidate {
        DcCandidate { dc_id: id.into(), tier, free_slices, ping_ms }
    }
    fn ids(v: Vec<&DcCandidate>) -> Vec<String> {
        v.into_iter().map(|c| c.dc_id.clone()).collect()
    }

    #[test]
    fn latency_band_wins_across_bands() {
        // Sovereign prefers V, but a near Tier I (10ms) beats a far Tier V (80ms):
        // different latency bands, lower ping wins (latency #1).
        let cands = vec![dc("v-far", Tier::V, 10, 80), dc("i-near", Tier::I, 10, 10)];
        assert_eq!(ids(rank_candidates(ServiceClass::Sovereign, 1, &cands)), vec!["i-near", "v-far"]);
    }

    #[test]
    fn tier_preference_wins_within_a_band() {
        // Standard: Tier IV (12ms) and Tier III (10ms) are in the same band (<25ms),
        // so the preferred tier (IV) wins despite a slightly higher ping.
        let cands = vec![dc("iii", Tier::III, 10, 10), dc("iv", Tier::IV, 10, 12)];
        assert_eq!(ids(rank_candidates(ServiceClass::Standard, 1, &cands)), vec!["iv", "iii"]);
    }

    #[test]
    fn premium_degrades_gracefully_when_top_tier_absent() {
        // No Tier V available: Priority takes the next best (IV), then III.
        let cands = vec![dc("iii", Tier::III, 10, 8), dc("iv", Tier::IV, 10, 8)];
        assert_eq!(ids(rank_candidates(ServiceClass::Priority, 1, &cands)), vec!["iv", "iii"]);
    }

    #[test]
    fn free_is_placed_even_if_only_high_tier_is_left() {
        // Graceful: Free prefers low tiers but is still placed on V if that's all
        // there is (and it's preemptible, so a payer can reclaim it later).
        let cands = vec![dc("v-only", Tier::V, 5, 20)];
        assert_eq!(ids(rank_candidates(ServiceClass::Free, 1, &cands)), vec!["v-only"]);
    }

    #[test]
    fn free_prefers_cheapest_within_a_band() {
        let cands = vec![dc("v", Tier::V, 10, 12), dc("i", Tier::I, 10, 10)];
        assert_eq!(ids(rank_candidates(ServiceClass::Free, 1, &cands)), vec!["i", "v"]);
    }

    #[test]
    fn capacity_filter_excludes_too_small_dcs() {
        let cands = vec![dc("small", Tier::IV, 3, 8), dc("big", Tier::III, 8, 9)];
        assert_eq!(ids(rank_candidates(ServiceClass::Standard, 4, &cands)), vec!["big"]);
    }

    #[test]
    fn unplaceable_when_no_capacity_anywhere() {
        let cands = vec![dc("full", Tier::IV, 0, 8)];
        assert!(rank_candidates(ServiceClass::Standard, 1, &cands).is_empty());
    }

    #[test]
    fn preemption_order() {
        assert!(can_preempt(ServiceClass::Standard, ServiceClass::Free));
        assert!(can_preempt(ServiceClass::Sovereign, ServiceClass::Free));
        assert!(!can_preempt(ServiceClass::Free, ServiceClass::Standard));
        assert!(!can_preempt(ServiceClass::Standard, ServiceClass::Standard));
        assert!(!can_preempt(ServiceClass::Sovereign, ServiceClass::Priority)); // not preemptible
    }
}
