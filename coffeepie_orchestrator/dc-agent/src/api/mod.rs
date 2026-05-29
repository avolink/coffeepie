// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::sync::Arc;

use axum::extract::{Path, State};
use axum::Json;

use crate::adapter::HypervisorAdapter;
use crate::types::{ApiResponse, CapacityReport};

/// Shared application state passed to all route handlers.
#[derive(Clone)]
pub struct AppState {
    pub adapter: Arc<Box<dyn HypervisorAdapter>>,
    /// Central QFDM broker URL for heartbeats (optional — can be disabled)
    pub broker_url: Option<String>,
    pub agent_id: String,
}

// ─── Capacity ────────────────────────────────────────────────────────

/// GET /capacity — Called by the QFDM broker to get current DC capacity.
pub async fn get_capacity(
    State(state): State<AppState>,
) -> Json<ApiResponse<CapacityReport>> {
    match state.adapter.get_capacity().await {
        Ok(report) => Json(ApiResponse::ok(report)),
        Err(e) => Json(ApiResponse::err(format!("Failed to get capacity: {}", e))),
    }
}

// ─── Instances ────────────────────────────────────────────────────────

/// POST /instances — Create a new VM instance (slice).
pub async fn create_instance(
    State(state): State<AppState>,
    Json(request): Json<crate::types::CreateSliceRequest>,
) -> Json<ApiResponse<crate::types::CreateSliceResponse>> {
    match state.adapter.create_instance(request).await {
        Ok(handle) => Json(ApiResponse::ok(crate::types::CreateSliceResponse { handle })),
        Err(e) => Json(ApiResponse::err(format!("Failed to create instance: {}", e))),
    }
}

/// DELETE /instances/:instance_id — Destroy a VM instance.
pub async fn destroy_instance(
    State(state): State<AppState>,
    Path(instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> Json<ApiResponse<String>> {
    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return Json(ApiResponse::err("provider_vm_id and node are required"));
    }

    match state
        .adapter
        .destroy_instance(&instance_id, provider_vm_id, node)
        .await
    {
        Ok(()) => Json(ApiResponse::ok("Instance destroyed".to_string())),
        Err(e) => Json(ApiResponse::err(format!("Failed to destroy instance: {}", e))),
    }
}

/// POST /instances/:instance_id/start — Start a stopped instance.
pub async fn start_instance(
    State(state): State<AppState>,
    Path(_instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> Json<ApiResponse<String>> {
    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return Json(ApiResponse::err("provider_vm_id and node are required"));
    }

    match state.adapter.start_instance(provider_vm_id, node).await {
        Ok(()) => Json(ApiResponse::ok("Instance started".to_string())),
        Err(e) => Json(ApiResponse::err(format!("Failed to start instance: {}", e))),
    }
}

/// POST /instances/:instance_id/stop — Stop a running instance.
pub async fn stop_instance(
    State(state): State<AppState>,
    Path(_instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> Json<ApiResponse<String>> {
    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return Json(ApiResponse::err("provider_vm_id and node are required"));
    }

    match state.adapter.stop_instance(provider_vm_id, node).await {
        Ok(()) => Json(ApiResponse::ok("Instance stopped".to_string())),
        Err(e) => Json(ApiResponse::err(format!("Failed to stop instance: {}", e))),
    }
}

/// GET /templates — List available OS templates.
pub async fn list_templates(
    State(state): State<AppState>,
) -> Json<ApiResponse<Vec<String>>> {
    match state.adapter.list_templates().await {
        Ok(templates) => Json(ApiResponse::ok(templates)),
        Err(e) => Json(ApiResponse::err(format!("Failed to list templates: {}", e))),
    }
}

/// GET /health — Simple health check.
pub async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "ok",
        "service": "coffeepie-dc-agent",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}
