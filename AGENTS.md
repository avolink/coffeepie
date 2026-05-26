# Coffee Pie Project - AGENTS.md
# Project Rules, Conventions, and Direction
# Update this file as the project evolves to guide all agents


PROJECT IDENTITY

- Project URL: https://www.coffeepie.co

- Main Contributors: avolink, juandaniel777, diegoalejandromendoza, torvalds?, linuxfoundation?, valve?, microsoft?, apple?, google?, nvidia?, amd?, intel?, arm?...

 Development Stack:<br>
    Backend: Rust, C/C++, Shell/Bash Scripting.<br>
    Frontend: Qt (QML), JavaScript, HTML, CSS.<br>
    Prototyping & Automation: Python.<br>

- Mission: Democratizing computing power and eradicating global electronic waste.

- Product Brief: Coffee Pie® is an open technological ecosystem that provides a general-purpose computing service, like an "internet cafe" or "cybercafe", but from the comfort of your home, office or public space with internet access, with flexible capabilities, without high costs, without strings attached, without maintenance, without significant heat or noise, and without generating electronic waste, based on the patented Quantized Fractional Distribution and Management System (QFDM), Patent NC2025/0012723.

- Community: We are an open community in terms of electronics (mostly open hardware, mostly open source), anyone who wishes can participate in the development of the ecosystem from their knowledge and possibilities, however, in order to be able to keep the project direction, maintain operations, continue improving the service and expanding scope, it is necessary hiring capable people to standardize and monetize it in some way to return valuation and dividends to all conscious investors, so we decided to start the process of becoming a BIC, that is, a private capital company with socio-environmental consciousness, and give the choice to the user between watching ads on-demand, where the Advertisers are the ones paying for the service, or paying directly for "credit packages", which is much cheaper and more convenient than buying a traditional PC. If you are a manufacturer you can freely integrate your modules and accessories around our service, however, if you wish to manufacture the codec terminals themselves to rent them to third parties, you will have to pay a small percentage of royalties through licenses so that these can connect to our QFDM Backend.

- Goal: Initial Public Offering (IPO) and Tokenization (TRC20) by the end of 2035, for the benefit of highly conscious investors and stakeholders. No single individual nor entity will have controlling stakes. We will always be guided by stoic and ethical principles, and our success will be measured by our positive impact on society and the environment, not just by our profits.

- COFFEE Token — COFP (TRC20): The native utility token of the Coffee Pie ecosystem, deployed on the TRON blockchain (TRC-20 standard) for ultra-low fees and fast settlement. COFP tokens confer different rights depending on how they were acquired:

  * Contributors (Community Developers): Earn COFP by contributing code, documentation, translations, or community support. Rights: vote on technical decisions (development stack, deprecation policies, implementation priorities); burn tokens for Platform Credits to consume computing power (capped per account to prevent capacity abuse).

  * Providers (Datacenter Operators): Earn COFP by supplying computing resources to the QFDM Network. Rights: vote on regional pricing (average slice cost, electricity rates, labor costs); burn tokens for fiat currency transferred to their registered bank accounts within 24-72 hours. Provider settlement is an internal ledger operation — provider-earned COFFEE is not publicly tradeable.

  * Investors (BVC Stock Exchange): Acquire COFP through public markets. Rights: proportional dividends and valuation appreciation. No voting rights in technical or operational decisions; their sole governance function is the binary choice of reinvesting profits versus distributing dividends.

- COFP tokens are convertible into Platform Credits (Cr) via a one-way burning mechanism: holders may irreversibly retire their tokens (and all associated economic rights) in exchange for immediately spendable credits, analogous to a company repurchasing B shares with service obligations instead of cash.

- Transparent Monetization Model: 1) licenses and royalties for the rental of codec terminals from manufacturers to third parties 2) sale of massive highly segmented advertising spaces to Advertisers 3) alliances with the public sector, educational entities, libraries, NGOs, etc. 4) services to manufacturers such as setup, maintenance, repair, recycling and final disposal 5) direct consumers who do not wish to watch ads or have a need for high computing resources, but prefer the convenience of our service instead of buying a "NASA computer".

- GUI name: "Coffee Pie Qt".

- Coffee Pie Frontend: The one that connects to the Coffee Pie Backend Streaming Service through TCP credentials control + UDP protocols. While the standard interface is the Coffee Pie Qt GUI running in kiosk mode, advanced users and IT Admins can open a CLI with a keyboard shortcut (e.g., Ctrl + Alt + T) to consume the service via commands, which is especially useful for managing large deployments, automation, or operating without a GUI.

- Orchestrator: Based on OpenUDS v4.0, heavily customized for supporting ultra-low latency streaming protocols like Sunshine/Moonlight.

- Codec Terminal: Simple, dirt cheap, highly modular, highly durable, easily repairable, upgradeable and infinitely recyclable ARM SBC devices (https://coffeepie.co/fabricantes), usually lended by Internet Service Providers (ISPs) to their customers, which includes high decoding capabilities (at least 4K@60Hz in H.264 and/or AV1), running the Frontend Package: Debian Minimal + Sway Kiosk + Coffee Pie Qt GUI + USB-IP for peripherals.

- QFDM System: "QFDM, which stands for "Quantized, Fractional, Distribution and Management System," is a patented on-demand computer management system that enables dynamic distribution through demand quantization via a series of devices known as codec terminals, it involves resource fractionation, machine instantiation, and real-time transmission, even for users with no technical expertise. In simple words, imagine an airplane as a large computer, and each seat as a "slice" of that computer. You wouldn't consider "buying a plane" for just a couple of trips; You buy a ticket each time you need one, multiple tickets if you're traveling with others (multiple users simultaneously), or if you need more space for your luggage (files). In this case, the QFDM system would be the equivalent of the "airport" where airlines (datacenters) operate with their aircrafts (servers), abstracting all the complexity, high investment, operation, maintenance, and marketing costs, dividing them into thousands of small tickets (portions) and providing a simple, affordable, and accessible service for the great benefit of users and the environment. This is because it reduces the cost of infrastructure and natural resource extraction, transforming what used to be an exponential problem O(n²) with no clear limits (infinite resource extraction and infinite waste) into a linear one O(n) with a clear limit: the maximum demand for the service at any given time (rush hour). Furthermore, it can be implemented on existing infrastructure, minimizing adoption risk to virtually zero."

Coffee Pie® Slice Technical Specifications:

PWR: 1 Wh (*indicates the maximum electrical consumption of the instance in one hour).

CPU: 1 vCore (indicates the number of serial processing threads, logical cores or vCores).

RAM: 1 GB (indicates the amount of volatile random access memory).

SSD: 8 GB (indicates the high-speed memory for the operating system and small files).

NET: 8 Mbps (indicates the bandwidth of the internet connection, in the Backend).

HDD: 125 GB (indicates the amount of low-speed storage for files and backups).

GPU: 125 MB (indicates the random access memory of the parallel processor or GPU).

RES: 15 vMPX/s (indicates max amount of virtual pixels per second displayed on terminal).

IA: 3 TOPS (INT8) (indicates the parallel processing capacity for Artificial Intelligence).

*If an instance is consuming too much power, warnings will be triggered to the user account thus preventing further charges and/or automatic suspension. This also dissuades dishonest behavior like cryptomining (mining cryptocurrency is strictly prohibited, though transactions are allowed if regional law permits), spamming or serving malicious content, which are strictly prohibited and may lead to permanent suspension of the user account.


CORE PRINCIPLES


1. OPENUDS API ONLY (COFFEE PIE ORCHESTRATOR)
   The frontend must NEVER talk directly to Proxmox API, hypervisor APIs,
   or any infrastructure API. All communication goes through the Orchestrator
   (OpenUDS broker, forked to coffeepie_orchestrator, which replaces Guacamole for Sunshine in order to achieve ultra-low latency streaming and better performance, at cost of higher complexity and maintenance).

2. DIRECT STREAMING
   Video/audio streams go direct P2P between Codec Terminal and VM (Sunshine
   → Moonlight over UDP, supporting server side encoding for H.264 and AV1).
   The orchestrator brokers the connection but does NOT proxy the stream.
   The tunnel server is for orchestration signaling only, not for media transport.

3. L2/L3/L4 PRIVATE NETWORKS
   The system operates over a Layer 2/3/4 Private LAN/MAN/WAN (stretched VLAN).
   Assumptions:
   - All hosts are directly reachable at private IPsFF
   - No NAT traversal needed
   - mDNS works across the domain
   - Encryption is optional (network-layer security handles it)
   - No GeoDNS needed (single IP space)
   - Accesing from L2 and from not certified devices will be implemented for Pay-As-You-Go users only (Free Tier users will be restricted to L3/L4 network connections from internet at the cost of higher latencies)

4. HARDWARE-ACCELERATED EVERYTHING
   Streaming is GPU-accelerated end-to-end:
   - Encode: VM GPU (NVENC, VAAPI, AMF)
   - Decode: Codec Terminal SBC (/dev/dri/renderD128)
   - No CPU-based software encoding/decoding in the critical path
   - AI real time video upscaling in the terminal codec thanks to specialized ultra-low power consumption NPUs capable of zero effort, zero added latency for at least H.264 (Basic Codec Terminal) and AV1 (Pro Codec Terminal).

5. BACKWARD COMPATIBLE MIGRATION
   Guacamole is deprecated, not removed. Existing Guacamole-based transports
   will continue to work. New deployments use Sunshine. When Sunshine is proven
   stable Guacamole components could be removed.


CODE CONVENTIONS


Orchestrator (Python/Django):
  - Follow OpenUDS module patterns (transport base class, auto-discovery)
  - Transports live under server/src/uds/transports/<Name>/
  - Each transport has __init__.py that imports the class
  - is_base  True for abstract classes, False for concrete
  - own_link  True for transports that return URLs
  - own_link  False for transports that return UDS client scripts
  - Use types.transports.Protocol enum for protocol identification
  - Use TicketStore for secure parameter passing
  - All user-facing strings use django gettext_noop / _()
  - Open Core license header on all new files

Actor (Rust):
  - Follow worker pattern (subscribe to broadcast channel, filter by type)
  - Workers live under crates/service/src/workers/http/
  - Register workers in mod.rs via spawn_workers! macro
  - New message types go in crates/shared/src/ws/types.rs
  - TryFrom implementations in crates/shared/src/ws/rcptraits.rs
  - Platform-specific code uses #[cfg(target_family  "...")]
  - Use tokio::process::Command for subprocess management
  - Log via shared::log macros

Frontend (Qt for GUI / Python for Business Logic):
  - Primary: C++ entry + QML UI (CMake build)
  - Secondary: Python entry + QML UI (PySide6, for rapid prototyping)
  - Keep QML declarative - business logic in C++/Python, not QML
  - Fullscreen + frameless at all times (kiosk mode)
  - Design for 1920x1080 (FHD) resolution as standard
  - Hardware: assume /dev/dri/renderD128 available for Moonlight
  - REST API calls via QNetworkAccessManager (C++) or requests (Python)

Website Frontend (Vanilla Web Technologies):
  - NO FRAMEWORKS ALLOWED FOR FRONTEND (No React, No Angular, No Vue, etc.)
  - NO TYPESCRIPT (Use latest ECMAScript standards Vanilla JS only)
  - NO CSS PREPROCESSORS/FRAMEWORKS (No Tailwind, No Bootstrap, Use Vanilla CSS only)
  - Pure HTML, CSS, and Vanilla JS
  - Since the Project was founded in Colombia, the website is spanish first for SEO optimization and SPA like speed, but it will be available in multiple languages, e.g. english, portuguese, french, german, japanese, russian, hindi, arabic, korean and chinese, and any other the community wants to translate to through the translations.json file only for keeping order and instant translation without reloading.

Website Backend (e.g., Python, Django, FastAPI, Supabase, PostgreSQL):
  - Unlike the frontend, the website backend IS permitted and encouraged to use robust frameworks (like Django, FastAPI, Supabase) or Backend-as-a-Service (like Supabase).
  - Use the backend to securely manage payments, database interactions, and sensitive business logic.
  - All secrets, API keys, and environment variables MUST reside in the backend infrastructure and never be exposed or committed to the frontend repository.


GIT:
  - NEVER commit secrets, tokens, or credentials
  - NEVER force push to main (master is deprecated)
  - NEVER skip pre-commit hooks without explicit request
  - ALWAYS commit with descriptive messages (feat:/fix:/chore:/docs: prefix)
  - Keep GENERATED.txt and autogen/ files (Qt Design Studio artifacts)
  - Submodule changes must be committed in submodule first, then meta-repo
  - .gitignore should include *.rar, *.zip and other compression formats.


ARCHITECTURAL DECISIONS


Decision: Since it's meant to be an international project for anyone to use and benefit from it, the main language used will be USA English (en-us), but the Frontend will be displaying labels, menus and options in multi-language, supporting at least Spanish, Portuguese, French, German, Japanese, Russian, Hindi, Arabic, Korean and Chinese, the community is welcome to improve these translations according to their locales. Keyboard Layout is also en-us, but can be freely changed via QMK/VIA configuration to adapt to any locale or specific needs of the user.

Decision: Latency and performance is the top priority, above all else, including security, that's why Rust is the canonical language.
  Reason: Latency and performance are the primary factors that determine the quality of the user experience. The lower the latency and the higher the performance, the better the user experience. Therefore, all architectural decisions must be made with the goal of minimizing latency and maximizing performance, while still maintaining an excellent level of security, that's why Rust is used for the service/actor layer instead of Python, Qt for the Frontend instead of web technologies, and AV1 for the Pro Codec Terminal instead of H.264 in the Pro Codec Terminal. At the end, Coffee Pie is a tool for productivity, and the users can achieve more in less time with a better user experience. In addition, it's a tool for entertainment, and the users can enjoy more with a better user experience.

Decision: H.264 for Basic Codec Terminal, AV1 for Pro Codec Terminal
  Reason: H.264 is a widely used codec that is supported by all devices with at least HDMI 2.0 support. AV1 is a newer codec that offers better compression efficiency, but it is not as widely supported as H.264. The Basic Codec Terminal is designed for users who need a simple, affordable and reliable solution, while the Pro Codec Terminal is designed for users who need a high-performance solution with as low latency as possible. Therefore, the Basic Codec Terminal should use H.264 and Ethernet PoE, while the Pro Codec Terminal should use AV1 and Optical Fiber, or low latency satellital connection like AST Space Mobile and Starlink, etc.

Decision: Qt for GUI/ Python for Logic (Frontend)
  Reason: Qt for GUI for speed and performance (performance comes first), Python for logic for rapid prototyping and ease of maintenance.

Decision: OpenUDS for Orchestrator, Sunshine for Streaming, Codec Terminal for Playback
  Reason: Open source and highly customizable, with excellent community support, documentation, and the ability to integrate with other open source projects to create a comprehensive solution

Decision: REST API and WebSockets for frontend-orchestrator communication.
  Reason: REST API for requests, WebSockets for real-time updates.

Decision: Sunshine API Local Connection Security (SSL Verification)
  Reason: Bypassing strict SSL validation or handling internal connection security for Sunshine/Moonlight is completely intended. Security is handled in a higher layer of the service (Login with 2FA, OTP, orchestrator credentials). Other contributors should not treat internal SSL bypasses in this context as a vulnerability.

Decision: Rust for service/actor layer.
  Reason: Performance, type safety, and modern async ecosystem. Python may be
  used for rapid prototyping but Rust is the long-term choice.

Decision: VM over LXC for orchestrator
  Reason: Kernel isolation for the management plane. A Proxmox host kernel
  panic should not take down the ability to manage the cluster.
  Revisit: When orchestrator HA is implemented, LXC might be acceptable.

Decision: Single orchestrator per DC initially
  Reason: Over L2 private network, frontend fallback list handles failover.
  A GeoDNS layer adds complexity with no benefit at this stage.
  Revisit: When deploying internet-facing Codec Terminals.

Decision: PostgreSQL single instance + streaming replica
  Reason: The database is the real single point of failure. Standby replica
  is higher priority than multiple orchestrator instances.
  Revisit: When scaling beyond 2 DCs, consider multi-master or distributed SQL.

Decision: Supabase for Identity & Backend services (Replacing Firebase)
  Reason: While Firebase is used for initial rapid prototyping, Supabase perfectly aligns with the PostgreSQL decision and the project's goal of technological sovereignty and open standards. It allows future self-hosting of user identity (IAM) without relying on proprietary Google infrastructure.

Decision: Moonlight CLI over embedded Moonlight SDK
  Reason: Moonlight SDK is complex to embed. CLI subprocess via QProcess
  is simpler, well-tested, and allows Moonlight to manage its own DRM/KMS.
  Revisit: If subprocess management becomes unreliable.

Decision: Keep Guacamole transports functional during migration
  Reason: Allows gradual rollout. Users can fallback to HTML5 if Sunshine
  has issues. Removes risk of all-or-nothing deployment.


DEPLOYMENT TARGETS


Codec Terminal:
  OS: Debian Minimal (no desktop environment)
  Display: Sway (Wayland compositor) in kiosk mode
  GUI: Coffee Pie frontend (Qt 6.5 QML), fullscreen frameless
  Client: Moonlight Qt (hardware-accelerated via KMS/DRM)
  Ports needed: Outbound to orchestrator (HTTPS), outbound UDP to VMs

VM (User Desktop):
  OS: Windows 10/11 or Linux (with GPU or vGPU)
  Services: OpenUDS Actor (Rust daemon, port 43910), Sunshine (GameStream host)
  GPU: Required for hardware encoding (NVIDIA NVENC, Intel QSV, AMD AMF)
  Ports: 47984-48010 TCP+UDP (Sunshine GameStream ports)

Orchestrator:
  OS: Debian or Ubuntu LTS
  Services: Django (Gunicorn/uWSGI), PostgreSQL, Redis (cache)
  Ports: 443 (HTTPS), 80 (HTTP redirect)
  Resources: 2-4 vCPU, 4GB RAM, 40GB disk (minimum)


ANTI-PATTERNS (DO NOT DO)


1. DO NOT expose Proxmox API to Codec Terminals
2. DO NOT proxy video streams through the tunnel server
3. DO NOT use Electron for the frontend (too heavy for ARM SBCs)
4. DO NOT hardcode IPs in the frontend (use config file or env vars)
5. DO NOT remove Guacamole transports before Sunshine/Moonlight stability is proven
6. DO NOT modify the sunshine/ reference repo (it's upstream)
7. DO NOT commit without reading files first
8. DO NOT import libraries without verifying they exist in the project
9. DO NOT add comments unless explicitly requested
10. DO NOT generate emojis in code or commit messages unless asked
11. DO NOT use web frameworks (React, Angular, Vue, Tailwind, etc.) or TypeScript for the website. Use only Vanilla JS, HTML, and CSS.
12. DO NOT run automated translation tools (LibreTranslate, Google Translate API, etc.) on the entire `translations.json` file. Translations must be manually reviewed per-language. Automated translation tools do not understand context: they mistranslate proper nouns (e.g., "INICIO" became "INITIO" instead of "HOME"), corrupt HTML/special characters (e.g., `|||` paragraph separators became `h. 124;` fragments), and produce misleading output in non-Latin scripts (e.g., Japanese "ホーム" became "インティオ", Chinese "首页" became "印度"). Instead, use Weblate (the canonical TMS for this project — see TRANSLATIONS.md) which supports machine translation pre-fill with mandatory human review, glossary enforcement, and voting workflows.
13. DO NOT translate language-independent identifiers in `translations.json`. These must remain identical across all languages: (a) email addresses (e.g., `accesibilidad@coffeepie.co`), (b) physical addresses (e.g., `Cr 46 #56-11, La Candelaria, Medellín, Antioquia.`), (c) brand names with registered trademarks (e.g., `Coffee Pie®`, `Commanders™`, `Sentinels™`, `Rangers™`), (d) company/project names (e.g., `QFDM`, `OpenUDS`, `Sunshine`, `Moonlight`, `Proxmox`), (e) URLs and API endpoints, (f) technical specs and units (e.g., `1 Wh`, `8 GB`, `3 TOPS`), and (g) proper nouns like social media handles (e.g., `Instagram`, `Facebook`, `TikTok`). These keys should store the same value for all language codes.



PROJECT DIRECTION


Current Phase: Foundation
  - Sunshine transport integrated into orchestrator
  - Actor manages Sunshine lifecycle
  - Guacamole marked as deprecated
  - Frontend needs REST API integration

Next Phase: Frontend Integration
  - Add QNetworkAccessManager-based REST client to Qt/QML frontend
  - Replace hardcoded data with API responses
  - Add PIN dialog for Moonlight pairing
  - Add orchestrator URL configuration
  - Add multi-orchestrator fallback list

Future Phase: Production Hardening
  - Database streaming replication
  - Orchestrator HA (Proxmox HA restart)
  - Multi-DC MetaPool configuration
  - Monitoring and alerting
  - Automated VM template provisioning

Long-term: Scale
  - Internet-facing Codec Terminals (GeoDNS)
  - Hypervisor-agnostic provider layer
  - Credit/billing system integration
  - Multi-tenant isolation


TWEAKS AND OVERRIDES


# Use this section to override or refine project direction:

<!-- TWEAK: (add specific direction tweaks here) -->
<!-- Example: "The frontend should use Python/PySide6 path for development
     and switch to C++/CMake for production builds" -->

<!-- TWEAK: (add more as the project evolves) -->

- Numeric Format: Both comma , and dot . will be taken as floating separators. e.g.: pi = 3.141592653589793 or e = 2,718281828459045 are both valid Floats. Always use apostrophe ' as thousands separators for better readability. eg.: int = 1'000'000 units | float = 7'837,50 | float = 25'500.43 | etc.
- Dates Format: All dates must to be handled in YYYY-MM-DD international format, no other formats are allowed. If working with external databases these need to be parsed to match before any operation or calculation for better consistency and redeability.
- Translations Policy: Email addresses, physical addresses, brand names with registered brands ® Trademarks ™ human names, company/project names (QFDM, OpenUDS, Sunshine, Moonlight, Proxmox), URLs, API endpoints, technical specs/units, proper nouns, and social media handles must remain IDENTICAL across all languages in translations.json. These are language-independent identifiers and should never be translated.
- If an Agent creates a single use script (.py, .js, .rs, etc), it should be deleted after executed for not taking extra space in the repository, unless explicitly told by the user to keep it.


SECURITY POSTURE & HARDENING (2026-05-25 Audit)


Decision: TLS verification bypass limited to internal L2/L3 private networks.
  Reason: The `NoVerifySsl` certificate verifier and `danger_accept_invalid_certs` are 
  explicitly restricted to internal connections where the network layer already provides 
  encryption (stretched VLAN). External-facing connections MUST use full TLS verification.
  Documented in: `actor/crates/shared/src/tls/noverify.rs`, `tunnel-server/.../broker/mod.rs:90`

Decision: Post-Quantum KEM handled by Rust (libcrux), Python pqcrypto is deprecated.
  Reason: The Python `pqcrypto` package (`orchestrator/server/requirements.txt:24`) is 
  unmaintained and unavailable on Python 3.14+. The Rust components already use 
  `libcrux-ml-kem` (0.0.7-0.0.8) for ML-KEM-768 key exchange. The Python orchestrator's 
  `kem.py` module must be migrated to call the Rust libcrux implementation via a sidecar 
  subprocess or PyO3 FFI binding. Until then, `pqcrypto` is pinned in requirements and 
  marked as known technical debt.
  Revisit: When libcrux reaches >= 1.0 or a maintained Python PQ crypto library emerges.

Decision: FastAPI Proxmox backend requires Firebase Bearer token authentication.
  Reason: The proxmox_backend FastAPI endpoints were previously unauthenticated, allowing 
  any network-accessible caller to manage VMs. All `/nodes/` endpoints now require a valid 
  Firebase ID token passed as `Authorization: Bearer <token>` header. Token validation uses 
  `firebase_admin.auth.verify_id_token()`.
  Implemented in: `proxmox_backend/app/dependencies.py:verify_bearer_token()`

Decision: Content-Security-Policy header enforced on all website pages.
  Reason: Defense-in-depth against XSS and data injection. Allows scripts from self, 
  gstatic.com (Firebase), parastorage.com/avostatic.com (Wix/Avo platform). Styles, 
  images, fonts, and connect-src are appropriately scoped. frame-ancestors 'self' 
  prevents clickjacking.
  Configured in: `coffeepie_website/public/.htaccess`

Decision: Python dependencies pinned to exact versions.
  Reason: Unpinned dependencies create non-reproducible builds and supply-chain risk.
  All requirements.txt files now use exact version pins (==).
  Revisit: On each dependency update, audit for CVEs using `pip-audit` or `safety`.

Decision: Django production security flags must be enabled before deployment.
  The settings.py.sample file contains DEBUG=True, ALLOWED_HOSTS=['*'], and hardcoded 
  SECRET_KEY/RSA_KEY. Before any production deployment:
  1. Set DEBUG=False
  2. Set ALLOWED_HOSTS to the actual domain list
  3. Generate new SECRET_KEY and RSA_KEY via environment variables
  4. Set SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SECURE=True, CSRF_COOKIE_SECURE=True
  5. Set SECURE_SSL_REDIRECT=True, SECURE_HSTS_SECONDS=31536000
  6. Set SECURE_BROWSER_XSS_FILTER=True, SECURE_CONTENT_TYPE_NOSNIFF=True

Known Technical Debt (from audit):
  - `SessionRecoveryBuffer` uses UnsafeCell with unsafe Send+Sync (tunnel-server, client)
  - `addin.rs` transmutes between incompatible function pointer types (RDP FFI)
  - `process.rs` allows arbitrary command execution from JS context (needs sandboxing)
  - 70+ unwrap/expect calls in network-facing Rust paths (DoS risk on lock poisoning)
  - pickle.loads at 30+ locations in orchestrator (DB compromise = RCE)
  - `chpasswd` stdin injection via newlines in user parameter
  - 6 CSRF-exempt endpoints in orchestrator
  - Unpinned git dependency `cannatag/ldap3.git` in orchestrator requirements
  - `pqcrypto` Python package is unmaintained (migration to Rust libcrux pending)
