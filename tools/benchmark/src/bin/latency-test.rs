// Coffee Pie Latency Test
// Measures RTT, jitter, and percentile latency to any endpoint.
// Critical for QFDM: latency directly impacts user experience.
// Ideal: <5ms (L2), <15ms (L3 metro), <50ms (regional), <100ms (acceptable).

use std::net::{SocketAddr, ToSocketAddrs};
use std::time::{Duration, Instant};
use clap::Parser;
use rand::Rng;

#[derive(Parser)]
#[command(name = "latency-test")]
#[command(about = "Coffee Pie QFDM Latency Benchmark", long_about = None)]
struct Cli {
    /// Target address (IP:port or hostname:port)
    #[arg(default_value = "localhost:43910")]
    target: String,

    /// Number of pings to send
    #[arg(short, long, default_value = "100")]
    count: u32,

    /// Interval between pings in ms
    #[arg(short, long, default_value = "100")]
    interval: u64,

    /// Payload size in bytes
    #[arg(short, long, default_value = "64")]
    size: usize,

    /// Timeout per ping in ms
    #[arg(long, default_value = "2000")]
    timeout: u64,

    /// JSON output mode
    #[arg(long)]
    json: bool,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie QFDM Latency Test");
        println!("==============================");
        println!("Target: {}", cli.target);
        println!("Count: {}, Interval: {}ms, Payload: {}B", cli.count, cli.interval, cli.size);
        println!();
    }

    let addr: SocketAddr = match cli.target.to_socket_addrs() {
        Ok(mut addrs) => match addrs.next() {
            Some(a) => a,
            None => {
                eprintln!("ERROR: Could not resolve '{}'", cli.target);
                std::process::exit(1);
            }
        },
        Err(e) => {
            eprintln!("ERROR: DNS resolution failed for '{}': {}", cli.target, e);
            std::process::exit(1);
        }
    };

    let timeout = Duration::from_millis(cli.timeout);
    let mut rtts: Vec<f64> = Vec::with_capacity(cli.count as usize);
    let mut lost = 0u32;
    let payload: Vec<u8> = (0..cli.size).map(|_| rand::thread_rng().gen()).collect();

    for i in 1..=cli.count {
        let socket = match std::net::UdpSocket::bind("0.0.0.0:0") {
            Ok(s) => s,
            Err(e) => { eprintln!("ERROR: bind failed: {}", e); std::process::exit(1); }
        };
        let _ = socket.set_read_timeout(Some(timeout));

        let start = Instant::now();
        let _ = socket.send_to(&payload, addr);

        let mut buf = [0u8; 1024];
        match socket.recv_from(&mut buf) {
            Ok(_) => {
                let rtt = start.elapsed().as_secs_f64() * 1000.0;
                rtts.push(rtt);
                if !cli.json && i % 10 == 0 {
                    println!("  ping {}: {:.2}ms", i, rtt);
                }
            }
            Err(_) => {
                lost += 1;
                if !cli.json {
                    eprintln!("  ping {}: timeout", i);
                }
            }
        }

        if i < cli.count {
            std::thread::sleep(Duration::from_millis(cli.interval));
        }
    }

    if rtts.is_empty() {
        eprintln!("\nERROR: All pings lost — target unreachable.");
        std::process::exit(1);
    }

    rtts.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let n = rtts.len();
    let min = rtts[0];
    let max = rtts[n - 1];
    let avg = rtts.iter().sum::<f64>() / n as f64;

    // Jitter: mean absolute deviation from avg
    let jitter = rtts.iter().map(|r| (r - avg).abs()).sum::<f64>() / n as f64;

    // Percentiles
    let p50 = percentile(&rtts, 50.0);
    let p95 = percentile(&rtts, 95.0);
    let p99 = percentile(&rtts, 99.0);
    let loss_pct = (lost as f64 / cli.count as f64) * 100.0;

    if cli.json {
        let result = serde_json::json!({
            "target": cli.target,
            "count": cli.count,
            "sent": cli.count,
            "received": n,
            "lost": lost,
            "loss_pct": format!("{:.1}", loss_pct),
            "min_ms": format!("{:.2}", min),
            "avg_ms": format!("{:.2}", avg),
            "max_ms": format!("{:.2}", max),
            "jitter_ms": format!("{:.2}", jitter),
            "p50_ms": format!("{:.2}", p50),
            "p95_ms": format!("{:.2}", p95),
            "p99_ms": format!("{:.2}", p99),
            "qfdm_grade": grade_qfdm(avg, jitter, loss_pct)
        });
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else {
        println!();
        println!("--- Latency Results for {} ---", cli.target);
        println!("  Sent: {}, Received: {}, Lost: {} ({:.1}%)", cli.count, n, lost, loss_pct);
        println!("  Min: {:.2}ms  Avg: {:.2}ms  Max: {:.2}ms", min, avg, max);
        println!("  Jitter: {:.2}ms", jitter);
        println!("  P50: {:.2}ms  P95: {:.2}ms  P99: {:.2}ms", p50, p95, p99);
        println!();
        println!("  QFDM Grade: {}", grade_qfdm(avg, jitter, loss_pct));
        println!();
        println!("  Grades: Excellent (<5ms) | Great (<15ms) | Good (<50ms)");
        println!("          Acceptable (<100ms) | Poor (>100ms)");
    }
}

fn percentile(sorted: &[f64], p: f64) -> f64 {
    let idx = (p / 100.0) * (sorted.len() - 1) as f64;
    let lo = idx.floor() as usize;
    let hi = idx.ceil() as usize;
    if lo == hi { return sorted[lo]; }
    let frac = idx - lo as f64;
    sorted[lo] * (1.0 - frac) + sorted[hi] * frac
}

fn grade_qfdm(avg: f64, jitter: f64, loss: f64) -> &'static str {
    if loss > 5.0 { return "Unusable — packet loss too high"; }
    if avg < 5.0 && jitter < 2.0 { return "Excellent — L2 direct or ultra-low latency"; }
    if avg < 15.0 && jitter < 5.0 { return "Great — suitable for 4K60 gaming/streaming"; }
    if avg < 50.0 && jitter < 15.0 { return "Good — suitable for 1080p60 desktop use"; }
    if avg < 100.0 { return "Acceptable — office/productivity, may lag on interaction"; }
    "Poor — >100ms, noticeable lag, not recommended for real-time use"
}
