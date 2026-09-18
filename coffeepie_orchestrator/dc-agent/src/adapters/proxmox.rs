// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::sync::atomic::{AtomicU32, Ordering};

use anyhow::{anyhow, Context, Result};
use async_trait::async_trait;

use crate::adapter::HypervisorAdapter;
use crate::placement::{self, PlacementPolicy};
use crate::types::{
    is_safe_identifier, CapacityReport, CreateSliceRequest, HealthStatus, InstanceState,
    NodeCapacity, RunningInstance, SliceHandle, SunshineEndpoint,
};

/// Proxmox hypervisor adapter.
///
/// Communicates with the proxmox_backend FastAPI service which abstracts
/// Proxmox VE REST API access. The backend handles PVE authentication
/// (ticket + CSRF token) transparently.
pub struct ProxmoxAdapter {
    /// Base URL of the proxmox_backend FastAPI service (e.g., "https://proxmox-api.dc1.lan")
    backend_url: String,
    /// Firebase ID token for bearer authentication to the proxmox_backend
    bearer_token: String,
    /// HTTP client with connection pooling
    client: reqwest::Client,
    /// Agent ID for capacity reports
    agent_id: String,
}

/// Atomic counter for Proxmox VMID generation.
/// Starts at 100,000 to avoid low-numbered Proxmox-reserved VMIDs.
/// Race-free: each call to `next_vmid()` returns a unique, monotonically increasing value.
static NEXT_VMID: AtomicU32 = AtomicU32::new(100_000);

fn next_vmid() -> u32 {
    NEXT_VMID.fetch_add(1, Ordering::SeqCst)
}

impl ProxmoxAdapter {
    pub fn new(backend_url: String, bearer_token: String, agent_id: String) -> Self {
        let client = reqwest::Client::builder()
            .use_rustls_tls()
            .timeout(std::time::Duration::from_secs(30))
            .build()
            .expect("Failed to build reqwest client");

        Self {
            backend_url: backend_url.trim_end_matches('/').to_string(),
            bearer_token,
            client,
            agent_id,
        }
    }

    fn auth_header(&self) -> String {
        format!("Bearer {}", self.bearer_token)
    }

    /// Check if the HTTP response status indicates success.
    /// If not, extract the error body and return an error.
    /// This prevents masking auth failures (401), backend errors (500), etc.
    async fn check_status(resp: reqwest::Response) -> Result<reqwest::Response> {
        if resp.status().is_success() {
            return Ok(resp);
        }
        let status = resp.status();
        let body = resp.text().await.unwrap_or_default();
        Err(anyhow!(
            "Backend returned HTTP {}: {}",
            status.as_u16(),
            body
        ))
    }

    /// Validate that node and vm_name are safe identifiers before building a URL path.
    fn validate_node_and_vm(node: &str, vm_name: &str) -> Result<()> {
        if !is_safe_identifier(node) {
            return Err(anyhow!(
                "Invalid node name '{}': must be alphanumeric with hyphens/underscores/dots",
                node
            ));
        }
        if !is_safe_identifier(vm_name) {
            return Err(anyhow!(
                "Invalid VM name '{}': must be alphanumeric with hyphens/underscores/dots",
                vm_name
            ));
        }
        Ok(())
    }

    /// Build a safe URL path for a node+vm endpoint.
    /// Node and vm_name are validated as safe identifiers before interpolation.
    fn safe_path(&self, template: &str, node: &str, vm_name: &str) -> Result<String> {
        Self::validate_node_and_vm(node, vm_name)?;
        Ok(format!(
            "{}{}",
            self.backend_url,
            template.replace("{node}", node).replace("{vm}", vm_name)
        ))
    }

    /// Call GET on a proxmox_backend endpoint.
    /// Validates HTTP status before returning JSON.
    async fn get(&self, path: &str) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        tracing::debug!(url = %url, "GET");

        let resp = self
            .client
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .with_context(|| format!("GET {} failed", url))?;

        let resp = Self::check_status(resp).await?;
        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// Call POST on a proxmox_backend endpoint.
    /// Validates HTTP status before returning JSON.
    async fn post(&self, path: &str, body: &serde_json::Value) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        tracing::debug!(url = %url, "POST");

        let resp = self
            .client
            .post(&url)
            .header("Authorization", self.auth_header())
            .header("Content-Type", "application/json")
            .json(body)
            .send()
            .await
            .with_context(|| format!("POST {} failed", url))?;

        let resp = Self::check_status(resp).await?;
        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// Call DELETE on a proxmox_backend endpoint.
    /// Validates HTTP status before returning JSON.
    async fn delete(&self, path: &str) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        tracing::debug!(url = %url, "DELETE");

        let resp = self
            .client
            .delete(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .with_context(|| format!("DELETE {} failed", url))?;

        let resp = Self::check_status(resp).await?;
        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// List all Proxmox nodes from the backend (names only).
    async fn list_nodes(&self) -> Result<Vec<String>> {
        Ok(self
            .list_nodes_raw()
            .await?
            .iter()
            .filter_map(|n| n["node"].as_str().map(String::from))
            .collect())
    }

    /// List all Proxmox nodes with their full resource objects.
    /// The `/nodes` payload carries `maxcpu`, `maxmem`, `mem`, `maxdisk`, `disk`,
    /// and a `cpu` load fraction — everything placement needs for real fit
    /// decisions, instead of counting VMs.
    async fn list_nodes_raw(&self) -> Result<Vec<serde_json::Value>> {
        let json = self.get("/nodes").await?;
        Ok(json["data"].as_array().cloned().unwrap_or_default())
    }

    /// List VMs on a specific node
    async fn list_vms(&self, node: &str) -> Result<Vec<serde_json::Value>> {
        let json = self.get(&format!("/nodes/{}/vms", node)).await?;
        let vms = json["vms"].as_array().unwrap_or(&vec![]).clone();
        Ok(vms)
    }
}

#[async_trait]
impl HypervisorAdapter for ProxmoxAdapter {
    fn adapter_type(&self) -> &str {
        "proxmox"
    }

    async fn list_templates(&self) -> Result<Vec<String>> {
        let nodes = self.list_nodes().await?;
        let mut templates = Vec::new();

        for node in &nodes {
            let vms = self.list_vms(node).await?;
            for vm in &vms {
                if let Some(name) = vm.as_str() {
                    templates.push(format!("{}@{}", name, node));
                }
            }
        }

        Ok(templates)
    }

    async fn get_capacity(&self) -> Result<CapacityReport> {
        let raw_nodes = self.list_nodes_raw().await?;
        let mut available_slices = Vec::new();
        let mut running_instances = Vec::new();

        // Bytes → GB (GiB) for human-scale planning numbers.
        const GIB: f64 = 1_073_741_824.0;

        for node in &raw_nodes {
            let node_name = match node["node"].as_str() {
                Some(n) => n.to_string(),
                None => continue,
            };

            // Real per-node resources from the Proxmox `/nodes` payload.
            let max_cpu = node["maxcpu"].as_u64().unwrap_or(0) as u32;
            // `cpu` is a load fraction in [0,1]; convert to busy cores.
            let cpu_frac = node["cpu"].as_f64().unwrap_or(0.0);
            let used_cpu = (cpu_frac * max_cpu as f64).round() as u32;

            let total_ram_gb = (node["maxmem"].as_u64().unwrap_or(0) as f64 / GIB).floor() as u32;
            let used_ram_gb = (node["mem"].as_u64().unwrap_or(0) as f64 / GIB).floor() as u32;

            let total_disk_gb = (node["maxdisk"].as_u64().unwrap_or(0) as f64 / GIB).floor() as u32;
            let used_disk_gb = (node["disk"].as_u64().unwrap_or(0) as f64 / GIB).floor() as u32;

            // GPU: the Proxmox `/nodes` payload does NOT report GPU/VRAM. Until
            // proxmox_backend exposes per-node GPU telemetry we report 0 here,
            // which means placement cannot *gate* on GPU yet. See the policy
            // override in `create_instance` — GPU gating stays OFF until this is
            // real, otherwise every GPU slice would be unschedulable.
            // TODO(gpu-telemetry): populate total_gpu_mb/used_gpu_mb.
            let total_gpu_mb = 0;
            let used_gpu_mb = 0;

            // Rough "slices available" headline for the heartbeat/UX, derived
            // from the tightest of CPU and RAM headroom. Placement itself does
            // the precise multi-dimensional fit; this is just a summary number.
            let cpu_slices = max_cpu.saturating_sub(used_cpu);
            let ram_slices = total_ram_gb.saturating_sub(used_ram_gb);
            let slices_available = cpu_slices.min(ram_slices);

            available_slices.push(NodeCapacity {
                node_name: node_name.clone(),
                total_cpu_cores: max_cpu,
                used_cpu_cores: used_cpu,
                total_ram_gb,
                used_ram_gb,
                total_gpu_mb,
                used_gpu_mb,
                slices_available,
                total_disk_gb,
                used_disk_gb,
            });

            // Collect running Coffee Pie instances (VMs named cp-*).
            let vms = self.list_vms(&node_name).await?;
            for vm_name in &vms {
                if let Some(instance_id) = vm_name.as_str().and_then(|n| n.strip_prefix("cp-")) {
                    running_instances.push(RunningInstance {
                        instance_id: instance_id.to_string(),
                        node: node_name.clone(),
                        state: InstanceState::Running, // Conservative default
                        user_id: None,
                        created_at: chrono::Utc::now().timestamp(),
                    });
                }
            }
        }

        Ok(CapacityReport {
            agent_id: self.agent_id.clone(),
            timestamp: chrono::Utc::now().timestamp(),
            available_slices,
            running_instances,
            health: HealthStatus::Healthy,
        })
    }

    async fn create_instance(&self, request: CreateSliceRequest) -> Result<SliceHandle> {
        let instance_id = uuid::Uuid::new_v4().to_string();
        let new_name = format!("cp-{}", instance_id);

        // ── Capacity-aware placement ────────────────────────────────────
        // Query live capacity, then rank the nodes that can actually host this
        // slice. The ranked list is what makes a user's machine count bounded by
        // hardware rather than by a fixed node assignment: we keep falling
        // through to the next-emptiest node until one accepts the clone.
        let report = self.get_capacity().await.context("capacity query failed")?;
        let policy = PlacementPolicy {
            // GPU gating stays OFF until get_capacity reports real per-node GPU
            // (it currently reports 0 for every node). With a true gate, every
            // default slice — which requests BASE_GPU_MB — would be unschedulable.
            // FLIP THIS TO `true` the moment GPU telemetry lands, or GPU slices
            // can be placed on GPU-less nodes and stream black frames.
            require_gpu_for_gpu_slices: false,
            ..PlacementPolicy::default()
        };
        let candidates = placement::rank_candidates(
            &report.available_slices,
            &request.spec,
            request.preferred_node.as_deref(),
            &policy,
        )
        .map_err(|e| anyhow!("{}", e))?; // NoNodeWithCapacity → broker spills to next DC

        tracing::info!(
            instance_id = %instance_id,
            candidate_nodes = ?candidates,
            "Placement ranked candidate nodes (best first)"
        );

        // ── Try-and-fallback across nodes ───────────────────────────────
        // A capacity check is a snapshot; between ranking and cloning another
        // request can win the race and fill the node. So we don't trust the
        // head blindly — we attempt each candidate in order and reallocate to
        // the next on failure. This is the "DC Agent silently moves the new
        // instance to another node with capacity" behavior, in-cluster.
        let mut last_err: Option<anyhow::Error> = None;

        for target_node in &candidates {
            // Defense-in-depth: the node name came from our own capacity report,
            // but it is interpolated into a URL path, so re-validate.
            if !is_safe_identifier(target_node) {
                tracing::warn!(node = %target_node, "Skipping node with unsafe name");
                continue;
            }

            // Fresh, collision-free VMID per attempt.
            let vmid = next_vmid();

            let clone_body = serde_json::json!({
                "source_name": request.template,
                "name": new_name,
                "newid": vmid,
                "node": target_node,
                "full": 0, // linked clone for speed
            });

            match self.post("/clone-by-name", &clone_body).await {
                Ok(clone_result) => {
                    // proxmox_backend returns {"error": "..."} with HTTP 200 on
                    // application failures (e.g. node became full). Treat that as
                    // a placement miss and fall through to the next candidate.
                    if let Some(error_msg) = clone_result["error"].as_str() {
                        tracing::warn!(
                            node = %target_node,
                            error = %error_msg,
                            "Clone rejected on this node; trying next candidate"
                        );
                        last_err = Some(anyhow!("clone failed on {}: {}", target_node, error_msg));
                        continue;
                    }
                }
                Err(e) => {
                    tracing::warn!(node = %target_node, error = %e, "Clone call failed; trying next candidate");
                    last_err = Some(e);
                    continue;
                }
            }

            // Clone succeeded on this node — start, wait for boot, resolve IP.
            let _ = self
                .post(
                    &format!("/nodes/{}/vms/{}/start", target_node, new_name),
                    &serde_json::json!({}),
                )
                .await;

            tokio::time::sleep(std::time::Duration::from_secs(10)).await;

            let ip = self
                .get_instance_ip(&new_name, target_node)
                .await
                .unwrap_or_else(|_| "0.0.0.0".to_string());

            tracing::info!(instance_id = %instance_id, node = %target_node, "Instance placed");

            return Ok(SliceHandle {
                instance_id: instance_id.clone(),
                provider_vm_id: new_name.clone(),
                node: target_node.clone(),
                sunshine_endpoint: Some(SunshineEndpoint {
                    ip,
                    api_port: 47990,
                    gamestream_port_range: (47984, 48010),
                }),
                created_at: chrono::Utc::now().timestamp(),
                spec: request.spec.clone(),
            });
        }

        // Every candidate rejected the clone — the cluster is effectively full
        // for this spec right now. Surfacing this lets the broker spill the
        // request to another datacenter.
        Err(last_err.unwrap_or_else(|| anyhow!(
            "no node in this datacenter could host the slice (all candidates rejected the clone)"
        )))
    }

    async fn destroy_instance(
        &self,
        _instance_id: &str,
        provider_vm_id: &str,
        node: &str,
    ) -> Result<()> {
        // Validate inputs against injection
        Self::validate_node_and_vm(node, provider_vm_id)?;

        // Stop the VM first (best-effort, may already be stopped)
        let _ = self
            .post(
                &format!("/nodes/{}/vms/{}/stop", node, provider_vm_id),
                &serde_json::json!({}),
            )
            .await;

        tokio::time::sleep(std::time::Duration::from_secs(3)).await;

        self.delete(&format!("/nodes/{}/vms/{}", node, provider_vm_id))
            .await?;

        Ok(())
    }

    async fn start_instance(&self, provider_vm_id: &str, node: &str) -> Result<()> {
        Self::validate_node_and_vm(node, provider_vm_id)?;

        self.post(
            &format!("/nodes/{}/vms/{}/start", node, provider_vm_id),
            &serde_json::json!({}),
        )
        .await?;
        Ok(())
    }

    async fn stop_instance(&self, provider_vm_id: &str, node: &str) -> Result<()> {
        Self::validate_node_and_vm(node, provider_vm_id)?;

        self.post(
            &format!("/nodes/{}/vms/{}/stop", node, provider_vm_id),
            &serde_json::json!({}),
        )
        .await?;
        Ok(())
    }

    async fn get_instance_state(&self, provider_vm_id: &str, node: &str) -> Result<InstanceState> {
        Self::validate_node_and_vm(node, provider_vm_id)?;

        let vms = self.list_vms(node).await?;
        let found = vms.iter().any(|v| v.as_str() == Some(provider_vm_id));

        if found {
            Ok(InstanceState::Running)
        } else {
            Ok(InstanceState::Stopped)
        }
    }

    async fn get_instance_ip(&self, provider_vm_id: &str, node: &str) -> Result<String> {
        Self::validate_node_and_vm(node, provider_vm_id)?;

        let json = self
            .get(&format!("/nodes/{}/vms/{}/ip", node, provider_vm_id))
            .await?;

        let ips = json["ip_addresses"].as_array();

        match ips {
            Some(ips) if !ips.is_empty() => {
                // Prefer the first non-loopback, non-link-local IPv4 address.
                // The QEMU Guest Agent may return multiple interfaces;
                // we want one that is reachable for Sunshine streaming.
                for ip_val in ips {
                    if let Some(ip_str) = ip_val.as_str() {
                        if !ip_str.starts_with("127.")
                            && !ip_str.starts_with("169.254.")
                            && ip_str.contains('.')
                        {
                            return Ok(ip_str.to_string());
                        }
                    }
                }
                // Fallback to first IP if none match the filter
                let ip = ips[0].as_str().unwrap_or("0.0.0.0");
                Ok(ip.to_string())
            }
            _ => Ok("0.0.0.0".to_string()),
        }
    }

    async fn get_sunshine_endpoint(&self, handle: &SliceHandle) -> Result<SunshineEndpoint> {
        let ip = self
            .get_instance_ip(&handle.provider_vm_id, &handle.node)
            .await?;

        Ok(SunshineEndpoint {
            ip,
            api_port: 47990,
            gamestream_port_range: (47984, 48010),
        })
    }
}
