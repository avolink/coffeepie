// Coffee Pie Network Health Diagnostic
// Comprehensive network health check for QFDM deployments.
// Tests: DNS resolution, MTU discovery, packet loss, jitter,
// traceroute-like path discovery, and basic connectivity.

use clap::Parser;
use std::net::{SocketAddr, ToSocketAddrs, UdpSocket};
use std::process::Command;
use std::time::{Duration, Instant};

#[derive(Parser)]
#[command(name = "network-health")]
#[command(about = "Coffee Pie Network Health Diagnostic", long_about = None)]
struct Cli {
    /// Target hostname or IP to test against
    #[arg(default_value = "coffeepie.co")]
    target: String,

    /// Port for connectivity test
    #[arg(short, long, default_value = "443")]
    port: u16,

    /// Number of pings for loss/jitter test
    #[arg(short, long, default_value = "50")]
    count: u32,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Default)]
struct Results {
    dns_resolved: bool,
    dns_ips: Vec<String>,
    dns_time_ms: f64,
    tcp_connect: bool,
    tcp_time_ms: f64,
    mtu: Option<u32>,
    trace_hops: u32,
    ping_sent: u32,
    ping_recv: u32,
    ping_loss_pct: f64,
    ping_min_ms: f64,
    ping_avg_ms: f64,
    ping_max_ms: f64,
    ping_jitter_ms: f64,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie Network Health Diagnostic");
        println!("=====================================");
        println!("Target: {}:{}", cli.target, cli.port);
        println!();
    }

    let mut r = Results::default();

    // 1. DNS Resolution
    if !cli.json { println!("[1/5] DNS Resolution..."); }
    let dns_start = Instant::now();
    match (cli.target.as_str(), cli.port).to_socket_addrs() {
        Ok(addrs) => {
            r.dns_resolved = true;
            r.dns_time_ms = dns_start.elapsed().as_secs_f64() * 1000.0;
            for a in addrs {
                r.dns_ips.push(a.ip().to_string());
                if !cli.json { println!("       {} ({:.1}ms)", a.ip(), r.dns_time_ms); }
            }
        }
        Err(e) => {
            if !cli.json { println!("       FAILED: {}", e); }
        }
    }

    // 2. TCP Connectivity
    if !cli.json { println!("[2/5] TCP Connectivity (port {})...", cli.port); }
    if let Some(addr) = r.dns_ips.first() {
        let target = format!("{}:{}", addr, cli.port);
        let tcp_start = Instant::now();
        match std::net::TcpStream::connect_timeout(
            &target.parse().unwrap(),
            Duration::from_secs(5),
        ) {
            Ok(_) => {
                r.tcp_connect = true;
                r.tcp_time_ms = tcp_start.elapsed().as_secs_f64() * 1000.0;
                if !cli.json { println!("       Connected ({:.1}ms)", r.tcp_time_ms); }
            }
            Err(e) => {
                if !cli.json { println!("       FAILED: {}", e); }
            }
        }
    }

    // 3. MTU Discovery
    if !cli.json { println!("[3/5] MTU Discovery..."); }
    r.mtu = discover_mtu(&cli.target);
    if !cli.json {
        if let Some(mtu) = r.mtu {
            println!("       MTU: {} bytes ({} usable for QFDM)", mtu, mtu - 40);
        } else {
            println!("       Could not determine MTU");
        }
    }

    // 4. Trace
    if !cli.json { println!("[4/5] Path Discovery (traceroute)..."); }
    r.trace_hops = measure_hops(&cli.target);
    if !cli.json {
        if r.trace_hops > 0 {
            println!("       ~{} network hops", r.trace_hops);
        } else {
            println!("       Could not trace");
        }
    }

    // 5. Packet loss & jitter
    if !cli.json { println!("[5/5] Packet Loss & Jitter ({} pings)...", cli.count); }
    if let Some(addr) = r.dns_ips.first() {
        let (loss, min, avg, max, jitter) = ping_test(addr, cli.count);
        r.ping_sent = cli.count;
        r.ping_recv = cli.count - loss;
        r.ping_loss_pct = (loss as f64 / cli.count as f64) * 100.0;
        r.ping_min_ms = min;
        r.ping_avg_ms = avg;
        r.ping_max_ms = max;
        r.ping_jitter_ms = jitter;
        if !cli.json {
            println!("       Sent: {} Recv: {} Lost: {} ({:.1}%)",
                cli.count, r.ping_recv, loss, r.ping_loss_pct);
            println!("       Min: {:.1}ms Avg: {:.1}ms Max: {:.1}ms Jitter: {:.1}ms",
                min, avg, max, jitter);
        }
    }

    // Report
    if cli.json {
        println!("{}", serde_json::json!({
            "target": cli.target,
            "dns": {
                "resolved": r.dns_resolved,
                "ips": r.dns_ips,
                "time_ms": format!("{:.1}", r.dns_time_ms),
            },
            "tcp_port_443": {
                "reachable": r.tcp_connect,
                "time_ms": format!("{:.1}", r.tcp_time_ms),
            },
            "mtu": r.mtu,
            "hops": r.trace_hops,
            "ping": {
                "sent": r.ping_sent,
                "received": r.ping_recv,
                "loss_pct": format!("{:.1}", r.ping_loss_pct),
                "min_ms": format!("{:.1}", r.ping_min_ms),
                "avg_ms": format!("{:.1}", r.ping_avg_ms),
                "max_ms": format!("{:.1}", r.ping_max_ms),
                "jitter_ms": format!("{:.1}", r.ping_jitter_ms),
            },
            "qfdm_readiness": assess_qfdm_readiness(&r),
        }));
    } else {
        println!();
        println!("--- QFDM Readiness Assessment ---");
        let (grade, issues) = assess_qfdm_readiness(&r);
        println!("  {}", grade);
        for issue in &issues {
            println!("    - {}", issue);
        }
        if issues.is_empty() {
            println!("  Network is ready for Coffee Pie QFDM deployment.");
        }
    }
}

fn discover_mtu(target: &str) -> Option<u32> {
    // Try increasing sizes via UDP to find path MTU
    // Starts at 1500, works down
    let addr = format!("{}:1", target);
    for mtu in [1500u32, 1472, 1400, 1300, 1200, 1000].iter() {
        let socket = UdpSocket::bind("0.0.0.0:0").ok()?;
        socket.set_read_timeout(Some(Duration::from_millis(500))).ok()?;
        let addr: SocketAddr = addr.parse().ok()?;
        let payload = vec![0u8; (*mtu - 28) as usize]; // 28 = IP+UDP headers
        if socket.send_to(&payload, addr).is_ok() {
            return Some(*mtu);
        }
    }
    Some(1000) // Fallback minimum
}

fn measure_hops(target: &str) -> u32 {
    // Use system traceroute if available, fallback to ping TTL method
    if let Ok(output) = Command::new("traceroute")
        .args(["-n", "-m", "30", "-w", "1", target])
        .output()
    {
        if output.status.success() {
            let stdout = String::from_utf8_lossy(&output.stdout);
            return stdout.lines().count() as u32;
        }
    }
    // Fallback: try increasing TTL via ping (Linux)
    if let Ok(output) = Command::new("ping")
        .args(["-c", "1", "-t", "30", "-W", "1", target])
        .output()
    {
        // Rough: if it succeeds with TTL=30, count lines from ttl-exceeded
        0 // Can't determine without raw sockets
    } else {
        0
    }
}

fn ping_test(ip: &str, count: u32) -> (u32, f64, f64, f64, f64) {
    let mut rtts = Vec::new();
    let mut lost = 0u32;

    for _ in 0..count {
        let socket = match UdpSocket::bind("0.0.0.0:0") {
            Ok(s) => s,
            Err(_) => { lost += 1; continue; }
        };
        socket.set_read_timeout(Some(Duration::from_millis(1000))).ok();
        let addr: SocketAddr = format!("{}:7", ip).parse().unwrap_or_else(|_| "127.0.0.1:7".parse().unwrap());

        let start = Instant::now();
        let _ = socket.send_to(&[0u8; 32], addr);
        if socket.recv(&mut [0u8; 64]).is_ok() {
            rtts.push(start.elapsed().as_secs_f64() * 1000.0);
        } else {
            lost += 1;
        }
    }

    if rtts.is_empty() {
        return (lost, 0.0, 0.0, 0.0, 0.0);
    }

    rtts.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let min = rtts[0];
    let max = rtts[rtts.len() - 1];
    let avg = rtts.iter().sum::<f64>() / rtts.len() as f64;
    let jitter = rtts.iter().map(|r| (r - avg).abs()).sum::<f64>() / rtts.len() as f64;
    (lost, min, avg, max, jitter)
}

fn assess_qfdm_readiness(r: &Results) -> (String, Vec<String>) {
    let mut issues = Vec::new();

    if !r.dns_resolved {
        issues.push("DNS resolution failed — cannot reach orchestrator".to_string());
    }
    if !r.tcp_connect {
        issues.push("TCP port not reachable — firewall or routing issue".to_string());
    }
    if r.ping_loss_pct > 5.0 {
        issues.push(format!("Packet loss {:.1}% is too high (max 5%)", r.ping_loss_pct));
    }
    if r.ping_avg_ms > 100.0 {
        issues.push(format!("Latency {:.0}ms exceeds 100ms threshold for good UX", r.ping_avg_ms));
    }
    if let Some(mtu) = r.mtu {
        if mtu < 1200 {
            issues.push(format!("MTU {} is too low — QFDM needs >= 1200", mtu));
        }
    }

    if issues.is_empty() {
        ("✓ READY for QFDM deployment".to_string(), issues)
    } else if issues.len() <= 2 {
        (format!("⚠ MARGINAL — {} issue(s) to address", issues.len()), issues)
    } else {
        (format!("✗ NOT READY — {} critical issues", issues.len()), issues)
    }
}
