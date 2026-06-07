// Coffee Pie Product Sync
// Syncs Avo store product pages with products.json data file.
//
// Reads product HTML pages from products/ directory, extracts metadata,
// compares with existing products.json, and reports changes.
//
// Usage:
//   product-sync                          # Dry-run: show what would change
//   product-sync --apply                  # Apply changes to products.json
//   product-sync --json                   # JSON diff output

use clap::Parser;
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "product-sync")]
#[command(about = "Coffee Pie Product Catalog Sync — Avo ↔ products.json", long_about = None)]
struct Cli {
    /// Product pages directory
    #[arg(long, default_value = "coffeepie_website/public/products")]
    pages_dir: PathBuf,

    /// products.json path
    #[arg(long, default_value = "coffeepie_website/public/data/products.json")]
    data_file: PathBuf,

    /// Apply changes (writes to products.json)
    #[arg(long)]
    apply: bool,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Show verbose per-product details
    #[arg(short, long)]
    verbose: bool,
}

#[derive(Debug, Serialize, Deserialize, Clone)]
struct Product {
    slug: String,
    name: String,
    image: String,
    price: String,
    url: String,
    category: String,
}

#[derive(Debug, Serialize)]
struct SyncReport {
    total_in_data: usize,
    total_in_pages: usize,
    added: Vec<Product>,
    removed: Vec<Product>,
    updated: Vec<ProductChange>,
    unchanged: usize,
}

#[derive(Debug, Serialize)]
struct ProductChange {
    slug: String,
    name: String,
    field: String,
    old_value: String,
    new_value: String,
}

fn main() {
    let cli = Cli::parse();

    if !cli.json {
        println!("Coffee Pie Product Catalog Sync");
        println!("===============================");
        println!("Pages: {}", cli.pages_dir.display());
        println!("Data:  {}", cli.data_file.display());
        println!();
    }

    // Read existing data
    let existing: Vec<Product> = if cli.data_file.exists() {
        let raw = fs::read_to_string(&cli.data_file).expect("Failed to read products.json");
        serde_json::from_str(&raw).unwrap_or_default()
    } else {
        Vec::new()
    };

    let existing_map: HashMap<String, &Product> = existing.iter()
        .map(|p| (p.slug.clone(), p))
        .collect();

    // Scan product pages
    let scraped = scrape_pages(&cli.pages_dir);
    let scraped_map: HashMap<String, &Product> = scraped.iter()
        .map(|p| (p.slug.clone(), p))
        .collect();

    // Diff
    let mut added = Vec::new();
    let mut removed = Vec::new();
    let mut updated = Vec::new();
    let mut unchanged = 0u32;

    // Find added: in pages but not in data
    for (slug, product) in &scraped_map {
        if !existing_map.contains_key(slug) {
            added.push((*product).clone());
        }
    }

    // Find removed: in data but not in pages
    for (slug, product) in &existing_map {
        if !scraped_map.contains_key(slug) {
            removed.push((*product).clone());
        }
    }

    // Find updated: in both but different
    for (slug, scraped_product) in &scraped_map {
        if let Some(existing_product) = existing_map.get(slug) {
            let mut changes = Vec::new();
            if scraped_product.name != existing_product.name {
                changes.push(ProductChange {
                    slug: slug.clone(), name: scraped_product.name.clone(),
                    field: "name".into(), old_value: existing_product.name.clone(),
                    new_value: scraped_product.name.clone(),
                });
            }
            if scraped_product.price != existing_product.price {
                changes.push(ProductChange {
                    slug: slug.clone(), name: scraped_product.name.clone(),
                    field: "price".into(), old_value: existing_product.price.clone(),
                    new_value: scraped_product.price.clone(),
                });
            }
            if scraped_product.image != existing_product.image {
                changes.push(ProductChange {
                    slug: slug.clone(), name: scraped_product.name.clone(),
                    field: "image".into(), old_value: existing_product.image.clone(),
                    new_value: scraped_product.image.clone(),
                });
            }

            if changes.is_empty() {
                unchanged += 1;
            } else {
                updated.extend(changes);
            }
        }
    }

    let report = SyncReport {
        total_in_data: existing.len(),
        total_in_pages: scraped.len(),
        added, removed, updated, unchanged,
    };

    // Output
    if cli.json {
        println!("{}", serde_json::to_string_pretty(&report).unwrap());
    } else {
        println!("Products in data:  {}", report.total_in_data);
        println!("Products in pages: {}", report.total_in_pages);
        println!("Unchanged:         {}", report.unchanged);
        println!("Added:             {}", report.added.len());
        println!("Removed:           {}", report.removed.len());
        println!("Updated:           {}", report.updated.len());
        println!();

        if !report.added.is_empty() {
            println!("--- ADDED ---");
            for p in &report.added {
                println!("  + {} ({} — {})", p.name, p.category, p.price);
            }
            println!();
        }

        if !report.removed.is_empty() {
            println!("--- REMOVED (page deleted but still in data) ---");
            for p in &report.removed {
                println!("  - {} ({})", p.name, p.slug);
            }
            println!();
        }

        if !report.updated.is_empty() {
            println!("--- UPDATED ---");
            for c in &report.updated {
                println!("  ~ {} [{}]: '{}' → '{}'", c.name, c.field, c.old_value, c.new_value);
            }
            println!();
        }

        if report.added.is_empty() && report.removed.is_empty() && report.updated.is_empty() {
            println!("✓ products.json is in sync with product pages.");
        }
    }

    // Apply
    if cli.apply {
        if !cli.json { println!("Applying changes..."); }
        let mut merged: Vec<Product> = existing.clone();

        // Remove deleted
        merged.retain(|p| scraped_map.contains_key(&p.slug));

        // Update existing
        for p in &mut merged {
            if let Some(scraped) = scraped_map.get(&p.slug) {
                p.name = scraped.name.clone();
                p.price = scraped.price.clone();
                p.image = scraped.image.clone();
                p.url = scraped.url.clone();
            }
        }

        // Add new
        for p in &report.added {
            merged.push(p.clone());
        }

        // Sort by category then name
        merged.sort_by(|a, b| a.category.cmp(&b.category).then(a.name.cmp(&b.name)));

        let json_str = serde_json::to_string_pretty(&merged).unwrap();
        fs::write(&cli.data_file, json_str).expect("Failed to write products.json");

        if !cli.json {
            println!("✓ products.json updated ({} products).", merged.len());
        }
    } else if !cli.json && !report.added.is_empty() {
        println!("Run with --apply to write changes to products.json");
    }
}

fn scrape_pages(dir: &PathBuf) -> Vec<Product> {
    let mut products = Vec::new();

    if !dir.exists() {
        eprintln!("Product pages directory not found: {}", dir.display());
        return products;
    }

    let entries = match fs::read_dir(dir) {
        Ok(e) => e,
        Err(_) => return products,
    };

    for entry in entries.flatten() {
        let path = entry.path();
        if path.extension().map_or(true, |e| e != "html") { continue; }

        let content = match fs::read_to_string(&path) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let slug = path.file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("unknown")
            .to_string();

        // Extract title
        let name = extract_meta(&content, "<title>", "| Coffee Pie")
            .unwrap_or_else(|| slug.replace('-', " "));

        // Extract price
        let price = extract_regex(&content, r"\$[\d.'\.,]+")
            .unwrap_or_else(|| "$0".into());

        // Extract image
        let image = extract_regex(&content, r#"https?://[^\s"']+\.(png|jpg|jpeg|webp)"#)
            .or_else(|| extract_regex(&content, r"/assets/[^\s"']+\.(png|jpg|jpeg)"))
            .unwrap_or_else(|| "/assets/avo/media/placeholder.png".into());

        // Determine category from slug prefix or path
        let category = categorize(&slug, &name);

        let url = format!("/products/{}", slug);

        products.push(Product {
            slug, name: name.trim().to_string(),
            image: image.trim().to_string(),
            price: price.trim().to_string(),
            url, category,
        });
    }

    products.sort_by(|a, b| a.slug.cmp(&b.slug));
    products
}

fn extract_meta(content: &str, tag: &str, suffix: &str) -> Option<String> {
    let start = content.find(tag)? + tag.len();
    let end = content[start..].find(suffix)?;
    Some(content[start..start + end].trim().to_string())
}

fn extract_regex(content: &str, pattern: &str) -> Option<String> {
    // Simple regex-like extraction without regex crate dependency
    let bytes = content.as_bytes();
    let mut results = Vec::new();

    // Look for $ followed by digits, dots, commas, apostrophes
    if pattern.contains('$') {
        for i in 0..bytes.len().saturating_sub(1) {
            if bytes[i] == b'$' {
                let mut j = i + 1;
                while j < bytes.len() && (bytes[j].is_ascii_digit() || bytes[j] == b'.' || bytes[j] == b',' || bytes[j] == b'\'') {
                    j += 1;
                }
                if j > i + 1 {
                    return Some(String::from_utf8_lossy(&bytes[i..j]).to_string());
                }
            }
        }
    }

    // Look for /assets/... image paths
    if pattern.contains("/assets/") {
        for i in 0..bytes.len().saturating_sub(8) {
            if &bytes[i..i+8] == b"/assets/" {
                let mut j = i + 8;
                while j < bytes.len() && bytes[j] != b'"' && bytes[j] != b'\'' && bytes[j] != b'>' && bytes[j] != b' ' {
                    j += 1;
                }
                let path = String::from_utf8_lossy(&bytes[i..j]).to_string();
                if path.ends_with(".png") || path.ends_with(".jpg") || path.ends_with(".jpeg") {
                    return Some(path);
                }
            }
        }
    }

    // Look for https://... image URLs
    if pattern.contains("https://") {
        for i in 0..bytes.len().saturating_sub(8) {
            if &bytes[i..i+8] == b"https://" {
                let mut j = i + 8;
                while j < bytes.len() && bytes[j] != b'"' && bytes[j] != b'\'' && bytes[j] != b'>' && bytes[j] != b' ' {
                    j += 1;
                }
                let url = String::from_utf8_lossy(&bytes[i..j]).to_string();
                if url.ends_with(".png") || url.ends_with(".jpg") || url.ends_with(".jpeg") || url.ends_with(".webp") {
                    return Some(url);
                }
            }
        }
    }

    None
}

fn categorize(slug: &str, name: &str) -> String {
    let lower = format!("{} {}", slug.to_lowercase(), name.to_lowercase());

    if lower.contains("commander") || lower.contains("sentinel") || lower.contains("ranger") || lower.contains("terminal-codec") {
        "commanders".into()
    } else if lower.contains("tecla") || lower.contains("suiche") || lower.contains("switch") || lower.contains("keycap") || lower.contains("estabilizador") {
        "teclas-suiches".into()
    } else if lower.contains("expansion") || lower.contains("expansión") || lower.contains("tarjeta") {
        "expansion".into()
    } else if lower.contains("adaptador") || lower.contains("adapter") || lower.contains("ethernet") || lower.contains("wifi") {
        "adaptadores".into()
    } else if lower.contains("modulo") || lower.contains("módulo") || lower.contains("module") || lower.contains("pad") {
        "modulos".into()
    } else if lower.contains("bateria") || lower.contains("battery") || lower.contains("cable") || lower.contains("accesorio") || lower.contains("sensor") {
        "accesorios".into()
    } else {
        "accesorios".into() // Default
    }
}
