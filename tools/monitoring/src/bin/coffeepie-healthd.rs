// Coffee Pie Health Daemon (healthd)
// Lightweight monitoring daemon that polls Coffee Pie services and alerts on failures.
//
// Checks:
//   - Orchestrator HTTP health
//   - DC Agent /health endpoint
//   - Actor TCP port reachability
//   - Sunshine streaming ports
//   - Database connectivity (PostgreSQL)
//   - Redis connectivity
//
// Output modes:
//   - stdout (human-readable, for terminal)
//   - JSON (for log aggregation: Loki, Elasticsearch, CloudWatch)
//   - Prometheus metrics endpoint (--metrics flag)
//   - Exit code (for cron/nagios-style monitoring)
//
// Usage:
//   coffeepie-healthd                           # one-shot check, stdout
//   coffeepie-healthd --daemon --interval 30s   # run continuously
//   coffeepie-healthd --json --once             # one-shot, JSON output
//   coffeepie-healthd --metrics --port 9091      # Prometheus metrics server

use clap::Parser;
use serde::Serialize;
use std::io::Write;
use std::net::TcpStream;
use std::process::{Command, exit};
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use std::thread;

#[derive(Parser)]
#[command(name = "coffeepie-healthd")]
#[command(about = "Coffee Pie Health Monitoring Daemon", long_about = None)]
struct Cli {
    /// Orchestrator URL
    #[arg(long, default_value = "http://localhost:8000")]
    orchestrator: String,

    /// DC Agent URL
    #[arg(long, default_value = "http://localhost:9090")]
    dc_agent: String,

    /// PostgreSQL connection check (host:port)
    #[arg(long, default_value = "localhost:5432")]
    postgres: String,

    /// Redis connection check (host:port)
    #[arg(long, default_value = "localhost:6379")]
    redis: String,

    /// Actor TCP port
    #[arg(long, default_value = "localhost:43910")]
    actor: String,

    /// Sunshine control port
    #[arg(long, default_value = "localhost:47989")]
    sunshine: String,

    /// Run continuously as daemon
    #[arg(long)]
    daemon: bool,

    /// Check interval (daemon mode)
    #[arg(long, default_value = "30s")]
    interval: String,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Single check and exit (default)
    #[arg(long)]
    once: bool,

    /// Prometheus metrics endpoint mode
    #[arg(long)]
    metrics: bool,

    /// Metrics server port
    #[arg(long, default_value = "9091")]
    metrics_port: u16,

    /// Timeout per check in seconds
    #[arg(long, default_value = "5")]
    timeout: u64,

    /// Exit with non-zero if any check fails (for cron/CI)
    #[arg(long)]
    strict: bool,
}

#[derive(Debug, Serialize)]
struct HealthReport {
    timestamp: String,
    overall: String,        // HEALTHY | DEGRADED | DOWN
    checks: Vec<CheckResult>,
    summary: CheckSummary,
}

#[derive(Debug, Serialize)]
struct CheckResult {
    service: String,
    status: String,         // OK | FAIL | TIMEOUT
    latency_ms: u64,
    detail: String,
}

#[derive(Debug, Serialize)]
struct CheckSummary {
    total: u32,
    ok: u32,
    fail: u32,
    timeout: u32,
}

fn main() {
    let cli = Cli::parse();

    if cli.metrics {
        run_metrics_server(&cli);
        return;
    }

    if cli.daemon {
        run_daemon(&cli);
    } else {
        let report = run_checks(&cli);
        output_report(&report, &cli);
        if cli.strict && report.summary.fail + report.summary.timeout > 0 {
            exit(1);
        }
    }
}

fn run_checks(cli: &Cli) -> HealthReport {
    let timeout = Duration::from_secs(cli.timeout);
    let mut checks = Vec::new();

    // 1. Orchestrator HTTP
    let (status, latency, detail) = check_http(&cli.orchestrator, timeout);
    checks.push(CheckResult { service: "orchestrator".into(), status, latency_ms: latency, detail });

    // 2. DC Agent
    let (status, latency, detail) = check_http(&format!("{}/health", cli.dc_agent), timeout);
    checks.push(CheckResult { service: "dc_agent".into(), status, latency_ms: latency, detail });

    // 3. Actor TCP
    let (status, latency, detail) = check_tcp(&cli.actor, timeout);
    checks.push(CheckResult { service: "actor".into(), status, latency_ms: latency, detail });

    // 4. Sunshine
    let (status, latency, detail) = check_tcp(&cli.sunshine, timeout);
    checks.push(CheckResult { service: "sunshine".into(), status, latency_ms: latency, detail });

    // 5. PostgreSQL
    let (status, latency, detail) = check_tcp(&cli.postgres, timeout);
    checks.push(CheckResult { service: "postgres".into(), status, latency_ms: latency, detail });

    // 6. Redis
    let (status, latency, detail) = check_redis(&cli.redis, timeout);
    checks.push(CheckResult { service: "redis".into(), status, latency_ms: latency, detail });

    let ok = checks.iter().filter(|c| c.status == "OK").count() as u32;
    let fail = checks.iter().filter(|c| c.status == "FAIL").count() as u32;
    let timeout_c = checks.iter().filter(|c| c.status == "TIMEOUT").count() as u32;
    let total = checks.len() as u32;

    let overall = if fail + timeout_c == 0 {
        "HEALTHY"
    } else if ok >= total / 2 {
        "DEGRADED"
    } else {
        "DOWN"
    };

    HealthReport {
        timestamp: now_iso(),
        overall: overall.into(),
        checks,
        summary: CheckSummary { total, ok, fail, timeout: timeout_c },
    }
}

fn check_http(url: &str, timeout: Duration) -> (String, u64, String) {
    let start = Instant::now();
    // Use curl for reliable HTTP with timeout
    let output = Command::new("curl")
        .args(["-s", "-o", "/dev/null", "-w", "%{http_code}", "--max-time", &timeout.as_secs().to_string(), url])
        .output();

    let latency = start.elapsed().as_millis() as u64;

    match output {
        Ok(out) => {
            let code = String::from_utf8_lossy(&out.stdout).trim().to_string();
            if code == "200" || code == "302" || code == "401" {
                ("OK".into(), latency, format!("HTTP {}", code))
            } else if code.is_empty() {
                ("TIMEOUT".into(), latency, "no response".into())
            } else {
                ("FAIL".into(), latency, format!("HTTP {}", code))
            }
        }
        Err(e) => ("FAIL".into(), latency, format!("curl error: {}", e)),
    }
}

fn check_tcp(addr: &str, timeout: Duration) -> (String, u64, String) {
    let start = Instant::now();
    match TcpStream::connect_timeout(
        &addr.parse().unwrap_or_else(|_| "127.0.0.1:1".parse().unwrap()),
        timeout,
    ) {
        Ok(_) => {
            let latency = start.elapsed().as_millis() as u64;
            ("OK".into(), latency, "connected".into())
        }
        Err(e) => {
            let latency = start.elapsed().as_millis() as u64;
            if latency >= timeout.as_millis() as u64 {
                ("TIMEOUT".into(), latency, format!("timeout after {}ms", latency))
            } else {
                ("FAIL".into(), latency, format!("{}", e))
            }
        }
    }
}

fn check_redis(addr: &str, _timeout: Duration) -> (String, u64, String) {
    let start = Instant::now();
    // Use redis-cli for proper protocol check
    let output = Command::new("redis-cli")
        .args(["-h", &addr.split(':').next().unwrap_or("localhost"),
               "-p", &addr.split(':').nth(1).unwrap_or("6379"),
               "PING"])
        .output();

    let latency = start.elapsed().as_millis() as u64;

    match output {
        Ok(out) => {
            let resp = String::from_utf8_lossy(&out.stdout);
            if resp.contains("PONG") {
                ("OK".into(), latency, "PONG".into())
            } else {
                ("FAIL".into(), latency, format!("unexpected: {}", resp.trim()))
            }
        }
        Err(e) => ("FAIL".into(), latency, format!("{}", e)),
    }
}

fn output_report(report: &HealthReport, cli: &Cli) {
    if cli.json {
        println!("{}", serde_json::to_string_pretty(report).unwrap());
        return;
    }

    let icon = match report.overall.as_str() {
        "HEALTHY" => "✓",
        "DEGRADED" => "⚠",
        _ => "✗",
    };

    println!("{} Coffee Pie Health — {} — {}", icon, report.overall, report.timestamp);
    println!("{}", "─".repeat(55));
    for check in &report.checks {
        let status_icon = match check.status.as_str() {
            "OK" => "✓", "FAIL" => "✗", _ => "⏱",
        };
        println!("  {} {: <16} {: >4}ms  {}",
            status_icon, check.service, check.latency_ms, check.detail);
    }
    println!("{}", "─".repeat(55));
    println!("  {} OK, {} FAIL, {} TIMEOUT",
        report.summary.ok, report.summary.fail, report.summary.timeout);

    // Recommendations
    if report.summary.fail > 0 {
        println!();
        for check in &report.checks {
            if check.status == "FAIL" {
                match check.service.as_str() {
                    "orchestrator" => println!("  → Check: docker compose logs orchestrator | systemctl status coffeepie-orchestrator"),
                    "dc_agent" => println!("  → Check: docker compose logs dc-agent | journalctl -u coffeepie-dc-agent"),
                    "actor" => println!("  → Check: systemctl status coffeepie-actor | ss -tlnp | grep 43910"),
                    "sunshine" => println!("  → Check: systemctl status sunshine | ss -tlnp | grep 47989"),
                    "postgres" => println!("  → Check: systemctl status postgresql | pg_isready"),
                    "redis" => println!("  → Check: systemctl status redis | redis-cli PING"),
                    _ => {}
                }
            }
        }
    }
}

fn run_daemon(cli: &Cli) {
    let interval = parse_duration(&cli.interval);
    println!("Coffee Pie healthd starting — interval: {}s", interval.as_secs());
    println!("Services: orchestrator={} dc-agent={} actor={} sunshine={}",
        cli.orchestrator, cli.dc_agent, cli.actor, cli.sunshine);
    println!();

    loop {
        let report = run_checks(cli);
        output_report(&report, cli);
        println!();

        if report.overall != "HEALTHY" && !cli.json {
            let failures: Vec<_> = report.checks.iter()
                .filter(|c| c.status != "OK")
                .map(|c| c.service.as_str())
                .collect();
            eprintln!("⚠  ALERT: {} down — {:?}", report.overall, failures);
        }

        thread::sleep(interval);
    }
}

fn run_metrics_server(cli: &Cli) {
    let port = cli.metrics_port;
    println!("Coffee Pie healthd — Prometheus metrics on :{}", port);
    println!("Scrape endpoint: http://localhost:{}/metrics", port);
    println!();

    // Simple HTTP server for Prometheus metrics
    let listener = std::net::TcpListener::bind(format!("0.0.0.0:{}", port))
        .expect("Failed to bind metrics port");

    for stream in listener.incoming() {
        if let Ok(mut stream) = stream {
            let report = run_checks(cli);
            let metrics = format_prometheus(&report);

            let response = format!(
                "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: {}\r\n\r\n{}",
                metrics.len(), metrics
            );
            let _ = stream.write_all(response.as_bytes());
        }
    }
}

fn format_prometheus(report: &HealthReport) -> String {
    let mut out = String::new();
    out.push_str("# HELP coffeepie_health_check Service health check status (1=OK, 0=FAIL/TIMEOUT)\n");
    out.push_str("# TYPE coffeepie_health_check gauge\n");

    for check in &report.checks {
        let value = if check.status == "OK" { 1 } else { 0 };
        out.push_str(&format!(
            "coffeepie_health_check{{service=\"{}\"}} {}\n",
            check.service, value
        ));
    }

    out.push_str(&format!(
        "coffeepie_health_latency_ms{{service=\"orchestrator\"}} {}\n",
        report.checks.iter().find(|c| c.service == "orchestrator").map(|c| c.latency_ms).unwrap_or(0)
    ));

    out.push_str("# HELP coffeepie_health_overall Overall health (2=HEALTHY, 1=DEGRADED, 0=DOWN)\n");
    out.push_str("# TYPE coffeepie_health_overall gauge\n");
    let overall_val = match report.overall.as_str() {
        "HEALTHY" => 2, "DEGRADED" => 1, _ => 0,
    };
    out.push_str(&format!("coffeepie_health_overall {}\n", overall_val));

    out
}

fn parse_duration(s: &str) -> Duration {
    let s = s.trim().to_lowercase();
    if let Ok(secs) = s.trim_end_matches('s').parse::<u64>() {
        return Duration::from_secs(secs);
    }
    if s.ends_with("ms") {
        if let Ok(ms) = s.trim_end_matches("ms").parse::<u64>() {
            return Duration::from_millis(ms);
        }
    }
    if s.ends_with('m') {
        if let Ok(mins) = s.trim_end_matches('m').parse::<u64>() {
            return Duration::from_secs(mins * 60);
        }
    }
    Duration::from_secs(30) // default
}

fn now_iso() -> String {
    let dur = SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default();
    let secs = dur.as_secs();
    let d = secs / 86400;
    let t = secs % 86400;
    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z",
        1970 + d / 365, ((d % 365) / 30) + 1, (d % 30) + 1,
        t / 3600, (t % 3600) / 60, t % 60)
}
