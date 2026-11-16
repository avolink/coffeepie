"""Commander mainboard design model.

Reads the hand-maintained netlist sources in src/netlist/*.net and the part
definitions below, and exposes one consistent in-memory model that the symbol,
schematic, PCB and BOM generators all share.  Pure Python (runs under both the
system interpreter and KiCad's bundled one).

Netlist syntax (one statement per line, '#' starts a comment):
  SHEET <name>                      following components belong to this sheet
  <REF> <VALUE> <net1> <net2>       two-pin part; prefix R/C/L/FB/F picks the kind
  <REF> <PART>[:<VALUE>] pin=net... multi-pin part (PART is a key of PARTS)
  P <REF> pin=net ...               more pin assignments for an existing part
  N <REF> <net> pin pin ...         same, written net-first (handy for supplies)
  NC <REF> pin pin ...              pins deliberately left unconnected
  CAPS C<a>-C<b> <VALUE> <n1> <n2>  a run of identical two-pin parts
  TP<n> TP <net>                    test point
Value "DNP" (or PART:DNP) marks a part as not populated.
"""
import csv
import glob
import os
import re
from collections import OrderedDict, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
# CP_ROOT selects the project directory the tools work on (default: the mainboard these tools live in).
ROOT = os.path.normpath(os.environ.get("CP_ROOT") or os.path.join(HERE, ".."))
PRJ = os.path.basename(ROOT)                    # project name = directory name = KiCad file stem
VARIANT = ("strip" if PRJ.endswith("strip_test") else "kbmcu" if PRJ.endswith("keyboard_mcu")
           else "hub" if PRJ.endswith("commander_hub")
           else "kbd" if PRJ.endswith("commander_keyboard")
           else "hat" if PRJ.endswith("poe_hat")
           else "batt" if PRJ.endswith("commander_battery")
           else "numpad" if PRJ.endswith("commander_numpad")
           else "touch" if PRJ.endswith("commander_touchpad")
           else "tray" if PRJ.endswith("commander_tray") else "main")
REV = {"strip": "revT0", "kbmcu": "revK0", "kbd": "revK1", "hat": "revH0", "hub": "revU0",
       "batt": "revB0", "numpad": "revN0", "touch": "revP0", "tray": "revR0"}.get(VARIANT, "revA1")
SMALL = VARIANT in ("batt", "numpad", "touch", "tray")  # two-layer module boards built by tools/small_board.py
NETDIR = os.path.join(ROOT, "src", "netlist")
MAIN_NETDIR = os.path.normpath(os.path.join(HERE, "..", "src", "netlist"))


def net_files(netdir=NETDIR):
    """Netlist files of the project, in sheet order.  A variant lists in src/netlist/shared.txt the
    files it takes unchanged from the mainboard, so there is one source for the shared circuitry."""
    files = glob.glob(os.path.join(netdir, "*.net"))
    shared = os.path.join(netdir, "shared.txt")
    if os.path.exists(shared):
        for line in open(shared, encoding="utf-8"):
            name = line.split("#", 1)[0].strip()
            if name:
                files.append(os.path.join(MAIN_NETDIR, name))
    return sorted(files, key=os.path.basename)

# --------------------------------------------------------------------------
# footprints
# --------------------------------------------------------------------------
FP_R0402 = "Resistor_SMD:R_0402_1005Metric"
FP_C0402 = "Capacitor_SMD:C_0402_1005Metric"
FP_C0603 = "Capacitor_SMD:C_0603_1608Metric"
FP_C0805 = "Capacitor_SMD:C_0805_2012Metric"
FP_C1206 = "Capacitor_SMD:C_1206_3216Metric"
FP_L0402 = "Inductor_SMD:L_0402_1005Metric"


def footprint_for_two_pin(kind, value):
    """Package choice for R / C / L / FB by value (first-pass, cost-oriented: 0402 wherever possible)."""
    v = value.upper()
    for size, lib in (("_0603", "0603_1608Metric"), ("_0805", "0805_2012Metric"), ("_1206", "1206_3216Metric")):
        if v.endswith(size) and kind in ("R", "C"):         # an explicit size in the value wins (the keyboard is 0805 / 0603)
            return ("Resistor_SMD:R_" if kind == "R" else "Capacitor_SMD:C_") + lib
    if kind == "R":
        if "1W" in v:
            return "Resistor_SMD:R_2512_6332Metric"
        if v.startswith("FB120R_3A"):
            return "Inductor_SMD:L_0805_2012Metric"
        if v.startswith("FB"):
            return FP_L0402
        return FP_R0402
    if kind == "FB":
        return "Inductor_SMD:L_0603_1608Metric"
    if kind == "F":
        return "Fuse:Fuse_1206_3216Metric"
    if kind == "C":
        if "_ALU" in v:
            return "Capacitor_SMD:CP_Elec_6.3x7.7"
        if "_POLY" in v:
            return "Capacitor_Tantalum_SMD:CP_EIA-7343-20_Kemet-V"      # 2.0 mm tall (the -31 case is 3.1 mm)
        if "2KV" in v:
            return "Capacitor_SMD:C_1808_4520Metric"
        if "100V" in v:
            return "Capacitor_SMD:C_1210_3225Metric" if v.startswith("2.2UF") else FP_C0805
        if v.startswith(("47UF",)):
            return FP_C1206
        if v.startswith(("22UF",)):
            return FP_C0805
        if v.startswith(("10UF", "4.7UF")):
            return FP_C0603
        return FP_C0402
    if kind == "L":
        if "2520" in v:
            return "Inductor_SMD:L_1008_2520Metric"
        if "5A" in v:
            return "Inductor_SMD:L_Coilcraft_XAL4020-XXX"               # 4 x 4 x 2.1 mm (the SRP5030T is 3.0 mm tall)
        if "2A" in v:
            return "Inductor_SMD:L_Sunlord_SWPA4030S"
        return "Inductor_SMD:L_0805_2012Metric"
    raise ValueError(kind)


def seq(n, start=1):
    return [str(i) for i in range(start, start + n)]


def named(spec):
    """'1:SCL 2:SDA ...' -> [(num, name), ...]"""
    return [tuple(t.split(":", 1)) for t in spec.split()]


# --------------------------------------------------------------------------
# part definitions
#   fp      footprint (lib:name); custom ones live in lib/commander.pretty
#   pins    [(pin_id, name)] in drawing order, or None -> taken from the netlist
#   padmap  pin_id -> pad name(s) on the footprint (default: identical)
#   two     True for simple two-terminal parts drawn inline
# --------------------------------------------------------------------------
PARTS = {
    "RK3566": dict(fp="commander:RK3566_FCCSP-565_15.5x14.4mm", pins=None, desc="Rockchip RK3566 SoC, FCCSP-565"),
    # 1 GB / 8 GB since 2026-11-15 (cost target; the 2 GB K4F6E3S4HM and the 16 GB KLMAG1JETD-B041 fit the same footprints)
    "LPDDR4_200": dict(fp="Package_BGA:BGA-200_10x14.5mm_Layout12x22_P0.8x0.65mm", pins=None, lcsc="C2920231",
                       desc="LPDDR4 SDRAM 200-ball FBGA, 1 GB (8 Gb, x32 dual channel): Samsung K4F8E3S4HD-MGCL"),
    "EMMC153": dict(fp="Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm", pins=None, fill_nc=True, lcsc="C499918",
                    desc="eMMC 5.1 153-ball, 8 GB: Samsung KLM8G1GETF-B041"),
    "RK817": dict(fp="Package_DFN_QFN:ArtInChip_QFN-68-1EP_7x7mm_P0.35mm_EP5.49x5.49mm", desc="Rockchip RK817-5 PMIC + codec, QFN-68", pins=named(
        "1:SCL 2:SDA 3:LDO7 4:VCC7 5:LDO8 6:LDO9 7:INT 8:FB2 9:SW2 10:VCC2 11:VCC1 12:SW1 13:FB1 14:LRCLK 15:BCLK 16:MCLK 17:SDI "
        "18:SDO/PDMDATA 19:PDMCLK 20:LDO3 21:LDO2 22:VCC5 23:LDO1 24:VCC3 25:SW3 26:VBUCK3 27:FB3 28:LDO4 29:LDO5 30:VCC6 31:LDO6 "
        "32:SPK_OUTP 33:VCC_SPK_HP 34:SPK_OUTN 35:VCC_CPVSS 36:CPN 37:CPP 38:VCC_CPVDD 39:HPL_OUT 40:HP_SNS 41:HPR_OUT 42:MIC1N 43:MIC1P "
        "44:VCC_1P8A 45:VCC_RTC 46:VREF 47:GNDREF 48:VCC_1P8D 49:SLEEP 50:XIN 51:XOUT 52:PWRON 53:SW5 54:MIDU 55:USB 56:BAT1 57:BAT2 "
        "58:SYS1 59:SYS2 60:GATE 61:TS/GPIO 62:SNSP 63:SNSN 64:FB4 65:SW4 66:VCC4 67:RESETB 68:CLK32K 69:EPAD")),
    "RK860": dict(fp="Package_CSP:Anpec_WLCSP-20_1.76x2.03mm_Layout4x5_P0.4mm", desc="Rockchip RK860-0 buck (VDD_CPU), WLCSP-20", pins=named(
        "D1:VIN D2:VIN E1:VIN E2:VIN A2:EN A1:VSEL B1:SDA A3:SCL B4:AGND D3:SW D4:SW E3:SW E4:SW A4:VOUT B2:GND B3:GND C1:GND C2:GND C3:GND C4:GND")),
    "RTL8211F": dict(fp="Package_DFN_QFN:QFN-40-1EP_5x5mm_P0.4mm_EP3.8x3.8mm", desc="Realtek RTL8211F-CG GbE PHY, QFN-40", pins=named(
        "1:MDI0+ 2:MDI0- 3:AVDD10 4:MDI1+ 5:MDI1- 6:MDI2+ 7:MDI2- 8:AVDD10 9:MDI3+ 10:MDI3- 11:AVDD33 12:PHYRSTB 13:MDC 14:MDIO 15:TXD3 "
        "16:TXD2 17:TXD1 18:TXD0 19:TXCTL 20:TXC 21:DVDD10 22:RXD3/PHYAD0 23:RXD2/PLLOFF 24:RXD1/TXDLY 25:RXD0/RXDLY 26:RXCTL/PHYAD2 "
        "27:RXC/PHYAD1 28:DVDD_RG 29:DVDD33 30:REG_OUT 31:INTB/PMEB 32:LED0/CFG_EXT 33:LED1/CFG_LDO0 34:LED2/CFG_LDO1 35:CLKOUT 36:XTAL_IN "
        "37:XTAL_OUT 38:AVDD10 39:RSET 40:AVDD33 41:EPAD")),
    "UM3204H": dict(fp="commander:WLCSP-12_3x4_P0.5mm", desc="Union UM3204H 4-ch level shifter (HDMI DDC/CEC), WLCSP-12", pins=named(
        "A2:VCCB B2:VCCA C2:OE D2:GND A1:B1 B1:B2 C1:B3 D1:B4 A3:A1 B3:A2 C3:A3 D3:A4")),
    "TPD4E05U06": dict(fp="Package_SON:USON-10_2.5x1.0mm_P0.5mm", desc="TI TPD4E05U06 4-ch ESD, flow-through", pins=named(
        "1:IO1 2:IO2 3:GND 4:IO3 5:IO4 6:IO4 7:IO3 8:GND 9:IO2 10:IO1")),
    "USBLC6-2SC6": dict(fp="Package_TO_SOT_SMD:SOT-23-6", desc="ST USBLC6-2SC6 USB ESD", pins=named(
        "1:IO1 2:GND 3:IO2 4:IO2 5:VBUS 6:IO1")),
    "HDMI_MICRO_D": dict(fp="Connector_Video:HDMI_Micro-D_Molex_46765-2xxx", desc="micro HDMI (type D) receptacle", padmap={"SH": ["SH"]},
                         pins=named("1:HPD 2:UTILITY 3:D2+ 4:D2_SH 5:D2- 6:D1+ 7:D1_SH 8:D1- 9:D0+ 10:D0_SH 11:D0- 12:CK+ 13:CK_SH 14:CK- "
                                    "15:CEC 16:GND 17:SCL 18:SDA 19:+5V SH:SHIELD")),
    "RJ45_8P": dict(fp="commander:RJ45_HR6042S_8P8C_LowProfile", desc="RJ45 8P8C, no magnetics, low profile (Radxa: HanRun HR6042S-1188N15B-1R)",
                    padmap={"SH": ["SH"]}, pins=named("1:TX+ 2:TX- 3:RX+ 4:TN1 5:TN2 6:RX- 7:RN1 8:RN2 SH:SHIELD")),
    "MICROSD": dict(fp="Connector_Card:microSD_HC_Molex_104031-0811", desc="microSD push-push socket",
                    padmap={"CD": ["9"], "SH": ["SH", "10"]},
                    pins=named("1:DAT2 2:CD/DAT3 3:CMD 4:VDD 5:CLK 6:VSS 7:DAT0 8:DAT1 CD:DET SH:SHIELD")),
    # HOAUC HYCW498-USBC16-735B is a TYPE-C-31-M-12 clone: same land pattern (pad row 1.45 mm behind the locating holes,
    # shell slots 0.53 / 3.65 mm from them, outer pads 0.05 mm further in) - the HRO footprint stays
    "USBC16": dict(fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", lcsc="C42400252",
                   desc="USB-C receptacle, USB 2.0, 16-pin (HOAUC HYCW498-USBC16-735B, or HRO TYPE-C-31-M-12)",
                   padmap={"SH": ["SH"]},
                   pins=named("A1:GND A4:VBUS A5:CC1 A6:D+ A7:D- A8:SBU1 A9:VBUS A12:GND B1:GND B4:VBUS B5:CC2 B6:D+ B7:D- B8:SBU2 B9:VBUS B12:GND SH:SHIELD")),
    "USBC24": dict(fp="commander:USB_C_Receptacle_HOAUC_HYCW275-USBC24-050B", lcsc="C42400261",
                   desc="USB-C receptacle, full-featured 24-pin, right angle, top mount (HOAUC HYCW275-USBC24-050B)",
                   padmap={"SH": ["SH"]},
                   pins=named("A1:GND A2:TX1+ A3:TX1- A4:VBUS A5:CC1 A6:D+ A7:D- A8:SBU1 A9:VBUS A10:RX2- A11:RX2+ A12:GND "
                              "B1:GND B2:TX2+ B3:TX2- B4:VBUS B5:CC2 B6:D+ B7:D- B8:SBU2 B9:VBUS B10:RX1- B11:RX1+ B12:GND SH:SHIELD")),
    "USB5744": dict(fp="Package_DFN_QFN:QFN-56-1EP_7x7mm_P0.4mm_EP5.6x5.6mm", desc="Microchip USB5744 4-port USB 3.2 Gen 1 hub, VQFN-56", pins=named(
        "1:USB2DN_DP1 2:USB2DN_DM1 3:USB3DN_TXDP1 4:USB3DN_TXDM1 5:VDD12 6:USB3DN_RXDP1 7:USB3DN_RXDM1 8:USB2DN_DP2 9:USB2DN_DM2 "
        "10:USB3DN_TXDP2 11:USB3DN_TXDM2 12:VDD12 13:USB3DN_RXDP2 14:USB3DN_RXDM2 15:VDD12 16:VDD33 17:USB2DN_DP3 18:USB2DN_DM3 "
        "19:USB3DN_TXDP3 20:USB3DN_TXDM3 21:VDD12 22:USB3DN_RXDP3 23:USB3DN_RXDM3 24:USB2DN_DP4 25:USB2DN_DM4 26:USB3DN_TXDP4 "
        "27:USB3DN_TXDM4 28:VDD12 29:USB3DN_RXDP4 30:USB3DN_RXDM4 31:VDD33 32:PRT_CTL4/GANG_PWR 33:VDD12 34:PRT_CTL3 35:PRT_CTL2 "
        "36:PRT_CTL1 37:VBUS_DET 38:SPI_CLK/SMCLK 39:SPI_DO/SMDAT 40:SPI_DI/CFG_BC_EN 41:SPI_CE_N/CFG_NON_REM 42:RESET_N 43:VDD12 "
        "44:VDD33 45:USB2UP_DP 46:USB2UP_DM 47:USB3UP_TXDP 48:USB3UP_TXDM 49:VDD12 50:USB3UP_RXDP 51:USB3UP_RXDM 52:ATEST 53:XTALO "
        "54:XTALI/CLK_IN 55:VDD33 56:RBIAS 57:VSS(EP)")),
    "USB2517": dict(fp="Package_DFN_QFN:QFN-64-1EP_9x9mm_P0.5mm_EP7.3x7.3mm", desc="Microchip USB2517 7-port USB 2.0 hub, QFN-64", pins=named(
        "1:USBDN1_DM 2:USBDN1_DP 3:USBDN2_DM 4:USBDN2_DP 5:VDDA33 6:USBDN3_DM 7:USBDN3_DP 8:USBDN4_DM 9:USBDN4_DP 10:VDDA33 11:USBDN5_DM "
        "12:USBDN5_DP 13:CFG_SEL2 14:LED_B7_N 15:LED_A7_N 16:LED_B6_N 17:LED_A6_N 18:LED_B5_N 19:TEST 20:PRTPWR4 21:OCS4_N 22:OCS3_N "
        "23:PRTPWR3 24:VDD33CR 25:VDD18 26:PRTPWR2 27:OCS2_N 28:OCS1_N 29:PRTPWR1 30:PRTPWR5 31:LED_A5_N 32:LED_B4_N 33:LED_A4_N "
        "34:LED_B3_N/GANG_EN 35:OCS5_N 36:PRTPWR7 37:OCS7_N 38:OCS6_N 39:PRTPWR6 40:SDA/NON_REM1 41:SCL/CFG_SEL0 42:HS_IND/CFG_SEL1 "
        "43:RESET_N 44:VBUS_DET 45:SUSP_IND/NON_REM0 46:VDD33 47:LED_A3_N 48:LED_B2_N 49:LED_A2_N 50:LED_B1_N 51:LED_A1_N 52:VDDA33 "
        "53:USBDN6_DM 54:USBDN6_DP 55:USBDN7_DM 56:USBDN7_DP 57:VDDA33 58:USBUP_DM 59:USBUP_DP 60:XTAL2 61:XTAL1/CLKIN 62:VDD18PLL "
        "63:RBIAS 64:VDD33PLL 65:VSS(EP)")),
    "TPS23754": dict(fp="Package_SO:HTSSOP-20-1EP_4.4x6.5mm_P0.65mm_EP3.4x6.5mm", desc="TI TPS23754 PoE PD + DC/DC controller, HTSSOP-20", pins=named(
        "1:CTL 2:VB 3:CS 4:COM 5:GATE 6:VC 7:GAT2 8:ARTN 9:RTN 10:VSS 11:VDD1 12:VDD 13:DEN 14:PPD 15:CLS 16:DT 17:APD 18:BLNK 19:FRS 20:T2P 21:VSS(EP)")),
    "HD3SS3220": dict(fp="Package_DFN_QFN:Texas_RNH0030A_WQFN-30-1EP_2.5x4.5mm_P0.4mm_EP1.2x3.2mm",
                      desc="TI HD3SS3220 USB Type-C port controller with SuperSpeed 2:1 mux, VQFN-30 (RNH)", pins=named(
        "2:CC1 1:CC2 4:PORT 3:CURRENT_MODE 22:ADDR 29:ENn_CC 12:ENn_MUX 5:VBUS_DET 11:DIR 27:ID 23:INT_N/OUT3 24:VCONN_FAULT_N "
        "25:SDA/OUT1 26:SCL/OUT2 6:TXp 7:TXn 9:RXp 10:RXn 17:TX1p 16:TX1n 15:RX1p 14:RX1n 21:TX2p 20:TX2n 19:RX2p 18:RX2n "
        "30:VDD5 8:VCC33 13:GND 28:GND 31:EPAD")),
    "FUSB302B": dict(fp="Package_DFN_QFN:WQFN-14-1EP_2.5x2.5mm_P0.5mm_EP1.45x1.45mm", desc="onsemi FUSB302B USB-C port controller (or ET7301B), WQFN-14", pins=named(
        "1:CC2 2:VBUS 3:VDD 4:VDD 5:INT_N 6:SCL 7:SDA 8:GND 9:GND 10:CC1 11:CC1 12:VCONN 13:VCONN 14:CC2 15:EPAD")),
    "TPS2121": dict(fp="Package_DFN_QFN:Texas_VQFN-HR-12_2x2.5mm_P0.5mm", desc="TI TPS2121 power mux 2.8-22 V 4.5 A, fast switch-over, VQFN-HR-12", pins=named(
        "7:IN1 2:IN2 6:PR1 3:CP2 5:OV1 4:OV2 10:ILM 11:SS 9:ST 1:OUT 8:OUT 12:GND")),
    "PWRSW": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="USB power switch with fault flag", pins=named("5:IN 4:EN 3:FLG 2:GND 1:OUT")),
    "BUCK_SOT235": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="synchronous buck 2 A, SOT-23-5", pins=named("4:VIN 1:EN 5:FB 2:GND 3:SW")),
    "AT24C02": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="I2C EEPROM 2 kbit (AT24C02 / AT24CS02), SOT-23-5", pins=named("1:SCL 2:GND 3:SDA 4:VCC 5:WP")),
    "OPTO": dict(fp="Package_SO:SOP-4_4.4x2.6mm_P1.27mm", desc="optocoupler, 4-pin mini-flat SOP, 2.1 mm tall, 5 mm creepage (TLP291 / EL3H7 / LTV-217)",
                 pins=named("1:A 2:K 4:C 3:E")),
    "TL431": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="TL431 shunt reference, SOT-23 (DBZ pinout)", pins=named("1:K 2:REF 3:A")),
    "XFMR_FLYBACK": dict(fp="commander:XFMR_Bourns_PLN0xx-ER20",
                         desc="Bourns PLN060-ER20A05S planar PoE flyback transformer, 5 V out, 1 : 0.25 : 0.5, 40 uH, 200 kHz, 1500 Vrms, 8.0 mm tall",
                         pins=named("2:PRI+ 3:PRI_SW 4:AUX 1:AUX_RTN 6:SEC 5:SEC_RTN")),
    "XFMR6": dict(fp="commander:XFMR_LAN_1CH_6P", desc="single-channel LAN transformer 1:1 with centre taps (Radxa: GB020G00)",
                  pins=named("1:TD+ 6:TCT 2:TD- 5:MX+ 3:MCT 4:MX-")),
    "CMC": dict(fp="Inductor_SMD:L_CommonModeChoke_Coilank_ACM2012", desc="common-mode choke, 4-pad 0805",
                pins=named("1:A1 2:A2 4:B1 3:B2")),
    "XTAL4": dict(fp="Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm", desc="crystal, 4-pad 3225", pins=named("1:X1 2:GND 3:X2 4:GND")),
    "NMOS_GSD": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="N-MOSFET SOT-23", padmap={"G": ["1"], "S": ["2"], "D": ["3"]}, pins=named("G:G S:S D:D")),
    "PMOS_GSD": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="P-MOSFET SOT-23", padmap={"G": ["1"], "S": ["2"], "D": ["3"]}, pins=named("G:G S:S D:D")),
    "NMOS_PWR": dict(fp="Package_SO:Vishay_PowerPAK_1212-8_Single", desc="150 V N-MOSFET, PowerPAK 1212-8",
                     padmap={"S": ["1", "2", "3"], "G": ["4"], "D": ["5"]}, pins=named("G:G D:D S:S")),
    "JST_SH4": dict(fp="Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", desc="JST-SH 4-pin 1.0 mm", pins=named("1:VBUS 2:D- 3:D+ 4:GND")),
    "ATMEGA32U4": dict(fp="Package_QFP:TQFP-44_10x10mm_P0.8mm", desc="Microchip ATmega32U4-AU, TQFP-44 (the microcontroller of the Arduino Micro)", pins=named(
        "14:VCC 34:VCC 2:UVCC 7:VBUS 24:AVCC 44:AVCC 42:AREF 6:UCAP 3:D- 4:D+ 13:RESET_N 33:HWB/PE2 17:XTAL1 16:XTAL2 "
        "8:PB0 9:PB1 10:PB2 11:PB3 28:PB4 29:PB5 30:PB6 12:PB7 31:PC6 32:PC7 18:PD0 19:PD1 20:PD2 21:PD3 25:PD4 22:PD5 26:PD6 27:PD7 "
        "1:PE6 41:PF0 40:PF1 39:PF4 38:PF5 37:PF6 36:PF7 5:UGND 15:GND 23:GND 35:GND 43:GND")),
    "ISP2x3": dict(fp="Connector_PinHeader_2.54mm:PinHeader_2x03_P2.54mm_Vertical", desc="AVR ISP header 2x3, 2.54 mm",
                   pins=named("1:MISO 2:VCC 3:SCK 4:MOSI 5:RESET 6:GND")),
    # --- the keyboard (project commander_keyboard) ---
    "ATMEGA32U4_MU": dict(fp="Package_DFN_QFN:QFN-44-1EP_7x7mm_P0.5mm_EP5.2x5.2mm", desc="Microchip ATmega32U4-MU, QFN-44 7 x 7 mm (the microcontroller of the Arduino Micro)", pins=named(
        "14:VCC 34:VCC 2:UVCC 7:VBUS 24:AVCC 44:AVCC 42:AREF 6:UCAP 3:D- 4:D+ 13:RESET_N 33:HWB/PE2 17:XTAL1 16:XTAL2 "
        "8:PB0 9:PB1 10:PB2 11:PB3 28:PB4 29:PB5 30:PB6 12:PB7 31:PC6 32:PC7 18:PD0 19:PD1 20:PD2 21:PD3 25:PD4 22:PD5 26:PD6 27:PD7 "
        "1:PE6 41:PF0 40:PF1 39:PF4 38:PF5 37:PF6 36:PF7 5:UGND 15:GND 23:GND 35:GND 43:GND 45:EP")),
    # since 2026-11-15 (cost): STC8H8K64U, 5 V, crystal-less full-speed USB with its own USB boot loader (P3.2 low at
    # power-up), LQFP-32; pinout from the JLCEDA/EasyEDA Official Library symbol of C5210757 (https://easyeda.com)
    "STC8H_LQFP32": dict(fp="Package_QFP:LQFP-32_7x7mm_P0.8mm", lcsc="C5210757",
                         desc="STC STC8H8K64U-45I-LQFP32, 8051 MCU, 5 V, crystal-less USB 2.0 full speed, USB boot loader", pins=named(
        "1:P1.0 2:P1.1 3:P1.4 4:P1.5 5:P1.6 6:P1.7 7:P1.3 8:UCAP 9:P5.4 10:VCC 11:VREF 12:GND 13:P3.0/D- 14:P3.1/D+ 15:P3.2/BOOT "
        "16:P3.3 17:P3.4 18:P3.5 19:P3.6 20:P3.7 21:P2.0 22:P2.1 23:P2.2 24:P2.3 25:P2.4 26:P2.5 27:P2.6 28:P2.7 29:P0.0 30:P0.1 "
        "31:P0.2 32:P0.3")),
    "ISP2x3_PADS": dict(fp="commander:ISP_2x3_P2.54mm_Pads", desc="AVR ISP, six bare pads on the 2 x 3, 2.54 mm grid (for a pogo-pin adapter)",
                       pins=named("1:MISO 2:VCC 3:SCK 4:MOSI 5:RESET 6:GND")),
    # footprint taken over from the Altium design; pin roles are inferred from the circuit around the switch
    "KEYSW_OPT": dict(fp="commander:KeySwitch_Keychron_LP_Optical", desc="Keychron low-profile optical key switch",
                      pins=named("1:PT_E 2:PT_C 3:LED_A 4:G1 5:G2 6:LED_K")),
    "NPN_BEC": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="NPN transistor SOT-23", padmap={"B": ["1"], "E": ["2"], "C": ["3"]}, pins=named("B:B C:C E:E")),
    "JUMPER2": dict(fp="Connector_PinHeader_2.54mm:PinHeader_1x02_P2.54mm_Vertical", desc="2-pin header / jumper, 2.54 mm", pins=named("1:1 2:2")),
    "HDR1x4G": dict(fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", desc="pin header 1x4 2.54 mm", pins=named("1:P1 2:P2 3:P3 4:P4")),
    "HDR1x8G": dict(fp="Connector_PinHeader_2.54mm:PinHeader_1x08_P2.54mm_Vertical", desc="pin header 1x8 2.54 mm",
                    pins=named("1:P1 2:P2 3:P3 4:P4 5:P5 6:P6 7:P7 8:P8")),
    "HDR2x20": dict(fp="Connector_PinHeader_2.54mm:PinHeader_2x20_P2.54mm_Vertical", desc="pin header 2x20 2.54 mm (40-pin GPIO, ribbon cable or stacking socket)",
                    pins=named("1:3V3 2:5V 3:P3 4:5V 5:P5 6:GND 7:P7 8:P8 9:GND 10:P10 11:P11 12:P12 13:P13 14:GND 15:P15 16:P16 17:3V3 18:P18 19:P19 20:GND "
                               "21:P21 22:P22 23:P23 24:P24 25:GND 26:P26 27:P27 28:P28 29:P29 30:GND 31:P31 32:P32 33:P33 34:GND 35:P35 36:P36 37:P37 38:P38 39:GND 40:P40")),
    "JST_SH4_UART": dict(fp="Connector_JST:JST_SH_SM04B-SRSS-TB_1x04-1MP_P1.00mm_Horizontal", desc="JST-SH 4-pin 1.0 mm, horizontal, 2.95 mm tall (debug UART)",
                         pins=named("1:GND 2:TX 3:RX 4:3V3")),
    "HDR1x4": dict(fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", desc="pin header 1x4 2.54 mm", pins=named("1:GND 2:TX 3:RX 4:3V3")),
    # --- mainboard <-> hub board link (branch m2-hub, pinout in tools/hub_link.py) ---
    "M2_SOCKET_M": dict(fp="commander:M2_Socket_KeyM_LOTES_APCI0146", padmap={"MP": ["MP"]},
                        desc="M.2 Key M socket, top mount, 2.06 mm, 67 contacts 0.5 mm, 0.5 A each, 25 cycles: LOTES APCI0146-P002A "
                             "(10u\" gold; -P001A = LCSC C841645). Carries the hub board link (tools/hub_link.py), not an M.2 slot",
                        pins=None),
    "M2_EDGE_M": dict(fp="commander:M2_CardEdge_KeyM_Tongue",
                      desc="M.2 Key M card-edge fingers, 0.8 mm board, ENIG, bevelled (the hub board's plug into J41 on the mainboard)",
                      pins=None),
    # --- two-terminal parts with an explicit part name ---
    "ESD": dict(fp="Diode_SMD:D_0402_1005Metric", two="tvs", desc="ESD diode, bidirectional, 0402"),
    "TVS": dict(fp="Diode_SMD:D_SOD-123F", two="tvs", desc="TVS, bidirectional"),
    "TVS_UNI": dict(fp="Diode_SMD:D_SMA", two="diode", desc="TVS, unidirectional, SMA", padmap={"A": ["2"], "K": ["1"]}),
    "SCHOTTKY": dict(fp="Diode_SMD:D_SMA", two="diode", desc="Schottky diode", padmap={"A": ["2"], "K": ["1"]}),
    "SCHOTTKY_PWR": dict(fp="Diode_SMD:D_PowerDI-5", two="diode", desc="Schottky rectifier 10 A", padmap={"A": ["2"], "K": ["1"]}),
    "DIODE": dict(fp="Diode_SMD:D_SOD-123", two="diode", desc="diode", padmap={"A": ["2"], "K": ["1"]}),
    "LED": dict(fp="LED_SMD:LED_0603_1608Metric", two="led", desc="LED 0603", padmap={"A": ["2"], "K": ["1"]}),
    "PTC": dict(fp="Fuse:Fuse_1206_3216Metric", two="r", desc="resettable fuse"),
    "TACT": dict(fp="Button_Switch_SMD:SW_Push_1P1T_NO_CK_KMR2", two="sw", desc="tact switch"),
    "TACT_SIDE": dict(fp="Button_Switch_SMD:SW_SPST_EVQP7A", two="sw", desc="tact switch, side-operated (Panasonic EVQ-P7A, 3.5 x 2.9 x 1.35 mm)"),
    "XTAL2": dict(fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", two="xtal", desc="32.768 kHz crystal, 3215"),
    # --- battery module (project commander_battery) and tray modules (commander_numpad, commander_touchpad), 2026-11-16;
    #     pinouts from the JLCEDA/EasyEDA Official Library symbols of the LCSC parts named (https://easyeda.com) ---
    "MT3608": dict(fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C84817", desc="Aerosemi MT3608 boost converter 2 A switch, 1.2 MHz, SOT-23-6",
                   pins=named("1:SW 2:GND 3:FB 4:EN 5:IN 6:NC")),
    "TPS563201": dict(fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C116592", desc="TI TPS563201 synchronous buck 4.5-17 V, 3 A, Eco-mode (no sinking at light load), SOT-23-6",
                      pins=named("1:GND 2:SW 3:VIN 4:VFB 5:EN 6:VBST")),
    "HT7333": dict(fp="Package_TO_SOT_SMD:SOT-89-3", lcsc="C347191", desc="HT7333-A 3.3 V LDO, 12 V in, 4 uA quiescent, SOT-89",
                   pins=named("1:GND 2:VIN 3:VOUT")),
    "INA181A1": dict(fp="Package_TO_SOT_SMD:SOT-23-6", lcsc="C2058943", desc="TI INA181A1 bidirectional current-sense amplifier, gain 20, SOT-23-6",
                     pins=named("1:OUT 2:GND 3:IN+ 4:IN- 5:REF 6:VS")),
    "BAT54C": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="BAT54C dual Schottky, common cathode, SOT-23", pins=named("1:A1 2:A2 3:K")),
    "IQS550": dict(fp="Package_DFN_QFN:QFN-48-1EP_7x7mm_P0.5mm_EP5.6x5.6mm", lcsc="C5271144",
                   desc="Azoteq IQS550-B000 projected-capacitance trackpad controller, 15 Tx x 10 Rx, I2C, QFN-48", pins=named(
        "1:Tx14 2:PGM 3:SW_IN 4:NC4 5:SDA 6:SCL 7:VDDHI 8:VSS 9:VREG 10:NRST 11:RDY 12:NC12 13:Rx0A 14:Rx0B 15:Rx1A 16:Rx1B "
        "17:Rx2A 18:Rx2B 19:Rx3A 20:Rx3B 21:Rx4A 22:Rx4B 23:Rx5A 24:Rx5B 25:Rx6A 26:Rx6B 27:Rx7A 28:Rx7B 29:Rx8A 30:Rx8B "
        "31:Rx9A 32:Rx9B 33:Tx0 34:Tx1 35:Tx2 36:Tx3 37:VSSIO 38:VDDIO 39:Tx4 40:Tx5 41:Tx6 42:Tx7 43:Tx8 44:Tx9 45:Tx10 "
        "46:Tx11 47:Tx12 48:Tx13 49:EP")),
    "PTC1812": dict(fp="Fuse:Fuse_1812_4532Metric", two="r", desc="resettable fuse, 1812"),
    "TACT12": dict(fp="Button_Switch_THT:SW_PUSH-12mm", two="sw", lcsc="C10861",
                   desc="tactile switch 12 x 12 mm, through-hole (12x12x4.3 or x5 body for the 8 mm module; 12X12X7.3 = C10861 is the same footprint)"),
    "DOME12": dict(fp="commander:Dome_12mm_4Leg", two="sw",
                   desc="12 mm four-leg metal snap dome on gold pads (dome sheet, not soldered): centre = key, legs = ground"),
    "JST_PH4": dict(fp="Connector_JST:JST_PH_B4B-PH-K_1x04_P2.00mm_Vertical", lcsc="C131334", desc="JST PH 4-pin 2.0 mm, vertical (2 A per contact)",
                    pins=named("1:P1 2:P2 3:P3 4:P4")),
    "JST_PH2": dict(fp="Connector_JST:JST_PH_B2B-PH-K_1x02_P2.00mm_Vertical", desc="JST PH 2-pin 2.0 mm, vertical (B2B-PH-K-S)",
                    pins=named("1:P1 2:P2")),
    # --- tray carrier for two Framework Laptop 16 B-size input modules (project commander_tray), 2026-11-16 ---
    "CH334P": dict(fp="Package_DFN_QFN:QFN-16-1EP_3x3mm_P0.5mm_EP1.7x1.7mm", lcsc="C5373042",
                   desc="WCH CH334P 4-port USB 2.0 hub (MTT), internal 3.3 V regulator and crystal load capacitors, QFN-16 3 x 3",
                   pins=named("1:XO 2:XI 3:DM4 4:DP4 5:DM3 6:DP3 7:DM2 8:DP2 9:DM1 10:DP1 11:DMU 12:DPU 13:RESET#/CDP "
                              "14:PGANG 15:V5 16:VDD33 17:GND")),
    "SY6280": dict(fp="Package_TO_SOT_SMD:SOT-23-5", lcsc="C55136",
                   desc="Silergy SY6280AAC power distribution switch 2.4-5.5 V, current limit 6800 / R_ISET (A, ohm), 0.4-2 A, SOT-23-5",
                   pins=named("1:OUT 2:GND 3:ISET 4:EN 5:IN")),
    "ME6211": dict(fp="Package_TO_SOT_SMD:SOT-23-5", lcsc="C82942", desc="Microne ME6211C33M5G 3.3 V LDO 500 mA, SOT-23-5",
                   pins=named("1:VIN 2:VSS 3:CE 4:NC 5:VOUT")),
    # the system side of the Framework input-module interface (pinout of github.com/FrameworkComputer/InputModules);
    # footprint after Framework's Input Module Adapter (CC BY 4.0), CFE BP33242-08200H0-FS
    "POGO_FW8": dict(fp="commander:Pogo_CFE_BP33242-08200H0-FS_2x4_P2.0mm",
                     desc="pogo-pin connector 2 x 4, 2.0 mm, 1.6 mm working height, 1 A per pin (CFE BP33242-08200H0-FS), "
                          "mates the pads of a Framework Laptop 16 input module",
                     pins=named("1:GND 2:VCC_5V 3:USB_DN 4:BOARD_ID 5:USB_DP 6:SLEEP_N 7:GND 8:VCC_3V3")),
}
# LCSC / JLCPCB part numbers (checked on lcsc.com / JLC's BOM matcher, 2026-11-15) -> the 'lcsc' column of the BOM and the
# "LCSC Part #" column of the JLC parts list.  Passives are left to JLC's matcher (it picks Basic parts once the package
# is written as "0402" etc., see make_quote_package.py); parts without a stocked LCSC number are not listed here.
LCSC = {
    "RK3566": "C2943786", "RK817": "C5179490", "RK860": "C19188628", "RTL8211F": "C187932", "TPS23754": "C181651",
    "TPS2121": "C485916", "FUSB302B": "C132291", "XFMR_FLYBACK": "C24570980", "USB5744": "C633621", "USB2517": "C1521556",
    "HD3SS3220": "C701817", "TPD4E05U06": "C2827646", "USBLC6-2SC6": "C2827654", "PWRSW": "C3001659",   # AP22804AW5-7
    "BUCK_SOT235": "C141836",                                                                           # TLV62569DBVR
}
for _k, _v in LCSC.items():
    if _k in PARTS:
        PARTS[_k].setdefault("lcsc", _v)
# small-signal Schottky / service-port parts that are not SMA
FP_OVERRIDE = {
    "D6": "Diode_SMD:D_SOD-523",      # 1N5819WT
    "ED6": "Diode_SMD:D_0402_1005Metric",
    "D3": "Diode_SMD:D_SOD-123F",
}

TWO_PIN_PREFIX = OrderedDict([("FB", "FB"), ("R", "R"), ("C", "C"), ("L", "L"), ("F", "F")])


class Comp:
    __slots__ = ("ref", "part", "value", "dnp", "sheet", "pins", "order", "kind", "fp", "desc", "src")

    def __init__(self, ref, part, value, sheet, src):
        self.ref, self.part, self.value, self.sheet, self.src = ref, part, value, sheet, src
        self.dnp = False
        self.pins = OrderedDict()   # pin_id -> net name, or None for no-connect
        self.order = []             # (sheet, pin_id) in order of appearance
        self.kind = None            # 'R','C','L','FB','F','TP', 'two', or 'ic'
        self.fp = None
        self.desc = ""

    def __repr__(self):
        return f"<{self.ref} {self.part}:{self.value}>"


class Design:
    def __init__(self):
        self.comps = OrderedDict()
        self.errors = []
        self.warnings = []
        self.sheets = []
        self.sheet_title = {}

    # ---- helpers ----
    def err(self, src, msg):
        self.errors.append(f"{src}: {msg}")

    def nets(self):
        n = defaultdict(list)
        for c in self.comps.values():
            for pin, net in c.pins.items():
                if net is not None:
                    n[net].append((c.ref, pin))
        return n

    def sheet_comps(self, sheet):
        """Components (and, for multi-sheet parts, their pin subsets) drawn on one sheet."""
        out = []
        for c in self.comps.values():
            pins = [p for s, p in c.order if s == sheet]
            if pins or (c.sheet == sheet and not c.order):
                out.append((c, pins))
        return out


def _two_kind(ref):
    for pre, kind in TWO_PIN_PREFIX.items():
        if re.match(rf"^\d?{pre}\d", ref):
            return kind
    return None


def load(netdir=NETDIR):
    d = Design()
    sheet = None
    for path in net_files(netdir):
        fname = os.path.basename(path)
        with open(path, encoding="utf-8") as f:
            for ln, raw in enumerate(f, 1):
                line = raw.split("#", 1)[0].strip()
                if not line:
                    continue
                src = f"{fname}:{ln}"
                tok = line.split()
                head = tok[0]
                if head == "SHEET":
                    sheet = tok[1]
                    if sheet not in d.sheets:
                        d.sheets.append(sheet)
                    continue
                if head in ("P", "N", "NC"):
                    ref = tok[1]
                    if ref not in d.comps:
                        # first mention of a big multi-sheet part: declare it implicitly
                        part = {"U1": "RK3566", "U10": "LPDDR4_200"}.get(ref)
                        if not part:
                            d.err(src, f"{head} for undeclared part {ref}")
                            continue
                        c = Comp(ref, part, part, sheet, src)
                        c.kind = "ic"
                        d.comps[ref] = c
                    c = d.comps[ref]
                    if head == "P":
                        pairs = [t.split("=", 1) for t in tok[2:]]
                    elif head == "N":
                        pairs = [(p, tok[2]) for p in tok[3:]]
                    else:
                        pairs = [(p, None) for p in tok[2:]]
                    for pr in pairs:
                        if len(pr) != 2:
                            d.err(src, f"bad pin assignment {pr}")
                            continue
                        _assign(d, c, pr[0], pr[1], sheet, src)
                    continue
                if head == "CAPS":
                    m = re.match(r"^C(\d+)-C(\d+)$", tok[1])
                    if not m or len(tok) != 5:
                        d.err(src, "bad CAPS statement")
                        continue
                    for i in range(int(m.group(1)), int(m.group(2)) + 1):
                        _two(d, f"C{i}", "C", tok[2], tok[3], tok[4], sheet, src)
                    continue
                ref = head
                if ref in d.comps:
                    d.err(src, f"duplicate reference {ref} (first at {d.comps[ref].src})")
                    continue
                if len(tok) >= 3 and tok[1] == "TP":
                    c = Comp(ref, "TP", "TP", sheet, src)
                    c.kind = "TP"
                    c.fp = "TestPoint:TestPoint_Pad_D1.0mm"
                    c.desc = "test pad 1.0 mm"
                    d.comps[ref] = c
                    _assign(d, c, "1", tok[2], sheet, src)
                    continue
                kind = _two_kind(ref)
                if kind and len(tok) == 4 and "=" not in line:
                    _two(d, ref, kind, tok[1], tok[2], tok[3], sheet, src)
                    continue
                # multi-pin / named part
                pv = tok[1].split(":", 1)
                part = pv[0]
                value = pv[1] if len(pv) > 1 else part
                if part not in PARTS:
                    d.err(src, f"unknown part type '{part}' for {ref}")
                    continue
                pd = PARTS[part]
                c = Comp(ref, part, value, sheet, src)
                c.desc = pd.get("desc", "")
                c.fp = FP_OVERRIDE.get(ref, pd["fp"])
                if part == "CMC" and "BCMF062" in value:
                    c.fp = "commander:CMC_0504_4P"       # HDMI chokes are 0504, not 0805
                if value.upper() == "DNP":
                    c.dnp = True
                d.comps[ref] = c
                rest = tok[2:]
                if pd.get("two"):
                    c.kind = "two"
                    if all("=" in t for t in rest):
                        for t in rest:
                            p, n = t.split("=", 1)
                            _assign(d, c, p, n, sheet, src)
                    elif len(rest) == 2:
                        _assign(d, c, "1", rest[0], sheet, src)
                        _assign(d, c, "2", rest[1], sheet, src)
                    else:
                        d.err(src, f"{ref}: expected two nets")
                else:
                    c.kind = "ic"
                    for t in rest:
                        if "=" not in t:
                            d.err(src, f"{ref}: bad token '{t}'")
                            continue
                        p, n = t.split("=", 1)
                        _assign(d, c, p, n, sheet, src)
    _finish(d)
    return d


def _two(d, ref, kind, value, n1, n2, sheet, src):
    if ref in d.comps:
        d.err(src, f"duplicate reference {ref} (first at {d.comps[ref].src})")
        return
    c = Comp(ref, kind, value, sheet, src)
    c.kind = kind
    if value.upper() == "DNP":
        c.dnp = True
    c.fp = footprint_for_two_pin(kind, value)
    d.comps[ref] = c
    _assign(d, c, "1", n1, sheet, src)
    _assign(d, c, "2", n2, sheet, src)


def _assign(d, c, pin, net, sheet, src):
    if pin in c.pins:
        if c.pins[pin] == net:
            return                      # harmless repeat (e.g. overlapping ground lists)
        d.err(src, f"{c.ref}.{pin} assigned twice: {c.pins[pin]} and {net}")
        return
    c.pins[pin] = net
    c.order.append((sheet, pin))


def _natural(pin):
    m = re.match(r"^(1?)([A-Z]*)(\d+)$", pin)
    if not m:
        return (9, pin, 0)
    return (len(m.group(1)), len(m.group(2)), m.group(2), int(m.group(3)))


def _finish(d):
    # RK3566 ball names
    names = {}
    p = os.path.join(ROOT, "src", "rk3566_balls.csv")
    if os.path.exists(p):
        for row in csv.DictReader(open(p, encoding="utf-8")):
            names[row["ball"]] = row["name"]
    d.pin_names = {}
    for c in d.comps.values():
        if c.kind != "ic":
            continue
        pd = PARTS[c.part]
        if not c.fp:
            c.fp = FP_OVERRIDE.get(c.ref, pd["fp"])
        c.desc = pd.get("desc", "")
        defined = pd.get("pins")
        if defined:
            ids = [p for p, _ in defined]
            for pin in c.pins:
                if pin not in ids:
                    d.err(c.src, f"{c.ref}: pin '{pin}' is not a pin of {c.part}")
            for pin in ids:
                if pin not in c.pins:
                    d.err(c.src, f"{c.ref} ({c.part}): pin {pin} has neither a net nor an NC mark")
            d.pin_names[c.ref] = dict(defined)
        else:
            nm = {}
            for pin, net in c.pins.items():
                if c.part == "RK3566":
                    nm[pin] = names.get(pin, pin)
                else:
                    nm[pin] = (net or "NC").replace("LPDDR4_", "")
            d.pin_names[c.ref] = nm
    for c in d.comps.values():
        if c.kind in ("R", "C", "L", "FB", "F", "two") and len(c.pins) != 2:
            d.err(c.src, f"{c.ref}: two-terminal part with {len(c.pins)} pins")


def pads_for(c, pin):
    """Footprint pad name(s) for a schematic pin id."""
    if c.kind == "ic" or c.kind == "two":
        pm = PARTS[c.part].get("padmap", {})
        if pin in pm:
            return pm[pin]
    return [pin]


def report(d):
    lines = []
    kinds = defaultdict(int)
    for c in d.comps.values():
        kinds[c.kind if c.kind != "ic" else c.part] += 1
    nets = d.nets()
    lines.append(f"components: {len(d.comps)}   nets: {len(nets)}   sheets: {len(d.sheets)}")
    lines.append("  " + ", ".join(f"{k}={v}" for k, v in sorted(kinds.items())))
    for ref in ("U1", "U10", "U20"):
        if ref in d.comps:
            c = d.comps[ref]
            nc = sum(1 for n in c.pins.values() if n is None)
            lines.append(f"  {ref} {c.part}: {len(c.pins)} pins assigned ({nc} NC)")
    single = sorted(n for n, pins in nets.items() if len(pins) == 1)
    lines.append(f"single-pin nets ({len(single)}): " + ", ".join(single))
    return "\n".join(lines)


if __name__ == "__main__":
    d = load()
    print(report(d))
    if d.errors:
        print(f"\n{len(d.errors)} ERROR(S):")
        for e in d.errors:
            print("  " + e)
        raise SystemExit(1)
    print("\nmodel OK")
