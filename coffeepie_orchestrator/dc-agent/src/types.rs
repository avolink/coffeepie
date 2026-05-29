// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// Redistribution and use in source and binary forms, with or without modification,
// are permitted provided that the following conditions are met:
//
//    * Redistributions of source code must retain the above copyright notice,
//      this list of conditions and the following disclaimer.
//    * Redistributions in binary form must reproduce the above copyright notice,
//      this list of conditions and the following disclaimer in the documentation
//      and/or other materials provided with the distribution.
//    * Neither the name of Coffee Pie nor the names of its contributors
//      may be used to endorse or promote products derived from this software
//      without specific prior written permission.
//
// THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
// AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
// IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
// DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
// FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
// DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
// SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
// CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
// OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
// OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

use serde::{Deserialize, Serialize};

/// A Coffee Pie "slice" — the unit of computing power a user requests.
/// Maps 1:1 to the Slice Technical Specifications from AGENTS.md.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SliceSpec {
    /// CPU vCores (1 vCore = 1 serial processing thread)
    pub cpu_cores: u32,
    /// RAM in GB
    pub ram_gb: u32,
    /// SSD in GB (OS + small files)
    pub ssd_gb: u32,
    /// HDD in GB (bulk storage)
    pub hdd_gb: u32,
    /// Network bandwidth in Mbps
    pub net_mbps: u32,
    /// GPU RAM in MB
    pub gpu_mb: u32,
    /// Resolution budget in virtual megapixels per second
    pub res_vmpx_s: u32,
    /// AI TOPS (INT8)
    pub ai_tops: u32,
}

impl Default for SliceSpec {
    fn default() -> Self {
        Self {
            cpu_cores: 1,
            ram_gb: 1,
            ssd_gb: 8,
            hdd_gb: 125,
            net_mbps: 8,
            gpu_mb: 125,
            res_vmpx_s: 15,
            ai_tops: 3,
        }
    }
}

impl SliceSpec {
    /// Multiply all resources by a factor (e.g., a "4-slice" instance = factor 4)
    pub fn scale(&self, factor: u32) -> Self {
        Self {
            cpu_cores: self.cpu_cores * factor,
            ram_gb: self.ram_gb * factor,
            ssd_gb: self.ssd_gb * factor,
            hdd_gb: self.hdd_gb * factor,
            net_mbps: self.net_mbps * factor,
            gpu_mb: self.gpu_mb * factor,
            res_vmpx_s: self.res_vmpx_s * factor,
            ai_tops: self.ai_tops * factor,
        }
    }
}

/// A handle to a running instance, returned when a VM is created.
/// The QFDM broker uses this to manage the instance lifecycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SliceHandle {
    /// Unique instance identifier (UUID v4, assigned by this DC Agent)
    pub instance_id: String,
    /// The hypervisor's internal VM identifier (Proxmox vmid, etc.)
    pub provider_vm_id: String,
    /// Which node/host in the DC this instance is running on
    pub node: String,
    /// The Sunshine streaming endpoint this frontend should connect to
    pub sunshine_endpoint: Option<SunshineEndpoint>,
    /// When this instance was created (epoch seconds)
    pub created_at: i64,
    /// The slice spec this instance was provisioned with
    pub spec: SliceSpec,
}

/// Streaming connection details for the Coffee Pie Frontend.
/// The Frontend connects directly to this endpoint (P2P streaming).
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SunshineEndpoint {
    /// IPv4 address of the VM running Sunshine
    pub ip: String,
    /// HTTPS port for Sunshine API (typically 47990)
    pub api_port: u16,
    /// GameStream ports for Moonlight (47984-48010)
    pub gamestream_port_range: (u16, u16),
}

/// A report of this datacenter's current capacity.
/// Sent to the central QFDM broker on heartbeat.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CapacityReport {
    /// DC Agent's unique identifier (set in config)
    pub agent_id: String,
    /// Timestamp of this report (epoch seconds)
    pub timestamp: i64,
    /// How many slices worth of capacity is available per node
    pub available_slices: Vec<NodeCapacity>,
    /// All currently running instances
    pub running_instances: Vec<RunningInstance>,
    /// Overall health status
    pub health: HealthStatus,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct NodeCapacity {
    pub node_name: String,
    /// Total CPU cores available
    pub total_cpu_cores: u32,
    /// Currently used CPU cores
    pub used_cpu_cores: u32,
    /// Total RAM in GB
    pub total_ram_gb: u32,
    /// Currently used RAM in GB
    pub used_ram_gb: u32,
    /// Total GPU RAM in MB
    pub total_gpu_mb: u32,
    /// Currently used GPU RAM in MB
    pub used_gpu_mb: u32,
    /// Equivalent number of slices available
    pub slices_available: u32,
    /// Total disk in GB
    pub total_disk_gb: u32,
    /// Used disk in GB
    pub used_disk_gb: u32,
}

/// Summary of a running instance for the heartbeat report
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RunningInstance {
    pub instance_id: String,
    pub node: String,
    pub state: InstanceState,
    pub user_id: Option<String>,
    pub created_at: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "lowercase")]
pub enum InstanceState {
    Running,
    Stopped,
    Starting,
    Stopping,
    Unknown,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum HealthStatus {
    Healthy,
    Degraded(String),
    Unhealthy(String),
}

/// Request payload from the QFDM broker to create a slice
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSliceRequest {
    /// Desired slice spec (base slice × factor)
    pub spec: SliceSpec,
    /// User ID for attribution
    pub user_id: String,
    /// Which OS template to use
    pub template: String,
    /// Preferred node (optional — agent picks if empty)
    pub preferred_node: Option<String>,
}

/// Response when a slice is created
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateSliceResponse {
    pub handle: SliceHandle,
}

/// Standard API wrapper
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ApiResponse<T: Serialize> {
    pub result: Option<T>,
    pub error: Option<String>,
}

impl<T: Serialize> ApiResponse<T> {
    pub fn ok(result: T) -> Self {
        Self {
            result: Some(result),
            error: None,
        }
    }

    pub fn err(error: impl Into<String>) -> Self {
        Self {
            result: None,
            error: Some(error.into()),
        }
    }
}
