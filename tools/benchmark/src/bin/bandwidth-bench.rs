// Coffee Pie Bandwidth Benchmark
// Measures TCP throughput between two points — critical for determining
// how many simultaneous streams a link can support.
// Each Coffee Pie slice requires 8 Mbps. Use this to validate your
// network can handle the planned slice count.

use clap::Parser;
use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream, SocketAddr};
use std::thread;
use std::time::Instant;

#[derive(Parser)]
#[command(name = "bandwidth-bench")]
#[command(about = "Coffee Pie TCP Bandwidth Benchmark", long_about = None)]
struct Cli {
    /// Run in server mode (listen for client)
    #[arg(long)]
    server: bool,

    /// Target address (IP:port) — client mode only
    #[arg(long, default_value = "127.0.0.1:9090")]
    target: String,

    /// Server bind address — server mode only
    #[arg(long, default_value = "0.0.0.0:9090")]
    bind: String,

    /// Test duration in seconds
    #[arg(short, long, default_value = "10")]
    duration: u64,

    /// Buffer size in KB
    #[arg(short, long, default_value = "256")]
    buffer_kb: usize,

    /// JSON output
    #[arg(long)]
    json: bool,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie Bandwidth Benchmark");
        println!("===============================");
    }

    if cli.server {
        run_server(&cli);
    } else {
        run_client(&cli);
    }
}

fn run_server(cli: &Cli) {
    let listener = TcpListener::bind(&cli.bind).expect("Failed to bind");
    if !cli.json {
        println!("Server listening on {}", cli.bind);
        println!("Waiting for client connection...");
    }

    let (mut stream, addr) = listener.accept().expect("Accept failed");
    if !cli.json {
        println!("Client connected from {}", addr);
        println!("Receiving data for {}s...", cli.duration);
    }

    let buf_size = cli.buffer_kb * 1024;
    let mut buf = vec![0u8; buf_size];
    let start = Instant::now();
    let mut total_bytes: u64 = 0;

    while start.elapsed().as_secs() < cli.duration {
        match stream.read(&mut buf) {
            Ok(0) => break,
            Ok(n) => total_bytes += n as u64,
            Err(e) => {
                eprintln!("Read error: {}", e);
                break;
            }
        }
    }

    let elapsed = start.elapsed().as_secs_f64();
    let mbps = (total_bytes as f64 * 8.0) / elapsed / 1_000_000.0;
    let slices = (mbps / 8.0) as u64; // Each slice needs 8 Mbps

    if cli.json {
        println!("{}", serde_json::json!({
            "mode": "server",
            "client": addr.to_string(),
            "total_bytes": total_bytes,
            "duration_sec": format!("{:.1}", elapsed),
            "throughput_mbps": format!("{:.1}", mbps),
            "max_simultaneous_slices": slices,
        }));
    } else {
        println!();
        println!("Received: {} MB in {:.1}s", total_bytes / 1_000_000, elapsed);
        println!("Throughput: {:.1} Mbps ({:.1} MB/s)", mbps, mbps / 8.0);
        println!("Max simultaneous Coffee Pie slices (8 Mbps each): {}", slices);
    }
}

fn run_client(cli: &Cli) {
    if !cli.json {
        println!("Connecting to {}...", cli.target);
    }

    let addr: SocketAddr = cli.target.parse().expect("Invalid address");
    let mut stream = TcpStream::connect_timeout(
        &addr,
        std::time::Duration::from_secs(5),
    ).expect("Connection failed");

    if !cli.json {
        println!("Connected. Sending data for {}s...", cli.duration);
    }

    let buf_size = cli.buffer_kb * 1024;
    let buf = vec![0xAAu8; buf_size]; // Dummy data
    let start = Instant::now();
    let mut total_bytes: u64 = 0;

    while start.elapsed().as_secs() < cli.duration {
        match stream.write(&buf) {
            Ok(n) => total_bytes += n as u64,
            Err(e) => {
                eprintln!("Write error: {}", e);
                break;
            }
        }
    }

    let elapsed = start.elapsed().as_secs_f64();
    let mbps = (total_bytes as f64 * 8.0) / elapsed / 1_000_000.0;
    let slices = (mbps / 8.0) as u64;

    if cli.json {
        println!("{}", serde_json::json!({
            "mode": "client",
            "target": cli.target,
            "total_bytes": total_bytes,
            "duration_sec": format!("{:.1}", elapsed),
            "throughput_mbps": format!("{:.1}", mbps),
            "max_simultaneous_slices": slices,
        }));
    } else {
        println!();
        println!("Sent: {} MB in {:.1}s", total_bytes / 1_000_000, elapsed);
        println!("Throughput: {:.1} Mbps ({:.1} MB/s)", mbps, mbps / 8.0);
        println!("Max simultaneous Coffee Pie slices (8 Mbps each): {}", slices);
    }
}
