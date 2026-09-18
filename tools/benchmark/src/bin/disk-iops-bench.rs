// Coffee Pie Disk IOPS Benchmark
// Measures random read/write IOPS and sequential throughput
// for VM storage provisioning. Helps determine how many
// simultaneous VM instances a storage subsystem can support.
//
// Each Coffee Pie slice has 8 GB SSD. IOPS requirements:
//   Light (office): ~50 IOPS | Medium (dev): ~200 IOPS | Heavy (gaming): ~500+ IOPS

use clap::Parser;
use std::fs;
use std::io::{Read, Write, Seek, SeekFrom};
use std::path::PathBuf;
use std::time::Instant;
use rand::Rng;

#[derive(Parser)]
#[command(name = "disk-iops-bench")]
#[command(about = "Coffee Pie Disk IOPS & Throughput Benchmark", long_about = None)]
struct Cli {
    /// Directory for test files
    #[arg(short, long, default_value = "/tmp")]
    dir: PathBuf,

    /// Test file size in MB
    #[arg(short, long, default_value = "1024")]
    size_mb: u64,

    /// Block size for random I/O in KB
    #[arg(long, default_value = "4")]
    block_kb: usize,

    /// Number of random I/O operations
    #[arg(long, default_value = "10000")]
    io_count: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie Disk IOPS Benchmark");
        println!("================================");
        println!("Test dir: {}", cli.dir.display());
        println!("File size: {} MB | Block: {} KB | I/O ops: {}",
            cli.size_mb, cli.block_kb, cli.io_count);
        println!();
    }

    let test_dir = cli.dir.join("coffeepie_disk_bench");
    fs::create_dir_all(&test_dir).expect("Failed to create test dir");
    let file_path = test_dir.join("iops_test.bin");
    let size_bytes = (cli.size_mb * 1024 * 1024) as usize;
    let block_bytes = cli.block_kb * 1024;

    // Create and pre-fill test file
    if !cli.json { println!("Preparing test file ({} MB)...", cli.size_mb); }
    {
        let mut f = fs::File::create(&file_path).expect("Failed to create file");
        // Write in chunks to avoid huge allocation
        let chunk = vec![0x5Au8; 64 * 1024]; // 64KB chunks
        let mut remaining = size_bytes;
        while remaining > 0 {
            let to_write = std::cmp::min(chunk.len(), remaining);
            f.write_all(&chunk[..to_write]).expect("Write failed");
            remaining -= to_write;
        }
        f.sync_all().expect("fsync failed");
    }

    // --- Sequential Read ---
    if !cli.json { println!("[1/4] Sequential Read..."); }
    {
        let mut f = fs::File::open(&file_path).expect("Failed to open");
        let mut buf = vec![0u8; 256 * 1024]; // 256KB read buffer
        let start = Instant::now();
        let mut total = 0u64;
        loop {
            match f.read(&mut buf) {
                Ok(0) => break,
                Ok(n) => total += n as u64,
                Err(e) => { eprintln!("Read error: {}", e); break; }
            }
        }
        let elapsed = start.elapsed().as_secs_f64();
        let mbps = (total as f64 / elapsed) / 1_000_000.0;
        if !cli.json { println!("       {:.1} MB/s ({:.1} Mbps)", mbps, mbps * 8.0); }
    }

    // --- Sequential Write ---
    if !cli.json { println!("[2/4] Sequential Write..."); }
    {
        let mut f = fs::File::create(file_path.with_extension("seq_write.bin"))
            .expect("Failed to create");
        let buf = vec![0xA5u8; 256 * 1024];
        let start = Instant::now();
        let mut total = 0u64;
        while total < size_bytes as u64 {
            let to_write = std::cmp::min(buf.len(), (size_bytes as u64 - total) as usize);
            f.write_all(&buf[..to_write]).expect("Write failed");
            total += to_write as u64;
        }
        f.sync_all().expect("fsync failed");
        let elapsed = start.elapsed().as_secs_f64();
        let mbps = (total as f64 / elapsed) / 1_000_000.0;
        if !cli.json { println!("       {:.1} MB/s ({:.1} Mbps)", mbps, mbps * 8.0); }
        let _ = fs::remove_file(file_path.with_extension("seq_write.bin"));
    }

    // --- Random Read IOPS ---
    if !cli.json { println!("[3/4] Random Read IOPS ({}KB blocks)...", cli.block_kb); }
    let rand_read_iops = {
        let mut f = fs::File::open(&file_path).expect("Failed to open");
        let max_block = (size_bytes / block_bytes) as u64;
        let mut rng = rand::thread_rng();
        let mut buf = vec![0u8; block_bytes];
        let start = Instant::now();
        for _ in 0..cli.io_count {
            let offset = (rng.gen::<u64>() % max_block) * block_bytes as u64;
            f.seek(SeekFrom::Start(offset)).expect("Seek failed");
            let _ = f.read_exact(&mut buf);
        }
        let elapsed = start.elapsed().as_secs_f64();
        let iops = cli.io_count as f64 / elapsed;
        if !cli.json { println!("       {:.0} IOPS", iops); }
        iops
    };

    // --- Random Write IOPS ---
    if !cli.json { println!("[4/4] Random Write IOPS ({}KB blocks)...", cli.block_kb); }
    let rand_write_iops = {
        let mut f = fs::OpenOptions::new()
            .read(true).write(true)
            .open(&file_path)
            .expect("Failed to open for write");
        let max_block = (size_bytes / block_bytes) as u64;
        let mut rng = rand::thread_rng();
        let buf = vec![0xCCu8; block_bytes];
        let start = Instant::now();
        for _ in 0..cli.io_count {
            let offset = (rng.gen::<u64>() % max_block) * block_bytes as u64;
            f.seek(SeekFrom::Start(offset)).expect("Seek failed");
            f.write_all(&buf).expect("Write failed");
        }
        f.sync_all().expect("fsync failed");
        let elapsed = start.elapsed().as_secs_f64();
        let iops = cli.io_count as f64 / elapsed;
        if !cli.json { println!("       {:.0} IOPS", iops); }
        iops
    };

    // Cleanup
    let _ = fs::remove_file(&file_path);
    let _ = fs::remove_dir_all(&test_dir);

    // VM capacity estimates
    let light_vms = (rand_read_iops.min(rand_write_iops) / 50.0) as u64;
    let medium_vms = (rand_read_iops.min(rand_write_iops) / 200.0) as u64;
    let heavy_vms = (rand_read_iops.min(rand_write_iops) / 500.0) as u64;

    if cli.json {
        println!("{}", serde_json::json!({
            "random_read_iops": format!("{:.0}", rand_read_iops),
            "random_write_iops": format!("{:.0}", rand_write_iops),
            "estimated_vm_capacity": {
                "light_office_50_iops": light_vms,
                "medium_dev_200_iops": medium_vms,
                "heavy_gaming_500_iops": heavy_vms,
            }
        }));
    } else {
        println!();
        println!("--- Summary ---");
        println!("  Random Read:  {:.0} IOPS", rand_read_iops);
        println!("  Random Write: {:.0} IOPS", rand_write_iops);
        println!();
        println!("--- Estimated Simultaneous VMs (disk I/O limited) ---");
        println!("  Light (office, 50 IOPS):    {}", light_vms);
        println!("  Medium (dev, 200 IOPS):     {}", medium_vms);
        println!("  Heavy (gaming, 500+ IOPS):  {}", heavy_vms);
        println!();
        println!("Note: Each slice = 8 GB SSD. Multiply by slices per VM.");
        println!("  Standard VM (4 slices = 32 GB): {} light / {} medium / {} heavy",
            light_vms / 4, medium_vms / 4, heavy_vms / 4);
    }
}
