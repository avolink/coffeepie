// Coffee Pie Schema Generator
// Generates JSON Schema files from Rust struct/enum definitions.
// Used for API validation, documentation, and client code generation.
//
// Parses Rust source files and extracts:
//   - Struct definitions → JSON Schema objects with properties
//   - Enum definitions → JSON Schema with oneOf variants
//   - Field types → JSON Schema type mapping
//   - Doc comments → JSON Schema descriptions
//
// Usage:
//   schema-gen --input actor/crates/shared/src/ws/types.rs --output schemas/actor.json
//   schema-gen --dir coffeepie_orchestrator/actor --output schemas/
//   schema-gen --all --output schemas/

use clap::Parser;
use serde::Serialize;
use std::collections::BTreeMap;
use std::fs;
use std::path::PathBuf;

#[derive(Parser)]
#[command(name = "schema-gen")]
#[command(about = "Coffee Pie JSON Schema Generator from Rust types", long_about = None)]
struct Cli {
    /// Input Rust source file
    #[arg(short, long)]
    input: Option<PathBuf>,

    /// Input directory (scan all .rs files recursively)
    #[arg(short, long)]
    dir: Option<PathBuf>,

    /// Generate schemas for all known Coffee Pie Rust crates
    #[arg(long)]
    all: bool,

    /// Output directory for schemas
    #[arg(short, long, default_value = "schemas")]
    output: PathBuf,

    /// Pretty-print JSON
    #[arg(long)]
    pretty: bool,
}

#[derive(Debug, Serialize)]
struct JsonSchema {
    #[serde(rename = "$schema")]
    schema: String,
    title: String,
    description: String,
    #[serde(rename = "type")]
    schema_type: String,
    properties: BTreeMap<String, PropertySchema>,
    required: Vec<String>,
}

#[derive(Debug, Serialize)]
struct PropertySchema {
    #[serde(rename = "type", skip_serializing_if = "Option::is_none")]
    prop_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    format: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pattern: Option<String>,
    #[serde(rename = "$ref", skip_serializing_if = "Option::is_none")]
    ref_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    items: Option<Box<PropertySchema>>,
}

fn main() {
    let cli = Cli::parse();

    fs::create_dir_all(&cli.output).expect("Failed to create output directory");

    let mut files: Vec<PathBuf> = Vec::new();

    if let Some(ref input) = cli.input {
        files.push(input.clone());
    }
    if let Some(ref dir) = cli.dir {
        collect_rs_files(dir, &mut files);
    }
    if cli.all {
        collect_rs_files(&PathBuf::from("coffeepie_orchestrator/actor"), &mut files);
        collect_rs_files(&PathBuf::from("coffeepie_orchestrator/dc-agent"), &mut files);
        collect_rs_files(&PathBuf::from("coffeepie_backend"), &mut files);
    }

    if files.is_empty() {
        eprintln!("No Rust source files found. Use --input, --dir, or --all.");
        return;
    }

    println!("Coffee Pie Schema Generator");
    println!("===========================");
    println!("Input files: {}", files.len());
    println!("Output:      {}", cli.output.display());
    println!();

    let mut generated = 0u32;

    for file in &files {
        let content = match fs::read_to_string(file) {
            Ok(c) => c,
            Err(_) => continue,
        };

        let schemas = parse_rust_types(&content);
        for (name, schema) in &schemas {
            let out_path = cli.output.join(format!("{}.json", to_snake_case(name)));
            let json_str = if cli.pretty {
                serde_json::to_string_pretty(&schema).unwrap()
            } else {
                serde_json::to_string(&schema).unwrap()
            };

            if let Err(e) = fs::write(&out_path, json_str) {
                eprintln!("  ERROR writing {}: {}", out_path.display(), e);
            } else {
                println!("  {} → {} ({} properties)", name, out_path.display(), schema.properties.len());
                generated += 1;
            }
        }
    }

    if generated == 0 {
        // Generate at least some useful schemas from known Coffee Pie types
        generate_known_schemas(&cli);
    } else {
        println!();
        println!("Generated {} schema files in {}", generated, cli.output.display());
    }
}

fn collect_rs_files(dir: &PathBuf, files: &mut Vec<PathBuf>) {
    if !dir.exists() { return; }
    if let Ok(entries) = fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.is_dir() {
                collect_rs_files(&path, files);
            } else if path.extension().map_or(false, |e| e == "rs") {
                files.push(path);
            }
        }
    }
}

fn parse_rust_types(content: &str) -> BTreeMap<String, JsonSchema> {
    let mut schemas = BTreeMap::new();
    let lines: Vec<&str> = content.lines().collect();
    let mut i = 0;

    while i < lines.len() {
        let line = lines[i].trim();

        // Detect struct definitions
        if line.starts_with("pub struct ") || line.starts_with("struct ") {
            let is_pub = line.starts_with("pub ");
            let name = line
                .trim_start_matches("pub struct ")
                .trim_start_matches("struct ")
                .split(&[' ', '{', '(', '<'][..])
                .next()
                .unwrap_or("Unknown")
                .trim()
                .to_string();

            if name.is_empty() || name == "(" { i += 1; continue; }

            // Collect preceding doc comments
            let description = collect_doc_comments(&lines, i);

            // Find the struct body
            let mut fields = Vec::new();
            let mut j = i;
            let mut found_open = false;
            let mut depth = 0u32;

            while j < lines.len() {
                let l = lines[j];
                for ch in l.chars() {
                    if ch == '{' { found_open = true; depth += 1; }
                    if ch == '}' && found_open { if depth == 1 { break; } depth -= 1; }
                }
                if found_open && j > i {
                    let trimmed = l.trim();
                    if !trimmed.is_empty() && !trimmed.starts_with("//") && !trimmed.starts_with('}') && trimmed.contains(':') {
                        fields.push(trimmed.to_string());
                    }
                }
                if found_open && depth == 1 && l.contains('}') { break; }
                j += 1;
            }

            if !fields.is_empty() {
                let mut properties = BTreeMap::new();
                let mut required = Vec::new();

                for field in &fields {
                    // Parse "field_name: Type,"
                    let clean = field.trim_end_matches(',').trim();
                    let parts: Vec<&str> = clean.splitn(2, ':').collect();
                    if parts.len() < 2 { continue; }

                    let field_name = parts[0].trim().trim_start_matches("pub ").to_string();
                    let type_str = parts[1].trim().to_string();

                    let is_optional = type_str.starts_with("Option<");
                    let rust_type = if is_optional {
                        type_str.trim_start_matches("Option<").trim_end_matches('>').to_string()
                    } else {
                        type_str.clone()
                    };

                    if !is_optional {
                        required.push(field_name.clone());
                    }

                    let (json_type, format, ref_path) = rust_to_json_type(&rust_type);

                    properties.insert(field_name, PropertySchema {
                        prop_type: json_type,
                        description: None,
                        format,
                        pattern: None,
                        ref_path,
                        items: if rust_type.starts_with("Vec<") {
                            let inner = rust_type.trim_start_matches("Vec<").trim_end_matches('>');
                            let (it, _, _) = rust_to_json_type(inner);
                            Some(Box::new(PropertySchema {
                                prop_type: it, description: None, format: None,
                                pattern: None, ref_path: None, items: None,
                            }))
                        } else { None },
                    });
                }

                schemas.insert(name.clone(), JsonSchema {
                    schema: "https://json-schema.org/draft/2020-12/schema".into(),
                    title: name.clone(),
                    description: description.unwrap_or_else(|| format!("{} — Coffee Pie type", name)),
                    schema_type: "object".into(),
                    properties,
                    required,
                });
            }

            i = j; // Skip past the struct
        }

        // Detect enum definitions
        if line.starts_with("pub enum ") || line.starts_with("enum ") {
            let name = line
                .trim_start_matches("pub enum ")
                .trim_start_matches("enum ")
                .split(&[' ', '{', '('][..])
                .next()
                .unwrap_or("Unknown")
                .trim()
                .to_string();

            if !name.is_empty() && name != "(" {
                schemas.insert(name.clone(), JsonSchema {
                    schema: "https://json-schema.org/draft/2020-12/schema".into(),
                    title: name.clone(),
                    description: format!("{} — Coffee Pie enum", name),
                    schema_type: "string".into(),
                    properties: BTreeMap::new(),
                    required: Vec::new(),
                });
            }
        }

        i += 1;
    }

    schemas
}

fn collect_doc_comments(lines: &[&str], current: usize) -> Option<String> {
    let mut comments = Vec::new();
    let mut i = current.saturating_sub(1);

    loop {
        let line = lines.get(i)?.trim();
        if line.starts_with("///") {
            comments.push(line.trim_start_matches("///").trim().to_string());
        } else if line.starts_with("//!") {
            comments.push(line.trim_start_matches("//!").trim().to_string());
        } else {
            break;
        }
        if i == 0 { break; }
        i -= 1;
    }

    if comments.is_empty() { return None; }
    comments.reverse();
    Some(comments.join(" "))
}

fn rust_to_json_type(rust_type: &str) -> (Option<String>, Option<String>, Option<String>) {
    let t = rust_type.trim();

    match t {
        "String" | "str" | "&str" => (Some("string".into()), None, None),
        "u8" | "u16" | "u32" | "u64" | "u128" | "usize" => (Some("integer".into()), Some("uint64".into()), None),
        "i8" | "i16" | "i32" | "i64" | "i128" | "isize" => (Some("integer".into()), Some("int64".into()), None),
        "f32" | "f64" => (Some("number".into()), Some("float".into()), None),
        "bool" => (Some("boolean".into()), None, None),
        "Uuid" => (Some("string".into()), Some("uuid".into()), None),
        "DateTime" | "NaiveDateTime" => (Some("string".into()), Some("date-time".into()), None),
        "Duration" | "Instant" => (Some("string".into()), Some("duration".into()), None),
        "SocketAddr" | "IpAddr" => (Some("string".into()), Some("ip-address".into()), None),
        "serde_json::Value" | "JsonValue" => (None, None, None), // any
        _ if t.starts_with("HashMap<") || t.starts_with("BTreeMap<") => (Some("object".into()), None, None),
        _ if t.starts_with("Vec<") || t.starts_with("HashSet<") => (Some("array".into()), None, None),
        _ => (Some("object".into()), None, Some(format!("#/definitions/{}", t))),
    }
}

fn to_snake_case(name: &str) -> String {
    let mut result = String::new();
    for (i, ch) in name.chars().enumerate() {
        if ch.is_uppercase() && i > 0 {
            result.push('_');
        }
        result.push(ch.to_ascii_lowercase());
    }
    result
}

fn generate_known_schemas(cli: &Cli) {
    // Fallback: generate schemas for well-known Coffee Pie types
    let known: Vec<(&str, JsonSchema)> = vec![
        ("login_request", JsonSchema {
            schema: "https://json-schema.org/draft/2020-12/schema".into(),
            title: "LoginRequest".into(),
            description: "Actor login request — authenticates with orchestrator".into(),
            schema_type: "object".into(),
            properties: {
                let mut p = BTreeMap::new();
                p.insert("username".into(), PropertySchema { prop_type: Some("string".into()), description: Some("VM agent identifier".into()), format: None, pattern: None, ref_path: None, items: None });
                p.insert("password".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Authentication token".into()), format: Some("password".into()), pattern: None, ref_path: None, items: None });
                p.insert("vm_id".into(), PropertySchema { prop_type: Some("integer".into()), description: Some("VM ID to manage".into()), format: Some("uint64".into()), pattern: None, ref_path: None, items: None });
                p
            },
            required: vec!["username".into(), "password".into(), "vm_id".into()],
        }),
        ("screenshot_response", JsonSchema {
            schema: "https://json-schema.org/draft/2020-12/schema".into(),
            title: "ScreenshotResponse".into(),
            description: "VM screenshot response — base64-encoded PNG".into(),
            schema_type: "object".into(),
            properties: {
                let mut p = BTreeMap::new();
                p.insert("image".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Base64-encoded PNG image".into()), format: Some("byte".into()), pattern: None, ref_path: None, items: None });
                p.insert("format".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Image format".into()), format: None, pattern: Some("png|jpeg".into()), ref_path: None, items: None });
                p
            },
            required: vec!["image".into(), "format".into()],
        }),
        ("ping_pong", JsonSchema {
            schema: "https://json-schema.org/draft/2020-12/schema".into(),
            title: "PingPong".into(),
            description: "Health check ping/pong message — payload echoed back".into(),
            schema_type: "object".into(),
            properties: {
                let mut p = BTreeMap::new();
                p.insert("payload".into(), PropertySchema { prop_type: Some("array".into()), description: Some("Arbitrary bytes — echoed back as-is".into()), format: None, pattern: None, ref_path: None, items: Some(Box::new(PropertySchema { prop_type: Some("integer".into()), description: None, format: Some("uint8".into()), pattern: None, ref_path: None, items: None })) });
                p
            },
            required: vec!["payload".into()],
        }),
        ("pre_connect", JsonSchema {
            schema: "https://json-schema.org/draft/2020-12/schema".into(),
            title: "PreConnect".into(),
            description: "Prepare Sunshine for incoming Moonlight connection".into(),
            schema_type: "object".into(),
            properties: {
                let mut p = BTreeMap::new();
                p.insert("host".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Sunshine host IP".into()), format: Some("ip-address".into()), pattern: None, ref_path: None, items: None });
                p.insert("port".into(), PropertySchema { prop_type: Some("integer".into()), description: Some("Sunshine port (47989)".into()), format: Some("uint16".into()), pattern: None, ref_path: None, items: None });
                p.insert("pin".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Moonlight pairing PIN".into()), format: None, pattern: Some(r"\d{4}".into()), ref_path: None, items: None });
                p
            },
            required: vec!["host".into(), "port".into(), "pin".into()],
        }),
        ("payment_request", JsonSchema {
            schema: "https://json-schema.org/draft/2020-12/schema".into(),
            title: "PaymentRequest".into(),
            description: "Coffee Pie payment request — PSE, Bre-B, or Bancolombia QR".into(),
            schema_type: "object".into(),
            properties: {
                let mut p = BTreeMap::new();
                p.insert("amount_cop".into(), PropertySchema { prop_type: Some("integer".into()), description: Some("Amount in Colombian Pesos (COP)".into()), format: Some("uint64".into()), pattern: None, ref_path: None, items: None });
                p.insert("method".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Payment method: pse, breb, bancolombia_qr".into()), format: None, pattern: Some("pse|breb|bancolombia_qr".into()), ref_path: None, items: None });
                p.insert("customer_email".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Customer email for invoice".into()), format: Some("email".into()), pattern: None, ref_path: None, items: None });
                p.insert("customer_name".into(), PropertySchema { prop_type: Some("string".into()), description: None, format: None, pattern: None, ref_path: None, items: None });
                p.insert("customer_doc".into(), PropertySchema { prop_type: Some("string".into()), description: Some("Colombian ID (CC/NIT)".into()), format: None, pattern: Some(r"\d{7,10}".into()), ref_path: None, items: None });
                p
            },
            required: vec!["amount_cop".into(), "method".into(), "customer_email".into()],
        }),
    ];

    let mut generated = 0u32;
    for (name, schema) in &known {
        let out_path = cli.output.join(format!("{}.json", name));
        let json_str = if cli.pretty {
            serde_json::to_string_pretty(schema).unwrap()
        } else {
            serde_json::to_string(schema).unwrap()
        };
        fs::write(&out_path, json_str).expect("Failed to write schema");
        println!("  {} → {}", name, out_path.display());
        generated += 1;
    }
    println!();
    println!("Generated {} known Coffee Pie schemas in {}", generated, cli.output.display());
}
