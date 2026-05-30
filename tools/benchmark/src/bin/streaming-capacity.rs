// Coffee Pie Streaming Capacity Calculator
// Estimates how many simultaneous Sunshine/Moonlight streams a GPU
// can encode, given its NVENC/VAAPI/AMF hardware encoder limits.
//
// Ref: NVIDIA NVENC session limits, AMD VCE limits, Intel QSV limits.
// Each Coffee Pie stream = 1 user. Resolutions affect encoder load.

use clap::Parser;
use serde::Serialize;

#[derive(Parser)]
#[command(name = "streaming-capacity")]
#[command(about = "Coffee Pie Streaming Capacity Calculator (Sunshine/Moonlight)", long_about = None)]
struct Cli {
    /// GPU vendor: nvidia, amd, intel, apple, qualcomm
    #[arg(short, long, default_value = "nvidia")]
    vendor: String,

    /// GPU model for reference
    #[arg(short, long, default_value = "A4000")]
    model: String,

    /// Number of physical GPUs
    #[arg(long, default_value = "1")]
    gpu_count: u32,

    /// Max simultaneous NVENC sessions (NVIDIA only)
    #[arg(long)]
    nvenc_sessions: Option<u32>,

    /// Target resolution: 1080p, 1440p, 4K
    #[arg(long, default_value = "1080p")]
    resolution: String,

    /// Codec: h264, hevc, av1
    #[arg(long, default_value = "h264")]
    codec: String,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Debug, Serialize)]
struct StreamEstimate {
    resolution: &'static str,
    fps: u32,
    bitrate_mbps: u32,
    encoder_load_pct: f64,
    max_streams: u32,
    quality: &'static str,
}

#[derive(Debug, Serialize)]
struct CodecCapability {
    codec: String,
    max_sessions: u32,
    streams: Vec<StreamEstimate>,
}

fn main() {
    let cli = Cli::parse();

    let vendor = cli.vendor.to_lowercase();
    let max_sessions = cli.nvenc_sessions.unwrap_or_else(|| match vendor.as_str() {
        "nvidia" => nvidia_session_limit(&cli.model),
        "amd" => 16,      // AMD VCE typical limit
        "intel" => 18,    // Intel QSV typical limit
        "apple" => 4,     // Apple VideoToolbox
        "qualcomm" => 8,  // Qualcomm Adreno VPU
        _ => {
            eprintln!("Unknown vendor '{}'. Use --nvenc-sessions to specify max encoder sessions.", vendor);
            std::process::exit(1);
        }
    });

    if !cli.json {
        println!("Coffee Pie Streaming Capacity Calculator");
        println!("=========================================");
        println!("GPU: {} {} (x{})", vendor.to_uppercase(), cli.model, cli.gpu_count);
        println!("Max encoder sessions per GPU: {}", max_sessions);
        println!("Total sessions ({} GPU(s)): {}", cli.gpu_count, max_sessions * cli.gpu_count);
        println!();
    }

    let total = max_sessions * cli.gpu_count;

    // Resolution scaling factors relative to 1080p
    let (res_name, scale, base_bitrate) = match cli.resolution.as_str() {
        "4K" | "4k" | "2160p" => ("4K (2160p)", 4.0, 40u32),
        "1440p" | "2k" | "2K" => ("1440p", 2.25, 25u32),
        _ => ("1080p", 1.0, 15u32),
    };

    // Codec efficiency (relative to H.264)
    let codec_efficiency = match cli.codec.to_lowercase().as_str() {
        "av1" => 0.55,   // AV1 ~45% better than H.264
        "hevc" | "h265" => 0.7, // HEVC ~30% better
        _ => 1.0,
    };

    let effective_bitrate = (base_bitrate as f64 * scale * codec_efficiency) as u32;

    let resolutions = [
        ("1080p@60", 60u32, 1.0, 15u32, "Great — standard QFDM"),
        ("1440p@60", 60, 2.25, 25, "Great — Pro tier"),
        ("4K@60", 60, 4.0, 40, "Good — workstation/PRO"),
        ("1080p@120", 120, 1.5, 22, "Good — high refresh"),
        ("4K@120", 120, 5.0, 60, "Limited — extreme"),
    ];

    if !cli.json {
        println!("Resolution  FPS  Bitrate   Enc.Load  Max Streams  Quality");
        println!("{}", "-".repeat(65));
    }

    for (name, fps, res_scale, base_br, quality) in &resolutions {
        let br = (*base_br as f64 * codec_efficiency) as u32;
        let load = (res_scale / scale) * (br as f64 / effective_bitrate as f64) * (*fps as f64 / 60.0);
        let streams = (total as f64 / load) as u32;

        if !cli.json {
            println!("{: <12} {: >3}  {: >3} Mbps  {: >5.0}%      {: >5}        {}",
                name, fps, br, (load * 100.0).min(100.0), streams, quality);
        }
    }

    if cli.json {
        let streams: Vec<serde_json::Value> = resolutions.iter().map(|(name, fps, res_scale, base_br, quality)| {
            let br = (*base_br as f64 * codec_efficiency) as u32;
            let load = (res_scale / scale) * (br as f64 / effective_bitrate as f64) * (*fps as f64 / 60.0);
            serde_json::json!({
                "resolution": name,
                "fps": fps,
                "bitrate_mbps": br,
                "encoder_load_pct": format!("{:.0}", load * 100.0),
                "max_streams": (total as f64 / load) as u32,
                "quality": quality,
            })
        }).collect();

        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "vendor": vendor,
            "model": cli.model,
            "gpu_count": cli.gpu_count,
            "max_sessions_per_gpu": max_sessions,
            "total_sessions": total,
            "codec": cli.codec.to_lowercase(),
            "streams": streams,
            "note": "Encoder sessions are a hard limit. Streams beyond max_sessions require additional GPUs or software encoding (not recommended)."
        })).unwrap());
    } else {
        println!();
        println!("--- Recommendations ---");
        println!("  Encoder sessions are a HARD limit per GPU.");
        println!("  {} GPU(s) × {} sessions = {} max simultaneous users.", cli.gpu_count, max_sessions, total);
        println!();

        let concurrent_users = std::cmp::min(total, total); // same as total since GPU-bound
        if concurrent_users < 10 {
            println!("  ⚠ Low capacity. Consider adding more GPUs.");
        } else if concurrent_users < 50 {
            println!("  ✓ Suitable for small/medium datacenter.");
        } else if concurrent_users < 200 {
            println!("  ✓ Good for regional datacenter.");
        } else {
            println!("  ✓ Flagship datacenter ready.");
        }

        // Bottleneck check
        println!();
        println!("  Bottleneck check:");
        println!("    - Encoder sessions: {} (hard limit)", total);
        println!("    - Ensure network bandwidth >= {} Mbps for {} streams at {} Mbps each",
            total * effective_bitrate, total, effective_bitrate);
        println!("    - Ensure GPU VRAM >= {} MB ({} streams × {} MB at {})",
            total * 125, total, 125, res_name);
    }
}

fn nvidia_session_limit(model: &str) -> u32 {
    let m = model.to_lowercase();
    // Consumer GPUs (GeForce) — driver-limited to 3-8 sessions
    if m.contains("rtx 5090") || m.contains("rtx 4090") { return 8; }
    if m.contains("rtx 50") || m.contains("rtx 40") { return 5; }
    if m.contains("rtx 30") { return 3; }
    if m.contains("gtx") { return 3; }

    // Professional GPUs — unlimited but practical limits
    if m.contains("rtx 6000") || m.contains("rtx 5000") || m.contains("a6000") { return 40; }
    if m.contains("a5000") || m.contains("a5500") { return 30; }
    if m.contains("a4000") { return 20; }
    if m.contains("a2000") || m.contains("a1000") { return 12; }
    if m.contains("t1000") || m.contains("t600") || m.contains("t400") { return 6; }

    // Datacenter GPUs
    if m.contains("h100") || m.contains("h200") || m.contains("b100") || m.contains("b200") { return 60; }
    if m.contains("a100") || m.contains("l40") { return 40; }
    if m.contains("l4") || m.contains("t4") { return 8; }

    // Default conservative
    5
}
