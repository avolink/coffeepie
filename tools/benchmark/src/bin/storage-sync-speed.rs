// Coffee Pie Storage Sync Speed Test
// Simulates the file synchronization speed between a user's cloud VM instance
// and the codec terminal. Measures read, write, and network-capped transfer
// speeds to estimate real-world sync times for common file sizes.

use std::fs;
use std::io::{Read, Write, Seek, SeekFrom};
use std::path::PathBuf;
use std::time::Instant;
use clap::Parser;
use rand::RngCore;

#[derive(Parser)]
#[command(name = "storage-sync-speed")]
#[command(about = "Coffee Pie Storage Sync Speed Benchmark", long_about = None)]
struct Cli {
    /// Directory for temp test files (uses SSD by default)
    #[arg(short, long, default_value = "/tmp")]
    dir: PathBuf,

    /// Test file size in MB
    #[arg(short, long, default_value = "1024")]
    size_mb: u64,

    /// Simulated network bandwidth in Mbps (0 = no network cap, disk-only)
    #[arg(short, long, default_value = "0")]
    bandwidth_mbps: u64,

    /// Number of test iterations
    #[arg(short, long, default_value = "3")]
    iterations: u32,

    /// JSON output
    #[arg(long)]
    json: bool,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie Storage Sync Speed Benchmark");
        println!("========================================");
        println!("Test dir: {}", cli.dir.display());
        println!("File size: {} MB", cli.size_mb);
        if cli.bandwidth_mbps > 0 {
            println!("Network cap: {} Mbps (simulated)", cli.bandwidth_mbps);
        } else {
            println!("Network cap: none (raw disk I/O)");
        }
        println!("Iterations: {}", cli.iterations);
        println!();
    }

    // Create test directory
    let test_dir = cli.dir.join("coffeepie_bench");
    fs::create_dir_all(&test_dir).expect("Failed to create test directory");

    let file_path = test_dir.join("sync_test.bin");
    let size_bytes = (cli.size_mb * 1024 * 1024) as usize;

    // --- Write test ---
    let mut write_speeds = Vec::new();
    if !cli.json { println!("--- Write Test (Cloud VM → Local Disk) ---"); }
    for i in 1..=cli.iterations {
        let mut data = vec![0u8; size_bytes];
        rand::thread_rng().fill_bytes(&mut data);

        let start = Instant::now();
        let mut f = fs::File::create(&file_path).expect("Failed to create file");
        f.write_all(&data).expect("Write failed");
        f.sync_all().expect("fsync failed");
        let elapsed = start.elapsed();

        let speed_mbps = (size_bytes as f64 / elapsed.as_secs_f64()) * 8.0 / 1_000_000.0;
        write_speeds.push(speed_mbps);

        if !cli.json {
            println!("  Run {}/{}: {:.2} MB/s ({:.2} Mbps) — {:.2}s",
                i, cli.iterations, speed_mbps / 8.0, speed_mbps, elapsed.as_secs_f64());
        }
    }
    let avg_write = write_speeds.iter().sum::<f64>() / write_speeds.len() as f64;

    // Remove file between tests to avoid caching effects
    let _ = fs::remove_file(&file_path);

    // --- Read test ---
    let mut read_speeds = Vec::new();
    // Pre-create file for read test
    {
        let mut data = vec![0u8; size_bytes];
        rand::thread_rng().fill_bytes(&mut data);
        let mut f = fs::File::create(&file_path).expect("Failed to create read test file");
        f.write_all(&data).expect("Write failed");
        f.sync_all().expect("fsync failed");
    }

    if !cli.json { println!(); println!("--- Read Test (Local Disk → Memory) ---"); }
    for i in 1..=cli.iterations {
        let mut buf = vec![0u8; size_bytes];
        let start = Instant::now();
        let mut f = fs::File::open(&file_path).expect("Failed to open file");
        f.read_exact(&mut buf).expect("Read failed");
        let elapsed = start.elapsed();

        let speed_mbps = (size_bytes as f64 / elapsed.as_secs_f64()) * 8.0 / 1_000_000.0;
        read_speeds.push(speed_mbps);

        if !cli.json {
            println!("  Run {}/{}: {:.2} MB/s ({:.2} Mbps) — {:.2}s",
                i, cli.iterations, speed_mbps / 8.0, speed_mbps, elapsed.as_secs_f64());
        }
    }
    let avg_read = read_speeds.iter().sum::<f64>() / read_speeds.len() as f64;

    // --- Random I/O test (simulates many small files like a project sync) ---
    if !cli.json { println!(); println!("--- Random I/O Test (Simulating multi-file project sync) ---"); }

    let small_file_size = 1024 * 1024; // 1 MB per file
    let num_files = std::cmp::min(100, (size_bytes / small_file_size) as usize);
    let mut rand_io_speeds = Vec::new();

    for i in 1..=cli.iterations {
        let start = Instant::now();
        let mut total = 0u64;
        for j in 0..num_files {
            let path = test_dir.join(format!("rand_{:04}.bin", j));
            let data = vec![0u8; small_file_size];
            let mut f = fs::File::create(&path).expect("Failed");
            f.write_all(&data).expect("Write failed");
            total += small_file_size as u64;
        }
        // Read them back
        for j in 0..num_files {
            let path = test_dir.join(format!("rand_{:04}.bin", j));
            let mut f = fs::File::open(&path).expect("Failed");
            let mut buf = vec![0u8; small_file_size];
            f.read_exact(&mut buf).expect("Read failed");
            total += small_file_size as u64;
        }
        let elapsed = start.elapsed();
        let speed_mbps = (total as f64 / elapsed.as_secs_f64()) * 8.0 / 1_000_000.0;
        rand_io_speeds.push(speed_mbps);

        if !cli.json {
            println!("  Run {}/{}: {} files, {:.2} MB/s ({:.2} Mbps) — {:.2}s",
                i, cli.iterations, num_files * 2, speed_mbps / 8.0, speed_mbps, elapsed.as_secs_f64());
        }

        // Cleanup
        for j in 0..num_files {
            let _ = fs::remove_file(test_dir.join(format!("rand_{:04}.bin", j)));
        }
    }
    let avg_rand_io = rand_io_speeds.iter().sum::<f64>() / rand_io_speeds.len() as f64;

    // --- Effective sync speed (bottlenecked by network) ---
    let effective_mbps = if cli.bandwidth_mbps > 0 {
        cli.bandwidth_mbps as f64
    } else {
        // Bottleneck is the slower of write or read
        avg_write.min(avg_read)
    };

    // Cleanup
    let _ = fs::remove_file(&file_path);
    let _ = fs::remove_dir_all(&test_dir);

    if cli.json {
        let result = serde_json::json!({
            "test_dir": cli.dir.to_string_lossy(),
            "size_mb": cli.size_mb,
            "bandwidth_mbps_simulated": cli.bandwidth_mbps,
            "write_mbps": format!("{:.1}", avg_write),
            "read_mbps": format!("{:.1}", avg_read),
            "random_io_mbps": format!("{:.1}", avg_rand_io),
            "effective_mbps": format!("{:.1}", effective_mbps),
            "sync_estimates": {
                "1_GB_document": format_duration(1_000.0 / effective_mbps, effective_mbps),
                "10_GB_project": format_duration(10_000.0 / effective_mbps, effective_mbps),
                "100_GB_backup": format_duration(100_000.0 / effective_mbps, effective_mbps),
                "1_TB_full_sync": format_duration(1_000_000.0 / effective_mbps, effective_mbps),
            }
        });
        println!("{}", serde_json::to_string_pretty(&result).unwrap());
    } else {
        println!();
        println!("--- Summary ---");
        println!("  Avg Write Speed:  {:.1} Mbps ({:.1} MB/s)", avg_write, avg_write / 8.0);
        println!("  Avg Read Speed:   {:.1} Mbps ({:.1} MB/s)", avg_read, avg_read / 8.0);
        println!("  Avg Random I/O:   {:.1} Mbps ({:.1} MB/s)", avg_rand_io, avg_rand_io / 8.0);
        println!("  Effective Speed:  {:.1} Mbps ({:.1} MB/s)",
            effective_mbps, effective_mbps / 8.0);
        if cli.bandwidth_mbps > 0 {
            println!("  (Network-capped at {} Mbps)", cli.bandwidth_mbps);
        }
        println!();
        println!("--- Estimated Sync Times (at effective speed) ---");
        let scenarios = [
            ("1 GB document/project", 1_000.0),
            ("10 GB media project", 10_000.0),
            ("100 GB backup/archive", 100_000.0),
            ("1 TB full system sync", 1_000_000.0),
        ];
        for (label, size_mb) in &scenarios {
            let seconds = size_mb / (effective_mbps / 8.0); // MB / (MB/s)
            println!("  {: <25}: {}", label, format_duration(seconds, effective_mbps));
        }
    }
}

fn format_duration(seconds: f64, _mbps: f64) -> String {
    if seconds < 1.0 {
        format!("{:.0}ms", seconds * 1000.0)
    } else if seconds < 60.0 {
        format!("{:.1}s", seconds)
    } else if seconds < 3600.0 {
        let mins = (seconds / 60.0) as u64;
        let secs = (seconds % 60.0) as u64;
        format!("{}m {}s", mins, secs)
    } else {
        let hrs = (seconds / 3600.0) as u64;
        let mins = ((seconds % 3600.0) / 60.0) as u64;
        format!("{}h {}m", hrs, mins)
    }
}
