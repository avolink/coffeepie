use anyhow::Result;
use tokio::process::Command;

use shared::{
    log,
    ws::{server::ServerContext, types::PreConnect, wait_message_arrival},
};

use crate::{computer, platform};

/// Ensure the sunshine process is running on this host.
/// Sunshine is a self-hosted game stream host for Moonlight clients.
/// It must be installed and available on PATH or at a known location.
async fn ensure_sunshine_running() -> Result<()> {
    // Check if sunshine is already running by looking for its process
    // On Linux: pgrep sunshine, on Windows: tasklist /FI "IMAGENAME eq sunshine.exe"
    #[cfg(target_family = "unix")]
    {
        let output = Command::new("pgrep")
            .arg("-x")
            .arg("sunshine")
            .output()
            .await;
        if let Ok(out) = output {
            if out.status.success() {
                log::info!("Sunshine is already running");
                return Ok(());
            }
        }
    }
    #[cfg(target_family = "windows")]
    {
        let output = Command::new("tasklist")
            .args(["/FI", "IMAGENAME eq sunshine.exe", "/NH"])
            .output()
            .await;
        if let Ok(out) = output {
            if String::from_utf8_lossy(&out.stdout).contains("sunshine.exe") {
                log::info!("Sunshine is already running");
                return Ok(());
            }
        }
    }

    // Start sunshine in the background
    log::info!("Starting Sunshine...");
    #[cfg(target_family = "unix")]
    {
        let child = Command::new("sunshine")
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn();
        match child {
            Ok(_) => log::info!("Sunshine started successfully"),
            Err(e) => {
                log::warn!(
                    "Failed to start sunshine directly: {}. It may run as a system service.",
                    e
                );
            }
        }
    }
    #[cfg(target_family = "windows")]
    {
        let child = Command::new("sunshine.exe")
            .stdin(std::process::Stdio::null())
            .stdout(std::process::Stdio::null())
            .stderr(std::process::Stdio::null())
            .spawn();
        match child {
            Ok(_) => log::info!("Sunshine started successfully"),
            Err(e) => {
                log::warn!(
                    "Failed to start sunshine directly: {}. It may run as a system service.",
                    e
                );
            }
        }
    }

    Ok(())
}

// Owned ServerInfo and Platform
pub async fn worker(server_info: ServerContext, platform: platform::Platform) -> Result<()> {
    let mut rx = server_info.from_ws.subscribe();
    while let Some(env) = wait_message_arrival::<PreConnect>(&mut rx, Some(platform.get_stop())).await {
        log::debug!("Received PreConnect: {:?}", env.msg);
        // Process the Preconnect. If protocol is rdp, ensure the user can rdp
        let msg = env.msg;
        let protocol = msg.protocol.to_lowercase();
        if protocol == "rdp" {
            if let Err(e) = platform.system().ensure_user_can_rdp(&msg.user) {
                log::error!("Failed to ensure user can RDP: {}", e);
            } else {
                log::info!("Ensured user can RDP: {}", msg.user);
            }
        } else if protocol == "sunshine" || protocol == "other" {
            // Ensure Sunshine is running for Moonlight streaming
            if let Err(e) = ensure_sunshine_running().await {
                log::error!("Failed to ensure Sunshine is running: {}", e);
            }
        }
        // If the a pre command is configured, run it
        computer::process_command(&platform, computer::CommandType::PreConnect).await;
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::testing::mock;
    use std::time::Duration;

    use shared::ws::types::{RpcEnvelope, RpcMessage};

    #[tokio::test]
    async fn test_preconnect_worker() {
        log::setup_logging("debug", shared::log::LogType::Tests);
        let server_info = mock::mock_server_info().await;
        let mocked_platform = mock::mock_platform().await;
        let platform = mocked_platform.platform.clone();
        let calls = mocked_platform.calls.clone();
        platform.config().write().await.master_token = Some("mastertoken".into());

        let wsclient_to_workers = server_info.from_ws.clone();

        let _handle = tokio::spawn(async move {
            worker(server_info, platform).await.unwrap();
        });

        // Wait to have at least one receiver
        while wsclient_to_workers.receiver_count() == 0 {
            tokio::time::sleep(Duration::from_millis(50)).await;
        }
        log::info!("wsclient_to_workers has receiver");

        // Send 3 logoff requests
        for _i in 0..3 {
            let req = RpcEnvelope {
                id: None,
                msg: RpcMessage::PreConnect(PreConnect {
                    user: "testuser".into(),
                    protocol: "rdp".into(),
                    ip: Some("192.168.1.1".into()),
                    hostname: Some("testhost".into()),
                    udsuser: Some("udsuser".into()),
                }),
            };
            if let Err(e) = wsclient_to_workers.send(req) {
                log::error!("Failed to send MessageRequest: {}", e);
            }
        }
        // Wait a bit to let processing happen
        tokio::time::sleep(Duration::from_millis(200)).await;

        // No calls here, only redirects messages to wsclient
        log::info!("calls: {:?}", calls.dump());
        assert!(calls.count_calls("operations::ensure_user_can_rdp(") == 3);
    }
}
