// Coffee Pie Billing Calculator & Simulator
// Models credit consumption, COFP conversion, and pricing scenarios
// for the Coffee Pie QFDM monetization model.
//
// Coffee Pie Slice pricing tiers (per slice-hour):
//   Free Tier:   ad-supported (limited to 4 slices, 8h/day, L3/L4 only)
//   Basic:       25 Cr/slice-hour (up to 8 slices)
//   Standard:    50 Cr/slice-hour (up to 16 slices)
//   Pro:         100 Cr/slice-hour (up to 32 slices)
//   Workstation: 250 Cr/slice-hour (up to 128 slices)
//
// COFP → Credits conversion: 1 COFP = 1'000 Cr (one-way burn)
// Credits → COP: 1 Cr ≈ 1 COP (parity for MVP)
// Therefore: 1 COFP ≈ 1'000 COP
// Credits → COFP: NOT reversible (credits are consumed, not convertible back)
//
// Usage:
//   coffeepie-billing simulate --tier pro --slices 12 --hours 160
//   coffeepie-billing invoice --slices 12 --hours 160 --tier pro --month 2026-05
//   coffeepie-billing convert --cofp 50000
//   coffeepie-billing revenue --providers 5 --avg-slices 256 --utilization 0.6

use clap::Parser;
use serde::Serialize;
use std::fmt;

#[derive(Parser)]
#[command(name = "coffeepie-billing")]
#[command(about = "Coffee Pie Billing Calculator & Simulator", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Parser)]
enum Commands {
    /// Simulate credit consumption for a user
    Simulate(SimulateArgs),
    /// Generate an invoice preview
    Invoice(InvoiceArgs),
    /// Convert between COFP and Credits
    Convert(ConvertArgs),
    /// Revenue projection for providers/datacenters
    Revenue(RevenueArgs),
    /// Rate card: show all pricing tiers
    Rates,
}

#[derive(Parser)]
struct SimulateArgs {
    /// User tier: free, basic, standard, pro, workstation
    #[arg(short, long, default_value = "standard")]
    tier: String,

    /// Number of slices allocated
    #[arg(short, long, default_value = "4")]
    slices: u64,

    /// Hours of usage per month
    #[arg(short, long, default_value = "160")]
    hours: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct InvoiceArgs {
    /// User tier
    #[arg(short, long, default_value = "standard")]
    tier: String,

    /// Number of slices
    #[arg(short, long, default_value = "4")]
    slices: u64,

    /// Hours used
    #[arg(short, long, default_value = "160")]
    hours: u64,

    /// Billing month (YYYY-MM)
    #[arg(short, long, default_value = "2026-05")]
    month: String,

    /// Include ad-revenue discount
    #[arg(long)]
    ad_supported: bool,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct ConvertArgs {
    /// Amount in COFP to convert to Credits
    #[arg(long)]
    cofp: Option<u64>,

    /// Amount in Credits (reverse: how many COFP burned)
    #[arg(long)]
    credits: Option<u64>,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct RevenueArgs {
    /// Number of active providers
    #[arg(long, default_value = "1")]
    providers: u64,

    /// Average slices per provider
    #[arg(long, default_value = "256")]
    avg_slices: u64,

    /// Utilization rate (0.0–1.0)
    #[arg(long, default_value = "0.6")]
    utilization: f64,

    /// Average tier distribution: basic,standard,pro,workstation (sum=1.0)
    #[arg(long, default_value = "0.4,0.35,0.2,0.05")]
    tier_mix: String,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize)]
struct TierInfo {
    name: &'static str,
    cr_per_slice_hour: u64,
    max_slices: u64,
    max_hours_per_day: u64,
    ad_supported: bool,
    l2_access: bool,
    l3_l4_access: bool,
}

const TIERS: &[TierInfo] = &[
    TierInfo { name: "Free",      cr_per_slice_hour: 0,   max_slices: 4,   max_hours_per_day: 8,  ad_supported: true,  l2_access: false, l3_l4_access: true },
    TierInfo { name: "Basic",     cr_per_slice_hour: 25,  max_slices: 8,   max_hours_per_day: 24, ad_supported: true,  l2_access: false, l3_l4_access: true },
    TierInfo { name: "Standard",  cr_per_slice_hour: 50,  max_slices: 16,  max_hours_per_day: 24, ad_supported: false, l2_access: true,  l3_l4_access: true },
    TierInfo { name: "Pro",       cr_per_slice_hour: 100, max_slices: 32,  max_hours_per_day: 24, ad_supported: false, l2_access: true,  l3_l4_access: true },
    TierInfo { name: "Workstation", cr_per_slice_hour: 250, max_slices: 128, max_hours_per_day: 24, ad_supported: false, l2_access: true,  l3_l4_access: true },
];

const COFP_TO_CR: u64 = 1_000; // 1 COFP = 1'000 Credits

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Simulate(args) => cmd_simulate(&args),
        Commands::Invoice(args) => cmd_invoice(&args),
        Commands::Convert(args) => cmd_convert(&args),
        Commands::Revenue(args) => cmd_revenue(&args),
        Commands::Rates => cmd_rates(),
    }
}

fn find_tier(name: &str) -> &TierInfo {
    TIERS.iter()
        .find(|t| t.name.eq_ignore_ascii_case(name))
        .unwrap_or(&TIERS[2]) // default to Standard
}

// ─── Simulate ────────────────────────────────────────────

fn cmd_simulate(args: &SimulateArgs) {
    let tier = find_tier(&args.tier);
    let slices = args.slices.min(tier.max_slices);
    let hours = args.hours;
    let cr_per_hour = tier.cr_per_slice_hour * slices;
    let total_cr = cr_per_hour * hours;
    let cofp_equivalent = total_cr / COFP_TO_CR;

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "tier": tier.name,
            "slices": slices,
            "hours": hours,
            "cr_per_slice_hour": tier.cr_per_slice_hour,
            "cr_per_hour": cr_per_hour,
            "total_cr": total_cr,
            "cofp_equivalent": cofp_equivalent,
            "ad_supported": tier.ad_supported,
        })).unwrap());
    } else {
        println!("Coffee Pie Billing — Usage Simulation");
        println!("=====================================");
        println!("  Tier:         {}", tier.name);
        println!("  Slices:       {}", slices);
        println!("  Hours:        {}", hours);
        println!("  Rate:         {} Cr/slice-hour", tier.cr_per_slice_hour);
        println!("  Cr/hour:      {}", format_num(cr_per_hour));
        println!("  Total:        {} Cr/month", format_num(total_cr));
        println!("  COFP equiv:   {}", format_num(cofp_equivalent));
        if tier.ad_supported {
            println!("  Ad-supported: yes (discount applies)");
        }
    }
}

// ─── Invoice ─────────────────────────────────────────────

fn cmd_invoice(args: &InvoiceArgs) {
    let tier = find_tier(&args.tier);
    let slices = args.slices.min(tier.max_slices);
    let hours = args.hours;
    let cr_per_hour = tier.cr_per_slice_hour * slices;
    let subtotal = cr_per_hour * hours;

    // Ad-supported discount: 40% off for Basic tier
    let ad_discount = if args.ad_supported && tier.ad_supported {
        subtotal * 40 / 100
    } else {
        0
    };

    let total = subtotal - ad_discount;
    let cofp_burned = total / COFP_TO_CR;
    let tax_colombia = (total as f64 * 0.19) as u64; // 19% IVA Colombia
    let total_with_tax = total + tax_colombia;

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "invoice": {
                "number": format!("INV-{}-{:04}", args.month, rand_num()),
                "date": format!("{}-01", args.month),
                "due_date": format!("{}-15", args.month),
                "tier": tier.name,
                "slices": slices,
                "hours": hours,
                "rate_cr_per_slice_hour": tier.cr_per_slice_hour,
                "line_items": [
                    {"description": format!("Coffee Pie {} — {} slices × {}h", tier.name, slices, hours), "amount_cr": subtotal},
                ],
                "subtotal_cr": subtotal,
                "ad_discount_cr": ad_discount,
                "total_cr": total,
                "tax_colombia_19pct": tax_colombia,
                "total_with_tax_cr": total_with_tax,
                "cofp_equivalent": cofp_burned,
                "currency": "Cr (Coffee Pie Credits)",
            }
        })).unwrap());
    } else {
        println!("Coffee Pie Billing — Invoice Preview");
        println!("====================================");
        println!("  Invoice:      INV-{}-{:04}", args.month, rand_num());
        println!("  Period:       {}", args.month);
        println!("  Tier:         {}", tier.name);
        println!("  Usage:        {} slices × {}h", slices, hours);
        println!("  Rate:         {} Cr/slice-hour", tier.cr_per_slice_hour);
        println!("  ─────────────────────────────────");
        println!("  Subtotal:     {} Cr", format_num(subtotal));
        if ad_discount > 0 {
            println!("  Ad discount:  -{} Cr (40%)", format_num(ad_discount));
        }
        println!("  Total:        {} Cr", format_num(total));
        println!("  IVA (19%):    {} Cr", format_num(tax_colombia));
        println!("  Total + IVA:  {} Cr", format_num(total_with_tax));
        println!("  COFP equiv:   {} ({} COFP burned)", format_num(cofp_burned), cofp_burned);
        println!();
        println!("  1 COFP = {} Cr (one-way burn, irreversible)", COFP_TO_CR);
    }
}

// ─── Convert ─────────────────────────────────────────────

fn cmd_convert(args: &ConvertArgs) {
    if let Some(cofp) = args.cofp {
        let credits = cofp * COFP_TO_CR;
        if args.json {
            println!("{}", serde_json::json!({"cofp": cofp, "credits": credits, "rate": COFP_TO_CR}));
        } else {
            println!("{} COFP → {} Cr (1 COFP = {} Cr)", format_num(cofp), format_num(credits), COFP_TO_CR);
            println!("  ⚠ This is a ONE-WAY burn. Credits cannot be converted back to COFP.");
            println!("  All voting and economic rights are permanently extinguished.");
        }
    } else if let Some(credits) = args.credits {
        let cofp = (credits as f64 / COFP_TO_CR as f64).ceil() as u64;
        if args.json {
            println!("{}", serde_json::json!({"credits": credits, "cofp_required": cofp, "rate": COFP_TO_CR}));
        } else {
            println!("{} Cr requires at least {} COFP to burn (1 COFP = {} Cr)", format_num(credits), cofp, COFP_TO_CR);
        }
    } else {
        println!("Usage: coffeepie-billing convert --cofp 50000");
        println!("       coffeepie-billing convert --credits 5000000");
    }
}

// ─── Revenue ─────────────────────────────────────────────

fn cmd_revenue(args: &RevenueArgs) {
    let tier_mix: Vec<f64> = args.tier_mix.split(',')
        .filter_map(|s| s.trim().parse().ok())
        .collect();

    if tier_mix.len() != 4 || (tier_mix.iter().sum::<f64>() - 1.0).abs() > 0.01 {
        eprintln!("tier-mix must be 4 comma-separated values summing to 1.0 (basic,standard,pro,workstation)");
        return;
    }

    let total_slices = args.providers * args.avg_slices;
    let active_slices = (total_slices as f64 * args.utilization) as u64;
    let hours_per_month = 730; // average month

    // Distribute active slices across tiers
    let tier_cr_rates = [25u64, 50, 100, 250];
    let mut revenue_cr = 0u64;
    let mut slice_breakdown = Vec::new();

    for (i, &mix) in tier_mix.iter().enumerate() {
        let slices = (active_slices as f64 * mix) as u64;
        let cr = slices * tier_cr_rates[i] * hours_per_month;
        revenue_cr += cr;
        slice_breakdown.push((TIERS[i + 1].name, slices, cr));
    }

    let revenue_cofp = revenue_cr / COFP_TO_CR;
    let provider_revenue = revenue_cr / args.providers;

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "providers": args.providers,
            "total_slices": total_slices,
            "active_slices": active_slices,
            "utilization": args.utilization,
            "tier_mix": args.tier_mix,
            "breakdown": slice_breakdown.iter().map(|(name, slices, cr)| {
                serde_json::json!({"tier": name, "slices": slices, "cr_per_month": cr})
            }).collect::<Vec<_>>(),
            "total_revenue_cr": revenue_cr,
            "total_revenue_cofp_equiv": revenue_cofp,
            "avg_revenue_per_provider_cr": provider_revenue,
        })).unwrap());
    } else {
        println!("Coffee Pie Billing — Revenue Projection");
        println!("=======================================");
        println!("  Providers:        {}", args.providers);
        println!("  Total slices:     {}", format_num(total_slices));
        println!("  Active ({:.0}%):  {}", args.utilization * 100.0, format_num(active_slices));
        println!("  Hours/month:      {}", hours_per_month);
        println!();
        println!("  Tier Distribution:");
        for (name, slices, cr) in &slice_breakdown {
            println!("    {: <14} {} slices → {} Cr/month", name, format_num(*slices), format_num(*cr));
        }
        println!("  ─────────────────────────────────");
        println!("  Total revenue:    {} Cr/month", format_num(revenue_cr));
        println!("  COFP equivalent:  {}", format_num(revenue_cofp));
        println!("  Per provider:     {} Cr/month", format_num(provider_revenue));

        // Annual projection
        println!();
        println!("  Annual projection (×12):");
        println!("    Revenue:        {} Cr", format_num(revenue_cr * 12));
        println!("    COFP burned:    {}", format_num(revenue_cofp * 12));
    }
}

// ─── Rates ───────────────────────────────────────────────

fn cmd_rates() {
    println!("Coffee Pie — Slice Pricing Rate Card");
    println!("=====================================");
    println!("{: <14} {: >8} {: >8} {: >10} {: >12} {: >8}",
        "Tier", "Cr/h", "Max Sl.", "Max h/day", "Ad-Supported", "L2");
    println!("{}", "─".repeat(68));
    for t in TIERS {
        println!("{: <14} {: >8} {: >8} {: >10} {: >12} {: >8}",
            t.name,
            if t.cr_per_slice_hour == 0 { "FREE".to_string() } else { format!("{} Cr", t.cr_per_slice_hour) },
            t.max_slices,
            t.max_hours_per_day,
            if t.ad_supported { "Yes" } else { "No" },
            if t.l2_access { "Yes" } else { "No" },
        );
    }
    println!();
    println!("COFP Conversion: 1 COFP = {} Cr (one-way, irreversible burn)", COFP_TO_CR);
    println!("Credits are consumed, never refunded or converted back.");
}

// ─── Helpers ─────────────────────────────────────────────

fn format_num(n: u64) -> String {
    if n >= 1_000_000_000 {
        format!("{:.2}B", n as f64 / 1_000_000_000.0)
    } else if n >= 1_000_000 {
        format!("{:.1}M", n as f64 / 1_000_000.0)
    } else if n >= 1_000 {
        format!("{}'{}", n / 1_000, n % 1_000)
    } else {
        n.to_string()
    }
}

fn rand_num() -> u16 {
    use std::time::SystemTime;
    let ns = SystemTime::now()
        .duration_since(SystemTime::UNIX_EPOCH)
        .unwrap_or_default()
        .subsec_nanos();
    (ns % 9000 + 1000) as u16
}
