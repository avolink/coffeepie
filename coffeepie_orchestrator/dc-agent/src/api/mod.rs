// Copyright (c) 2025 Coffee Pie Contributors
// All rights reserved.
//
// See types.rs for full license text.

use std::sync::Arc;

use axum::extract::{Path, State};
use axum::http::{HeaderMap, StatusCode};
use axum::Json;

use crate::adapter::HypervisorAdapter;
use crate::types::{is_safe_identifier, ApiResponse, CapacityReport, CreateSliceRequest};

/// Shared application state passed to all route handlers.
#[derive(Clone)]
pub struct AppState {
    pub adapter: Arc<Box<dyn HypervisorAdapter>>,
    /// Central QFDM broker URL for heartbeats (optional — can be disabled)
    pub broker_url: Option<String>,
    pub agent_id: String,
    /// Shared auth token for mutation endpoints (Broker → Agent).
    /// If empty, auth is disabled (insecure — only for development).
    pub auth_token: Option<String>,
}

/// Verify the request is authenticated.
///
/// Checks the `Authorization: Bearer <token>` header against the configured
/// `DC_AGENT_AUTH_TOKEN`. If no auth token is configured (empty), auth is
/// bypassed with a warning — this is only acceptable in development.
fn verify_auth(headers: &HeaderMap, auth_token: &Option<String>) -> Result<(), (StatusCode, String)> {
    let token = match auth_token {
        Some(t) if !t.is_empty() => t,
        _ => {
            tracing::warn!("DC_AGENT_AUTH_TOKEN not set — accepting unauthenticated request");
            return Ok(());
        }
    };

    let auth_header = headers
        .get("Authorization")
        .and_then(|v| v.to_str().ok())
        .unwrap_or("");

    let expected = format!("Bearer {}", token);

    if auth_header == expected {
        Ok(())
    } else {
        tracing::warn!("Authentication failed: invalid or missing Authorization header");
        Err((
            StatusCode::UNAUTHORIZED,
            "Unauthorized: invalid or missing auth token".to_string(),
        ))
    }
}

/// Sanitize an error for the API response.
/// Logs the full error via tracing and returns a generic message to the caller
/// to avoid leaking internal infrastructure details (hostnames, IPs, paths).
fn sanitize_error(context: &str, error: &dyn std::error::Error) -> String {
    tracing::error!(error = %error, context = %context, "Request failed");
    format!("{}: internal error", context)
}

// ─── Health ────────────────────────────────────────────────────────────

/// GET /health — Simple health check. No auth required.
pub async fn health() -> Json<serde_json::Value> {
    Json(serde_json::json!({
        "status": "ok",
        "service": "coffeepie-dc-agent",
        "version": env!("CARGO_PKG_VERSION"),
    }))
}

// ─── Capacity ──────────────────────────────────────────────────────────

/// GET /capacity — Called by the QFDM broker to get current DC capacity.
/// No auth required (read-only operational data).
pub async fn get_capacity(
    State(state): State<AppState>,
) -> Json<ApiResponse<CapacityReport>> {
    match state.adapter.get_capacity().await {
        Ok(report) => Json(ApiResponse::ok(report)),
        Err(e) => Json(ApiResponse::err(sanitize_error("get_capacity", &e))),
    }
}

// ─── Templates ─────────────────────────────────────────────────────────

/// GET /templates — List available OS templates.
/// No auth required (read-only).
pub async fn list_templates(
    State(state): State<AppState>,
) -> Json<ApiResponse<Vec<String>>> {
    match state.adapter.list_templates().await {
        Ok(templates) => Json(ApiResponse::ok(templates)),
        Err(e) => Json(ApiResponse::err(sanitize_error("list_templates", &e))),
    }
}

// ─── Instances ─────────────────────────────────────────────────────────

/// POST /instances — Create a new VM instance (slice).
/// Requires auth.
pub async fn create_instance(
    State(state): State<AppState>,
    headers: HeaderMap,
    Json(request): Json<CreateSliceRequest>,
) -> (StatusCode, Json<ApiResponse<crate::types::CreateSliceResponse>>) {
    if let Err((status, msg)) = verify_auth(&headers, &state.auth_token) {
        return (status, Json(ApiResponse::err(msg)));
    }

    // Validate input
    if let Err(msg) = request.validate() {
        return (StatusCode::BAD_REQUEST, Json(ApiResponse::err(msg)));
    }

    match state.adapter.create_instance(request).await {
        Ok(handle) => (
            StatusCode::OK,
            Json(ApiResponse::ok(crate::types::CreateSliceResponse { handle })),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiResponse::err(sanitize_error("create_instance", &e))),
        ),
    }
}

/// DELETE /instances/:instance_id — Destroy a VM instance.
/// Requires auth.
pub async fn destroy_instance(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> (StatusCode, Json<ApiResponse<String>>) {
    if let Err((status, msg)) = verify_auth(&headers, &state.auth_token) {
        return (status, Json(ApiResponse::err(msg)));
    }

    // Validate instance_id
    if !is_safe_identifier(&instance_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid instance_id: {}",
                instance_id
            ))),
        );
    }

    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err("provider_vm_id and node are required")),
        );
    }

    // Validate inputs against injection
    if !is_safe_identifier(provider_vm_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid provider_vm_id: {}",
                provider_vm_id
            ))),
        );
    }
    if !is_safe_identifier(node) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!("Invalid node: {}", node))),
        );
    }

    match state
        .adapter
        .destroy_instance(&instance_id, provider_vm_id, node)
        .await
    {
        Ok(()) => (
            StatusCode::OK,
            Json(ApiResponse::ok("Instance destroyed".to_string())),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiResponse::err(sanitize_error("destroy_instance", &e))),
        ),
    }
}

/// POST /instances/:instance_id/start — Start a stopped instance.
/// Requires auth.
pub async fn start_instance(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> (StatusCode, Json<ApiResponse<String>>) {
    if let Err((status, msg)) = verify_auth(&headers, &state.auth_token) {
        return (status, Json(ApiResponse::err(msg)));
    }

    // Validate instance_id
    if !is_safe_identifier(&instance_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid instance_id: {}",
                instance_id
            ))),
        );
    }

    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err("provider_vm_id and node are required")),
        );
    }

    // Validate inputs against injection
    if !is_safe_identifier(provider_vm_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid provider_vm_id: {}",
                provider_vm_id
            ))),
        );
    }
    if !is_safe_identifier(node) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!("Invalid node: {}", node))),
        );
    }

    match state.adapter.start_instance(provider_vm_id, node).await {
        Ok(()) => (
            StatusCode::OK,
            Json(ApiResponse::ok("Instance started".to_string())),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiResponse::err(sanitize_error("start_instance", &e))),
        ),
    }
}

/// POST /instances/:instance_id/stop — Stop a running instance.
/// Requires auth.
pub async fn stop_instance(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(instance_id): Path<String>,
    Json(body): Json<serde_json::Value>,
) -> (StatusCode, Json<ApiResponse<String>>) {
    if let Err((status, msg)) = verify_auth(&headers, &state.auth_token) {
        return (status, Json(ApiResponse::err(msg)));
    }

    // Validate instance_id
    if !is_safe_identifier(&instance_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid instance_id: {}",
                instance_id
            ))),
        );
    }

    let provider_vm_id = body["provider_vm_id"].as_str().unwrap_or("");
    let node = body["node"].as_str().unwrap_or("");

    if provider_vm_id.is_empty() || node.is_empty() {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err("provider_vm_id and node are required")),
        );
    }

    // Validate inputs against injection
    if !is_safe_identifier(provider_vm_id) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!(
                "Invalid provider_vm_id: {}",
                provider_vm_id
            ))),
        );
    }
    if !is_safe_identifier(node) {
        return (
            StatusCode::BAD_REQUEST,
            Json(ApiResponse::err(format!("Invalid node: {}", node))),
        );
    }

    match state.adapter.stop_instance(provider_vm_id, node).await {
        Ok(()) => (
            StatusCode::OK,
            Json(ApiResponse::ok("Instance stopped".to_string())),
        ),
        Err(e) => (
            StatusCode::INTERNAL_SERVER_ERROR,
            Json(ApiResponse::err(sanitize_error("stop_instance", &e))),
        ),
    }
}
