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

/// Maximum slice multiplier (a single user can request up to 64 base slices).
/// This is consistent with the per-node capacity estimate of 64 slices/node.
pub const MAX_SLICE_FACTOR: u32 = 64;

/// Base slice specification (1 slice = 1 unit of each resource).
/// These values match the Coffee Pie Slice Technical Specifications from AGENTS.md.
pub const BASE_CPU_CORES: u32 = 1;
pub const BASE_RAM_GB: u32 = 1;
pub const BASE_SSD_GB: u32 = 8;
pub const BASE_HDD_GB: u32 = 125;
pub const BASE_NET_MBPS: u32 = 8;
pub const BASE_GPU_MB: u32 = 125;
pub const BASE_RES_VMPX_S: u32 = 15;
pub const BASE_AI_TOPS: u32 = 3;

/// Maximum allowed values per field = base × max factor.
pub const MAX_CPU_CORES: u32 = BASE_CPU_CORES * MAX_SLICE_FACTOR;
pub const MAX_RAM_GB: u32 = BASE_RAM_GB * MAX_SLICE_FACTOR;
pub const MAX_SSD_GB: u32 = BASE_SSD_GB * MAX_SLICE_FACTOR;
pub const MAX_HDD_GB: u32 = BASE_HDD_GB * MAX_SLICE_FACTOR;
pub const MAX_NET_MBPS: u32 = BASE_NET_MBPS * MAX_SLICE_FACTOR;
pub const MAX_GPU_MB: u32 = BASE_GPU_MB * MAX_SLICE_FACTOR;
pub const MAX_RES_VMPX_S: u32 = BASE_RES_VMPX_S * MAX_SLICE_FACTOR;
pub const MAX_AI_TOPS: u32 = BASE_AI_TOPS * MAX_SLICE_FACTOR;

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
            cpu_cores: BASE_CPU_CORES,
            ram_gb: BASE_RAM_GB,
            ssd_gb: BASE_SSD_GB,
            hdd_gb: BASE_HDD_GB,
            net_mbps: BASE_NET_MBPS,
            gpu_mb: BASE_GPU_MB,
            res_vmpx_s: BASE_RES_VMPX_S,
            ai_tops: BASE_AI_TOPS,
        }
    }
}

impl SliceSpec {
    /// Multiply all resources by a factor (e.g., a "4-slice" instance = factor 4).
    /// Uses saturating multiplication to prevent integer overflow wrapping.
    /// Returns None if any field would exceed its maximum allowed value,
    /// or if factor is 0 (which would zero out required fields).
    pub fn scale(&self, factor: u32) -> Option<Self> {
        if factor == 0 {
            return None;
        }
        let cpu_cores = self.cpu_cores.saturating_mul(factor);
        let ram_gb = self.ram_gb.saturating_mul(factor);
        let ssd_gb = self.ssd_gb.saturating_mul(factor);
        let hdd_gb = self.hdd_gb.saturating_mul(factor);
        let net_mbps = self.net_mbps.saturating_mul(factor);
        let gpu_mb = self.gpu_mb.saturating_mul(factor);
        let res_vmpx_s = self.res_vmpx_s.saturating_mul(factor);
        let ai_tops = self.ai_tops.saturating_mul(factor);

        if cpu_cores > MAX_CPU_CORES
            || ram_gb > MAX_RAM_GB
            || ssd_gb > MAX_SSD_GB
            || hdd_gb > MAX_HDD_GB
            || net_mbps > MAX_NET_MBPS
            || gpu_mb > MAX_GPU_MB
            || res_vmpx_s > MAX_RES_VMPX_S
            || ai_tops > MAX_AI_TOPS
        {
            return None;
        }

        Some(Self {
            cpu_cores,
            ram_gb,
            ssd_gb,
            hdd_gb,
            net_mbps,
            gpu_mb,
            res_vmpx_s,
            ai_tops,
        })
    }

    /// Validate that all fields are within allowed bounds.
    /// Returns Ok(()) if valid, or an error message describing which field is out of range.
    pub fn validate(&self) -> Result<(), String> {
        if self.cpu_cores == 0 || self.cpu_cores > MAX_CPU_CORES {
            return Err(format!(
                "cpu_cores must be 1–{} (got {})",
                MAX_CPU_CORES, self.cpu_cores
            ));
        }
        if self.ram_gb == 0 || self.ram_gb > MAX_RAM_GB {
            return Err(format!(
                "ram_gb must be 1–{} (got {})",
                MAX_RAM_GB, self.ram_gb
            ));
        }
        if self.ssd_gb == 0 || self.ssd_gb > MAX_SSD_GB {
            return Err(format!(
                "ssd_gb must be 1–{} (got {})",
                MAX_SSD_GB, self.ssd_gb
            ));
        }
        if self.hdd_gb > MAX_HDD_GB {
            return Err(format!(
                "hdd_gb must be 0–{} (got {})",
                MAX_HDD_GB, self.hdd_gb
            ));
        }
        if self.net_mbps == 0 || self.net_mbps > MAX_NET_MBPS {
            return Err(format!(
                "net_mbps must be 1–{} (got {})",
                MAX_NET_MBPS, self.net_mbps
            ));
        }
        if self.gpu_mb > MAX_GPU_MB {
            return Err(format!(
                "gpu_mb must be 0–{} (got {})",
                MAX_GPU_MB, self.gpu_mb
            ));
        }
        if self.res_vmpx_s == 0 || self.res_vmpx_s > MAX_RES_VMPX_S {
            return Err(format!(
                "res_vmpx_s must be 1–{} (got {})",
                MAX_RES_VMPX_S, self.res_vmpx_s
            ));
        }
        if self.ai_tops > MAX_AI_TOPS {
            return Err(format!(
                "ai_tops must be 0–{} (got {})",
                MAX_AI_TOPS, self.ai_tops
            ));
        }
        Ok(())
    }
}

/// A handle to a running instance, returned when a VM is created.
/// The QFDM broker uses this to manage the instance lifecycle.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SliceHandle {
    /// Unique instance identifier (UUID v4, assigned by this DC Agent)
    pub instance_id: String,
    /// The VM name in the hypervisor (e.g., "cp-<uuid>")
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

impl CreateSliceRequest {
    /// Validate the request payload.
    pub fn validate(&self) -> Result<(), String> {
        // Validate slice spec bounds
        self.spec.validate()?;

        // Validate template name — must be non-empty and not contain path traversal
        if self.template.is_empty() {
            return Err("template is required".to_string());
        }
        if !is_safe_identifier(&self.template) {
            return Err(format!(
                "template contains invalid characters: {}",
                self.template
            ));
        }

        // Validate user_id
        if self.user_id.is_empty() {
            return Err("user_id is required".to_string());
        }
        if !is_safe_identifier(&self.user_id) {
            return Err(format!(
                "user_id contains invalid characters: {}",
                self.user_id
            ));
        }

        // Validate preferred_node if provided
        if let Some(ref node) = self.preferred_node {
            if !is_safe_identifier(node) {
                return Err(format!(
                    "preferred_node contains invalid characters: {}",
                    node
                ));
            }
        }

        Ok(())
    }
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

/// Validate that a string is safe as an identifier for use in URL paths
/// and hypervisor naming. Allowed: alphanumeric, hyphen, underscore, dot.
/// Must be non-empty and start with an alphanumeric character.
pub fn is_safe_identifier(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    let first = s.chars().next().unwrap();
    if !first.is_ascii_alphanumeric() {
        return false;
    }
    s.chars()
        .all(|c| c.is_ascii_alphanumeric() || c == '-' || c == '_' || c == '.')
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_default_spec_is_valid() {
        SliceSpec::default().validate().unwrap();
    }

    #[test]
    fn test_max_spec_is_valid() {
        let spec = SliceSpec {
            cpu_cores: MAX_CPU_CORES,
            ram_gb: MAX_RAM_GB,
            ssd_gb: MAX_SSD_GB,
            hdd_gb: MAX_HDD_GB,
            net_mbps: MAX_NET_MBPS,
            gpu_mb: MAX_GPU_MB,
            res_vmpx_s: MAX_RES_VMPX_S,
            ai_tops: MAX_AI_TOPS,
        };
        spec.validate().unwrap();
    }

    #[test]
    fn test_over_max_fails() {
        let spec = SliceSpec {
            cpu_cores: MAX_CPU_CORES + 1,
            ..SliceSpec::default()
        };
        assert!(spec.validate().is_err());
    }

    #[test]
    fn test_zero_fails() {
        let spec = SliceSpec {
            cpu_cores: 0,
            ..SliceSpec::default()
        };
        assert!(spec.validate().is_err());
    }

    #[test]
    fn test_scale_is_valid_for_default() {
        let scaled = SliceSpec::default().scale(4).unwrap();
        assert_eq!(scaled.cpu_cores, 4);
        assert_eq!(scaled.ram_gb, 4);
    }

    #[test]
    fn test_scale_overflow_returns_none() {
        let huge = SliceSpec {
            cpu_cores: u32::MAX,
            ..SliceSpec::default()
        };
        assert!(huge.scale(2).is_none());
    }

    #[test]
    fn test_scale_factor_zero_returns_none() {
        // Factor 0 would make all required fields 0, which fails validation
        assert!(SliceSpec::default().scale(0).is_none());
    }

    #[test]
    fn test_is_safe_identifier_valid() {
        assert!(is_safe_identifier("test"));
        assert!(is_safe_identifier("ubuntu-2404-template"));
        assert!(is_safe_identifier("cp-550e8400-e29b-41d4-a716-446655440000"));
        assert!(is_safe_identifier("pve-west-1.internal"));
    }

    #[test]
    fn test_is_safe_identifier_invalid() {
        assert!(!is_safe_identifier(""));
        assert!(!is_safe_identifier("-badstart"));
        assert!(!is_safe_identifier("../../etc"));
        assert!(!is_safe_identifier("name with spaces"));
        assert!(!is_safe_identifier("inject\nheader"));
        assert!(!is_safe_identifier("traversal/../evil"));
        assert!(!is_safe_identifier("semicolon;drop"));
        assert!(!is_safe_identifier("backtick`cmd`"));
    }
}
