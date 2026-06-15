// Coffee Pie Slices Calculator
// Helps datacenter operators determine how many Coffee Pie slices they can offer
// based on their hardware specs, and identifies the primary bottleneck.
//
// Coffee Pie Slice definition (from AGENTS.md):
//   CPU: 1 vCore | RAM: 1 GB | SSD: 8 GB | NET: 8 Mbps
//   HDD: 125 GB | GPU: 125 MB VRAM | RES: 15 vMPX/s | IA: 3 TOPS (INT8)

use clap::Parser;
use serde::Serialize;
use std::collections::BTreeMap;

#[derive(Parser)]
#[command(name = "coffeepie-slices-calc")]
#[command(about = "Coffee Pie Datacenter Slice Capacity Calculator", long_about = None)]
struct Cli {
    /// Total CPU threads available (logical cores)
    #[arg(long, default_value = "256")]
    cpu_threads: u64,

    /// Total RAM in GB
    #[arg(long, default_value = "1024")]
    ram_gb: u64,

    /// Total SSD storage in GB (VMs + OS)
    #[arg(long, default_value = "4096")]
    ssd_gb: u64,

    /// Total HDD storage in GB (files/backups)
    #[arg(long, default_value = "32768")]
    hdd_gb: u64,

    /// Total GPU VRAM in MB
    #[arg(long, default_value = "32768")]
    gpu_vram_mb: u64,

    /// Total network bandwidth in Mbps
    #[arg(long, default_value = "20480")]
    net_mbps: u64,

    /// Total vMPX/s rendering capacity
    #[arg(long, default_value = "0")]
    vmp_res: u64,

    /// Total AI TOPS (INT8)
    #[arg(long, default_value = "0")]
    ai_tops: u64,

    /// vCPU overcommit ratio (e.g., 4 = 4 vCPUs per physical core)
    #[arg(long, default_value = "4")]
    overcommit_cpu: u64,

    /// RAM overcommit ratio (ballooning/deduplication factor)
    #[arg(long, default_value = "1")]
    overcommit_ram: f64,

    /// Consumer price per active Slice per MINUTE, in Credits (governance-set)
    #[arg(long, default_value = "30")]
    cr_per_slice_min: u64,

    /// Parking Fee per dormant Slice per hour, in Credits (governance-set)
    #[arg(long, default_value = "10")]
    parking_cr_per_slice_hour: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize)]
struct SliceDimension {
    name: &'static str,
    unit: &'static str,
    available: f64,
    per_slice: f64,
    slices: u64,
    usage_pct: f64,
    is_bottleneck: bool,
}

const SLICE_CPU: f64 = 1.0;      // 1 vCore
const SLICE_RAM: f64 = 1.0;      // 1 GB
const SLICE_SSD: f64 = 8.0;      // 8 GB
const SLICE_HDD: f64 = 125.0;    // 125 GB
const SLICE_NET: f64 = 8.0;      // 8 Mbps
const SLICE_GPU: f64 = 125.0;    // 125 MB VRAM
const SLICE_VMP: f64 = 15.0;     // 15 vMPX/s
const SLICE_AI: f64 = 3.0;       // 3 TOPS

fn main() {
    let cli = Cli::parse();

    let cpu = cli.cpu_threads as f64 * cli.overcommit_cpu as f64;
    let ram = cli.ram_gb as f64 * cli.overcommit_ram;
    let ssd = cli.ssd_gb as f64;
    let hdd = cli.hdd_gb as f64;
    let gpu = cli.gpu_vram_mb as f64;
    let net = cli.net_mbps as f64;

    let dims: Vec<SliceDimension> = vec![
        SliceDimension {
            name: "CPU (vCores)",
            unit: "vCores",
            available: cpu,
            per_slice: SLICE_CPU,
            slices: (cpu / SLICE_CPU) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
        SliceDimension {
            name: "RAM",
            unit: "GB",
            available: ram,
            per_slice: SLICE_RAM,
            slices: (ram / SLICE_RAM) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
        SliceDimension {
            name: "SSD",
            unit: "GB",
            available: ssd,
            per_slice: SLICE_SSD,
            slices: (ssd / SLICE_SSD) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
        SliceDimension {
            name: "HDD",
            unit: "GB",
            available: hdd,
            per_slice: SLICE_HDD,
            slices: (hdd / SLICE_HDD) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
        SliceDimension {
            name: "GPU VRAM",
            unit: "MB",
            available: gpu,
            per_slice: SLICE_GPU,
            slices: (gpu / SLICE_GPU) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
        SliceDimension {
            name: "Network",
            unit: "Mbps",
            available: net,
            per_slice: SLICE_NET,
            slices: (net / SLICE_NET) as u64,
            usage_pct: 0.0,
            is_bottleneck: false,
        },
    ];

    // Find the limiting dimension
    let max_slices = dims.iter().map(|d| d.slices).min().unwrap_or(0);
    let mut dims: Vec<SliceDimension> = dims.into_iter().map(|mut d| {
        d.usage_pct = if d.slices > 0 {
            (max_slices as f64 / d.slices as f64) * 100.0
        } else {
            100.0
        };
        d.is_bottleneck = d.slices == max_slices;
        d
    }).collect();

    // Optional dimensions
    let mut optional = Vec::new();
    if cli.vmp_res > 0 {
        let v = (cli.vmp_res as f64 / SLICE_VMP) as u64;
        optional.push(SliceDimension {
            name: "vMPX/s Render",
            unit: "vMPX/s",
            available: cli.vmp_res as f64,
            per_slice: SLICE_VMP,
            slices: v,
            usage_pct: if v > 0 { (max_slices as f64 / v as f64) * 100.0 } else { 100.0 },
            is_bottleneck: v == max_slices,
        });
    }
    if cli.ai_tops > 0 {
        let ai = (cli.ai_tops as f64 / SLICE_AI) as u64;
        optional.push(SliceDimension {
            name: "AI TOPS",
            unit: "TOPS",
            available: cli.ai_tops as f64,
            per_slice: SLICE_AI,
            slices: ai,
            usage_pct: if ai > 0 { (max_slices as f64 / ai as f64) * 100.0 } else { 100.0 },
            is_bottleneck: ai == max_slices,
        });
    }

    if cli.json {
        let mut map = BTreeMap::new();
        map.insert("max_slices".to_string(), serde_json::Value::from(max_slices));
        map.insert("raw_hardware".to_string(), serde_json::json!({
            "cpu_threads": cli.cpu_threads,
            "ram_gb": cli.ram_gb,
            "ssd_gb": cli.ssd_gb,
            "hdd_gb": cli.hdd_gb,
            "gpu_vram_mb": cli.gpu_vram_mb,
            "net_mbps": cli.net_mbps,
            "vmp_res": cli.vmp_res,
            "ai_tops": cli.ai_tops,
            "overcommit_cpu": cli.overcommit_cpu,
            "overcommit_ram": cli.overcommit_ram,
        }));
        map.insert("dimensions".to_string(), serde_json::to_value(&dims).unwrap());
        if !optional.is_empty() {
            map.insert("optional_dimensions".to_string(), serde_json::to_value(&optional).unwrap());
        }
        println!("{}", serde_json::to_string_pretty(&map).unwrap());
    } else {
        println!("Coffee Pie QFDM Slice Capacity Calculator");
        println!("===========================================");
        println!();
        println!("Hardware Summary:");
        println!("  CPU: {} threads ({} effective with {}x overcommit)",
            cli.cpu_threads, cpu as u64, cli.overcommit_cpu);
        println!("  RAM: {} GB ({} GB effective with {}x overcommit)",
            cli.ram_gb, ram as u64, cli.overcommit_ram);
        println!("  SSD: {} GB | HDD: {} GB", cli.ssd_gb, cli.hdd_gb);
        println!("  GPU VRAM: {} MB | Network: {} Mbps", cli.gpu_vram_mb, cli.net_mbps);
        if cli.vmp_res > 0 { println!("  vMPX/s: {} | AI: {} TOPS", cli.vmp_res, cli.ai_tops); }
        println!();
        println!("Dimension Analysis (per Coffee Pie Slice specs):");
        println!("{: <20} {: >10} {: >10} {: >10} {: >8}",
            "Resource", "Available", "Per Slice", "Max Slices", "Usage %");
        println!("{}", "-".repeat(65));

        for d in &dims {
            let marker = if d.is_bottleneck { " ← BOTTLENECK" } else { "" };
            println!("{: <20} {: >10.0} {: >3} {: >10} {: >10} {: >7.1}%{}",
                d.name, d.available, d.unit, format!("{:.0} {}", d.per_slice, d.unit),
                format_slices(d.slices), d.usage_pct, marker);
        }
        for d in &optional {
            let marker = if d.is_bottleneck { " ← BOTTLENECK" } else { "" };
            println!("{: <20} {: >10.0} {: >3} {: >10} {: >10} {: >7.1}%{}",
                d.name, d.available, d.unit, format!("{:.0} {}", d.per_slice, d.unit),
                format_slices(d.slices), d.usage_pct, marker);
        }

        println!();
        println!("═══════════════════════════════════════");
        println!("  MAXIMUM SIMULTANEOUS SLICES: {}", format_slices(max_slices));
        println!("═══════════════════════════════════════");
        println!();

        // Show bottlenecks
        let bottlenecks: Vec<&SliceDimension> = dims.iter()
            .chain(optional.iter())
            .filter(|d| d.is_bottleneck)
            .collect();

        if bottlenecks.len() == 1 {
            let b = &bottlenecks[0];
            println!("Bottleneck: {} ({} {} → {} slices max)", b.name, b.available as u64, b.unit, b.slices);
            println!();
            println!("To increase capacity, upgrade your {}.", b.name.split(' ').next().unwrap_or("hardware"));
        } else if bottlenecks.len() > 1 {
            println!("Multiple bottlenecks detected:");
            for b in &bottlenecks {
                println!("  - {} ({} {} → {} slices)", b.name, b.available as u64, b.unit, b.slices);
            }
            println!("Upgrade all bottlenecked resources proportionally.");
        }

        // Revenue estimation
        println!();
        println!("--- Revenue Estimation (COFP) ---");
        println!("  Assuming 50% utilization at {} Cr/slice/min:", cli.cr_per_slice_min);
        let active = max_slices / 2;
        let credits_per_hour = active * cli.cr_per_slice_min * 60;
        let credits_per_month = credits_per_hour * 24 * 30;
        println!("  Active slices: {} | Cr/hour: {} | Cr/month: {}",
            format_slices(active), format_slices(credits_per_hour), format_slices(credits_per_month));

        // Parking Fee: dormant slices still reserve SSD/HDD (see PROVIDERS.md).
        // Estimate the other 50% of capacity sitting dormant (powered off/suspended).
        let dormant = max_slices - active;
        let parking_per_hour = dormant * cli.parking_cr_per_slice_hour;
        let parking_per_month = parking_per_hour * 24 * 30;
        println!("  Dormant slices: {} | Parking Cr/hour: {} | Parking Cr/month: {}",
            format_slices(dormant), format_slices(parking_per_hour), format_slices(parking_per_month));
        println!("  (Parking Fee applies from a consumer's 10th dormant slice up; first 9 free.)");

        // Simultaneous users at different tiers
        println!();
        println!("--- Simultaneous Users ---");
        println!("  Basic (1 slice/user):  {}", format_slices(max_slices));
        println!("  Standard (4 slices):   {}", format_slices(max_slices / 4));
        println!("  Pro (12 slices):       {}", format_slices(max_slices / 12));
        println!("  Workstation (32 slices): {}", format_slices(max_slices / 32));
    }
}

fn format_slices(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{}'{:03}", n / 1_000, n % 1_000)
    } else {
        n.to_string()
    }
}
