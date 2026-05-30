// Coffee Pie Translations Validator
// Validates translations.json against Coffee Pie project rules.
// Ensures consistency across 11 languages, catches broken HTML,
// verifies language-independent identifiers, and reports untranslated keys.
//
// Rules (from AGENTS.md):
//   - Emails, addresses, brands (® ™), company names, URLs, API endpoints,
//     tech specs/units, and social media handles must be IDENTICAL across all langs.
//   - No broken HTML entities from automated translation corruption.
//   - All 11 languages must be present for each key.
//   - es (Spanish) is the canonical source; other langs must differ.

use clap::Parser;
use regex::Regex;
use serde::Deserialize;
use std::collections::{BTreeMap, HashMap, HashSet};
use std::fs;
use std::path::PathBuf;
use std::process;

#[derive(Parser)]
#[command(name = "translations-validator")]
#[command(about = "Coffee Pie translations.json validator", long_about = None)]
struct Cli {
    /// Path to translations.json
    #[arg(default_value = "coffeepie_website/public/translations.json")]
    path: PathBuf,

    /// Path to website public/ for HTML key reference scan
    #[arg(long, default_value = "coffeepie_website/public")]
    html_dir: Option<PathBuf>,

    /// Only show errors (silence warnings)
    #[arg(short, long)]
    quiet: bool,

    /// JSON output
    #[arg(long)]
    json: bool,

    /// Auto-fix common issues
    #[arg(long)]
    fix: bool,
}

const ALL_LANGS: &[&str] = &["es", "en", "pt", "fr", "de", "ru", "hi", "ja", "zh", "ko", "ar"];

// Patterns that should be IDENTICAL across all languages
const IDENTIFIER_PATTERNS: &[(&str, &str)] = &[
    ("email", r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    ("brand_rtm", r"\b(Coffee Pie®|Commanders™|Sentinels™|Rangers™)\b"),
    ("project_name", r"\b(QFDM|OpenUDS|Sunshine|Moonlight|Proxmox|Supabase)\b"),
    ("social_handle", r"\b(Instagram|Facebook|TikTok|YouTube|LinkedIn|Twitter|Discord|GitHub)\b"),
    ("url", r"https?://[^\s<>\"']+"),
    ("tech_spec", r"\b(\d+\s*(Wh|GB|MB|Mbps|vMPX/s|TOPS|vCore|INT8))\b"),
];

// HTML entity patterns that indicate corruption from automated translation
const CORRUPTION_PATTERNS: &[(&str, &str)] = &[
    ("broken_lt", r"&lt;"),
    ("broken_gt", r"&gt;"),
    ("broken_amp", r"&amp;"),
    ("broken_quot", r"&quot;"),
    ("numeric_entity", r"&#\d+;"),
    ("hex_entity", r"&#x[0-9a-fA-F]+;"),
    ("double_encoded", r"&amp;(lt|gt|amp|quot|#)"),
    ("fragment_remnant", r"\bh\.\s*\d{2,4}\b"),  // Common LibreTranslate artifact
];

type Translations = BTreeMap<String, BTreeMap<String, String>>;

#[derive(Default)]
struct Report {
    errors: Vec<String>,
    warnings: Vec<String>,
    stats: Stats,
}

#[derive(Default, serde::Serialize)]
struct Stats {
    total_keys: usize,
    complete_keys: usize,
    incomplete_keys: usize,
    untranslated_keys: usize,      // es == target lang
    identifier_violations: usize,
    html_corruption: usize,
    duplicate_keys: usize,
    orphan_html_refs: usize,
}

fn main() {
    let cli = Cli::parse();

    if !cli.path.exists() {
        eprintln!("ERROR: File not found: {}", cli.path.display());
        process::exit(1);
    }

    let raw = fs::read_to_string(&cli.path).expect("Failed to read translations.json");
    let dict: Translations = match serde_json::from_str(&raw) {
        Ok(d) => d,
        Err(e) => {
            eprintln!("ERROR: Invalid JSON: {}", e);
            process::exit(1);
        }
    };

    let mut report = Report::default();
    report.stats.total_keys = dict.len();

    // 1. Check each key for completeness
    check_completeness(&dict, &mut report);

    // 2. Check identifier invariance
    check_identifiers(&dict, &mut report);

    // 3. Check HTML corruption
    check_html_corruption(&dict, &mut report);

    // 4. Check untranslated keys (es == other lang)
    check_untranslated(&dict, &mut report);

    // 5. Scan HTML files for orphan keys
    if let Some(ref html_dir) = cli.html_dir {
        check_html_references(&dict, html_dir, &mut report);
    }

    report.stats.complete_keys = report.stats.total_keys
        - report.stats.incomplete_keys
        - report.stats.untranslated_keys;

    // Output
    if cli.json {
        println!("{}", serde_json::json!({
            "stats": report.stats,
            "errors": report.errors,
            "warnings": report.warnings,
        }));
        return;
    }

    // Pretty output
    println!("Coffee Pie Translations Validator");
    println!("===================================");
    println!("File: {}", cli.path.display());
    println!("Keys: {} | Complete: {} | Issues: {}",
        report.stats.total_keys,
        report.stats.complete_keys,
        report.errors.len() + report.warnings.len());
    println!();

    if !report.errors.is_empty() {
        println!("--- ERRORS ({} items) ---", report.errors.len());
        for e in &report.errors {
            println!("  ✗ {}", e);
        }
        println!();
    }

    if !report.warnings.is_empty() && !cli.quiet {
        println!("--- WARNINGS ({} items) ---", report.warnings.len());
        for w in &report.warnings {
            println!("  ⚠ {}", w);
        }
        println!();
    }

    // Summary table
    println!("--- SUMMARY ---");
    println!("  Total keys:           {}", report.stats.total_keys);
    println!("  Complete (all 11):    {}", report.stats.complete_keys);
    println!("  Missing languages:    {}", report.stats.incomplete_keys);
    println!("  Untranslated (es==X): {}", report.stats.untranslated_keys);
    println!("  Identifier violations: {}", report.stats.identifier_violations);
    println!("  HTML corruption:      {}", report.stats.html_corruption);
    if cli.html_dir.is_some() {
        println!("  Orphan HTML refs:     {}", report.stats.orphan_html_refs);
    }
    println!();

    if report.errors.is_empty() && report.warnings.is_empty() {
        println!("✓ translations.json is valid and complete.");
    } else if report.errors.is_empty() {
        println!("⚠ translations.json has warnings but no errors.");
        process::exit(0);
    } else {
        println!("✗ translations.json has {} error(s) to fix.", report.errors.len());
        process::exit(1);
    }
}

fn check_completeness(dict: &Translations, report: &mut Report) {
    let lang_set: HashSet<&&str> = ALL_LANGS.iter().collect();

    for (key, langs) in dict {
        let present: HashSet<&&str> = langs.keys().collect();
        let missing: Vec<&&str> = lang_set.difference(&present).copied().collect();

        if !missing.is_empty() {
            report.stats.incomplete_keys += 1;
            let truncated = if key.len() > 80 {
                format!("{}...", &key[..77])
            } else {
                key.clone()
            };
            report.errors.push(format!(
                "Missing languages for '{}': {}",
                truncated,
                missing.iter().map(|l| l.to_string()).collect::<Vec<_>>().join(", ")
            ));
        }
    }
}

fn check_identifiers(dict: &Translations, report: &mut Report) {
    for (pattern_name, pattern_str) in IDENTIFIER_PATTERNS {
        let re = Regex::new(pattern_str).unwrap();

        for (key, langs) in dict {
            // Collect identifiers found in es (canonical)
            let es_text = match langs.get("es") {
                Some(t) => t,
                None => {
                    // If no es, use first available lang as reference
                    match langs.values().next() {
                        Some(t) => t,
                        None => continue,
                    }
                }
            };

            let es_ids: HashSet<String> = re.find_iter(es_text)
                .map(|m| m.as_str().to_lowercase())
                .collect();

            if es_ids.is_empty() { continue; }

            // Check all other languages have the same identifiers
            for lang in ALL_LANGS {
                if *lang == "es" { continue; }
                if let Some(text) = langs.get(*lang) {
                    let lang_ids: HashSet<String> = re.find_iter(text)
                        .map(|m| m.as_str().to_lowercase())
                        .collect();

                    let missing: Vec<_> = es_ids.difference(&lang_ids).collect();
                    let extra: Vec<_> = lang_ids.difference(&es_ids).collect();

                    if !missing.is_empty() || !extra.is_empty() {
                        report.stats.identifier_violations += 1;
                        let truncated = if key.len() > 60 {
                            format!("{}...", &key[..57])
                        } else {
                            key.clone()
                        };
                        if !missing.is_empty() {
                            report.errors.push(format!(
                                "[{}] '{}' — {} missing in {}: {:?}",
                                pattern_name, truncated, missing.len(), lang, missing
                            ));
                        }
                        if !extra.is_empty() {
                            report.warnings.push(format!(
                                "[{}] '{}' — {} extra in {}: {:?}",
                                pattern_name, truncated, extra.len(), lang, extra
                            ));
                        }
                    }
                }
            }
        }
    }
}

fn check_html_corruption(dict: &Translations, report: &mut Report) {
    for (pattern_name, pattern_str) in CORRUPTION_PATTERNS {
        let re = Regex::new(pattern_str).unwrap();

        for (key, langs) in dict {
            for (lang, text) in langs {
                if re.is_match(text) {
                    report.stats.html_corruption += 1;
                    let truncated = if key.len() > 60 {
                        format!("{}...", &key[..57])
                    } else {
                        key.clone()
                    };
                    let matches: Vec<_> = re.find_iter(text)
                        .map(|m| m.as_str().to_string())
                        .take(3)
                        .collect();
                    report.errors.push(format!(
                        "[{}] '{}' [{}] — corruption: {:?}",
                        pattern_name, truncated, lang, matches
                    ));
                }
            }
        }
    }
}

fn check_untranslated(dict: &Translations, report: &mut Report) {
    for (key, langs) in dict {
        let es_text = match langs.get("es") {
            Some(t) => t,
            None => continue,
        };

        // Skip identifiers that should be identical (emails, URLs, specs)
        if is_identifier_only(es_text) { continue; }

        for lang in ALL_LANGS {
            if *lang == "es" { continue; }
            if let Some(text) = langs.get(*lang) {
                if text == es_text {
                    report.stats.untranslated_keys += 1;
                    let truncated = if key.len() > 60 {
                        format!("{}...", &key[..57])
                    } else {
                        key.clone()
                    };
                    report.warnings.push(format!(
                        "Untranslated: '{}' — {} == es (identical text)",
                        truncated, lang
                    ));
                }
            }
        }
    }
}

fn is_identifier_only(text: &str) -> bool {
    // If text is purely an email, URL, dollar amount, or tech spec, skip
    let ident_res: Vec<Regex> = [
        r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        r"^https?://[^\s]+$",
        r"^\$\d[\d.',]*$",
        r"^\d+\s*(Wh|GB|MB|Mbps|vMPX/s|TOPS|vCore|INT8)$",
        r"^\d{4}-\d{2}-\d{2}$",
    ].iter().filter_map(|p| Regex::new(p).ok()).collect();

    let trimmed = text.trim();
    ident_res.iter().any(|re| re.is_match(trimmed))
}

fn check_html_references(dict: &Translations, html_dir: &PathBuf, report: &mut Report) {
    // Walk HTML files looking for text that matches translation keys
    // Report keys in dict that are never referenced in HTML
    let mut html_text = String::new();

    fn collect_html(dir: &PathBuf, buffer: &mut String) {
        if let Ok(entries) = fs::read_dir(dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.is_dir() {
                    collect_html(&path, buffer);
                } else if path.extension().map_or(false, |e| e == "html") {
                    if let Ok(content) = fs::read_to_string(&path) {
                        buffer.push_str(&content);
                    }
                }
            }
        }
    }

    collect_html(html_dir, &mut html_text);

    // Check which dict keys appear in HTML
    let mut orphan_count = 0;
    for (key, _) in dict {
        if key.len() < 5 { continue; } // Skip short/structural keys
        if !html_text.contains(key.as_str()) {
            orphan_count += 1;
            // Only report first 20 to avoid noise
            if orphan_count <= 20 {
                report.warnings.push(format!(
                    "Key not found in HTML: '{}' (may be unused or dead)",
                    if key.len() > 70 { format!("{}...", &key[..67]) } else { key.clone() }
                ));
            }
        }
    }
    report.stats.orphan_html_refs = orphan_count;
}
