// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

pub mod proxmox;

use crate::adapter::HypervisorAdapter;

/// Registry of all available hypervisor adapters.
///
/// When a datacenter registers with the QFDM network, it declares
/// its hypervisor type. The DC Agent selects the matching adapter
/// from this registry.
pub struct AdapterRegistry;

impl AdapterRegistry {
    /// Build the appropriate adapter from a hypervisor type string and config.
    ///
    /// # Arguments
    /// * `hv_type` - One of: "proxmox", "vmware", "qemu-kvm", etc.
    /// * `backend_url` - The base URL of the hypervisor management API
    /// * `bearer_token` - Authentication token for the management API
    /// * `agent_id` - Unique identifier for this DC Agent instance
    pub fn build(
        hv_type: &str,
        backend_url: &str,
        bearer_token: &str,
        agent_id: &str,
    ) -> anyhow::Result<Box<dyn HypervisorAdapter>> {
        match hv_type.to_lowercase().as_str() {
            "proxmox" => Ok(Box::new(proxmox::ProxmoxAdapter::new(
                backend_url.to_string(),
                bearer_token.to_string(),
                agent_id.to_string(),
            ))),
            _ => Err(anyhow::anyhow!(
                "Unknown hypervisor type: {}. Supported: proxmox",
                hv_type
            )),
        }
    }
}
