░█▀▀░█▀█░█▀▀░█▀▀░█▀▀░█▀▀░░░█▀█░▀█▀░█▀▀<br>
░█░░░█░█░█▀▀░█▀▀░█▀▀░█▀▀░░░█▀▀░░█░░█▀▀<br>
░▀▀▀░▀▀▀░▀░░░▀░░░▀▀▀░▀▀▀░░░▀░░░▀▀▀░▀▀▀<br>

🍰 Coffee Pie® Ecosystem ☕<br>Democratizing Computing Power & Eradicating Global Electronic Waste.<br>

"In the future, you won't own anything, but you'll have access to everything and you'll be happy. Life is too short, so don't worry. Enjoy life peacefully with your loved ones, eat healthily, meditate, train your mind, exercise your body, travel light like a backpacker while you can, and find your balance. We came into this world with nothing, and we'll leave with nothing. All that remains are the lives we improved, the happiness we brought to others and to ourselves." - Anonymous<br>

Project Status: Active<br>
Concluded Phase: Lab Testing (TRL6)<br>
Current Phase: Alpha Testing (TRL7)<br>
Current Version: v0.1.0-alpha<br>

Company: Coffee Pie® Colombia is a Benefit and Collective Interest (BIC) subsidiary of GRUPO 3P1 COLOMBIA S.A.S.<br>
Patent: NC2025/0012723 (expiring by 2045).<br>
License: Community License & QFDM Royalty Terms (see LICENSE and CONSTITUTION files)<br>

Coffee Pie® is an open technological ecosystem that provides a general-purpose computing service. Think of it as a "global freemium cybercafe" accessible from anywhere, powered by the patented Quantized Fractional Distribution and Management System (QFDM), transforming what was an exponential problem O(n²) with no clear limits (infinite resource extraction and infinite waste) into a linear one O(n) with a clear limit: the maximum demand for the service at any given time (rush hour). Furthermore, it can be implemented on existing infrastructure, minimizing adoption risk to virtually zero...<br>

🖥️ Legit and Recommended Uses (but not limited to):<br>
AI training, AI inferencing, Big Data, deploying servers, apps and databases, studying, working, writing, developing, programming, compiling, designing, composing, transforming, editing, exporting, rendering, calculating, organizing, communicating, collaborating, undertaking, selling, analysing, researching, creating, entertaining, casual gaming, but not really meant for hardcore gaming due to higher latency (10 ~ 80ms), you'd enjoy competitive games better with a handheld or console.<br>

🛠 Project Identity & Stack:<br>
 Official URL: https://coffeepie.co<br>
 Main Contributors (and initial Moderators):<br>
 - avolink (The Architect and QA, Frontend Developer UI/UX, Industrial Designer and Marketer)<br>
 - juandaniel777 (The Engineer and Software Backend Developer, Embedded Specialist)<br>
 - Diego-M-PZ (The Electronics, Maintenance and Circular Services Manager).<br>

  ⌨️ Development Stack:<br>
    - Backend: Rust, Shell/Bash Scripting (C/C++ deprecated by 2030, Rust becoming Canon, but still a lot of Legacy Code in dependencies like Linux Kernel).<br>
    - Frontend: Qt (QML), Django, HTML, CSS, JavaScript (No Frameworks).<br>
    - Prototyping & Automation: Python.<br>
    - Networking: IPv4 (current). IPv8 roadmap — early adoption by 2035 or RFC maturity.<br>

 🌐 Potential Contributors and Investors:<br> Our architecture is designed to welcome contributions (and future partnerships) from pioneers like the Linux Foundation, Valve, AMD, Intel, Nvidia, ARM, Apple, Microsoft, Alphabet, IBM, OpenAI, Anthropic, Meta, SpaceX, AST Space Mobile, up to anyone committed to open standards and e-waste eradication. Big Cloud players like Azure, AWS, GCP, Linode, ShadowTech, etc, are also welcome to provide their unused infrastructure for profit (tokens earned are burnable for fiat money, although right now the provider needs a bank account in Colombia, or can be kept for future dividends and valuation).<br>
 
 🚀 The Vision "The Airport of Computing":
- Imagine a computer as an airplane. Usually you don't buy an airplane, you get a ticket just when you need it.<br>
- QFDM is the Backbone: The highway connecting all the Airports in the Global Network.<br>
- The Datacenters are the Airlines operating their Aircrafts (Servers: Clusters/Nodes).<br>
- Coffee Pie® is the Admin of the Airport: The infrastructure glue, the control tower, and the ticketing system, abstracting all the complexity, operating, maintenance and marketing costs, for directly connecting supply and demand in real time.<br>
- The Codec Terminal is your remote controller (thin-client): A dirt-cheap, modular, durable, easily repairable, upgradeable and highly recyclable standardized device that connects you to your machine/s in the cloud, although your data is yours, just sync it locally and take it away whenever you want, no ties, no high costs, no maintenance, no complex setups, no heat, no noise, no e-waste.<br>
- The Slices are the "tickets" (the seats in the airplane).<br>
 
 📐 The Atomic Unit - Coffee Pie® Slice:
We don't sell "computers", we rent slices. Each slice is a standardized deterministic portion of hardware resources (the Quanto in QFDM), regardless of the physical Node configuration. They can be added together like lego bricks or shipping containers to get more powerful and capable machines (vertical scaling), according to your needs:<br>

| Resource | Capacity | Description |
|---|---|---|
| PWR | 1 Wh | Max electrical consumption per hour |
| CPU | 1 vCore | Logical thread for serial processing (x86-64) |
| RAM | 1 GB | Volatile memory |
| SSD | 8 GB | High-speed for OS & App storage |
| HDD | 125 GB | Low-speed bulk storage & backups |
| NET | 8 Mbps | Guaranteed backend bandwidth |
| GPU | 125 MB | VRAM for parallel processing (Vulkan, DirectX, SR-IOV) |
| RES | 15 vMPX/s | Max virtual pixels per second streaming (perceived) |
| IA | 3 TOPS | INT8 parallel processing capacity |

> Anti-Abuse Guardrail: If an instance exceeds its power limit then warnings, automatic AI Agent observation and recording will be triggered for human audit, if violating Law or community rules (e.g., unauthorized pentesting, cryptomining, spamming, fake news, etc), it will lead to temporary account suspension or even permanent ban, depending on the severity of the violation or repeated offenses. Note: Cryptocurrency mining is strictly prohibited, but crypto transactions are allowed if regional Law permits. We want to save the planet, not the bots!...<br>

 🏗 System Architecture:<br>
 1. The Orchestrator (The Traffic Guard): Based on OpenUDS v4.0, heavily customized for ultra-low latency streaming. It manages the connection between the frontend and the available nodes, regardless of the Type 1 Hypervisor being used by the Datacenters (Proxmox Recommended).<br>
 2. The Providers (The Brain): Datacenters and companies with structured hardware willing to monetize their unused hardware in the Ecosystem.<br>
 3. The Codec Terminal (The Remote Controller):<br>
ARM-based SBCs (Radxa, Orange Pi, custom RISC-V, etc) running:<br>
  - Operating System: Debian Minimal.<br>
  - Display Server: Wayland
  - Window Manager: Sway (Kiosk Mode).<br>
  - Graphical User Interface: Coffee Pie® Qt.<br>
  - Connectivity: USB-IP for local peripherals + QFDM Protocol (Sunshine/Moonlight based for ultra-low latency).<br>
 4. The Frontend: A lightweight package that manages TCP credentials and UDP streaming protocols. Available in GUI (Qt) for casual users, and also CLI for experienced IT Admins (Ctrl + Alt + T).<br>

 ⚖️ Licensing & Contribution (The Social Contract):<br>
Coffee Pie® is full open hardware and mostly open software. To protect our path to a 2035 IPO and ensure the ecosystem remains standardized, we use a tiered licensing model:
- QFDM Core & Orchestrator: Open Core. The core orchestration and QFDM Backend components are source-available under a proprietary Open Core license, granting free use for personal and small-scale deployments, while any commercial use — by codec terminal manufacturers, large-scale deployments, enterprise use and potential competitors — is subject to QFDM Royalty Fees for use of the patented QFDM system (Patent NC2025/0012723), payable as patent royalties rather than a software license fee.<br>
- Frontend & Drivers: Apache 2.0. We want these everywhere.<br>
- Hardware Design: CERN Open Hardware License. Easily repairable and upgradeable.<br>
- Contributing: We welcome anyone to contribute, but by contributing, you agree to our Contributor License Agreement (CLA) to keep the project commercially viable for its "BIC status" (Benefit and Collective Interest, in middle-ground between private company and NGO).<br>

💰 Monetization & Ethics:<br>
 We are guided by ethical and stoic principles — Meritocracy, Ataraxia, Areté, Eudaimonia — and we measure our success mainly by positive social and environmental impact, not just profits and ROI.<br>
 
 1. Free Tier: Advertisers pay for the computing power, ideal for casual users (Ads on-demand).<br>
 2. Credits Packages: No interruptions, high-performance and more resources for professionals and casual gamers.<br>
 3. B2B / ISP Licensing: Royalties from manufacturers and ISPs renting codec terminals to third parties.<br>
 4. Circular Services: Preventive maintenance, repair, remanufacturing, recycling and/or safe final disposal.<br>
 5. B2G: Public Sector (technological sovereignty for governments).<br>
 - At least 10% of the profits will be used for granting internet access and terminal codecs in developing countries, mainly through libraries, elementary schools, high-schools, universities, cybercafes, NGOs, etc, until every human being, willing to, has access to our service.<br>

❌ Strictly Prohibited in the Ecosystem:<br>
❌ NEITHER governments nor third parties will have access to users' private info, unless supplied a valid court order directly issued and sent by a judge from verified emails (.gov), duly processed through the Coffee Pie® Legal Department: legal@coffeepie.co.<br>
❌ Illegal Content: Including, but not limited to, illicit drugs, counterfeit products and services that violate the law.<br>
❌ Hate and Discrimination: Content that attacks or degrades groups based on race, religion, gender, sexual orientation or disability. All software and hardware, free, open or proprietary, is welcome to the community, as long as aligning with the Circular Economy Principles.<br>
❌ Violence and Disturbing Content: Incitement to violence, terrorism, animal cruelty or graphic images of damage.<br>
❌ The service is NOT meant nor allowed for military or warlike purposes.<br>
❌ Weapons and Explosives: Promotion of the sale of firearms, ammunition or explosive material.<br>
❌ Deceptive Practices: Scams, malware, phishing or fraudulent financial promises.<br>
❌ Cryptocurrency Mining: Mining any kind of cryptocurrency is strictly prohibited (you better get an ASIC for that), but cryptocurrencies and cryptoassets related transactions are allowed only if the Law allows it, consult your local jurisdiction's regulations.<br>

 🎯 The Goals:<br>
 2030: Becoming an Open, Reliable, Global Standard and the Backbone of Computing.<br>
 2035: Initial Public Offering (IPO) or Tokenization (TRC20) by the end of 2035.<br>
 2040: 1'000'000'000 active users in the QFDM Network.<br>
 2050: Guaranteed Global Access to a Codec Terminal.<br>
 
 💎 COFP Token: Coffee Pie®'s native utility token (TRC-20 on TRON), symbol COFP, it is NOT a fiat currency nor a regulated asset. **Token unit: 1 COFP = 1 Coffee Pie® Slice served for 1 minute.** Earnings scale linearly (e.g., a Provider hosting 4 Slices for 60 minutes earns 4 × 60 = 240 COFP). Smart contract: `blockchain/COFP_Token.sol`, deployment guide at `blockchain/DEPLOY.md`. **Elastic supply model**: initial supply of 100'000'000 COFP. New tokens are emitted at a fixed rate of 1 COFP per Slice·min by Providers, supply grows organically with the network. No supply cap. **Two-currency model**: COFP is exclusively for Providers and Contributors. End users (consumers) never hold or interact with COFP, but operate entirely with Coffee Pie® Credits (Cr), obtained by watching Ads (paid by Advertisers) or purchasing Credit Packages at `coffeepie.co/prices`. COFP tokens confer different rights depending on how they were acquired:

  * Contributors (Community Developers, Moderators, Translators, Auditors, Tech Supporters, etc.): Earn COFP by contributing to the ecosystem (code, documentation, translations, moderation, community support, etc.). Rights: vote on technical decisions (development stack, deprecation policies, implementation priorities). Wallet holding limit: 100'000'000'000 COFP per wallet (or 10% of the total supply), enforced by the Coffee Pie® backend. Contributors may: (a) sell earned COFP on the TRON open market (TRC-20), the seller permanently loses all voting rights, the buyer receives an Investor-class token with economic rights only; (b) hold COFP for long-term valuation appreciation and future dividends after IPO; (c) burn COFP for Credits at a rate of 10 Cr per COFP. **Contributors cannot burn COFP for fiat**, that right is exclusive to Providers.

  * Trusted Providers (Datacenter Operators): Earn COFP by supplying computing resources to the QFDM Network at a rate of **1 COFP per Slice per minute** (e.g., hosting 4 Slices for 60 minutes = 240 COFP). Rights: vote on regional pricing (average slice cost, electricity rates, labor costs); burn tokens for fiat currency transferred to their registered bank accounts within 24-72 hours (no burning cap, providers are selling real resources). Provider settlement is an internal ledger operation, provider-earned COFP is not publicly tradeable. **Important**: if a provider transfers COFP to a secondary wallet and sells on the open market, those tokens lose all voting and burning-for-fiat rights, the buyer receives an Investor-class token.

  * Investors (BVC Stock Exchange): Acquire COFP through public markets. Rights: proportional dividends and valuation appreciation. No voting rights in technical or operational decisions; their sole governance function is the binary choice of reinvesting profits versus distributing dividends.

  **Two-Currency Model**: Coffee Pie® operates two strictly separate currencies. **COFP** (TRC-20 on TRON) is the supply-side token: only Providers and Contributors earn it, and only Providers may burn it for fiat cash flow (transferred to their registered bank account within 24-72 hours) to sustain datacenter operations, this is an internal ledger operation, not a public token redemption. **Credits (Cr)** are the demand-side consumer currency: end users obtain Cr exclusively by watching Ads (paid by Advertisers) or purchasing Credit Packages at `coffeepie.co/prices`, then spend Cr to rent computing Slices. Consumers never hold, earn, or interact with COFP directly. Contributors may burn COFP for Credits at a rate of 10 Cr per COFP. Monetary policy: Elastic supply, COFP is emitted at a fixed rate of 1 COFP per Slice·min served by Providers on the QFDM Network. Initial supply of 100'000'000 COFP. No supply cap. Coffee Pie® is not a bank; COFP is more like a contribution score representing the relevance of Providers and Contributors within the QFDM Network, granting proportional voting weight. The more time, talent, and capital at risk, the more voting power, but that power naturally dilutes as new contributors earn their stake, preventing plutocratic or populist capture of the Ecosystem.
 <br>
 <br>
 BIC Status: A private capital company with socio-environmental consciousness.<br>

No Controlling Stakes: No single entity will own the majority. Coffee Pie® belongs to the community and the conscious investors prioritizing humanity and environment over profits. Maximum private ownership is limited to 10% aside the founder.<br>

"Competition is the law of the jungle, cooperation the law of civilization."<br>

🌍 Ready to slice the future? Check the Wiki | Join the Dev Discord | Invest in the Planet 🌳
