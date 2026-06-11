// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

//! Capacity-aware node placement for a single datacenter.
//!
//! A DC Agent owns exactly one cluster. This module decides *which node in that
//! cluster* a new slice should land on. It never reaches across datacenters —
//! cross-DC / cross-provider routing (lowest ping, "silent" multi-provider) is
//! the QFDM broker's job, because only the broker sees every DC at once and only
//! the *client* can measure user→node latency. See `select_node` docs.
//!
//! ## What this gives the platform
//! - "Virtually infinite machines per user": the agent keeps placing slices on
//!   whichever node still fits, so a user is bounded by *hardware*, not by an
//!   arbitrary per-node assignment.
//! - Automatic reallocation: if the preferred/first node is full (or a clone
//!   fails), `rank_candidates` yields the next-best node so the caller can retry
//!   elsewhere without bothering the user.
//!
//! ## What this deliberately does NOT do (and why)
//! - It does not enforce a *per-user* instance quota. The agent is stateless and
//!   has no user ledger — quota/billing lives at the broker. Placement here will
//!   happily fill a whole cluster for one user; the broker MUST gate that first.
//!   (See `README` note added with this module.)
//! - It does not measure ping. Ping is user→node and can only be measured from
//!   the client. The broker ranks DCs by the client's probe results, then asks
//!   the winning DC's agent to place via this module.

use crate::types::{NodeCapacity, SliceSpec};

/// How aggressively the scheduler is allowed to oversubscribe physical
/// resources. Streaming desktops are bursty and rarely use 100% at once, so a
/// modest CPU overcommit is normal; RAM overcommit is dangerous (the OOM killer
/// will murder a user's session), so it defaults to 1.0 (no overcommit).
#[derive(Debug, Clone)]
pub struct PlacementPolicy {
    /// Multiplier on physical CPU cores (e.g. 4.0 = sell 4 vCPU per physical core).
    pub cpu_overcommit: f64,
    /// Multiplier on physical RAM. Keep at 1.0 unless you have swap/ballooning
    /// you trust — overcommitting RAM trades a cheaper bill for killed sessions.
    pub ram_overcommit: f64,
    /// Multiplier on physical disk. Thin-provisioned storage can exceed 1.0, but
    /// only if you monitor real allocation — a full datastore corrupts every VM.
    pub disk_overcommit: f64,
    /// If the slice requests GPU (gpu_mb > 0) but a node reports 0 total GPU,
    /// that node is rejected. Sunshine needs a hardware encoder to stream, so a
    /// GPU-less node silently produces a black/broken stream. Always true in prod.
    pub require_gpu_for_gpu_slices: bool,
    /// Fraction of each node's capacity reserved as headroom for the host OS,
    /// migrations, and burst (e.g. 0.10 = never plan past 90% of a node).
    pub headroom_fraction: f64,
}

impl Default for PlacementPolicy {
    fn default() -> Self {
        Self {
            cpu_overcommit: 4.0,
            ram_overcommit: 1.0,
            disk_overcommit: 1.0,
            require_gpu_for_gpu_slices: true,
            headroom_fraction: 0.10,
        }
    }
}

/// Why no node could host a slice — surfaced to the caller (and ultimately the
/// broker) so it can decide whether to spill to another DC.
#[derive(Debug, Clone, PartialEq)]
pub enum PlacementError {
    /// The cluster has nodes, but none has enough free capacity for this spec.
    /// The broker should treat this as "this DC is full — try the next DC".
    NoNodeWithCapacity,
    /// The cluster reported zero nodes at all (agent/backend misconfiguration).
    NoNodesAtAll,
}

impl std::fmt::Display for PlacementError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            PlacementError::NoNodeWithCapacity => {
                write!(f, "no node in this datacenter has capacity for the requested slice")
            }
            PlacementError::NoNodesAtAll => write!(f, "this datacenter reported no nodes"),
        }
    }
}

impl std::error::Error for PlacementError {}

/// Free resources on a node after applying overcommit and headroom.
/// All values are "how many more units we may still allocate".
struct Headroom {
    cpu_cores: f64,
    ram_gb: f64,
    disk_gb: f64,
    gpu_mb: f64,
    has_gpu: bool,
}

impl Headroom {
    fn for_node(node: &NodeCapacity, policy: &PlacementPolicy) -> Self {
        // Plannable capacity = physical * overcommit * (1 - headroom).
        let plannable = |total: u32, mult: f64| -> f64 {
            (total as f64) * mult * (1.0 - policy.headroom_fraction)
        };

        let cpu_cores = plannable(node.total_cpu_cores, policy.cpu_overcommit)
            - node.used_cpu_cores as f64;
        let ram_gb = plannable(node.total_ram_gb, policy.ram_overcommit)
            - node.used_ram_gb as f64;
        let disk_gb = plannable(node.total_disk_gb, policy.disk_overcommit)
            - node.used_disk_gb as f64;
        // GPU is not overcommitted — encoder VRAM is hard-partitioned.
        let gpu_mb = (node.total_gpu_mb as f64) * (1.0 - policy.headroom_fraction)
            - node.used_gpu_mb as f64;

        Headroom {
            cpu_cores,
            ram_gb,
            disk_gb,
            gpu_mb,
            has_gpu: node.total_gpu_mb > 0,
        }
    }

    /// Does this node have room for `spec`?
    fn fits(&self, spec: &SliceSpec, policy: &PlacementPolicy) -> bool {
        let needs_gpu = spec.gpu_mb > 0;
        if needs_gpu && policy.require_gpu_for_gpu_slices && !self.has_gpu {
            return false;
        }
        self.cpu_cores >= spec.cpu_cores as f64
            && self.ram_gb >= spec.ram_gb as f64
            && self.disk_gb >= (spec.ssd_gb + spec.hdd_gb) as f64
            && self.gpu_mb >= spec.gpu_mb as f64
    }

    /// Spread score in [0, 1]: the *tightest* remaining resource fraction after
    /// hypothetically placing `spec`. Higher = more balanced headroom left, so we
    /// prefer the emptiest fitting node. Spreading (worst-fit) beats tight packing
    /// (best-fit) for interactive streaming: it minimizes noisy-neighbor CPU/GPU
    /// contention and leaves room to live-migrate. Flip the comparison in
    /// `rank_candidates` if you ever optimize for cost density instead of QoS.
    fn spread_score(&self, spec: &SliceSpec, policy: &PlacementPolicy) -> f64 {
        let frac = |free: f64, need: u32, total_plannable: f64| -> f64 {
            if total_plannable <= 0.0 {
                return 1.0; // resource not constrained on this node
            }
            ((free - need as f64) / total_plannable).clamp(0.0, 1.0)
        };
        // Approximate per-resource plannable totals for normalization.
        let cpu = frac(self.cpu_cores, spec.cpu_cores, self.cpu_cores.max(1.0) + spec.cpu_cores as f64);
        let ram = frac(self.ram_gb, spec.ram_gb, self.ram_gb.max(1.0) + spec.ram_gb as f64);
        let gpu = if spec.gpu_mb > 0 {
            frac(self.gpu_mb, spec.gpu_mb, self.gpu_mb.max(1.0) + spec.gpu_mb as f64)
        } else {
            1.0
        };
        let _ = policy;
        // The bottleneck resource defines the score (a node tight on any one
        // resource is a bad spread choice even if others are roomy).
        cpu.min(ram).min(gpu)
    }
}

/// Rank the nodes that can host `spec`, best candidate first.
///
/// The returned list is meant for **try-and-fallback**: attempt the head, and if
/// the clone fails (lost a capacity race, transient backend error) move to the
/// next. This is how a single user gets "as many machines as the hardware can
/// hold" and how the agent silently reallocates when a node fills up.
///
/// `preferred_node` (the prosumer "Advanced View" choice, scoped to *this* DC):
/// if provided AND it fits, it is pinned to the front. If it does NOT fit, it is
/// dropped and we fall back to automatic placement — a manual hint should never
/// strand a user on a full box. (Cluster/provider selection is a separate,
/// broker-level choice; this only picks a node within the already-chosen DC.)
pub fn rank_candidates(
    nodes: &[NodeCapacity],
    spec: &SliceSpec,
    preferred_node: Option<&str>,
    policy: &PlacementPolicy,
) -> Result<Vec<String>, PlacementError> {
    if nodes.is_empty() {
        return Err(PlacementError::NoNodesAtAll);
    }

    // Score every fitting node.
    let mut scored: Vec<(String, f64)> = nodes
        .iter()
        .filter_map(|node| {
            let hr = Headroom::for_node(node, policy);
            if hr.fits(spec, policy) {
                Some((node.node_name.clone(), hr.spread_score(spec, policy)))
            } else {
                None
            }
        })
        .collect();

    if scored.is_empty() {
        return Err(PlacementError::NoNodeWithCapacity);
    }

    // Highest spread score first (emptiest fitting node).
    scored.sort_by(|a, b| b.1.partial_cmp(&a.1).unwrap_or(std::cmp::Ordering::Equal));

    let mut ranked: Vec<String> = scored.into_iter().map(|(name, _)| name).collect();

    // Pin a valid preferred node to the front (it's already known to fit if it's
    // in `ranked`; if it isn't, the operator's hint can't be honored and we keep
    // the automatic order).
    if let Some(pref) = preferred_node {
        if let Some(pos) = ranked.iter().position(|n| n == pref) {
            let chosen = ranked.remove(pos);
            ranked.insert(0, chosen);
        } else {
            tracing::warn!(
                preferred_node = %pref,
                "Preferred node cannot host this slice; falling back to automatic placement"
            );
        }
    }

    Ok(ranked)
}

/// Convenience: the single best node, or a `PlacementError` if none fit.
/// The create path uses `rank_candidates` directly (it needs the fallback
/// list); this is kept for future adapters that can't retry.
#[allow(dead_code)]
pub fn select_node(
    nodes: &[NodeCapacity],
    spec: &SliceSpec,
    preferred_node: Option<&str>,
    policy: &PlacementPolicy,
) -> Result<String, PlacementError> {
    rank_candidates(nodes, spec, preferred_node, policy).map(|mut v| v.remove(0))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn node(name: &str, cpu_total: u32, cpu_used: u32, ram_total: u32, ram_used: u32, gpu_total: u32) -> NodeCapacity {
        NodeCapacity {
            node_name: name.to_string(),
            total_cpu_cores: cpu_total,
            used_cpu_cores: cpu_used,
            total_ram_gb: ram_total,
            used_ram_gb: ram_used,
            total_gpu_mb: gpu_total,
            used_gpu_mb: 0,
            slices_available: 0,
            total_disk_gb: 10_000,
            used_disk_gb: 0,
        }
    }

    #[test]
    fn empty_cluster_errors() {
        let err = rank_candidates(&[], &SliceSpec::default(), None, &PlacementPolicy::default()).unwrap_err();
        assert_eq!(err, PlacementError::NoNodesAtAll);
    }

    #[test]
    fn full_cluster_errors() {
        // One node, CPU fully used even after overcommit headroom.
        let n = node("n1", 1, 100, 64, 0, 1000);
        let err = rank_candidates(&[n], &SliceSpec::default(), None, &PlacementPolicy::default()).unwrap_err();
        assert_eq!(err, PlacementError::NoNodeWithCapacity);
    }

    #[test]
    fn picks_emptiest_node_for_spread() {
        let busy = node("busy", 20, 60, 64, 40, 4000); // cpu overcommit 4x -> 80 plannable, 60 used
        let empty = node("empty", 20, 0, 64, 0, 4000);
        let ranked = rank_candidates(
            &[busy, empty],
            &SliceSpec::default(),
            None,
            &PlacementPolicy::default(),
        )
        .unwrap();
        assert_eq!(ranked[0], "empty", "should spread onto the emptiest fitting node");
    }

    #[test]
    fn gpu_slice_rejects_gpuless_node() {
        let gpuless = node("cpu-only", 64, 0, 256, 0, 0);
        let spec = SliceSpec { gpu_mb: 500, ..SliceSpec::default() };
        let err = rank_candidates(&[gpuless], &spec, None, &PlacementPolicy::default()).unwrap_err();
        assert_eq!(err, PlacementError::NoNodeWithCapacity, "GPU slice must not land on a GPU-less node");
    }

    #[test]
    fn preferred_node_pinned_when_it_fits() {
        let a = node("a", 64, 0, 256, 0, 4000);
        let b = node("b", 64, 0, 256, 0, 4000);
        let ranked = rank_candidates(&[a, b], &SliceSpec::default(), Some("b"), &PlacementPolicy::default()).unwrap();
        assert_eq!(ranked[0], "b");
    }

    #[test]
    fn preferred_node_ignored_when_it_cannot_fit() {
        let small = node("small", 1, 100, 1, 100, 0); // full
        let big = node("big", 64, 0, 256, 0, 4000);
        // Prefer the full node — must fall back to the one that fits.
        let ranked = rank_candidates(&[small, big], &SliceSpec::default(), Some("small"), &PlacementPolicy::default()).unwrap();
        assert_eq!(ranked, vec!["big".to_string()]);
    }

    #[test]
    fn ram_is_not_overcommitted_by_default() {
        // 8 GB node, 8 used. Default RAM overcommit = 1.0, so no room for 1 GB.
        let n = node("n", 64, 0, 8, 8, 4000);
        let err = rank_candidates(&[n], &SliceSpec::default(), None, &PlacementPolicy::default()).unwrap_err();
        assert_eq!(err, PlacementError::NoNodeWithCapacity);
    }
}
