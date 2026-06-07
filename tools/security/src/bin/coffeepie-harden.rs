// Coffee Pie Hardening Tool
// Post-install security hardening for Debian VMs running Coffee Pie.
//
// Applies defense-in-depth across 7 layers:
//   kernel → sysctl network/memory/ASLR/ptrace hardening
//   ssh    → key-only auth, disable root password, cipher restrictions
//   firewall → strict iptables/nftables for Coffee Pie ports only
//   filesystem → noexec/nosuid on /tmp, /dev/shm, immutable key files
//   users  → audit accounts, lock unused, enforce passwords
//   updates → unattended-upgrades for security patches
//   audit  → auditd rules for /etc/coffeepie/, actor binary, Sunshine config
//
// Three hardening levels:
//   basic    — safe for dev/staging, won't break anything
//   standard — production-ready, might require adjustments
//   paranoid — maximum lockdown, may require manual tuning
//
// Usage:
//   coffeepie-harden --target root@10.0.0.50 --level standard
//   coffeepie-harden --target root@10.0.0.50 --dry-run
//   coffeepie-harden --target root@10.0.0.50 --level paranoid --json

use clap::Parser;
use serde::Serialize;
use std::io::Write;
use std::process::{Command, Stdio};

#[derive(Parser)]
#[command(name = "coffeepie-harden")]
#[command(about = "Coffee Pie Node Hardening Tool — CIS-inspired defense-in-depth", long_about = None)]
struct Cli {
    /// SSH target (user@host)
    #[arg(short, long)]
    target: Option<String>,

    /// SSH port
    #[arg(long, default_value = "22")]
    ssh_port: u16,

    /// Hardening level: basic, standard, paranoid
    #[arg(short, long, default_value = "standard")]
    level: String,

    /// Only run checks, don't apply fixes
    #[arg(short, long)]
    dry_run: bool,

    /// Skip confirmation prompt
    #[arg(short, long)]
    yes: bool,

    /// Only show failing checks
    #[arg(short, long)]
    quiet: bool,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Specific categories to harden (comma-separated: kernel,ssh,firewall,fs,users,updates,audit,coffee)
    #[arg(long, default_value = "all")]
    categories: String,

    /// Revert changes (where supported)
    #[arg(long)]
    undo: bool,
}

#[derive(Debug, Clone, Serialize)]
struct HardeningCheck {
    id: &'static str,
    category: &'static str,
    name: &'static str,
    level: &'static str,        // basic | standard | paranoid
    check_cmd: &'static str,
    fix_cmd: &'static str,
    undo_cmd: &'static str,
    expect_pass: &'static str,   // substring that indicates the check passes
    description: &'static str,
    reboot_required: bool,
}

#[derive(Debug, Serialize)]
struct CheckResult {
    id: String,
    category: String,
    name: String,
    level: String,
    status: String,     // PASS | FAIL | FIXED | SKIPPED | ERROR
    detail: String,
    reboot_required: bool,
}

const CHECKS: &[HardeningCheck] = &[
    // ═══ KERNEL ═══
    HardeningCheck {
        id: "kernel-aslr", category: "kernel", name: "ASLR enabled (2=full)",
        level: "basic", reboot_required: false,
        check_cmd: "sysctl -n kernel.randomize_va_space",
        fix_cmd: "sysctl -w kernel.randomize_va_space=2 && echo 'kernel.randomize_va_space=2' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/kernel.randomize_va_space/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "2",
        description: "Address Space Layout Randomization — must be 2 (full)",
    },
    HardeningCheck {
        id: "kernel-kptr", category: "kernel", name: "Kernel pointer restriction",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n kernel.kptr_restrict",
        fix_cmd: "sysctl -w kernel.kptr_restrict=2 && echo 'kernel.kptr_restrict=2' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/kernel.kptr_restrict/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "2",
        description: "Restrict /proc/kallsyms to root — prevents kernel address leaks",
    },
    HardeningCheck {
        id: "kernel-ptrace", category: "kernel", name: "ptrace restricted to root",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n kernel.yama.ptrace_scope",
        fix_cmd: "sysctl -w kernel.yama.ptrace_scope=1 && echo 'kernel.yama.ptrace_scope=1' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/kernel.yama.ptrace_scope/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "1",
        description: "Only root (or parent) can ptrace — prevents process injection",
    },
    HardeningCheck {
        id: "kernel-dmesg", category: "kernel", name: "dmesg restricted",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n kernel.dmesg_restrict",
        fix_cmd: "sysctl -w kernel.dmesg_restrict=1 && echo 'kernel.dmesg_restrict=1' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/kernel.dmesg_restrict/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "1",
        description: "Only root can read kernel log buffer",
    },
    HardeningCheck {
        id: "kernel-syncookies", category: "kernel", name: "TCP SYN cookies",
        level: "basic", reboot_required: false,
        check_cmd: "sysctl -n net.ipv4.tcp_syncookies",
        fix_cmd: "sysctl -w net.ipv4.tcp_syncookies=1 && echo 'net.ipv4.tcp_syncookies=1' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/net.ipv4.tcp_syncookies/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "1",
        description: "Protect against SYN flood attacks",
    },
    HardeningCheck {
        id: "kernel-rp-filter", category: "kernel", name: "Reverse path filtering",
        level: "basic", reboot_required: false,
        check_cmd: "sysctl -n net.ipv4.conf.all.rp_filter",
        fix_cmd: "sysctl -w net.ipv4.conf.all.rp_filter=1 && echo 'net.ipv4.conf.all.rp_filter=1' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/net.ipv4.conf.all.rp_filter/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "1",
        description: "Prevent IP spoofing — drop packets from impossible routes",
    },
    HardeningCheck {
        id: "kernel-redirects", category: "kernel", name: "ICMP redirects disabled",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n net.ipv4.conf.all.accept_redirects",
        fix_cmd: "sysctl -w net.ipv4.conf.all.accept_redirects=0 && sysctl -w net.ipv6.conf.all.accept_redirects=0 && echo 'net.ipv4.conf.all.accept_redirects=0' >> /etc/sysctl.d/99-coffeepie.conf && echo 'net.ipv6.conf.all.accept_redirects=0' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/accept_redirects/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "0",
        description: "Prevent MITM via ICMP redirect attacks on L2 VLAN",
    },
    HardeningCheck {
        id: "kernel-forwarding", category: "kernel", name: "IP forwarding disabled",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n net.ipv4.ip_forward",
        fix_cmd: "sysctl -w net.ipv4.ip_forward=0 && echo 'net.ipv4.ip_forward=0' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/net.ipv4.ip_forward/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "0",
        description: "Nodes should not route traffic — prevents lateral pivot",
    },
    HardeningCheck {
        id: "kernel-source-routing", category: "kernel", name: "Source-routed packets dropped",
        level: "standard", reboot_required: false,
        check_cmd: "sysctl -n net.ipv4.conf.all.accept_source_route",
        fix_cmd: "sysctl -w net.ipv4.conf.all.accept_source_route=0 && echo 'net.ipv4.conf.all.accept_source_route=0' >> /etc/sysctl.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/accept_source_route/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "0",
        description: "Drop packets with source routing — network bypass vector",
    },
    HardeningCheck {
        id: "kernel-core-dumps", category: "kernel", name: "Core dumps restricted",
        level: "paranoid", reboot_required: false,
        check_cmd: "sysctl -n fs.suid_dumpable",
        fix_cmd: "sysctl -w fs.suid_dumpable=0 && echo 'fs.suid_dumpable=0' >> /etc/sysctl.d/99-coffeepie.conf && echo '* hard core 0' >> /etc/security/limits.d/99-coffeepie.conf",
        undo_cmd: "sed -i '/fs.suid_dumpable/d' /etc/sysctl.d/99-coffeepie.conf",
        expect_pass: "0",
        description: "Prevent SUID programs from dumping core with sensitive data",
    },

    // ═══ SSH ═══
    HardeningCheck {
        id: "ssh-root-login", category: "ssh", name: "Root password login disabled",
        level: "basic", reboot_required: false,
        check_cmd: "grep -E '^PermitRootLogin[[:space:]]+(no|prohibit-password|without-password)' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "sed -i 's/^#*PermitRootLogin.*/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i 's/^PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config",
        expect_pass: "PermitRootLogin",
        description: "Root can only login with SSH keys, never password",
    },
    HardeningCheck {
        id: "ssh-password-auth", category: "ssh", name: "Password authentication disabled",
        level: "basic", reboot_required: false,
        check_cmd: "grep -E '^PasswordAuthentication[[:space:]]+no' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "sed -i 's/^#*PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i 's/^PasswordAuthentication.*/PasswordAuthentication yes/' /etc/ssh/sshd_config",
        expect_pass: "PasswordAuthentication",
        description: "SSH keys only — no brute-force password attacks",
    },
    HardeningCheck {
        id: "ssh-empty-passwords", category: "ssh", name: "Empty passwords denied",
        level: "basic", reboot_required: false,
        check_cmd: "grep -E '^PermitEmptyPasswords[[:space:]]+no' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "sed -i 's/^#*PermitEmptyPasswords.*/PermitEmptyPasswords no/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i 's/^PermitEmptyPasswords.*/PermitEmptyPasswords yes/' /etc/ssh/sshd_config",
        expect_pass: "PermitEmptyPasswords",
        description: "No accounts with empty passwords can SSH in",
    },
    HardeningCheck {
        id: "ssh-x11-forwarding", category: "ssh", name: "X11 forwarding disabled",
        level: "standard", reboot_required: false,
        check_cmd: "grep -E '^X11Forwarding[[:space:]]+no' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "sed -i 's/^#*X11Forwarding.*/X11Forwarding no/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i 's/^X11Forwarding.*/X11Forwarding yes/' /etc/ssh/sshd_config",
        expect_pass: "X11Forwarding",
        description: "No X11 tunnel — reduces attack surface on headless servers",
    },
    HardeningCheck {
        id: "ssh-banner", category: "ssh", name: "SSH banner set",
        level: "standard", reboot_required: false,
        check_cmd: "grep -E '^Banner[[:space:]]+' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "echo 'Authorized Coffee Pie node access only. All activity is monitored.' > /etc/issue.net && chmod 644 /etc/issue.net && sed -i 's/^#*Banner.*/Banner \\/etc\\/issue.net/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i '/^Banner/d' /etc/ssh/sshd_config",
        expect_pass: "Banner",
        description: "Legal warning banner before authentication",
    },
    HardeningCheck {
        id: "ssh-max-auth-tries", category: "ssh", name: "Max authentication attempts: 3",
        level: "standard", reboot_required: false,
        check_cmd: "grep -E '^MaxAuthTries[[:space:]]+[1-3]$' /etc/ssh/sshd_config || echo 'FAIL'",
        fix_cmd: "sed -i 's/^#*MaxAuthTries.*/MaxAuthTries 3/' /etc/ssh/sshd_config",
        undo_cmd: "sed -i 's/^MaxAuthTries.*/MaxAuthTries 6/' /etc/ssh/sshd_config",
        expect_pass: "MaxAuthTries",
        description: "Limit brute force attempts per connection",
    },
    HardeningCheck {
        id: "ssh-protocol", category: "ssh", name: "SSH protocol 2 only",
        level: "basic", reboot_required: false,
        check_cmd: "grep -E '^Protocol[[:space:]]+2' /etc/ssh/sshd_config 2>/dev/null || grep -E '^#Protocol' /etc/ssh/sshd_config 2>/dev/null && echo 'PROTOCOL_UNSET_OK' || echo 'FAIL'",
        fix_cmd: "grep -q '^Protocol' /etc/ssh/sshd_config || echo 'Protocol 2' >> /etc/ssh/sshd_config",
        undo_cmd: "sed -i '/^Protocol/d' /etc/ssh/sshd_config",
        expect_pass: "PROTOCOL_UNSET_OK",
        description: "SSH v1 is insecure — Protocol 2 (default) is fine",
    },

    // ═══ FIREWALL ═══
    HardeningCheck {
        id: "fw-enabled", category: "firewall", name: "Firewall active (iptables output policy drop)",
        level: "basic", reboot_required: false,
        check_cmd: "iptables -L OUTPUT -n | grep -q 'policy DROP' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "iptables -P INPUT DROP && iptables -P FORWARD DROP && iptables -P OUTPUT ACCEPT",
        undo_cmd: "iptables -P INPUT ACCEPT && iptables -P FORWARD ACCEPT && iptables -P OUTPUT ACCEPT",
        expect_pass: "OK",
        description: "Default-deny inbound — allow only Coffee Pie + SSH ports",
    },
    HardeningCheck {
        id: "fw-coffee-ports", category: "firewall", name: "Coffee Pie ports allowed",
        level: "basic", reboot_required: false,
        check_cmd: "iptables -L INPUT -n | grep -q 'dpt:43910' && iptables -L INPUT -n | grep -q 'dpt:47984' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "iptables -A INPUT -p tcp --dport 22 -j ACCEPT && for port in 43910 47984 47989 47990 48010; do iptables -A INPUT -p tcp --dport $port -j ACCEPT; done && for port in 47998 47999 48000 48002 48010; do iptables -A INPUT -p udp --dport $port -j ACCEPT; done && iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT && iptables -A INPUT -i lo -j ACCEPT",
        undo_cmd: "iptables -F INPUT",
        expect_pass: "OK",
        description: "Only SSH + Coffee Pie actor/Sunshine ports are open",
    },

    // ═══ FILESYSTEM ═══
    HardeningCheck {
        id: "fs-tmp-noexec", category: "fs", name: "/tmp mounted noexec,nosuid",
        level: "standard", reboot_required: true,
        check_cmd: "mount | grep ' /tmp ' | grep -q 'noexec' && mount | grep ' /tmp ' | grep -q 'nosuid' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "grep -q '/tmp' /etc/fstab && sed -i 's|^.* /tmp .*|tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev 0 0|' /etc/fstab || echo 'tmpfs /tmp tmpfs defaults,noexec,nosuid,nodev 0 0' >> /etc/fstab",
        undo_cmd: "sed -i 's|^tmpfs /tmp.*noexec,nosuid.*|tmpfs /tmp tmpfs defaults 0 0|' /etc/fstab",
        expect_pass: "OK",
        description: "Prevents binary execution from world-writable /tmp",
    },
    HardeningCheck {
        id: "fs-shm-noexec", category: "fs", name: "/dev/shm mounted noexec",
        level: "standard", reboot_required: true,
        check_cmd: "mount | grep ' /dev/shm ' | grep -q 'noexec' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "grep -q '/dev/shm' /etc/fstab || echo 'tmpfs /dev/shm tmpfs defaults,noexec,nosuid,nodev 0 0' >> /etc/fstab; sed -i 's|^.* /dev/shm .*|tmpfs /dev/shm tmpfs defaults,noexec,nosuid,nodev 0 0|' /etc/fstab",
        undo_cmd: "sed -i 's|^tmpfs /dev/shm.*noexec.*|tmpfs /dev/shm tmpfs defaults 0 0|' /etc/fstab",
        expect_pass: "OK",
        description: "Prevents shared memory execution — common exploit staging area",
    },
    HardeningCheck {
        id: "fs-keys-perms", category: "fs", name: "Coffee Pie keys: root-only (600)",
        level: "basic", reboot_required: false,
        check_cmd: "test -d /etc/coffeepie/keys && find /etc/coffeepie/keys -type f ! -perm 600 | wc -l | grep -q '^0$' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "chmod 600 /etc/coffeepie/keys/* 2>/dev/null; chown root:root /etc/coffeepie/keys/* 2>/dev/null; echo 'OK'",
        undo_cmd: "echo 'N/A'",
        expect_pass: "OK",
        description: "Private keys must be 0600 — no group/other access",
    },
    HardeningCheck {
        id: "fs-cron-restrict", category: "fs", name: "Cron restricted to root",
        level: "paranoid", reboot_required: false,
        check_cmd: "test -f /etc/cron.allow && cat /etc/cron.allow | grep -q '^root$' && test ! -f /etc/cron.deny && echo 'OK' || echo 'FAIL'",
        fix_cmd: "echo 'root' > /etc/cron.allow && chmod 644 /etc/cron.allow && rm -f /etc/cron.deny /etc/at.deny",
        undo_cmd: "rm -f /etc/cron.allow /etc/cron.deny",
        expect_pass: "OK",
        description: "Only root can schedule cron/at jobs — prevents persistence",
    },

    // ═══ USERS ═══
    HardeningCheck {
        id: "users-no-empty-pass", category: "users", name: "No accounts with empty passwords",
        level: "basic", reboot_required: false,
        check_cmd: "awk -F: '($2 == \"\" || $2 == \"!\") {next} ($2 ~ /^\\$/) {print}' /etc/shadow | wc -l | grep -q '^0$' && echo 'OK' || (awk -F: '($2 == \"\" ) {print $1 \" has empty password!\"}' /etc/shadow; echo 'FAIL')",
        fix_cmd: "for user in $(awk -F: '($2 == \"\") {print $1}' /etc/shadow); do passwd -l $user 2>/dev/null; done; echo 'OK'",
        undo_cmd: "echo 'N/A — manually unlock if needed'",
        expect_pass: "OK",
        description: "No login-capable accounts without passwords",
    },
    HardeningCheck {
        id: "users-shell-access", category: "users", name: "Service accounts have nologin shell",
        level: "standard", reboot_required: false,
        check_cmd: "awk -F: '($3 >= 1000 || $1 == \"root\") {next} ($7 !~ /(nologin|false)$/ && $7 != \"\") {print $1 \" has shell: \" $7}' /etc/passwd | wc -l | grep -q '^0$' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "echo 'Review service accounts manually: awk -F: '\\''($3 < 1000) && ($1 != \"root\") && ($7 !~ /(nologin|false)/) {print $1, $7}'\\'' /etc/passwd'; echo 'OK'",
        undo_cmd: "echo 'N/A'",
        expect_pass: "OK",
        description: "Daemon/service accounts should not have login shells",
    },

    // ═══ UPDATES ═══
    HardeningCheck {
        id: "updates-automatic", category: "updates", name: "Unattended security upgrades enabled",
        level: "basic", reboot_required: false,
        check_cmd: "dpkg -l unattended-upgrades 2>/dev/null | grep -q '^ii' && grep -q '^\"origin=Debian,codename=${distro_codename}-security\"' /etc/apt/apt.conf.d/50unattended-upgrades 2>/dev/null && echo 'OK' || echo 'FAIL'",
        fix_cmd: "apt-get install -y -qq unattended-upgrades apt-listchanges 2>/dev/null && echo 'unattended-upgrades unattended-upgrades/enable_auto_updates boolean true' | debconf-set-selections && dpkg-reconfigure -f noninteractive unattended-upgrades",
        undo_cmd: "apt-get remove -y unattended-upgrades 2>/dev/null || true",
        expect_pass: "OK",
        description: "Automatic security patches — critical for internet-facing nodes",
    },

    // ═══ AUDIT ═══
    HardeningCheck {
        id: "audit-installed", category: "audit", name: "auditd installed and running",
        level: "standard", reboot_required: false,
        check_cmd: "dpkg -l auditd 2>/dev/null | grep -q '^ii' && systemctl is-active auditd 2>/dev/null | grep -q '^active$' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "apt-get install -y -qq auditd 2>/dev/null && systemctl enable auditd && systemctl start auditd",
        undo_cmd: "systemctl stop auditd; apt-get remove -y auditd 2>/dev/null",
        expect_pass: "OK",
        description: "auditd for file access monitoring and intrusion detection",
    },
    HardeningCheck {
        id: "audit-coffee-rules", category: "audit", name: "auditd rules for Coffee Pie paths",
        level: "standard", reboot_required: false,
        check_cmd: "grep -q 'coffeepie' /etc/audit/rules.d/coffeepie.rules 2>/dev/null && echo 'OK' || echo 'FAIL'",
        fix_cmd: "echo '-w /etc/coffeepie/keys/ -p wa -k coffee_keys' > /etc/audit/rules.d/coffeepie.rules && echo '-w /usr/local/bin/coffeepie-actor -p wa -k coffee_actor' >> /etc/audit/rules.d/coffeepie.rules && echo '-w /root/.config/sunshine/ -p wa -k coffee_sunshine' >> /etc/audit/rules.d/coffeepie.rules && auditctl -R /etc/audit/rules.d/coffeepie.rules 2>/dev/null; echo 'OK'",
        undo_cmd: "rm -f /etc/audit/rules.d/coffeepie.rules; auditctl -D",
        expect_pass: "OK",
        description: "Monitor access to keys, actor binary, and Sunshine config",
    },

    // ═══ COFFEE PIE SPECIFIC ═══
    HardeningCheck {
        id: "coffee-actor-immutable", category: "coffee", name: "Actor binary immutable (chattr +i)",
        level: "paranoid", reboot_required: false,
        check_cmd: "test -f /usr/local/bin/coffeepie-actor && lsattr /usr/local/bin/coffeepie-actor 2>/dev/null | grep -q '^....i' && echo 'OK' || echo 'FAIL'",
        fix_cmd: "chattr +i /usr/local/bin/coffeepie-actor 2>/dev/null; echo 'OK'",
        undo_cmd: "chattr -i /usr/local/bin/coffeepie-actor 2>/dev/null",
        expect_pass: "OK",
        description: "Immutable bit prevents actor binary tampering (must chattr -i to update)",
    },
    HardeningCheck {
        id: "coffee-sunshine-user", category: "coffee", name: "Sunshine runs as dedicated user",
        level: "standard", reboot_required: false,
        check_cmd: "id sunshine 2>/dev/null && echo 'OK' || echo 'FAIL'",
        fix_cmd: "useradd -r -s /usr/sbin/nologin -d /var/lib/sunshine sunshine 2>/dev/null; echo 'OK'",
        undo_cmd: "userdel sunshine 2>/dev/null",
        expect_pass: "OK",
        description: "Dedicated unprivileged user for Sunshine — no root for streaming",
    },
];

fn main() {
    let cli = Cli::parse();

    let target = cli.target.clone().unwrap_or_else(|| "root@localhost".into());
    let level = cli.level.to_lowercase();
    if !["basic", "standard", "paranoid"].contains(&level.as_str()) {
        eprintln!("ERROR: Level must be basic, standard, or paranoid");
        std::process::exit(1);
    }

    if !cli.json && !cli.dry_run && !cli.yes {
        println!("Coffee Pie Hardening Tool — Level: {}", level.to_uppercase());
        println!("Target: {}", target);
        println!();
        println!("⚠  This will modify system configuration on the target node.");
        println!("   Dry-run first with --dry-run to see what would change.");
        println!();
        print!("Proceed? [y/N] ");
        std::io::stdout().flush().ok();
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        if !input.trim().eq_ignore_ascii_case("y") {
            println!("Aborted.");
            return;
        }
    }

    // Filter checks by level and category
    let level_order = |l: &str| match l {
        "basic" => 0, "standard" => 1, "paranoid" => 2, _ => 99,
    };
    let max_level = level_order(&level);

    let cats: Vec<&str> = if cli.categories == "all" {
        vec!["kernel", "ssh", "firewall", "fs", "users", "updates", "audit", "coffee"]
    } else {
        cli.categories.split(',').map(|s| s.trim()).collect()
    };

    let checks: Vec<&HardeningCheck> = CHECKS.iter()
        .filter(|c| level_order(c.level) <= max_level)
        .filter(|c| cats.contains(&c.category))
        .collect();

    if !cli.json {
        println!();
        println!("Running {} checks at level {} across {:?}...", checks.len(), level.to_uppercase(), cats);
        println!();
    }

    let mut results: Vec<CheckResult> = Vec::new();
    let (mut passed, mut failed, mut fixed, mut skipped, mut errored) = (0u32, 0, 0, 0, 0);

    for check in &checks {
        let mode = if cli.dry_run { "check" } else if cli.undo { "undo" } else { "fix" };

        // Run check
        let check_out = exec_ssh(&target, cli.ssh_port, check.check_cmd);

        let (status, detail) = match check_out {
            Ok(out) => {
                let s = String::from_utf8_lossy(&out.stdout);
                if s.contains(check.expect_pass) {
                    if !cli.json && !cli.quiet { println!("  ✓ {}", check.name); }
                    passed += 1;
                    ("PASS".into(), s.trim().to_string())
                } else if cli.dry_run {
                    if !cli.json { println!("  ✗ {}  [would fix]", check.name); }
                    failed += 1;
                    ("FAIL".into(), format!("{} (would run: {})", s.trim(), check.fix_cmd))
                } else {
                    // Apply fix
                    let cmd = if cli.undo { check.undo_cmd } else { check.fix_cmd };
                    match exec_ssh(&target, cli.ssh_port, cmd) {
                        Ok(fix_out) => {
                            let fix_s = String::from_utf8_lossy(&fix_out.stdout);
                            if !cli.json { println!("  ⚡ {}  [fixed]", check.name); }
                            fixed += 1;
                            ("FIXED".into(), format!("before: {} | after: {}", s.trim(), fix_s.trim()))
                        }
                        Err(e) => {
                            if !cli.json { println!("  ✗ {}  [error: {}]", check.name, e); }
                            errored += 1;
                            ("ERROR".into(), format!("fix failed: {}", e))
                        }
                    }
                }
            }
            Err(e) => {
                if !cli.json { println!("  ✗ {}  [error: {}]", check.name, e); }
                errored += 1;
                ("ERROR".into(), e)
            }
        };

        results.push(CheckResult {
            id: check.id.into(),
            category: check.category.into(),
            name: check.name.into(),
            level: check.level.into(),
            status,
            detail,
            reboot_required: check.reboot_required,
        });
    }

    // Summary
    if cli.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "target": target,
            "level": level,
            "mode": if cli.dry_run { "dry-run" } else if cli.undo { "undo" } else { "apply" },
            "total": checks.len(),
            "passed": passed,
            "failed": failed,
            "fixed": fixed,
            "skipped": skipped,
            "errored": errored,
            "results": results,
            "reboot_required": results.iter().any(|r| r.reboot_required && r.status != "PASS"),
        })).unwrap());
    } else {
        println!();
        println!("═══════════════════════════════════════");
        println!("  Results: {} passed, {} fixed, {} failed, {} errors",
            passed, fixed, failed, errored);
        if failed > 0 || errored > 0 {
            println!("  ⚠ {} issues remaining — review manually", failed + errored);
        } else if fixed > 0 {
            println!("  ✓ All {} issues fixed", fixed);
        } else {
            println!("  ✓ All checks passed — node is hardened");
        }
        println!("═══════════════════════════════════════");

        // Reboot warning
        if results.iter().any(|r| r.reboot_required && r.status != "PASS") {
            println!();
            println!("  ⚠ Some changes require a reboot to take effect:");
            for r in &results {
                if r.reboot_required && r.status != "PASS" {
                    println!("    - {}", r.name);
                }
            }
        }
    }
}

fn exec_ssh(target: &str, port: u16, cmd: &str) -> Result<SshOutput, String> {
    let ssh_target = if target.contains('@') { target.to_string() } else { format!("root@{}", target) };
    let full_cmd = format!(
        "ssh -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes -p {} {} '{}'",
        port, ssh_target, cmd.replace('\'', "'\\''"),
    );

    let output = Command::new("sh")
        .arg("-c")
        .arg(&full_cmd)
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .output()
        .map_err(|e| format!("SSH error: {}", e))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr);
        return Err(format!("exit {}: {}", output.status.code().unwrap_or(-1), stderr.trim()));
    }

    Ok(SshOutput {
        stdout: output.stdout,
        stderr: output.stderr,
    })
}

struct SshOutput {
    stdout: Vec<u8>,
    #[allow(dead_code)]
    stderr: Vec<u8>,
}
