// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::sync::atomic::{AtomicU32, Ordering};

use anyhow::{anyhow, Context, Result};
use async_trait::async_trait;

use crate::adapter::HypervisorAdapter;
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

    /// List all Proxmox nodes from the backend
    async fn list_nodes(&self) -> Result<Vec<String>> {
        let json = self.get("/nodes").await?;
        let data = json["data"].as_array().unwrap_or(&vec![]);
        Ok(data
            .iter()
            .filter_map(|n| n["node"].as_str().map(String::from))
            .collect())
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
        let nodes = self.list_nodes().await?;
        let mut available_slices = Vec::new();
        let mut running_instances = Vec::new();

        for node_name in &nodes {
            let vms = self.list_vms(node_name).await?;
            let total_vms = vms.len() as u32;

            // Since the proxmox_backend doesn't expose raw node resources yet,
            // we estimate capacity from VM counts. Each VM on Proxmox can
            // theoretically host many slices, but we conservatively treat each
            // VM as one slice unit.
            //
            // TODO: When proxmox_backend adds GET /nodes/{node}/status with
            //       maxcpu, maxmem, maxdisk, cpu, mem, disk, call that endpoint
            //       and replace these estimates with real numbers.
            let estimated_max_slices = crate::types::MAX_SLICE_FACTOR;
            let slices_available = estimated_max_slices.saturating_sub(total_vms);

            available_slices.push(NodeCapacity {
                node_name: node_name.clone(),
                total_cpu_cores: estimated_max_slices,
                used_cpu_cores: total_vms,
                total_ram_gb: estimated_max_slices,
                used_ram_gb: total_vms,
                total_gpu_mb: 0,
                used_gpu_mb: 0,
                slices_available,
                total_disk_gb: estimated_max_slices * 133,
                used_disk_gb: total_vms * 133,
            });

            // Collect running instances
            for vm_name in &vms {
                if let Some(name) = vm_name.as_str() {
                    if name.starts_with("cp-") {
                        let instance_id = name.trim_start_matches("cp-").to_string();
                        running_instances.push(RunningInstance {
                            instance_id,
                            node: node_name.clone(),
                            state: InstanceState::Running, // Conservative default
                            user_id: None,
                            created_at: chrono::Utc::now().timestamp(),
                        });
                    }
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

        // Pick a node — preferred or first available
        let nodes = self.list_nodes().await?;
        let target_node = request
            .preferred_node
            .clone()
            .or_else(|| nodes.first().cloned())
            .context("No Proxmox nodes available")?;

        // Validate node name is safe (defense-in-depth)
        if !is_safe_identifier(&target_node) {
            return Err(anyhow!("Invalid node name: {}", target_node));
        }

        // Generate a VMID using an atomic counter (collision-free, race-free)
        let vmid = next_vmid();

        // Clone from template via proxmox_backend
        let clone_body = serde_json::json!({
            "source_name": request.template,
            "name": new_name,
            "newid": vmid,
            "node": target_node,
            "full": 0, // linked clone for speed
        });

        let clone_result = self.post("/clone-by-name", &clone_body).await?;

        // Check for backend-level errors returned as JSON (proxmox_backend
        // returns {"error": "..."} with HTTP 200 on application failures)
        if let Some(error_msg) = clone_result["error"].as_str() {
            return Err(anyhow!("Clone operation failed: {}", error_msg));
        }

        // Start the VM
        let _ = self
            .post(
                &format!("/nodes/{}/vms/{}/start", target_node, new_name),
                &serde_json::json!({}),
            )
            .await;

        // Wait briefly for the VM to boot and get an IP
        tokio::time::sleep(std::time::Duration::from_secs(10)).await;

        let ip = self
            .get_instance_ip(&new_name, &target_node)
            .await
            .unwrap_or_else(|_| "0.0.0.0".to_string());

        let handle = SliceHandle {
            instance_id: instance_id.clone(),
            provider_vm_id: new_name.clone(),
            node: target_node,
            sunshine_endpoint: Some(SunshineEndpoint {
                ip: ip.clone(),
                api_port: 47990,
                gamestream_port_range: (47984, 48010),
            }),
            created_at: chrono::Utc::now().timestamp(),
            spec: request.spec,
        };

        Ok(handle)
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
