# Coffee Pie Codec Terminals — Manufacturer Guide

## Overview

Coffee Pie Codec Terminals are dirt-cheap, highly modular, highly durable,
easily repairable, upgradeable, and infinitely recyclable ARM SBC devices
that connect end users to the QFDM Network. They decode ultra-low-latency
video/audio streams (H.264 and/or AV1) and relay USB peripherals via USB-IP
to the user's cloud desktop.

All hardware designs are open source under **CERN-OHL-S v2 + Coffee Pie
Circular Economy Addendum** (see `hardware/LICENSE`). Anyone may freely
study, manufacture, modify, and distribute these devices. Commercial
connection to the QFDM Backend requires a dirt-cheap license (cents per
terminal per month).

## Product Lines

### Commander (Basic Codec Terminal)

| Spec | Value |
|---|---|
| Decoding | 4K@60Hz H.264 HW decode |
| NPU | AI real-time upscaling (basic) |
| Connectivity | Ethernet PoE (100 Mbps) |
| RAM | 2 GB LPDDR4 |
| Storage | 16 GB eMMC |
| Display Output | HDMI 2.0 |
| USB | 2x USB 2.0 (USB-IP peripherals) |
| Reference SBC | Radxa Zero 3E |
| Target Price (BOM) | < 25 USD |
| Target Users | Home users, students, libraries, NGOs |

### Sentinel (Mid-Tier Codec Terminal)

| Spec | Value |
|---|---|
| Decoding | 4K@60Hz H.264 + AV1 HW decode |
| NPU | AI real-time upscaling (enhanced) |
| Connectivity | Gigabit Ethernet PoE + Wi-Fi 6 |
| RAM | 4 GB LPDDR4X |
| Storage | 32 GB eMMC |
| Display Output | HDMI 2.1 |
| USB | 2x USB 3.0 + 1x USB-C (USB-IP peripherals) |
| Reference SBC | TBD |
| Target Price (BOM) | < 45 USD |
| Target Users | Professionals, SMEs, public sector |

### Ranger (Pro Codec Terminal)

| Spec | Value |
|---|---|
| Decoding | 4K@120Hz or 8K@60Hz AV1 HW decode |
| NPU | AI real-time upscaling (advanced, zero added latency) |
| Connectivity | Optical Fiber (1 Gbps) + Wi-Fi 6E |
| RAM | 8 GB LPDDR5 |
| Storage | 64 GB eMMC + NVMe slot |
| Display Output | DisplayPort 2.0 + HDMI 2.1 |
| USB | 4x USB 3.1 (USB-IP peripherals) |
| Reference SBC | TBD |
| Target Price (BOM) | < 98 USD |
| Target Users | Engineers, designers, data scientists, gamers |

## Folder Structure

```
hardware/
├── LICENSE                          # CERN-OHL-S v2 + Circular Economy Addendum
├── README.md                        # This file
├── commander/                       # Commander model (Radxa Zero 3E based)
│   ├── schematics/                  # Electrical schematics (PDF)
│   ├── pcb/                         # PCB layout files (Gerber, KiCad)
│   ├── fabrication/                 # Manufacturing outputs
│   │   ├── gerber/                  # PCB fabrication files
│   │   ├── bom/                     # Bill of materials
│   │   └── position/               # Pick-and-place / component placement
│   ├── 3d-models/                   # 3D enclosure models (SKP, OBJ, STEP)
│   └── 2d-models/                   # 2D technical drawings (DXF)
├── sentinel/                        # Sentinel model (TBD SBC)
│   └── (same structure)
└── ranger/                          # Ranger model (TBD SBC)
    └── (same structure)
```

## How to Manufacture

### 1. Review the License

Read `hardware/LICENSE` carefully. The CERN-OHL-S v2 (Part I) governs the
hardware designs. The Circular Economy Addendum (Part II) adds Coffee Pie
specific obligations: repairability, spare parts availability for 10 years,
end-of-life takeback, zero landfill, no planned obsolescence.

### 2. Study the Reference Designs

Each model folder contains everything needed to reproduce the device:
schematics, PCB layouts, BOM, enclosure models, and technical drawings.

### 3. Build Prototypes

You are free to build as many prototypes as you want at zero royalty cost.
No license is needed for personal, educational, or research use (up to 9
terminals).

### 4. Get Certified (Optional but Recommended)

To sell devices under the Coffee Pie brand or as "Coffee Pie Certified":

1. Submit your design at: https://www.coffeepie.co/fabricantes
2. Demonstrate compliance with the Circular Economy Obligations (Section C
   of the License)
3. Execute a Brand License Agreement with Grupo 3P1 Colombia

OEM/White-Label manufacturing (under your own brand) does not require
certification or a brand agreement — just the QFDM Backend License.

### 5. Obtain QFDM Backend License

If the terminals will connect to the QFDM Backend for commercial use
(renting to third parties), a license is required:

| Terminals | USD/terminal/month |
|---|---|
| 1 – 999 | 1.00 |
| 1'000 – 9'999 | 0.90 |
| 10'000 – 99'999 | 0.70 |
| 100'000 – 999'999 | 0.50 |
| 1'000'000+ | 0.30 |

Licenses are obtained at: https://www.coffeepie.co/panel (Licensing Tab)

## ISP / Rental Model

ISPs and rental companies are the primary distribution channel. They can:

- **Manufacture themselves** or through third parties, paying only the
  QFDM Backend License per terminal.
- **Offer terminals free to customers** (the license cost is absorbed by
  the ISP) or **charge a small monthly fee** for the service.
- **White-label** under their own brand without additional certification.
- **Benefit from the Community Incentive Program**: 1% monthly credit on
  active device rental value, usable for Coffee Pie services or promotion.

## Community Incentive Program

Manufacturers with devices actively in service within the Coffee Pie
ecosystem receive a monthly credit incentive of 1% of the rented asset
value per active device, distributed as non-refundable platform credits.

## Circular Economy — Non-Negotiable

Every Codec Terminal manufactured under this license must:

- Achieve a repairability score of **9/10** or higher (iFixit methodology)
- Guarantee spare parts availability for **10 years** from last manufacture
- Accept **free end-of-life returns** from users for remanufacturing,
  component harvesting, or certified recycling
- **Zero landfill, zero incineration** — every gram returns to the cycle
- Maintain **material traceability** records for all primary materials

These obligations are binding. Violation terminates the license.

## Quick Links

| Resource | URL |
|---|---|
| Manufacturer Registration | https://www.coffeepie.co/fabricantes |
| Licensing Dashboard | https://www.coffeepie.co/panel |
| Certified Service Partners | https://www.coffeepie.co/dispositivos-certificados |
| Reference SBC Info | https://wiki.radxa.com/Zero3E |
| iFixit Repairability | https://www.ifixit.com/repairability |

Copyright (C) 2025 Grupo 3P1 Colombia. Patent NC2025/0012723.
