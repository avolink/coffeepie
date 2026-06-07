// Coffee Pie Payment Test Tool
// Simulates and validates payment flows for all Colombian payment backends.
// Tests Bre-B, PSE, Bancolombia QR, and invoice generation locally
// without needing real bank credentials.
//
// Usage:
//   coffeepie-payment-test simulate --method pse --amount 50000
//   coffeepie-payment-test invoice --customer "Juan Perez" --credits 500
//   coffeepie-payment-test flow --method breb --amount 100000
//   coffeepie-payment-test webhook-test --provider bancolombia

use clap::Parser;
use serde::Serialize;
use std::fmt;

#[derive(Parser)]
#[command(name = "coffeepie-payment-test")]
#[command(about = "Coffee Pie Payment Flow Simulator & Validator", long_about = None)]
struct Cli {
    #[command(subcommand)]
    command: Commands,
}

#[derive(Parser)]
enum Commands {
    /// Simulate a single payment
    Simulate(SimulateArgs),
    /// Generate a test invoice
    Invoice(InvoiceArgs),
    /// Run full payment flow (create → check → confirm)
    Flow(FlowArgs),
    /// Test webhook payloads
    WebhookTest(WebhookArgs),
    /// QR code data preview
    QrPreview(QrArgs),
}

#[derive(Parser)]
struct SimulateArgs {
    /// Payment method: pse, breb, bancolombia_qr
    #[arg(short, long, default_value = "pse")]
    method: String,

    /// Amount in COP (Colombian Pesos)
    #[arg(short, long, default_value = "50000")]
    amount: u64,

    /// Customer email
    #[arg(long, default_value = "test@coffeepie.co")]
    email: String,

    /// Customer name
    #[arg(long, default_value = "Usuario de Prueba")]
    name: String,

    /// Customer document (CC/NIT)
    #[arg(long, default_value = "1234567890")]
    doc: String,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct InvoiceArgs {
    /// Customer name
    #[arg(long, default_value = "Juan Perez")]
    customer: String,

    /// Customer document
    #[arg(long, default_value = "1234567890")]
    doc: String,

    /// Customer email
    #[arg(long, default_value = "juan@email.com")]
    email: String,

    /// Credits purchased
    #[arg(long, default_value = "500")]
    credits: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct FlowArgs {
    /// Payment method
    #[arg(short, long, default_value = "breb")]
    method: String,

    /// Amount in COP
    #[arg(short, long, default_value = "100000")]
    amount: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct WebhookArgs {
    /// Provider: pse, breb, bancolombia
    #[arg(short, long, default_value = "breb")]
    provider: String,

    /// Transaction ID to simulate
    #[arg(long, default_value = "TEST-TX-001")]
    tx_id: String,

    /// Amount in COP
    #[arg(long, default_value = "50000")]
    amount: u64,

    /// JSON output
    #[arg(long)]
    json: bool,
}

#[derive(Parser)]
struct QrArgs {
    /// Amount in COP
    #[arg(short, long, default_value = "50000")]
    amount: u64,

    /// Reference
    #[arg(short, long, default_value = "CP-TEST-001")]
    reference: String,
}

fn main() {
    let cli = Cli::parse();

    match cli.command {
        Commands::Simulate(args) => cmd_simulate(&args),
        Commands::Invoice(args) => cmd_invoice(&args),
        Commands::Flow(args) => cmd_flow(&args),
        Commands::WebhookTest(args) => cmd_webhook(&args),
        Commands::QrPreview(args) => cmd_qr(&args),
    }
}

fn cmd_simulate(args: &SimulateArgs) {
    let method_name = match args.method.as_str() {
        "pse" => "PSE (ACH Debit)",
        "breb" => "Bre-B (Instant Transfer)",
        "bancolombia_qr" | "qr" => "Bancolombia QR",
        _ => &args.method,
    };

    let credits = args.amount; // 1 COP ≈ 1 Cr
    let iva = (args.amount as f64 * 0.19) as u64;

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "method": args.method,
            "method_name": method_name,
            "amount_cop": args.amount,
            "credits": credits,
            "iva_19pct": iva,
            "total_with_iva": args.amount + iva,
            "customer": {"name": args.name, "email": args.email, "doc": args.doc},
            "status": "SIMULATED",
        })).unwrap());
    } else {
        println!("Coffee Pie Payment Simulation");
        println!("=============================");
        println!("  Method:    {}", method_name);
        println!("  Amount:    {} COP", format_num(args.amount));
        println!("  Credits:   {} Cr", format_num(credits));
        println!("  IVA 19%:   {} COP", format_num(iva));
        println!("  Total+IVA: {} COP", format_num(args.amount + iva));
        println!("  Customer:  {} ({})", args.name, args.email);
        println!();

        match args.method.as_str() {
            "pse" => {
                println!("  Flow: User → bank selection page → login → authorize → redirect back");
                println!("  Redirect: https://pse-test.coffeepie.co/select-bank?amount={}", args.amount);
                println!("  Confirmation: webhook POST to /payments/webhook/pse (up to 24h)");
            }
            "breb" => {
                println!("  Flow: Coffee Pie provides Bre-B key → user sends from bank app");
                println!("  Bre-B key: coffeepie@bancolombia");
                println!("  Send {} COP to this key from your Bancolombia/Davivienda/etc app", format_num(args.amount));
                println!("  Confirmation: webhook POST to /payments/webhook/breb (< 30s)");
            }
            "bancolombia_qr" | "qr" => {
                println!("  Flow: Show QR code → user scans with Bancolombia App → confirms");
                println!("  QR data: amount={} COP, ref=CP-{}", args.amount, &args.doc[..4]);
                println!("  Confirmation: webhook POST to /payments/webhook/bancolombia (< 5s)");
            }
            _ => {}
        }
    }
}

fn cmd_invoice(args: &InvoiceArgs) {
    let subtotal = args.credits;
    let iva = (subtotal as f64 * 0.19) as u64;
    let total = subtotal + iva;
    let cufe = format!("CUFE-{:X}", simple_hash(&format!("{}{}{}", args.doc, total, "2026-05-30")));

    if args.json {
        println!("{}", serde_json::json!({
            "invoice_number": format!("FECP-{:08X}", simple_hash(&args.doc) % 99999999),
            "customer": {"name": args.customer, "doc": args.doc, "email": args.email},
            "items": [{"description": format!("Creditos Coffee Pie — {} Cr", args.credits), "amount_cop": subtotal}],
            "subtotal_cop": subtotal,
            "iva_19pct": iva,
            "total_cop": total,
            "credits": args.credits,
            "cufe": cufe,
        }));
    } else {
        println!("Coffee Pie — Factura Electrónica (Simulación)");
        println!("=============================================");
        println!("  N.º Factura:  FECP-{:08X}", simple_hash(&args.doc) % 99999999);
        println!("  Cliente:      {} (CC: {})", args.customer, args.doc);
        println!("  Email:        {}", args.email);
        println!("  ─────────────────────────────────────────");
        println!("  Concepto:     Creditos Coffee Pie — {} Cr", format_num(args.credits));
        println!("  Subtotal:     {} COP", format_num(subtotal));
        println!("  IVA 19%:      {} COP", format_num(iva));
        println!("  Total:        {} COP", format_num(total));
        println!("  ─────────────────────────────────────────");
        println!("  CUFE:         {}", cufe);
        println!("  Estado DIAN:  SIMULADO (test mode)");
        println!();
        println!("  ⚠ Real invoices require DIAN authorization via their web service.");
        println!("  See: https://www.dian.gov.co/factura-electronica");
    }
}

fn cmd_flow(args: &FlowArgs) {
    let ref_id = format!("CP-FLOW-{:04X}", simple_hash(&format!("{}{}", args.method, args.amount)) % 9999);
    let credits = args.amount;
    let method_name = method_display(&args.method);

    if !args.json {
        println!("Coffee Pie — Full Payment Flow Simulation");
        println!("==========================================");
        println!("  Method:  {}", method_name);
        println!("  Amount:  {} COP ({} Cr)", format_num(args.amount), format_num(credits));
        println!("  Ref:     {}", ref_id);
        println!();
    }

    // Phase 1: Create payment
    if !args.json { println!("[1/3] Creating payment..."); }
    let tx_id = format!("TX-{}", &ref_id);
    if !args.json { println!("      Transaction ID: {}", tx_id); }

    match args.method.as_str() {
        "pse" => {
            if !args.json {
                println!("      Redirect URL: https://pse-test.coffeepie.co/bank-select?tx={}", tx_id);
                println!("      → User selects bank, logs in, authorizes debit");
            }
        }
        "breb" => {
            if !args.json {
                println!("      Bre-B key: coffeepie@bancolombia");
                println!("      → User opens bank app, sends {} COP to key", format_num(args.amount));
            }
        }
        _ => {
            if !args.json {
                println!("      QR code displayed on screen");
                println!("      → User scans with Bancolombia App, confirms payment");
            }
        }
    }

    // Phase 2: Check status (simulate processing)
    if !args.json {
        println!();
        println!("[2/3] Checking status...");
        println!("      Status: PROCESSING → bank confirming...");
    }

    // Phase 3: Webhook confirmation
    if !args.json {
        println!();
        println!("[3/3] Webhook received!");
        println!("      Status: COMPLETED ✓");
        println!("      {} COP credited as {} Cr", format_num(args.amount), format_num(credits));
    }

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "flow": "complete",
            "transaction_id": tx_id,
            "amount_cop": args.amount,
            "credits": credits,
            "method": args.method,
            "phases": [
                {"phase": 1, "status": "created", "tx_id": tx_id},
                {"phase": 2, "status": "processing"},
                {"phase": 3, "status": "completed", "webhook": "confirmed"},
            ]
        })).unwrap());
    } else {
        println!();
        println!("  ✓ Payment flow complete. {} Cr added to user account.", format_num(credits));
        println!("  Webhook POST /payments/webhook/{} → 200 OK", args.method);
    }
}

fn cmd_webhook(args: &WebhookArgs) {
    let payload = match args.provider.as_str() {
        "pse" => serde_json::json!({
            "transaction_id": args.tx_id,
            "status": "APPROVED",
            "amount": args.amount,
            "completed_at": "2026-05-30T15:30:00Z",
        }),
        "breb" => serde_json::json!({
            "transaction_id": args.tx_id,
            "sender_key": "3001234567",
            "receiver_key": "coffeepie@bancolombia",
            "amount": args.amount,
            "status": "COMPLETED",
            "reference": "CP-TEST-001",
            "timestamp": "2026-05-30T15:30:00Z",
        }),
        _ => serde_json::json!({
            "id_transaccion": args.tx_id,
            "estado": "APROBADO",
            "valor": args.amount,
            "fecha_pago": "2026-05-30T15:30:00Z",
        }),
    };

    if args.json {
        println!("{}", serde_json::to_string_pretty(&serde_json::json!({
            "webhook": {
                "provider": args.provider,
                "endpoint": format!("/payments/webhook/{}", args.provider),
                "payload": payload,
                "expected_response": {"status": "ok", "transaction_id": args.tx_id},
            }
        })).unwrap());
    } else {
        println!("Coffee Pie — Webhook Test Payload");
        println!("=================================");
        println!("  Provider:  {}", args.provider);
        println!("  Endpoint:  POST /payments/webhook/{}", args.provider);
        println!("  Payload:");
        println!("{}", serde_json::to_string_pretty(&payload).unwrap());
        println!();
        println!("  Expected response: 200 OK");
        println!("  {{ \"status\": \"ok\", \"transaction_id\": \"{}\" }}", args.tx_id);
    }
}

fn cmd_qr(args: &QrArgs) {
    // Generate QR code data in Bancolombia EMVCo format
    let qr_payload = serde_json::json!({
        "tipo": "QR_ESTATICO",
        "comercio": {
            "id": "COFFEEPIE",
            "nombre": "Coffee Pie®",
            "ciudad": "Medellin",
            "terminal": "WEB001",
        },
        "transaccion": {
            "referencia": args.reference,
            "valor": args.amount,
            "moneda": "COP",
            "descripcion": format!("Recarga Coffee Pie — {} Creditos", args.amount),
        },
    });

    println!("Coffee Pie — Bancolombia QR Code Preview");
    println!("========================================");
    println!("  Merchant:  COFFEEPIE (Coffee Pie®)");
    println!("  Terminal:  WEB001");
    println!("  Amount:    {} COP ({} Cr)", format_num(args.amount), format_num(args.amount));
    println!("  Ref:       {}", args.reference);
    println!();
    println!("  QR Payload (EMVCo):");
    println!("{}", serde_json::to_string_pretty(&qr_payload).unwrap());
    println!();
    println!("  To render: encode this JSON as a QR code (qrencode, OR easily with a frontend library).");
    println!("  The Bancolombia App reads this format and auto-fills the payment screen.");
    println!();
    println!("  Test: echo '{}' | qrencode -o coffee-qr.png -s 10", 
        serde_json::to_string(&qr_payload).unwrap().replace('\'', "'\\''"));
}

fn method_display(method: &str) -> &str {
    match method {
        "pse" => "PSE (ACH Debit)",
        "breb" => "Bre-B (Instant Transfer)",
        "bancolombia_qr" | "qr" => "Bancolombia QR",
        _ => method,
    }
}

fn format_num(n: u64) -> String {
    if n >= 1_000_000 {
        format!("{}'{:03}'{:03}", n / 1_000_000, (n % 1_000_000) / 1_000, n % 1_000)
    } else if n >= 1_000 {
        format!("{}'{:03}", n / 1_000, n % 1_000)
    } else {
        n.to_string()
    }
}

fn simple_hash(s: &str) -> u64 {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    let mut h = DefaultHasher::new();
    s.hash(&mut h);
    h.finish()
}
