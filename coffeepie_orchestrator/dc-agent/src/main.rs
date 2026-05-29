// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::net::SocketAddr;
use std::sync::Arc;

use axum::{routing::get, Router};
use tower_http::cors::{Any, CorsLayer};
use tower_http::trace::TraceLayer;

mod adapter;
mod adapters;
mod api;
mod heartbeat;
pub mod types;

use api::AppState;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "coffeepie_dc_agent=info,tower_http=info".into()),
        )
        .with_target(false)
        .init();

    tracing::info!("Coffee Pie DC Agent starting...");

    // ── Configuration (from environment variables) ──────────────────

    let bind_addr: SocketAddr = std::env::var("DC_AGENT_BIND")
        .unwrap_or_else(|_| "0.0.0.0:9090".to_string())
        .parse()
        .expect("Invalid DC_AGENT_BIND address");

    let hypervisor_type = std::env::var("DC_AGENT_HYPERVISOR")
        .unwrap_or_else(|_| "proxmox".to_string());

    let backend_url = std::env::var("DC_AGENT_BACKEND_URL").unwrap_or_else(|_| {
        tracing::warn!("DC_AGENT_BACKEND_URL not set, using default");
        "https://proxmox-api.dc1.lan".to_string()
    });

    let bearer_token = std::env::var("DC_AGENT_BEARER_TOKEN").unwrap_or_else(|_| {
        tracing::warn!("DC_AGENT_BEARER_TOKEN not set — authentication will fail");
        String::new()
    });

    let agent_id = std::env::var("DC_AGENT_ID").unwrap_or_else(|_| {
        let id = format!("dc-agent-{}", uuid::Uuid::new_v4());
        tracing::warn!("DC_AGENT_ID not set, generated: {}", id);
        id
    });

    let broker_url = std::env::var("QFDM_BROKER_URL").ok();

    // ── Build hypervisor adapter ────────────────────────────────────

    let adapter = adapters::AdapterRegistry::build(
        &hypervisor_type,
        &backend_url,
        &bearer_token,
        &agent_id,
    )
    .expect("Failed to build hypervisor adapter");

    let adapter = Arc::new(adapter);

    tracing::info!(
        hypervisor = %hypervisor_type,
        backend = %backend_url,
        agent_id = %agent_id,
        "Hypervisor adapter initialized"
    );

    // ── Start heartbeat to central broker (if configured) ───────────

    if let Some(ref url) = broker_url {
        heartbeat::spawn_heartbeat(adapter.clone(), url.clone(), agent_id.clone());
        tracing::info!(broker_url = %url, "Heartbeat worker spawned");
    } else {
        tracing::info!("No QFDM_BROKER_URL set — heartbeat disabled");
    }

    // ── Build shared application state ──────────────────────────────

    let state = AppState {
        adapter,
        broker_url,
        agent_id: agent_id.clone(),
    };

    // ── Build router ────────────────────────────────────────────────

    let cors = CorsLayer::new()
        .allow_origin(Any)
        .allow_methods(Any)
        .allow_headers(Any);

    let app = Router::new()
        // Health check
        .route("/health", get(api::health))
        // Capacity
        .route("/capacity", get(api::get_capacity))
        // Templates
        .route("/templates", get(api::list_templates))
        // Instances
        .route("/instances", axum::routing::post(api::create_instance))
        .route(
            "/instances/{instance_id}",
            axum::routing::delete(api::destroy_instance),
        )
        .route(
            "/instances/{instance_id}/start",
            axum::routing::post(api::start_instance),
        )
        .route(
            "/instances/{instance_id}/stop",
            axum::routing::post(api::stop_instance),
        )
        .layer(TraceLayer::new_for_http())
        .layer(cors)
        .with_state(state);

    // ── Start server ────────────────────────────────────────────────

    tracing::info!(bind = %bind_addr, "DC Agent HTTP server starting");

    let listener = tokio::net::TcpListener::bind(bind_addr).await?;
    axum::serve(listener, app).await?;

    Ok(())
}
