// Coffee Pie Key Generator
// Generates cryptographic key material for Coffee Pie deployments:
//   - Ed25519 keypairs (orchestrator auth, actor identity, API signing)
//   - ML-KEM-768 seed material (post-quantum key exchange, for libcrux)
//
// Outputs keys in multiple formats: PEM, hex, JSON, .env-ready.
// Designed for secure, reproducible deployments across datacenter nodes.

use clap::Parser;
use ed25519_dalek::{SigningKey, VerifyingKey};
use rand::rngs::OsRng;
use rand::RngCore;
use std::fs;
use std::io::Write;
use std::os::unix::fs::PermissionsExt;
use std::path::PathBuf;
use std::time::SystemTime;

#[derive(Parser)]
#[command(name = "coffeepie-keygen")]
#[command(about = "Coffee Pie Cryptographic Key Generator", long_about = None)]
struct Cli {
    /// Output directory for key files
    #[arg(short, long, default_value = "./keys")]
    out_dir: PathBuf,

    /// Key purpose label (actor, orchestrator, tunnel, provider, node)
    #[arg(short, long, default_value = "node")]
    purpose: String,

    /// Node identifier (e.g., dc-us-east-1, node-07)
    #[arg(short, long, default_value = "node-01")]
    node_id: String,

    /// Number of key sets to generate (for multi-node deployments)
    #[arg(short, long, default_value = "1")]
    count: u32,

    /// Deterministic seed phrase for reproducible keygen
    #[arg(long)]
    seed: Option<String>,

    /// Output format: pem, json, env, all
    #[arg(short, long, default_value = "all")]
    format: String,

    /// Generate self-signed CA certificate for internal L2/L3 TLS
    #[arg(long)]
    ca: bool,

    /// JSON-only output (for scripting)
    #[arg(long)]
    json: bool,

    /// Skip file creation, print to stdout only
    #[arg(long)]
    dry_run: bool,
}

#[derive(serde::Serialize)]
struct KeySet {
    node_id: String,
    purpose: String,
    ed25519_public_hex: String,
    ed25519_public_pem: String,
    ed25519_seed_hex: String,
    ed25519_ssh: String,
    mlkem768_seed_hex: String,
    fingerprint: String,
    created_at: String,
}

fn main() {
    let cli = Cli::parse();

    if !cli.dry_run && !cli.out_dir.exists() {
        fs::create_dir_all(&cli.out_dir).expect("Failed to create output directory");
    }

    let mut all_keys: Vec<KeySet> = Vec::new();

    for i in 0..cli.count {
        let node = if cli.count > 1 {
            format!("{}-{:02}", cli.node_id, i + 1)
        } else {
            cli.node_id.clone()
        };
        all_keys.push(generate_keys(&node, &cli.purpose, cli.seed.as_deref(), i));
    }

    if cli.json {
        println!("{}", serde_json::to_string_pretty(&all_keys).unwrap());
        return;
    }

    // JSON output
    if cli.format == "json" || cli.format == "all" {
        let json_str = serde_json::to_string_pretty(&all_keys).unwrap();
        println!("{}", json_str);
        if !cli.dry_run {
            write_file(&cli.out_dir.join(format!("{}_keys.json", cli.purpose)), &json_str, true);
        }
    }

    // Env output
    if cli.format == "env" || cli.format == "all" {
        let mut env_content = String::from("# Coffee Pie keys for purpose: ");
        env_content.push_str(&cli.purpose);
        env_content.push('\n');
        for ks in &all_keys {
            let prefix = ks.node_id.to_uppercase().replace('-', "_");
            env_content.push_str(&format!("COFFEE_{}_ED25519_SEED={}\n", prefix, ks.ed25519_seed_hex));
            env_content.push_str(&format!("COFFEE_{}_ED25519_PUB={}\n", prefix, ks.ed25519_public_hex));
            env_content.push_str(&format!("COFFEE_{}_MLKEM768_SEED={}\n", prefix, ks.mlkem768_seed_hex));
        }
        println!();
        println!("# {}", cli.out_dir.join(format!("{}_keys.env", cli.purpose)).display());
        println!("{}", env_content);
        if !cli.dry_run {
            write_file(&cli.out_dir.join(format!("{}_keys.env", cli.purpose)), &env_content, true);
        }
    }

    // PEM output
    if cli.format == "pem" || cli.format == "all" {
        for ks in &all_keys {
            let dir = cli.out_dir.join(&ks.node_id);
            if !cli.dry_run {
                fs::create_dir_all(&dir).expect("Failed to create node key dir");
            }

            // Ed25519 private seed
            let priv_path = dir.join("id_ed25519");
            if !cli.dry_run {
                write_file(&priv_path, &format!("{}\n", ks.ed25519_seed_hex), true);
            }
            // Ed25519 public PEM
            let pub_path = dir.join("id_ed25519.pub");
            if !cli.dry_run {
                write_file(&pub_path, &ks.ed25519_public_pem, false);
            }
            // SSH format
            let ssh_path = dir.join("id_ed25519.ssh");
            if !cli.dry_run {
                write_file(&ssh_path, &ks.ed25519_ssh, false);
            }
            // ML-KEM-768 seed
            let mlkem_path = dir.join("mlkem768_seed.hex");
            if !cli.dry_run {
                write_file(&mlkem_path, &format!("{}\n", ks.mlkem768_seed_hex), true);
            }

            println!();
            println!("═══ {} ({}) ═══", ks.node_id, ks.purpose);
            println!("  Private:     {}", priv_path.display());
            println!("  Public:      {}", pub_path.display());
            println!("  SSH:         {}", ssh_path.display());
            println!("  ML-KEM:      {}", mlkem_path.display());
            println!("  Fingerprint: {}", ks.fingerprint);
        }
    }

    if !cli.dry_run && !cli.json {
        println!();
        println!("═══════════════════════════════════════");
        println!("  SECURITY");
        println!("═══════════════════════════════════════");
        println!("  Private keys: 0600 permissions");
        println!("  NEVER commit to version control");
        println!("  Store seeds offline (HSM / air-gap)");
        println!("  Rotate every 90 days");
        println!("  ML-KEM-768: feed seed → libcrux-ml-kem KeyGen()");
    }

    if cli.ca {
        generate_ca(&cli.out_dir, cli.dry_run);
    }
}

fn generate_keys(node_id: &str, purpose: &str, seed_override: Option<&str>, index: u32) -> KeySet {
    // Deterministic or random seed
    let mut seed = [0u8; 32];
    if let Some(phrase) = seed_override {
        let input = format!("coffeepie:{}:{}:{}:ed25519", phrase, purpose, node_id, index);
        let hash = simple_hash64(&input);
        seed.copy_from_slice(&hash[..32]);
    } else {
        OsRng.fill_bytes(&mut seed);
    }

    let signing_key = SigningKey::from_bytes(&seed);
    let verifying_key = signing_key.verifying_key();

    let public_hex = hex::encode(verifying_key.as_bytes());

    // PEM
    let public_pem = format!(
        "-----BEGIN PUBLIC KEY-----\n{}\n-----END PUBLIC KEY-----\n",
        base64_encode(verifying_key.as_bytes(), 64)
    );

    // SSH public key
    let mut ssh_buf = Vec::new();
    ssh_buf.extend_from_slice(&(11u32.to_be_bytes())); // len("ssh-ed25519")
    ssh_buf.extend_from_slice(b"ssh-ed25519");
    ssh_buf.extend_from_slice(&(32u32.to_be_bytes())); // key length
    ssh_buf.extend_from_slice(verifying_key.as_bytes());
    let ssh_key = format!(
        "ssh-ed25519 {} coffee-pie-{}-{}",
        base64_encode(&ssh_buf, 0),
        purpose, node_id
    );

    // Fingerprint
    let fp_hash = simple_hash64(&format!("fp:{}", public_hex));
    let fingerprint = hex::encode(&fp_hash[..8]);

    // ML-KEM-768 seed (64 bytes)
    let mut mlkem_seed = [0u8; 64];
    if let Some(phrase) = seed_override {
        let input = format!("coffeepie:{}:{}:{}:mlkem768", phrase, purpose, node_id, index);
        let hash = simple_hash64(&input);
        mlkem_seed.copy_from_slice(&hash[..64]);
    } else {
        OsRng.fill_bytes(&mut mlkem_seed);
    }

    let now = system_time_rfc3339();

    KeySet {
        node_id: node_id.to_string(),
        purpose: purpose.to_string(),
        ed25519_public_hex: public_hex,
        ed25519_public_pem,
        ed25519_seed_hex: hex::encode(&seed),
        ed25519_ssh: ssh_key,
        mlkem768_seed_hex: hex::encode(&mlkem_seed),
        fingerprint,
        created_at: now,
    }
}

fn generate_ca(out_dir: &PathBuf, dry_run: bool) {
    println!();
    println!("--- Self-Signed CA for Internal L2/L3 Network ---");

    let mut seed = [0u8; 32];
    OsRng.fill_bytes(&mut seed);
    let ca_key = SigningKey::from_bytes(&seed);
    let ca_pub = ca_key.verifying_key();

    if !dry_run {
        let ca_dir = out_dir.join("ca");
        fs::create_dir_all(&ca_dir).expect("Failed to create CA dir");

        write_file(&ca_dir.join("ca.key"), &hex::encode(&seed), true);
        write_file(&ca_dir.join("ca.pub"), &hex::encode(ca_pub.as_bytes()), false);

        let conf = format!(
            "[ca]\norganization = Coffee Pie\nvalidity_days = 3650\nusage = internal_l2_l3_tls\n"
        );
        write_file(&ca_dir.join("ca.conf"), &conf, false);
    }

    println!("  CA key:  {}/ca/ca.key", out_dir.display());
    println!("  CA pub:  {}/ca/ca.pub", out_dir.display());
    println!("  CA conf: {}/ca/ca.conf", out_dir.display());
    println!("  Use this CA to sign node certs for internal TLS.");
}

fn write_file(path: &PathBuf, content: &str, sensitive: bool) {
    let mut f = fs::File::create(path).expect("Failed to create file");
    f.write_all(content.as_bytes()).expect("Write failed");
    if sensitive {
        if let Ok(metadata) = fs::metadata(path) {
            let mut perms = metadata.permissions();
            perms.set_mode(0o600);
            let _ = fs::set_permissions(path, perms);
        }
    }
}

fn base64_encode(data: &[u8], line_width: usize) -> String {
    const CHARS: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut out = String::new();
    for chunk in data.chunks(3) {
        let b0 = chunk[0] as u32;
        let b1 = if chunk.len() > 1 { chunk[1] as u32 } else { 0 };
        let b2 = if chunk.len() > 2 { chunk[2] as u32 } else { 0 };
        let n = (b0 << 16) | (b1 << 8) | b2;
        out.push(CHARS[((n >> 18) & 0x3F) as usize] as char);
        out.push(CHARS[((n >> 12) & 0x3F) as usize] as char);
        out.push(if chunk.len() > 1 { CHARS[((n >> 6) & 0x3F) as usize] as char } else { b'=' });
        out.push(if chunk.len() > 2 { CHARS[(n & 0x3F) as usize] as char } else { b'=' });
    }
    if line_width > 0 {
        let mut wrapped = String::new();
        for (i, c) in out.chars().enumerate() {
            if i > 0 && i % line_width == 0 { wrapped.push('\n'); }
            wrapped.push(c);
        }
        wrapped
    } else {
        out
    }
}

fn simple_hash64(input: &str) -> Vec<u8> {
    // Deterministic 64-byte hash from input using SipHash-like approach
    // Falls back to simple mixing for no-dependency keygen
    let bytes = input.as_bytes();
    let mut state: [u64; 8] = [
        0x6a09e667f3bcc908, 0xbb67ae8584caa73b,
        0x3c6ef372fe94f82b, 0xa54ff53a5f1d36f1,
        0x510e527fade682d1, 0x9b05688c2b3e6c1f,
        0x1f83d9abfb41bd6b, 0x5be0cd19137e2179,
    ];

    for (i, &b) in bytes.iter().enumerate() {
        let slot = i % 8;
        state[slot] = state[slot].wrapping_mul(0x9e3779b97f4a7c15);
        state[slot] = state[slot].wrapping_add(b as u64);
        state[slot] = state[slot].rotate_left((b as u32 % 61) + 1);
        // Mix with neighbor
        let next = (slot + 1) % 8;
        state[next] ^= state[slot].rotate_right(17);
    }

    // Finalization: multiple rounds
    for _ in 0..8 {
        for j in 0..8 {
            let next = (j + 1) % 8;
            let prev = (j + 7) % 8;
            state[j] = state[j].wrapping_add(state[prev].rotate_left(13));
            state[j] ^= state[next].rotate_right(7);
            state[j] = state[j].wrapping_mul(0xbf58476d1ce4e5b9);
        }
    }

    let mut out = Vec::with_capacity(64);
    for s in &state {
        out.extend_from_slice(&s.to_le_bytes());
    }
    out
}

fn system_time_rfc3339() -> String {
    let dur = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default();
    let secs = dur.as_secs();
    let d = (secs / 86400) as i64;
    let t = secs % 86400;

    // Approximate date from days since epoch
    let mut y = 1970i64;
    let mut days = d;
    loop {
        let diy = if (y % 4 == 0 && y % 100 != 0) || y % 400 == 0 { 366 } else { 365 };
        if days < diy { break; }
        days -= diy;
        y += 1;
    }
    let leap = (y % 4 == 0 && y % 100 != 0) || y % 400 == 0;
    let mdays = [31, if leap {29} else {28}, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    let mut m = 0;
    let mut rd = days;
    for (i, &md) in mdays.iter().enumerate() {
        if rd < md { m = i; break; }
        rd -= md;
    }

    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        y, m + 1, rd + 1,
        t / 3600, (t % 3600) / 60, t % 60)
}
