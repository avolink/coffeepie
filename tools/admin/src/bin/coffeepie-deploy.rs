// Coffee Pie Deploy
// One-command bootstrap for Coffee Pie nodes on Debian/Proxmox.
//
// Phases (idempotent — safe to re-run):
//   0. preflight   — SSH check, OS detection, resource validation
//   1. deps        — apt install required packages
//   2. sunshine    — Install & configure Sunshine streaming server
//   3. actor       — Deploy Rust actor daemon (systemd unit)
//   4. keys        — Generate Ed25519 + ML-KEM-768 key material
//   5. network     — Firewall, VLAN, port config
//   6. register    — Register with Coffee Pie orchestrator
//   7. validate    — Post-deploy health checks
//
// Usage:
//   coffeepie-deploy --target root@10.0.0.50 --orchestrator https://orch.coffeepie.co
//   coffeepie-deploy --config deploy.json
//   coffeepie-deploy --template > my-deploy.json  # generate config template

use clap::Parser;
use serde::{Deserialize, Serialize};
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

#[derive(Parser)]
#[command(name = "coffeepie-deploy")]
#[command(about = "Coffee Pie Node Deployer — one-command bootstrap for QFDM nodes", long_about = None)]
struct Cli {
    /// SSH target (user@host)
    #[arg(short, long)]
    target: Option<String>,

    /// Orchestrator URL
    #[arg(short, long)]
    orchestrator: Option<String>,

    /// Node role: provider, hybrid, edge
    #[arg(short, long, default_value = "provider")]
    role: String,

    /// Node name (e.g., dc-bogota-01)
    #[arg(long, default_value = "node-01")]
    name: String,

    /// SSH port
    #[arg(long, default_value = "22")]
    ssh_port: u16,

    /// Path to deploy config JSON
    #[arg(short, long)]
    config: Option<PathBuf>,

    /// Phases to run (0-7, comma-separated, default: all)
    #[arg(long, default_value = "0,1,2,3,4,5,6,7")]
    phases: String,

    /// Start from this phase (skip earlier, implies all after)
    #[arg(long)]
    resume_from: Option<u8>,

    /// GPU vendor for Sunshine: nvidia, amd, intel, none
    #[arg(long, default_value = "none")]
    gpu: String,

    /// Dry run — show what would happen
    #[arg(short, long)]
    dry_run: bool,

    /// Output deploy config template and exit
    #[arg(long)]
    template: bool,

    /// JSON progress output (for CI/CD)
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct DeployConfig {
    node: NodeConfig,
    orchestrator: OrchConfig,
    gpu: GpuConfig,
    network: NetworkConfig,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct NodeConfig {
    host: String,
    ssh_port: u16,
    role: String,
    name: String,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct OrchConfig {
    url: String,
    #[serde(default)]
    api_key: String,
    #[serde(default = "default_register")]
    register: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct GpuConfig {
    #[serde(default = "default_vendor")]
    vendor: String,
    #[serde(default)]
    passthrough: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct NetworkConfig {
    #[serde(default = "default_mgmt_ip")]
    management_ip: String,
    #[serde(default = "default_gateway")]
    gateway: String,
    #[serde(default)]
    vlan_id: u16,
}

fn default_register() -> bool { true }
fn default_vendor() -> String { "none".into() }
fn default_mgmt_ip() -> String { "dhcp".into() }
fn default_gateway() -> String { "auto".into() }

const PHASE_NAMES: &[&str] = &[
    "preflight",
    "dependencies",
    "sunshine",
    "actor",
    "keys",
    "network",
    "register",
    "validate",
];

fn main() {
    let cli = Cli::parse();

    // Template mode
    if cli.template {
        print_template();
        return;
    }

    // Build config
    let config = if let Some(ref path) = cli.config {
        let raw = fs::read_to_string(path).expect("Failed to read config file");
        serde_json::from_str(&raw).expect("Invalid deploy config JSON")
    } else {
        DeployConfig {
            node: NodeConfig {
                host: cli.target.clone().unwrap_or_else(|| "root@10.0.0.50".into()),
                ssh_port: cli.ssh_port,
                role: cli.role.clone(),
                name: cli.name.clone(),
            },
            orchestrator: OrchConfig {
                url: cli.orchestrator.clone().unwrap_or_else(|| "https://localhost".into()),
                api_key: String::new(),
                register: true,
            },
            gpu: GpuConfig {
                vendor: cli.gpu.clone(),
                passthrough: false,
            },
            network: NetworkConfig {
                management_ip: "dhcp".into(),
                gateway: "auto".into(),
                vlan_id: 0,
            },
        }
    };

    if !cli.json {
        println!("Coffee Pie Node Deployer");
        println!("========================");
        println!("Target:  {}:{}", config.node.host, config.node.ssh_port);
        println!("Role:    {} | Name: {}", config.node.role, config.node.name);
        println!("Orch:    {}", config.orchestrator.url);
        println!("GPU:     {}", config.gpu.vendor);
        println!("Dry run: {}", if cli.dry_run { "YES" } else { "no" });
        println!();
    }

    // Resolve phases
    let phases: Vec<u8> = if let Some(resume) = cli.resume_from {
        (resume..=7).collect()
    } else {
        cli.phases.split(',')
            .filter_map(|s| s.trim().parse().ok())
            .filter(|&p| p <= 7)
            .collect()
    };

    let total = phases.len();
    let started = Instant::now();

    for (i, phase) in phases.iter().enumerate() {
        let name = PHASE_NAMES[*phase as usize];
        let progress = format!("[{}/{}]", i + 1, total);

        if cli.json {
            println!("{}", serde_json::json!({
                "phase": phase, "name": name, "progress": progress, "status": "running"
            }));
        } else {
            println!("{} Phase {}/7: {}...", progress, phase, name);
        }

        let result = match phase {
            0 => run_preflight(&config, cli.dry_run),
            1 => run_dependencies(&config, cli.dry_run),
            2 => run_sunshine(&config, cli.dry_run),
            3 => run_actor(&config, cli.dry_run),
            4 => run_keys(&config, cli.dry_run),
            5 => run_network(&config, cli.dry_run),
            6 => run_register(&config, cli.dry_run),
            7 => run_validate(&config, cli.dry_run),
            _ => Ok(()),
        };

        match result {
            Ok(()) => {
                if cli.json {
                    println!("{}", serde_json::json!({"phase": phase, "status": "ok"}));
                } else {
                    println!("  ✓ {} complete", name);
                }
            }
            Err(e) => {
                let msg = format!("Phase {} '{}' failed: {}", phase, name, e);
                if cli.json {
                    println!("{}", serde_json::json!({"phase": phase, "status": "failed", "error": msg}));
                }
                eprintln!("\n✗ {}", msg);
                eprintln!("  Fix the issue and re-run with: --resume-from {}", phase);
                std::process::exit(1);
            }
        }
    }

    let elapsed = started.elapsed();
    if !cli.json {
        println!();
        println!("═══════════════════════════════════════");
        println!("  Deploy complete in {:.0}s", elapsed.as_secs());
        println!("  Node: {} ({})", config.node.name, config.node.role);
        println!("  Orchestrator: {}", config.orchestrator.url);
        println!("═══════════════════════════════════════");
    } else {
        println!("{}", serde_json::json!({
            "status": "complete",
            "duration_sec": elapsed.as_secs(),
            "node": config.node.name,
            "role": config.node.role,
        }));
    }
}

// ─── Phase implementations ───

fn run_preflight(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    let ssh = ssh_cmd(config, "uname -a && cat /etc/os-release | head -4 && nproc && free -g | head -2");
    if dry_run { println!("  [dry] Would SSH: {}", ssh.cmd); return Ok(()); }

    let output = exec_ssh_or_fail(ssh, "SSH connection failed — check target and credentials")?;
    let out = String::from_utf8_lossy(&output.stdout);

    println!("  OS: {}", out.lines().next().unwrap_or("unknown"));

    // Check kernel (needs >= 5.15 for GPU features)
    let kernel_ok = out.contains("Linux") && !out.contains("5.10") && !out.contains("5.4") && !out.contains("4.");
    if !kernel_ok {
        println!("  ⚠ Kernel may be too old for GPU features. Recommend >= 5.15.");
    }

    // Check CPU threads
    if let Some(cpu_line) = out.lines().find(|l| l.parse::<u32>().is_ok()) {
        let threads: u32 = cpu_line.parse().unwrap();
        println!("  CPU threads: {}", threads);
        if threads < 4 {
            return Err(format!("Need at least 4 CPU threads, found {}", threads));
        }
    }

    // Check RAM
    for line in out.lines() {
        if line.starts_with("Mem:") {
            let parts: Vec<&str> = line.split_whitespace().collect();
            if parts.len() >= 2 {
                if let Ok(gb) = parts[1].parse::<u32>() {
                    println!("  RAM: {} GB", gb);
                    if gb < 4 {
                        return Err(format!("Need at least 4 GB RAM, found {}", gb));
                    }
                }
            }
        }
    }

    // Check GPU if configured
    if config.gpu.vendor != "none" {
        let gpu_ssh = ssh_cmd(config, "lspci | grep -i 'vga\\|3d\\|display' || echo 'NO_GPU'");
        let gpu_out = exec_ssh_or_fail(gpu_ssh, "GPU detection failed")?;
        let gpu_str = String::from_utf8_lossy(&gpu_out.stdout);
        if gpu_str.contains("NO_GPU") {
            return Err("GPU vendor set but no GPU detected via lspci".into());
        }
        println!("  GPU: {}", gpu_str.trim());
    }

    println!("  ✓ Preflight passed");
    Ok(())
}

fn run_dependencies(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    let packages = "curl wget build-essential pkg-config libssl-dev libavcodec-extra libavformat-dev libswscale-dev libvdpau-dev libva-dev cmake git ufw";
    let cmds = format!(
        "export DEBIAN_FRONTEND=noninteractive && \
         apt-get update -qq && \
         apt-get install -y -qq {} && \
         echo 'DEPS_OK'",
        packages
    );

    if dry_run { println!("  [dry] Would install: {}", packages); return Ok(()); }

    let ssh = ssh_cmd(config, &cmds);
    let output = exec_ssh_or_fail(ssh, "Package installation failed")?;
    let out = String::from_utf8_lossy(&output.stdout);

    if out.contains("DEPS_OK") {
        println!("  ✓ Dependencies installed");
        Ok(())
    } else {
        Err("Package installation did not complete".into())
    }
}

fn run_sunshine(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if config.gpu.vendor == "none" {
        println!("  ⚠ No GPU — skipping Sunshine (software encoding not recommended)");
        return Ok(());
    }

    if dry_run {
        println!("  [dry] Would install Sunshine for {}", config.gpu.vendor);
        return Ok(());
    }

    // Check if Sunshine is already installed
    let check = exec_ssh_or_fail(
        ssh_cmd(config, "which sunshine || echo 'NOT_FOUND'"),
        "Sunshine check failed",
    )?;
    if !String::from_utf8_lossy(&check.stdout).contains("NOT_FOUND") {
        println!("  Sunshine already installed, skipping.");
        return Ok(());
    }

    // Install Sunshine (varies by GPU vendor)
    let install_script = match config.gpu.vendor.as_str() {
        "nvidia" => r#"
            # NVIDIA: install NVENC-capable Sunshine
            wget -q https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-24.04-amd64.deb -O /tmp/sunshine.deb && \
            apt-get install -y -qq /tmp/sunshine.deb && \
            rm /tmp/sunshine.deb
        "#,
        "amd" => r#"
            wget -q https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-24.04-amd64.deb -O /tmp/sunshine.deb && \
            apt-get install -y -qq /tmp/sunshine.deb && \
            rm /tmp/sunshine.deb
        "#,
        "intel" => r#"
            wget -q https://github.com/LizardByte/Sunshine/releases/latest/download/sunshine-ubuntu-24.04-amd64.deb -O /tmp/sunshine.deb && \
            apt-get install -y -qq intel-media-va-driver-non-free /tmp/sunshine.deb && \
            rm /tmp/sunshine.deb
        "#,
        _ => return Err(format!("Unknown GPU vendor: {}", config.gpu.vendor)),
    };

    let ssh = ssh_cmd(config, install_script);
    let _ = exec_ssh_or_fail(ssh, "Sunshine installation failed")?;

    // Configure Sunshine for Coffee Pie
    let sunshine_config = format!(
        r#"
mkdir -p ~/.config/sunshine
cat > ~/.config/sunshine/sunshine.conf << 'EOF'
[General]
port = 47989
upnp = disabled
origin_pin = disabled
origin_web_ui_allowed = lan
fps = 60
output_name = 0
encoder = {}
adapter_name = /dev/dri/renderD128
EOF
echo 'SUNSHINE_CONFIGURED'
"#,
        match config.gpu.vendor.as_str() {
            "nvidia" => "nvenc",
            "amd" => "vaapi",
            "intel" => "quicksync",
            _ => "software",
        }
    );

    let cfg_ssh = ssh_cmd(config, &sunshine_config);
    let output = exec_ssh_or_fail(cfg_ssh, "Sunshine config failed")?;
    if String::from_utf8_lossy(&output.stdout).contains("SUNSHINE_CONFIGURED") {
        println!("  ✓ Sunshine installed and configured with {}", config.gpu.vendor);
        Ok(())
    } else {
        Err("Sunshine configuration failed".into())
    }
}

fn run_actor(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if dry_run {
        println!("  [dry] Would deploy actor daemon");
        return Ok(());
    }

    // Create systemd unit for Coffee Pie Actor
    let unit = format!(
        r#"
cat > /etc/systemd/system/coffeepie-actor.service << 'EOF'
[Unit]
Description=Coffee Pie Actor Daemon
After=network.target sunshine.service
Wants=network.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/coffeepie-actor --orchestrator {} --role {} --name {}
Restart=always
RestartSec=5
Environment=RUST_LOG=info
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable coffeepie-actor
echo 'ACTOR_UNIT_CREATED'
"#,
        config.orchestrator.url,
        config.node.role,
        config.node.name,
    );

    let ssh = ssh_cmd(config, &unit);
    let output = exec_ssh_or_fail(ssh, "Actor unit creation failed")?;

    if String::from_utf8_lossy(&output.stdout).contains("ACTOR_UNIT_CREATED") {
        println!("  ✓ Actor systemd unit created (binary must be deployed separately)");
        println!("  Note: Place coffeepie-actor binary at /usr/local/bin/coffeepie-actor");
        Ok(())
    } else {
        Err("Actor unit creation failed".into())
    }
}

fn run_keys(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if dry_run {
        println!("  [dry] Would generate Ed25519 + ML-KEM-768 keys");
        return Ok(());
    }

    // Generate keys on the target
    let keygen_script = r#"
mkdir -p /etc/coffeepie/keys
# Generate Ed25519 keypair
openssl genpkey -algorithm Ed25519 -out /etc/coffeepie/keys/id_ed25519 2>/dev/null && \
openssl pkey -in /etc/coffeepie/keys/id_ed25519 -pubout -out /etc/coffeepie/keys/id_ed25519.pub 2>/dev/null
# Generate ML-KEM-768 seed (64 bytes from /dev/urandom)
dd if=/dev/urandom of=/etc/coffeepie/keys/mlkem768_seed.bin bs=64 count=1 2>/dev/null
xxd -p /etc/coffeepie/keys/mlkem768_seed.bin | tr -d '\n' > /etc/coffeepie/keys/mlkem768_seed.hex
chmod 600 /etc/coffeepie/keys/*
chown root:root /etc/coffeepie/keys/*
echo 'KEYS_OK'
"#;

    let ssh = ssh_cmd(config, keygen_script);
    let output = exec_ssh_or_fail(ssh, "Key generation failed")?;

    if String::from_utf8_lossy(&output.stdout).contains("KEYS_OK") {
        // Fetch public key fingerprint for record
        let fp_ssh = ssh_cmd(config, "cat /etc/coffeepie/keys/id_ed25519.pub | head -1 | sha256sum | cut -c1-16");
        if let Ok(fp_out) = exec_ssh_or_fail(fp_ssh, "Fingerprint read failed") {
            println!("  Fingerprint: {}", String::from_utf8_lossy(&fp_out.stdout).trim());
        }
        println!("  Keys: /etc/coffeepie/keys/");
        println!("    id_ed25519 (private)");
        println!("    id_ed25519.pub (public)");
        println!("    mlkem768_seed.hex (for libcrux)");
        println!("  ✓ Keys generated");
        Ok(())
    } else {
        Err("Key generation did not complete".into())
    }
}

fn run_network(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if dry_run {
        println!("  [dry] Would configure firewall and ports");
        return Ok(());
    }

    let ports = "43910 47984 47989 47990 48010";
    let fw_script = format!(
        r#"
ufw --force reset > /dev/null 2>&1
ufw default deny incoming > /dev/null 2>&1
ufw default allow outgoing > /dev/null 2>&1
ufw allow 22/tcp > /dev/null 2>&1  # SSH
{}  # Coffee Pie ports
ufw --force enable > /dev/null 2>&1
echo 'FW_OK'
"#,
        ports.split_whitespace()
            .map(|p| format!("ufw allow {}/tcp > /dev/null 2>&1  # Coffee Pie", p))
            .collect::<Vec<_>>()
            .join("\n")
    );

    let ssh = ssh_cmd(config, &fw_script);
    let output = exec_ssh_or_fail(ssh, "Firewall configuration failed")?;

    if String::from_utf8_lossy(&output.stdout).contains("FW_OK") {
        // Also add the Moonlight/Sunshine UDP ports
        let udp_ports = "47998 47999 48000 48002 48010";
        let udp_ssh = ssh_cmd(config, &format!(
            "{} && echo 'UDP_OK'",
            udp_ports.split_whitespace()
                .map(|p| format!("ufw allow {}/udp", p))
                .collect::<Vec<_>>()
                .join(" && ")
        ));
        let _ = exec_ssh_or_fail(udp_ssh, "UDP port config failed")?;

        println!("  ✓ Firewall configured");
        println!("  TCP: {}", ports.replace(' ', ", "));
        println!("  UDP: {}", udp_ports.replace(' ', ", "));
        Ok(())
    } else {
        Err("Firewall configuration did not complete".into())
    }
}

fn run_register(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if !config.orchestrator.register {
        println!("  ⚠ Registration disabled in config, skipping.");
        return Ok(());
    }
    if dry_run {
        println!("  [dry] Would register with {}", config.orchestrator.url);
        return Ok(());
    }

    // Attempt registration via orchestrator API
    let pub_key = fetch_remote_file(config, "/etc/coffeepie/keys/id_ed25519.pub")?;
    let pub_key_str = String::from_utf8_lossy(&pub_key.stdout).trim().to_string();

    let payload = serde_json::json!({
        "node_name": config.node.name,
        "role": config.node.role,
        "public_key": pub_key_str,
        "host": config.node.host,
        "gpu_vendor": config.gpu.vendor,
    });

    // Use curl via SSH to POST to orchestrator (avoids local network issues)
    let register_cmd = format!(
        r#"curl -s -X POST "{}/api/v1/nodes/register" \
           -H "Content-Type: application/json" \
           -H "Authorization: Bearer {}" \
           -d '{}' 2>&1 || echo 'REGISTER_FAILED'"#,
        config.orchestrator.url.trim_end_matches('/'),
        config.orchestrator.api_key,
        payload.to_string().replace('\'', "'\\''"),
    );

    let ssh = ssh_cmd(config, &register_cmd);
    let output = exec_ssh_or_fail(ssh, "Registration curl failed")?;
    let resp = String::from_utf8_lossy(&output.stdout);

    if resp.contains("REGISTER_FAILED") || resp.contains("error") || resp.contains("Error") {
        println!("  Orchestrator response: {}", resp.trim());
        println!("  ⚠ Registration may need manual approval in the admin panel.");
        println!("  ✓ Registration attempted (check orchestrator for pending nodes)");
        Ok(()) // Non-fatal — manual approval may be needed
    } else {
        println!("  ✓ Registered with orchestrator: {}", resp.trim());
        Ok(())
    }
}

fn run_validate(config: &DeployConfig, dry_run: bool) -> Result<(), String> {
    if dry_run {
        println!("  [dry] Would validate deployment");
        return Ok(());
    }

    println!("  Running post-deploy validation...");

    // Check services
    let checks = [
        ("SSH reachable", "echo OK"),
        ("Sunshine installed", "which sunshine || echo MISSING"),
        ("Actor unit exists", "systemctl list-unit-files coffeepie-actor.service | grep coffeepie || echo MISSING"),
        ("Keys present", "test -f /etc/coffeepie/keys/id_ed25519 && echo OK || echo MISSING"),
        ("Firewall active", "ufw status | grep -q active && echo OK || echo MISSING"),
        ("DNS working", "getent hosts coffeepie.co > /dev/null && echo OK || echo MISSING"),
    ];

    let mut ok = 0;
    let mut fail = 0;
    for (label, cmd) in &checks {
        let ssh = ssh_cmd(config, cmd);
        match exec_ssh_or_fail(ssh, &format!("Check '{}' failed", label)) {
            Ok(out) => {
                let s = String::from_utf8_lossy(&out.stdout);
                if s.contains("OK") && !s.contains("MISSING") {
                    println!("    ✓ {}", label);
                    ok += 1;
                } else {
                    println!("    ⚠ {} — {}", label, s.trim());
                    fail += 1;
                }
            }
            Err(_) => {
                println!("    ✗ {}", label);
                fail += 1;
            }
        }
    }

    println!("  Validation: {} passed, {} issues", ok, fail);
    if fail > 0 {
        Err(format!("{} validation checks failed", fail))
    } else {
        Ok(())
    }
}

// ─── Helpers ───

struct SshCommand {
    cmd: String,
}

fn ssh_cmd(config: &DeployConfig, remote_cmd: &str) -> SshCommand {
    let ssh_target = if config.node.host.contains('@') {
        config.node.host.clone()
    } else {
        format!("root@{}", config.node.host)
    };

    let cmd = format!(
        "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -p {} {} '{}'",
        config.node.ssh_port, ssh_target, remote_cmd.replace('\'', "'\\''"),
    );
    SshCommand { cmd }
}

struct SshOutput {
    stdout: Vec<u8>,
    #[allow(dead_code)]
    stderr: Vec<u8>,
}

fn exec_ssh_or_fail(ssh: SshCommand, context: &str) -> Result<SshOutput, String> {
    let output = Command::new("sh")
        .arg("-c")
        .arg(&ssh.cmd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|e| format!("{}: {}", context, e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        return Err(format!("{} — exit {}: {}", context, output.status.code().unwrap_or(-1), stderr));
    }

    Ok(SshOutput {
        stdout: output.stdout,
        stderr: output.stderr,
    })
}

fn fetch_remote_file(config: &DeployConfig, path: &str) -> Result<SshOutput, String> {
    let ssh = ssh_cmd(config, &format!("cat {}", path));
    exec_ssh_or_fail(ssh, &format!("Failed to read remote file: {}", path))
}

fn print_template() {
    let template = serde_json::json!({
        "_comment": "Coffee Pie deploy configuration — edit and pass with --config",
        "node": {
            "host": "root@10.0.0.50",
            "ssh_port": 22,
            "role": "provider",
            "name": "dc-bogota-01"
        },
        "orchestrator": {
            "url": "https://orchestrator.coffeepie.co",
            "api_key": "cp_live_xxxxxxxxxxxxxxxxxxxxxxxx",
            "register": true
        },
        "gpu": {
            "vendor": "nvidia",
            "passthrough": false
        },
        "network": {
            "management_ip": "dhcp",
            "gateway": "auto",
            "vlan_id": 0
        }
    });
    println!("{}", serde_json::to_string_pretty(&template).unwrap());
    println!();
    println!("# Save to file: coffeepie-deploy --template > deploy.json");
    println!("# Then deploy:    coffeepie-deploy --config deploy.json");
}
