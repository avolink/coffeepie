// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::sync::Arc;
use std::time::Duration;

use crate::adapter::HypervisorAdapter;
use crate::types::CapacityReport;

/// Heartbeat configuration.
const DEFAULT_HEARTBEAT_INTERVAL_SECS: u64 = 30;

/// Spawn a background task that periodically:
/// 1. Queries the hypervisor for current capacity
/// 2. Posts the capacity report to the central QFDM broker
///
/// Runs until the tokio runtime shuts down.
pub fn spawn_heartbeat(
    adapter: Arc<Box<dyn HypervisorAdapter>>,
    broker_url: String,
    agent_id: String,
) {
    tokio::spawn(async move {
        let client = reqwest::Client::builder()
            .use_rustls_tls()
            .timeout(Duration::from_secs(10))
            .build()
            .expect("Failed to build heartbeat HTTP client");

        let heartbeat_url = format!("{}/api/v1/dc-agents/heartbeat", broker_url.trim_end_matches('/'));

        tracing::info!(
            agent_id = %agent_id,
            broker_url = %broker_url,
            interval_secs = DEFAULT_HEARTBEAT_INTERVAL_SECS,
            "Heartbeat worker started"
        );

        loop {
            // Query capacity from the hypervisor
            match adapter.get_capacity().await {
                Ok(report) => {
                    // Send to central broker
                    match client
                        .post(&heartbeat_url)
                        .header("X-Agent-Id", &agent_id)
                        .json(&report)
                        .send()
                        .await
                    {
                        Ok(resp) if resp.status().is_success() => {
                            tracing::debug!(
                                agent_id = %agent_id,
                                status = resp.status().as_u16(),
                                "Heartbeat sent successfully"
                            );
                        }
                        Ok(resp) => {
                            // Capture the status before .text() consumes the response.
                            let status = resp.status().as_u16();
                            let body = resp.text().await.unwrap_or_default();
                            tracing::warn!(
                                agent_id = %agent_id,
                                status = status,
                                body = %body,
                                "Heartbeat rejected by broker"
                            );
                        }
                        Err(e) => {
                            tracing::error!(
                                agent_id = %agent_id,
                                error = %e,
                                "Failed to send heartbeat to broker"
                            );
                        }
                    }
                }
                Err(e) => {
                    // Send a degraded heartbeat even on failure
                    let emergency_report = CapacityReport {
                        agent_id: agent_id.clone(),
                        timestamp: chrono::Utc::now().timestamp(),
                        available_slices: vec![],
                        running_instances: vec![],
                        health: crate::types::HealthStatus::Unhealthy(format!(
                            "Capacity query failed: {}",
                            e
                        )),
                    };

                    let _ = client
                        .post(&heartbeat_url)
                        .header("X-Agent-Id", &agent_id)
                        .json(&emergency_report)
                        .send()
                        .await;
                }
            }

            tokio::time::sleep(Duration::from_secs(DEFAULT_HEARTBEAT_INTERVAL_SECS)).await;
        }
    });
}
