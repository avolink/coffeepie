// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use anyhow::Result;
use async_trait::async_trait;

use crate::types::{CapacityReport, CreateSliceRequest, SliceHandle};

/// The universal contract every hypervisor adapter must implement.
///
/// To add a new hypervisor (VMware, KVM, XCP-ng, bare metal, cloud burst),
/// just implement this trait. The rest of the platform never needs to know
/// what's behind the adapter.
///
/// ## Design constraints:
/// - The adapter is STATELESS — all state lives in the hypervisor itself.
///   The DC Agent queries it fresh on every request.
/// - Credentials live in the adapter config, never sent to the central broker.
/// - The adapter handles its own error mapping and retry logic.
#[async_trait]
pub trait HypervisorAdapter: Send + Sync {
    /// Unique name for this adapter type (e.g., "proxmox", "vmware", "qemu-kvm")
    fn adapter_type(&self) -> &str;

    /// List all OS templates available for provisioning
    async fn list_templates(&self) -> Result<Vec<String>>;

    /// Get current capacity of this hypervisor / datacenter
    async fn get_capacity(&self) -> Result<CapacityReport>;

    /// Create a new instance (VM/container) from a template
    async fn create_instance(&self, request: CreateSliceRequest) -> Result<SliceHandle>;

    /// Destroy/delete an instance
    async fn destroy_instance(&self, instance_id: &str, provider_vm_id: &str, node: &str) -> Result<()>;

    /// Start a stopped instance
    async fn start_instance(&self, provider_vm_id: &str, node: &str) -> Result<()>;

    /// Stop a running instance
    async fn stop_instance(&self, provider_vm_id: &str, node: &str) -> Result<()>;

    /// Get the current state of an instance
    async fn get_instance_state(&self, provider_vm_id: &str, node: &str) -> Result<crate::types::InstanceState>;

    /// Get the IP address of a running instance (for Sunshine streaming)
    async fn get_instance_ip(&self, provider_vm_id: &str, node: &str) -> Result<String>;

    /// Get the Sunshine streaming endpoint for a running instance
    async fn get_sunshine_endpoint(&self, handle: &SliceHandle) -> Result<crate::types::SunshineEndpoint>;
}
