// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use anyhow::{Context, Result};
use async_trait::async_trait;

use crate::adapter::HypervisorAdapter;
use crate::types::{
    CapacityReport, CreateSliceRequest, HealthStatus, InstanceState, NodeCapacity, RunningInstance,
    SliceHandle, SunshineEndpoint,
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

    /// Call GET on a proxmox_backend endpoint
    async fn get(&self, path: &str) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        let resp = self
            .client
            .get(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .with_context(|| format!("GET {} failed", url))?;

        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// Call POST on a proxmox_backend endpoint
    async fn post(&self, path: &str, body: &serde_json::Value) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        let resp = self
            .client
            .post(&url)
            .header("Authorization", self.auth_header())
            .header("Content-Type", "application/json")
            .json(body)
            .send()
            .await
            .with_context(|| format!("POST {} failed", url))?;

        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// Call DELETE on a proxmox_backend endpoint
    async fn delete(&self, path: &str) -> Result<serde_json::Value> {
        let url = format!("{}{}", self.backend_url, path);
        let resp = self
            .client
            .delete(&url)
            .header("Authorization", self.auth_header())
            .send()
            .await
            .with_context(|| format!("DELETE {} failed", url))?;

        let json: serde_json::Value = resp.json().await?;
        Ok(json)
    }

    /// List all Proxmox nodes from the backend
    async fn list_nodes(&self) -> Result<Vec<String>> {
        let json = self.get("/nodes").await?;
        let data = json["data"].as_array().unwrap_or(&vec![]);
        Ok(data.iter().filter_map(|n| n["node"].as_str().map(String::from)).collect())
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
                    // Proxmox templates are VMs named with "-template" suffix
                    // or tagged accordingly. We include all VM names here;
                    // the orchestrator frontend filters as needed.
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
            // VM as one slice unit. The backend will be extended to expose
            // actual node metrics (CPU, RAM, disk) in a future phase.
            //
            // TODO: When proxmox_backend adds GET /nodes/{node}/status with
            //       maxcpu, maxmem, maxdisk, cpu, mem, disk, call that endpoint
            //       and replace these estimates with real numbers.
            let estimated_max_slices = 64; // Conservative per-node capacity
            let slices_available = estimated_max_slices.saturating_sub(total_vms);

            available_slices.push(NodeCapacity {
                node_name: node_name.clone(),
                total_cpu_cores: estimated_max_slices, // 1 slice = ~1 vCore
                used_cpu_cores: total_vms,
                total_ram_gb: estimated_max_slices, // 1 slice = ~1 GB RAM
                used_ram_gb: total_vms,
                total_gpu_mb: 0,
                used_gpu_mb: 0,
                slices_available,
                total_disk_gb: estimated_max_slices * 133, // 8 SSD + 125 HDD per slice
                used_disk_gb: total_vms * 133,
            });

            // Collect running instances
            for vm_name in vms {
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

        // Generate a VMID (Proxmox requires integer VMID)
        let vmid = (chrono::Utc::now().timestamp() % 1000000) as u32;

        // Clone from template via proxmox_backend
        let clone_body = serde_json::json!({
            "source_name": request.template,
            "name": new_name,
            "newid": vmid,
            "node": target_node,
            "full": 0, // linked clone for speed
        });

        let result = self.post("/clone-by-name", &clone_body).await;

        if let Err(ref e) = result {
            return Err(anyhow::anyhow!("Failed to clone VM: {}", e));
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

    async fn destroy_instance(&self, _instance_id: &str, provider_vm_id: &str, node: &str) -> Result<()> {
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
        self.post(
            &format!("/nodes/{}/vms/{}/start", node, provider_vm_id),
            &serde_json::json!({}),
        )
        .await?;
        Ok(())
    }

    async fn stop_instance(&self, provider_vm_id: &str, node: &str) -> Result<()> {
        self.post(
            &format!("/nodes/{}/vms/{}/stop", node, provider_vm_id),
            &serde_json::json!({}),
        )
        .await?;
        Ok(())
    }

    async fn get_instance_state(&self, provider_vm_id: &str, node: &str) -> Result<InstanceState> {
        // The proxmox_backend doesn't expose a per-VM status endpoint yet.
        // Check if the VM exists by looking it up in the VM list.
        // If the VM is deletable (found in list), assume it's running.
        let vms = self.list_vms(node).await?;
        let found = vms.iter().any(|v| v.as_str() == Some(provider_vm_id));

        if found {
            Ok(InstanceState::Running)
        } else {
            Ok(InstanceState::Stopped)
        }
    }

    async fn get_instance_ip(&self, provider_vm_id: &str, node: &str) -> Result<String> {
        let json = self
            .get(&format!("/nodes/{}/vms/{}/ip", node, provider_vm_id))
            .await?;

        let ips = json["ip_addresses"].as_array();
        match ips {
            Some(ips) if !ips.is_empty() => {
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
