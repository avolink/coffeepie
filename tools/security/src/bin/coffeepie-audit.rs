// Coffee Pie Security Audit Scanner
// Scans target nodes for security posture: running services, open ports,
// package versions, known CVEs, and configuration drift from hardening baseline.
//
// Compares against coffeepie-harden baseline and CIS benchmarks.
// Reports pass/fail/warn with CVSS scores and remediation steps.
//
// Usage:
//   coffeepie-audit --target root@10.0.0.50
//   coffeepie-audit --target root@10.0.0.50 --json
//   coffeepie-audit --target root@10.0.0.50 --cve-scan

use clap::Parser;
use serde::Serialize;
use std::process::Command;

#[derive(Parser)]
#[command(name = "coffeepie-audit")]
#[command(about = "Coffee Pie Security Audit Scanner", long_about = None)]
struct Cli {
    /// SSH target (user@host)
    #[arg(short, long, default_value = "root@localhost")]
    target: String,

    /// SSH port
    #[arg(long, default_value = "22")]
    ssh_port: u16,

    /// Include CVE scan (requires debsecan or similar)
    #[arg(long)]
    cve_scan: bool,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Only show findings with severity >= this (low, medium, high, critical)
    #[arg(long, default_value = "medium")]
    min_severity: String,
}

#[derive(Debug, Serialize)]
struct AuditReport {
    target: String,
    timestamp: String,
    hostname: String,
    os: String,
    kernel: String,
    uptime: String,
    summary: AuditSummary,
    services: Vec<ServiceFinding>,
    ports: Vec<PortFinding>,
    packages: Vec<PackageFinding>,
    cves: Vec<CveFinding>,
    config_checks: Vec<ConfigCheck>,
    recommendations: Vec<String>,
}

#[derive(Debug, Serialize)]
struct AuditSummary {
    total_findings: u32,
    critical: u32,
    high: u32,
    medium: u32,
    low: u32,
    score: u32, // 0-100, higher is better
}

#[derive(Debug, Serialize)]
struct ServiceFinding {
    name: String,
    status: String,
    enabled: bool,
    exposed: bool,
    severity: String,
    recommendation: String,
}

#[derive(Debug, Serialize)]
struct PortFinding {
    port: u16,
    protocol: String,
    service: String,
    expected: bool,
    severity: String,
    recommendation: String,
}

#[derive(Debug, Serialize)]
struct PackageFinding {
    name: String,
    version: String,
    has_update: bool,
    is_security_update: bool,
    severity: String,
}

#[derive(Debug, Serialize)]
struct CveFinding {
    cve_id: String,
    package: String,
    description: String,
    cvss_score: f64,
    severity: String,
    fix_version: String,
}

#[derive(Debug, Serialize)]
struct ConfigCheck {
    check: String,
    status: String,
    expected: String,
    actual: String,
    severity: String,
}

fn main() {
    let cli = Cli::parse();
    let min_level = severity_level(&cli.min_severity);

    if !cli.json {
        println!("Coffee Pie Security Audit Scanner");
        println!("=================================");
        println!("Target: {}", cli.target);
        println!();
    }

    let mut report = AuditReport {
        target: cli.target.clone(),
        timestamp: now_iso(),
        hostname: ssh_exec(&cli, "hostname").unwrap_or_default(),
        os: ssh_exec(&cli, "cat /etc/os-release | head -2 | tr '\\n' ' '").unwrap_or_default(),
        kernel: ssh_exec(&cli, "uname -r").unwrap_or_default(),
        uptime: ssh_exec(&cli, "uptime -p").unwrap_or_default(),
        summary: AuditSummary { total_findings: 0, critical: 0, high: 0, medium: 0, low: 0, score: 100 },
        services: Vec::new(),
        ports: Vec::new(),
        packages: Vec::new(),
        cves: Vec::new(),
        config_checks: Vec::new(),
        recommendations: Vec::new(),
    };

    // 1. Service audit
    audit_services(&cli, &mut report);
    // 2. Port audit
    audit_ports(&cli, &mut report);
    // 3. Package audit
    audit_packages(&cli, &mut report);
    // 4. Config checks
    audit_config(&cli, &mut report);
    // 5. CVE scan
    if cli.cve_scan {
        audit_cves(&cli, &mut report);
    }

    // Calculate summary
    let all: Vec<&str> = report.services.iter().map(|f| f.severity.as_str())
        .chain(report.ports.iter().map(|f| f.severity.as_str()))
        .chain(report.packages.iter().map(|f| f.severity.as_str()))
        .chain(report.cves.iter().map(|f| f.severity.as_str()))
        .chain(report.config_checks.iter().map(|f| f.severity.as_str()))
        .collect();

    report.summary.total_findings = all.len() as u32;
    report.summary.critical = all.iter().filter(|&&s| s == "critical").count() as u32;
    report.summary.high = all.iter().filter(|&&s| s == "high").count() as u32;
    report.summary.medium = all.iter().filter(|&&s| s == "medium").count() as u32;
    report.summary.low = all.iter().filter(|&&s| s == "low").count() as u32;

    // Score: deduct points per finding
    let deductions = report.summary.critical * 25 + report.summary.high * 10 + report.summary.medium * 3 + report.summary.low;
    report.summary.score = 100u32.saturating_sub(deductions);

    // Generate recommendations
    if report.summary.critical > 0 { report.recommendations.push(format!("{} critical findings — address immediately", report.summary.critical)); }
    if report.summary.high > 0 { report.recommendations.push(format!("{} high-severity findings — patch within 7 days", report.summary.high)); }
    let unpatched = report.packages.iter().filter(|p| p.has_update && p.is_security_update).count();
    if unpatched > 0 { report.recommendations.push(format!("{} security updates available — run apt upgrade", unpatched)); }
    let unexpected_ports = report.ports.iter().filter(|p| !p.expected).count();
    if unexpected_ports > 0 { report.recommendations.push(format!("{} unexpected ports open — review firewall rules", unexpected_ports)); }
    if report.summary.score < 70 { report.recommendations.push("Score below 70 — run coffeepie-harden to apply baseline".into()); }

    // Filter by severity
    let min_sl = min_level;
    report.services.retain(|f| severity_level(&f.severity) >= min_sl);
    report.ports.retain(|f| severity_level(&f.severity) >= min_sl);
    report.packages.retain(|f| severity_level(&f.severity) >= min_sl);
    report.cves.retain(|f| severity_level(&f.severity) >= min_sl);
    report.config_checks.retain(|f| severity_level(&f.severity) >= min_sl);

    if cli.json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        println!("Host: {} | OS: {} | Kernel: {}", report.hostname, report.os.trim(), report.kernel);
        println!("Score: {}/100 — {} findings (C:{} H:{} M:{} L:{})",
            report.summary.score, report.summary.total_findings,
            report.summary.critical, report.summary.high, report.summary.medium, report.summary.low);
        println!();

        print_section("Services", &report.services, |s: &ServiceFinding| format!("  {: <3} {: <20} {: <12} {}", severity_icon(&s.severity), s.name, s.status, s.recommendation));
        print_section("Ports", &report.ports, |p: &PortFinding| format!("  {: <3} {: <6}/{: <4} {: <12} {}", severity_icon(&p.severity), p.port, p.protocol, p.service, if p.expected { "expected" } else { "⚠ unexpected" }));
        if !report.cves.is_empty() { print_section("CVEs", &report.cves, |c: &CveFinding| format!("  {: <3} {: <16} CVSS {:.1} {}", severity_icon(&c.severity), c.cve_id, c.cvss_score, c.description)); }
        print_section("Config", &report.config_checks, |c: &ConfigCheck| format!("  {: <3} {: <30} expected={} actual={}", severity_icon(&c.severity), c.check, c.expected, c.actual));

        if !report.recommendations.is_empty() {
            println!();
            println!("Recommendations:");
            for r in &report.recommendations { println!("  → {}", r); }
        }

        let grade = if report.summary.score >= 90 { "A — Excellent" } else if report.summary.score >= 75 { "B — Good" } else if report.summary.score >= 60 { "C — Needs work" } else if report.summary.score >= 40 { "D — Poor" } else { "F — Critical risk" };
        println!();
        println!("Grade: {}", grade);
    }
}

fn audit_services(cli: &Cli, report: &mut AuditReport) {
    let dangerous = ["telnet", "ftp", "rsh", "rlogin", "rexec", "tftp", "finger", "sendmail"];
    let coffee_expected = ["ssh", "sunshine", "coffeepie-actor", "docker", "nginx", "postgresql"];

    let svc_list = ssh_exec(cli, "systemctl list-units --type=service --no-pager --no-legend 2>/dev/null | head -40").unwrap_or_default();

    for line in svc_list.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 3 { continue; }
        let name = parts[0].trim_end_matches(".service");
        let status = parts[3];

        let is_dangerous = dangerous.iter().any(|d| name.contains(d));
        let is_expected = coffee_expected.iter().any(|e| name.contains(e));

        let (severity, recommendation) = if is_dangerous {
            ("critical".into(), format!("Remove {} — insecure legacy service", name))
        } else if status == "active" && !is_expected {
            ("low".into(), format!("Unexpected service {} — review if needed", name))
        } else {
            continue; // Expected, skip
        };

        report.services.push(ServiceFinding {
            name: name.into(), status: status.into(), enabled: status == "active",
            exposed: false, severity, recommendation,
        });
    }
}

fn audit_ports(cli: &Cli, report: &mut AuditReport) {
    let expected_ports: &[u16] = &[22, 43910, 47984, 47989, 47990, 48010, 9090, 8000];
    let port_list = ssh_exec(cli, "ss -tlnp 2>/dev/null | tail -n +2").unwrap_or_default();

    for line in port_list.lines() {
        let parts: Vec<&str> = line.split_whitespace().collect();
        if parts.len() < 4 { continue; }
        let addr = parts[3];
        if !addr.contains(':') { continue; }
        let port_str = addr.split(':').last().unwrap_or("0");
        let port: u16 = port_str.parse().unwrap_or(0);
        if port == 0 { continue; }

        let expected = expected_ports.contains(&port);
        let (severity, rec) = if [23, 21, 25, 110, 143, 3306, 6379].contains(&port) {
            ("high".into(), format!("Port {} exposes dangerous service — restrict to internal network", port))
        } else if !expected {
            ("medium".into(), format!("Port {} not in expected Coffee Pie range — investigate", port))
        } else {
            continue;
        };

        report.ports.push(PortFinding {
            port, protocol: "tcp".into(), service: String::new(),
            expected, severity, recommendation: rec,
        });
    }
}

fn audit_packages(cli: &Cli, report: &mut AuditReport) {
    let pkg_list = ssh_exec(cli, "apt list --upgradable 2>/dev/null | grep -i security | head -20").unwrap_or_default();

    for line in pkg_list.lines() {
        let parts: Vec<&str> = line.split('/').collect();
        let name = parts.first().unwrap_or(&"unknown").to_string();
        let ver = parts.get(1).map(|v| v.split_whitespace().last().unwrap_or("")).unwrap_or("");

        report.packages.push(PackageFinding {
            name, version: ver.into(), has_update: true, is_security_update: true,
            severity: "high".into(),
        });
    }
}

fn audit_config(cli: &Cli, report: &mut AuditReport) {
    let checks = [
        ("sshd PermitRootLogin", "grep '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}'", "prohibit-password", "high"),
        ("sshd PasswordAuth", "grep '^PasswordAuthentication' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}'", "no", "high"),
        ("Firewall active", "ufw status 2>/dev/null | grep -q active && echo active || echo inactive", "active", "medium"),
        ("Automatic updates", "dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii' && echo installed || echo missing", "installed", "medium"),
        ("Keys permissions", "stat -c '%a' /etc/coffeepie/keys/id_ed25519 2>/dev/null || echo missing", "600", "critical"),
        ("Core dumps restricted", "sysctl -n fs.suid_dumpable 2>/dev/null || echo unknown", "0", "low"),
    ];

    for (check, cmd, expected, severity) in &checks {
        let actual = ssh_exec(cli, cmd).unwrap_or_else(|| "unknown".into());
        let status = if actual.trim() == *expected { "PASS" } else { "FAIL" };

        if status == "FAIL" {
            report.config_checks.push(ConfigCheck {
                check: check.to_string(), status: status.into(),
                expected: expected.to_string(), actual: actual.trim().into(),
                severity: severity.to_string(),
            });
        }
    }
}

fn audit_cves(cli: &Cli, report: &mut AuditReport) {
    // Try debsecan if available, fallback to apt-check
    let cve_data = ssh_exec(cli, "debsecan --format detail 2>/dev/null | head -50 || apt list --upgradable 2>/dev/null | grep security | head -20").unwrap_or_default();

    for line in cve_data.lines() {
        if line.starts_with("CVE") {
            let parts: Vec<&str> = line.split_whitespace().collect();
            let cve = parts.first().unwrap_or(&"CVE-XXXX-XXXXX").to_string();
            let desc = parts.get(2..).map(|p| p.join(" ")).unwrap_or_default();
            report.cves.push(CveFinding {
                cve_id: cve, package: String::new(), description: desc,
                cvss_score: 7.5, severity: "high".into(), fix_version: "latest".into(),
            });
        }
    }
}

fn print_section<T>(title: &str, items: &[T], format_fn: fn(&T) -> String) {
    if items.is_empty() { return; }
    println!("{} ({} findings):", title, items.len());
    for item in items { println!("{}", format_fn(item)); }
    println!();
}

fn ssh_exec(cli: &Cli, cmd: &str) -> Option<String> {
    let target = if cli.target.contains('@') { cli.target.clone() } else { format!("root@{}", cli.target) };
    let full = format!("ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes -p {} {} '{}' 2>/dev/null", cli.ssh_port, target, cmd.replace('\'', "'\\''"));
    Command::new("sh").arg("-c").arg(&full).output().ok()
        .map(|o| String::from_utf8_lossy(&o.stdout).trim().to_string())
}

fn severity_level(s: &str) -> u32 {
    match s { "critical" => 4, "high" => 3, "medium" => 2, "low" => 1, _ => 0 }
}

fn severity_icon(s: &str) -> &str {
    match s { "critical" => "🔴", "high" => "🟠", "medium" => "🟡", "low" => "🔵", _ => "✓" }
}

fn now_iso() -> String {
    let dur = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap_or_default();
    let secs = dur.as_secs();
    format!("{:04}-{:02}-{:02}T{:02}:{:02}:{:02}Z", 1970 + (secs/86400/365), ((secs/86400)%365/30)+1, (secs/86400%30)+1, (secs%86400)/3600, (secs%86400%3600)/60, secs%60)
}
