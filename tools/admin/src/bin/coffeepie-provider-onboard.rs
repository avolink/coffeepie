// Coffee Pie Provider Onboarding CLI
// Interactive wizard for new datacenter providers to register hardware,
// calculate slice capacity, set regional pricing, and join the QFDM Network.
//
// Requirements (from cloud-providers/README.md):
//   - Minimum 10 nodes with 1'000 slices capacity
//   - ISA x86-64 servers
//   - GPU-accelerated encoding (NVENC/VAAPI/AMF)
//   - L2/L3 private network connectivity
//   - Renewable energy Tier bonus available
//
// Usage:
//   coffeepie-provider-onboard                          # Interactive wizard
//   coffeepie-provider-onboard --non-interactive --json  # Scriptable mode
//   coffeepie-provider-onboard --validate registration.json  # Validate existing

use clap::Parser;
use serde::Serialize;
use std::io::{self, Write, BufRead};

#[derive(Parser)]
#[command(name = "coffeepie-provider-onboard")]
#[command(about = "Coffee Pie Provider Onboarding Wizard", long_about = None)]
struct Cli {
    /// Non-interactive mode (values from flags)
    #[arg(long)]
    non_interactive: bool,

    /// JSON output (skip wizard, print registration JSON)
    #[arg(long)]
    json: bool,

    /// Validate an existing registration JSON
    #[arg(long)]
    validate: Option<String>,

    // Non-interactive flags
    #[arg(long)]
    company: Option<String>,
    #[arg(long)]
    nit: Option<String>,
    #[arg(long)]
    contact_email: Option<String>,
    #[arg(long)]
    contact_name: Option<String>,
    #[arg(long)]
    dc_location: Option<String>,
    #[arg(long)]
    dc_tier: Option<u32>,
    #[arg(long)]
    nodes: Option<u32>,
    #[arg(long)]
    cpu_per_node: Option<u32>,
    #[arg(long)]
    ram_gb_per_node: Option<u32>,
    #[arg(long)]
    gpu_vendor: Option<String>,
    #[arg(long)]
    gpu_vram_gb_per_node: Option<u32>,
    #[arg(long)]
    storage_tb: Option<u32>,
    #[arg(long)]
    bandwidth_gbps: Option<u32>,
    #[arg(long)]
    renewable_pct: Option<u32>,
    #[arg(long)]
    pricing_cop_per_slice_hour: Option<u32>,
}

#[derive(Debug, Serialize)]
struct ProviderRegistration {
    provider_id: String,
    company_name: String,
    nit: String,
    contact: Contact,
    datacenter: DatacenterInfo,
    hardware: HardwareSpecs,
    capacity: CapacityEstimate,
    pricing: PricingConfig,
    network: NetworkInfo,
    energy: EnergyInfo,
    compliance: ComplianceChecklist,
    submitted_at: String,
}

#[derive(Debug, Serialize)]
struct Contact {
    name: String,
    email: String,
    phone: String,
}

#[derive(Debug, Serialize)]
struct DatacenterInfo {
    location: String,
    tier: u32,
    tier_label: String,
    nodes: u32,
}

#[derive(Debug, Serialize)]
struct HardwareSpecs {
    cpu_threads_per_node: u32,
    total_cpu_threads: u32,
    ram_gb_per_node: u32,
    total_ram_gb: u32,
    gpu_vendor: String,
    gpu_vram_gb_per_node: u32,
    total_gpu_vram_gb: u32,
    storage_tb: u32,
    bandwidth_gbps: u32,
    overcommit_cpu: u32,
}

#[derive(Debug, Serialize)]
struct CapacityEstimate {
    max_slices: u32,
    meets_minimum: bool,
    simultaneous_users_basic: u32,
    simultaneous_users_pro: u32,
    cr_per_hour_at_50pct: u64,
    cr_per_month_at_50pct: u64,
    cofp_per_month_equiv: u64,
    bottleneck: String,
}

#[derive(Debug, Serialize)]
struct PricingConfig {
    base_cop_per_slice_hour: u32,
    tier_multiplier: f64,
    effective_cop_per_slice_hour: u32,
    renewable_discount_pct: u32,
}

#[derive(Debug, Serialize)]
struct NetworkInfo {
    connection_type: String,
    has_l2_vlan: bool,
    ip_range: String,
    asn: String,
}

#[derive(Debug, Serialize)]
struct EnergyInfo {
    renewable_pct: u32,
    tier_bonus_pct: f64,
    qualifies_for_tier_v: bool,
}

#[derive(Debug, Serialize)]
struct ComplianceChecklist {
    has_gpu_encoding: bool,
    meets_node_minimum: bool,
    meets_slice_minimum: bool,
    has_l2_connectivity: bool,
    accepts_terms: bool,
    kyc_verified: bool,
}

fn main() {
    let cli = Cli::parse();

    if let Some(path) = &cli.validate {
        validate_registration(path);
        return;
    }

    let reg = if cli.non_interactive {
        build_from_flags(&cli)
    } else if cli.json {
        build_from_flags(&cli)
    } else {
        interactive_wizard()
    };

    if cli.json || cli.non_interactive {
        println!("{}", serde_json::to_string_pretty(&reg).unwrap());
    } else {
        println!();
        println!("{}", serde_json::to_string_pretty(&reg).unwrap());
        println!();
        println!("═══════════════════════════════════════");
        println!("  Registration ready!");
        println!();
        println!("  Submit to: POST https://orchestrator.coffeepie.co/api/v1/providers/register");
        println!("  Or save:   coffeepie-provider-onboard --json > registration.json");
        println!("  Validate:  coffeepie-provider-onboard --validate registration.json");
        println!("═══════════════════════════════════════");
    }
}

fn interactive_wizard() -> ProviderRegistration {
    println!("Coffee Pie Provider Onboarding Wizard");
    println!("======================================");
    println!();
    println!("Welcome! This wizard will help you register your datacenter");
    println!("as a Coffee Pie QFDM Network provider.");
    println!();
    println!("Requirements: min 10 nodes, 1'000 slices, GPU encoding, L2 network");
    println!("See: cloud-providers/README.md for full details.");
    println!();

    let stdin = io::stdin();
    let mut reader = stdin.lock();

    // Company info
    let company = ask(&mut reader, "Company/legal name", "Datacenter S.A.S.");
    let nit = ask(&mut reader, "NIT (Colombian tax ID)", "900.123.456-7");
    let contact_name = ask(&mut reader, "Contact name", "Juan Perez");
    let contact_email = ask(&mut reader, "Contact email", "juan@datacenter.com");
    let contact_phone = ask(&mut reader, "Contact phone", "+57 300 000 0000");

    // Datacenter
    println!();
    println!("--- Datacenter Information ---");
    let location = ask(&mut reader, "Location (city, country)", "Bogota, Colombia");
    let tier_str = ask(&mut reader, "Datacenter Tier (1-5)", "3");
    let tier: u32 = tier_str.parse().unwrap_or(3);
    let nodes_str = ask(&mut reader, "Number of physical nodes", "10");
    let nodes: u32 = nodes_str.parse().unwrap_or(10);

    // Hardware
    println!();
    println!("--- Hardware Specifications ---");
    let cpu_str = ask(&mut reader, "CPU threads per node", "64");
    let cpu: u32 = cpu_str.parse().unwrap_or(64);
    let ram_str = ask(&mut reader, "RAM per node (GB)", "256");
    let ram: u32 = ram_str.parse().unwrap_or(256);
    let gpu_vendor = ask(&mut reader, "GPU vendor (nvidia/amd/intel)", "nvidia");
    let gpu_vram_str = ask(&mut reader, "GPU VRAM per node (GB)", "24");
    let gpu_vram: u32 = gpu_vram_str.parse().unwrap_or(24);
    let storage_str = ask(&mut reader, "Total storage (TB)", "100");
    let storage: u32 = storage_str.parse().unwrap_or(100);
    let bw_str = ask(&mut reader, "Total bandwidth (Gbps)", "40");
    let bw: u32 = bw_str.parse().unwrap_or(40);

    // Network
    println!();
    println!("--- Network ---");
    let conn_type = ask(&mut reader, "Connection type (fiber/copper/satellite)", "fiber");
    let has_l2 = ask_yes_no(&mut reader, "Do you have L2 VLAN capability?");
    let ip_range = ask(&mut reader, "IP range for Coffee Pie VLAN", "10.0.0.0/16");
    let asn = ask(&mut reader, "ASN (if applicable, or 'N/A')", "N/A");

    // Energy
    println!();
    println!("--- Energy & Sustainability ---");
    let renewable_str = ask(&mut reader, "Renewable energy percentage (0-100)", "0");
    let renewable: u32 = renewable_str.parse().unwrap_or(0);

    // Pricing
    println!();
    println!("--- Pricing ---");
    let price_str = ask(&mut reader, "Base price per slice-hour (COP)", "50");
    let price: u32 = price_str.parse().unwrap_or(50);

    // Terms
    println!();
    let accepts = ask_yes_no(&mut reader, "Accept Coffee Pie Provider Terms of Service?");

    // Calculate capacity
    let total_cpu = cpu * nodes * 4; // 4x overcommit
    let total_ram = ram * nodes;
    let total_vram_mb = gpu_vram * nodes * 1024;
    let total_net_mbps = bw * nodes * 1000;

    // Slice math (from coffeepie-slices-calc)
    let slices_cpu = total_cpu / 1;        // 1 vCore per slice
    let slices_ram = total_ram / 1;         // 1 GB per slice
    let slices_ssd = (storage * 1000) / 8;  // 8 GB per slice (rough)
    let slices_net = total_net_mbps / 8;    // 8 Mbps per slice
    let slices_gpu = total_vram_mb / 125;   // 125 MB VRAM per slice

    let max_slices = *[slices_cpu, slices_ram, slices_ssd, slices_net, slices_gpu]
        .iter().min().unwrap_or(&0);

    let bottleneck = if max_slices == slices_cpu { "CPU" }
        else if max_slices == slices_ram { "RAM" }
        else if max_slices == slices_ssd { "SSD Storage" }
        else if max_slices == slices_net { "Network Bandwidth" }
        else { "GPU VRAM" };

    // Tier pricing bonus
    let tier_multiplier = match tier {
        1 => 1.08, 2 => 1.10, 3 => 1.12, 4 => 1.15, 5 => 1.18, _ => 1.08,
    };

    // Renewable discount
    let renewable_discount = if renewable >= 90 { 18 }
        else if renewable >= 50 { 10 }
        else if renewable >= 30 { 5 }
        else { 0 };

    let effective_price = ((price as f64 * tier_multiplier) as u32)
        .saturating_sub((price as f64 * renewable_discount as f64 / 100.0) as u32);

    // Revenue estimate at 50% utilization
    let active = max_slices / 2;
    let cr_hour = active as u64 * effective_price as u64;
    let cr_month = cr_hour * 24 * 30;
    let cofp_equiv = cr_month / 10; // 1 COFP = 10 Cr (contributor burn rate)

    ProviderRegistration {
        provider_id: format!("PRV-{}-{}", location.split(',').next().unwrap_or("XX").to_uppercase().replace(' ', ""), &nit[..4]),
        company_name: company.clone(),
        nit,
        contact: Contact { name: contact_name, email: contact_email, phone: contact_phone },
        datacenter: DatacenterInfo {
            location,
            tier,
            tier_label: format!("Tier {} — {:.0}% price multiplier", tier, (tier_multiplier - 1.0) * 100.0),
            nodes,
        },
        hardware: HardwareSpecs {
            cpu_threads_per_node: cpu,
            total_cpu_threads: total_cpu,
            ram_gb_per_node: ram,
            total_ram_gb: total_ram,
            gpu_vendor,
            gpu_vram_gb_per_node: gpu_vram,
            total_gpu_vram_gb: gpu_vram * nodes,
            storage_tb: storage,
            bandwidth_gbps: bw,
            overcommit_cpu: 4,
        },
        capacity: CapacityEstimate {
            max_slices,
            meets_minimum: max_slices >= 1_000,
            simultaneous_users_basic: max_slices / 1,
            simultaneous_users_pro: max_slices / 12,
            cr_per_hour_at_50pct: cr_hour,
            cr_per_month_at_50pct: cr_month,
            cofp_per_month_equiv: cofp_equiv,
            bottleneck: bottleneck.to_string(),
        },
        pricing: PricingConfig {
            base_cop_per_slice_hour: price,
            tier_multiplier,
            effective_cop_per_slice_hour: effective_price,
            renewable_discount_pct: renewable_discount,
        },
        network: NetworkInfo {
            connection_type: conn_type,
            has_l2_vlan: has_l2,
            ip_range,
            asn,
        },
        energy: EnergyInfo {
            renewable_pct: renewable,
            tier_bonus_pct: tier_multiplier - 1.0,
            qualifies_for_tier_v: tier >= 5 && renewable >= 90,
        },
        compliance: ComplianceChecklist {
            has_gpu_encoding: !gpu_vendor.eq_ignore_ascii_case("none"),
            meets_node_minimum: nodes >= 10,
            meets_slice_minimum: max_slices >= 1_000,
            has_l2_connectivity: has_l2,
            accepts_terms: accepts,
            kyc_verified: false, // Requires manual verification
        },
        submitted_at: now_iso(),
    }
}

fn build_from_flags(cli: &Cli) -> ProviderRegistration {
    let nodes = cli.nodes.unwrap_or(10);
    let cpu = cli.cpu_per_node.unwrap_or(64);
    let ram = cli.ram_gb_per_node.unwrap_or(256);
    let gpu_vram = cli.gpu_vram_gb_per_node.unwrap_or(24);
    let storage = cli.storage_tb.unwrap_or(100);
    let bw = cli.bandwidth_gbps.unwrap_or(40);
    let gpu = cli.gpu_vendor.clone().unwrap_or_else(|| "nvidia".into());
    let tier = cli.dc_tier.unwrap_or(3);
    let renewable = cli.renewable_pct.unwrap_or(0);
    let price = cli.pricing_cop_per_slice_hour.unwrap_or(50);
    let location = cli.dc_location.clone().unwrap_or_else(|| "Unknown".into());
    let company = cli.company.clone().unwrap_or_else(|| "Unknown Provider".into());
    let nit = cli.nit.clone().unwrap_or_else(|| "N/A".into());

    let total_cpu = cpu * nodes * 4;
    let total_ram = ram * nodes;
    let total_vram_mb = gpu_vram * nodes * 1024;
    let total_net_mbps = bw * nodes * 1000;
    let slices_cpu = total_cpu / 1;
    let slices_ram = total_ram / 1;
    let slices_ssd = (storage * 1000) / 8;
    let slices_net = total_net_mbps / 8;
    let slices_gpu = total_vram_mb / 125;
    let max_slices = *[slices_cpu, slices_ram, slices_ssd, slices_net, slices_gpu].iter().min().unwrap_or(&0);
    let bottleneck = if max_slices == slices_cpu { "CPU" } else if max_slices == slices_ram { "RAM" } else if max_slices == slices_ssd { "SSD" } else if max_slices == slices_net { "Network" } else { "GPU VRAM" };
    let tier_mult = match tier { 1 => 1.08, 2 => 1.10, 3 => 1.12, 4 => 1.15, _ => 1.18 };
    let ren_disc = if renewable >= 90 { 18 } else if renewable >= 50 { 10 } else if renewable >= 30 { 5 } else { 0 };
    let eff_price = ((price as f64 * tier_mult) as u32).saturating_sub((price as f64 * ren_disc as f64 / 100.0) as u32);
    let active = max_slices / 2;
    let cr_h = active as u64 * eff_price as u64;
    let cr_m = cr_h * 24 * 30;

    ProviderRegistration {
        provider_id: format!("PRV-{}", &nit[..4.min(nit.len())]),
        company_name: company.clone(), nit, contact: Contact { name: "N/A".into(), email: cli.contact_email.clone().unwrap_or_default(), phone: "N/A".into() },
        datacenter: DatacenterInfo { location, tier, tier_label: format!("Tier {}", tier), nodes },
        hardware: HardwareSpecs { cpu_threads_per_node: cpu, total_cpu_threads: total_cpu, ram_gb_per_node: ram, total_ram_gb: total_ram, gpu_vendor: gpu, gpu_vram_gb_per_node: gpu_vram, total_gpu_vram_gb: gpu_vram * nodes, storage_tb: storage, bandwidth_gbps: bw, overcommit_cpu: 4 },
        capacity: CapacityEstimate { max_slices, meets_minimum: max_slices >= 1000, simultaneous_users_basic: max_slices, simultaneous_users_pro: max_slices / 12, cr_per_hour_at_50pct: cr_h, cr_per_month_at_50pct: cr_m, cofp_per_month_equiv: cr_m / 1000, bottleneck: bottleneck.into() },
        pricing: PricingConfig { base_cop_per_slice_hour: price, tier_multiplier: tier_mult, effective_cop_per_slice_hour: eff_price, renewable_discount_pct: ren_disc },
        network: NetworkInfo { connection_type: "fiber".into(), has_l2_vlan: true, ip_range: "10.0.0.0/16".into(), asn: "N/A".into() },
        energy: EnergyInfo { renewable_pct: renewable, tier_bonus_pct: tier_mult - 1.0, qualifies_for_tier_v: tier >= 5 && renewable >= 90 },
        compliance: ComplianceChecklist { has_gpu_encoding: true, meets_node_minimum: nodes >= 10, meets_slice_minimum: max_slices >= 1000, has_l2_connectivity: true, accepts_terms: true, kyc_verified: false },
        submitted_at: now_iso(),
    }
}

fn validate_registration(path: &str) {
    let content = match std::fs::read_to_string(path) {
        Ok(c) => c,
        Err(e) => { eprintln!("ERROR: Cannot read {}: {}", path, e); return; }
    };

    let reg: ProviderRegistration = match serde_json::from_str(&content) {
        Ok(r) => r,
        Err(e) => { eprintln!("ERROR: Invalid JSON: {}", e); return; }
    };

    let mut issues = Vec::new();
    if !reg.compliance.meets_node_minimum { issues.push("Less than 10 nodes — minimum requirement not met"); }
    if !reg.compliance.meets_slice_minimum { issues.push(format!("Only {} slices — minimum 1'000 required", reg.capacity.max_slices)); }
    if !reg.compliance.has_gpu_encoding { issues.push("No GPU encoding — NVENC/VAAPI/AMF required"); }
    if !reg.compliance.has_l2_connectivity { issues.push("L2 VLAN connectivity required for QFDM"); }
    if !reg.compliance.accepts_terms { issues.push("Terms of Service not accepted"); }

    if issues.is_empty() {
        println!("✓ Registration valid! Ready to submit.");
        println!("  Provider: {} ({})", reg.company_name, reg.provider_id);
        println!("  Location: {} — Tier {}", reg.datacenter.location, reg.datacenter.tier);
        println!("  Slices:   {} (bottleneck: {})", reg.capacity.max_slices, reg.capacity.bottleneck);
        println!("  Revenue:  {} Cr/month ({} COFP equiv)", reg.capacity.cr_per_month_at_50pct, reg.capacity.cofp_per_month_equiv);
    } else {
        println!("✗ Registration has {} issue(s):", issues.len());
        for (i, issue) in issues.iter().enumerate() {
            println!("  {}. {}", i + 1, issue);
        }
    }
}

fn ask(reader: &mut dyn BufRead, prompt: &str, default: &str) -> String {
    print!("  {} [{}]: ", prompt, default);
    io::stdout().flush().ok();
    let mut line = String::new();
    reader.read_line(&mut line).ok();
    let trimmed = line.trim();
    if trimmed.is_empty() { default.to_string() } else { trimmed.to_string() }
}

fn ask_yes_no(reader: &mut dyn BufRead, prompt: &str) -> bool {
    loop {
        print!("  {} (y/n): ", prompt);
        io::stdout().flush().ok();
        let mut line = String::new();
        reader.read_line(&mut line).ok();
        match line.trim().to_lowercase().as_str() {
            "y" | "yes" | "s" | "si" | "sí" => return true,
            "n" | "no" => return false,
            _ => println!("  Please answer y or n"),
        }
    }
}

fn now_iso() -> String {
    let dur = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default();
    let secs = dur.as_secs();
    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        1970 + (secs / 86400 / 365), ((secs / 86400) % 365 / 30) + 1, (secs / 86400 % 30) + 1,
        (secs % 86400) / 3600, (secs % 86400 % 3600) / 60, secs % 60)
}
