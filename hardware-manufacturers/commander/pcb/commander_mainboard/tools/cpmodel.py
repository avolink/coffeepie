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
ROOT = os.path.normpath(os.path.join(HERE, ".."))
NETDIR = os.path.join(ROOT, "src", "netlist")

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
            return "Capacitor_Tantalum_SMD:CP_EIA-7343-31_Kemet-D"
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
            return "Inductor_SMD:L_Bourns_SRP5030T"
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
    "LPDDR4_200": dict(fp="Package_BGA:BGA-200_10x14.5mm_Layout12x22_P0.8x0.65mm", pins=None,
                       desc="LPDDR4 SDRAM 200-ball FBGA, 2 GB (16 Gb) e.g. K4F6E3S4HM / NT6AN512T32"),
    "EMMC153": dict(fp="Package_BGA:LFBGA-153_11.5x13mm_Layout14x14_P0.5mm", pins=None, fill_nc=True,
                    desc="eMMC 5.1 153-ball, 16 GB"),
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
    "USBC16": dict(fp="Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12", desc="USB-C receptacle, USB 2.0, 16-pin (HRO TYPE-C-31-M-12)",
                   padmap={"SH": ["SH"]},
                   pins=named("A1:GND A4:VBUS A5:CC1 A6:D+ A7:D- A8:SBU1 A9:VBUS A12:GND B1:GND B4:VBUS B5:CC2 B6:D+ B7:D- B8:SBU2 B9:VBUS B12:GND SH:SHIELD")),
    "USBC24": dict(fp="Connector_USB:USB_C_Receptacle_JAE_DX07S024WJ1R350", desc="USB-C receptacle, full-featured 24-pin (JAE DX07S024WJ1R350)",
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
    "FUSB302B": dict(fp="Package_DFN_QFN:WQFN-14-1EP_2.5x2.5mm_P0.5mm_EP1.45x1.45mm", desc="onsemi FUSB302B USB-C port controller (or ET7301B), WQFN-14", pins=named(
        "1:CC2 2:VBUS 3:VDD 4:VDD 5:INT_N 6:SCL 7:SDA 8:GND 9:GND 10:CC1 11:CC1 12:VCONN 13:VCONN 14:CC2 15:EPAD")),
    "TPS2121": dict(fp="Package_DFN_QFN:Texas_VQFN-HR-12_2x2.5mm_P0.5mm", desc="TI TPS2121 power mux 2.8-22 V 4.5 A, fast switch-over, VQFN-HR-12", pins=named(
        "7:IN1 2:IN2 6:PR1 3:CP2 5:OV1 4:OV2 10:ILM 11:SS 9:ST 1:OUT 8:OUT 12:GND")),
    "PWRSW": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="USB power switch with fault flag", pins=named("5:IN 4:EN 3:FLG 2:GND 1:OUT")),
    "BUCK_SOT235": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="synchronous buck 2 A, SOT-23-5", pins=named("4:VIN 1:EN 5:FB 2:GND 3:SW")),
    "AT24C02": dict(fp="Package_TO_SOT_SMD:SOT-23-5", desc="I2C EEPROM 2 kbit (AT24C02 / AT24CS02), SOT-23-5", pins=named("1:SCL 2:GND 3:SDA 4:VCC 5:WP")),
    "OPTO": dict(fp="Package_DIP:SMDIP-4_W9.53mm", desc="optocoupler, 4-pin", pins=named("1:A 2:K 4:C 3:E")),
    "TL431": dict(fp="Package_TO_SOT_SMD:SOT-23", desc="TL431 shunt reference, SOT-23 (DBZ pinout)", pins=named("1:K 2:REF 3:A")),
    "XFMR_FLYBACK": dict(fp="commander:XFMR_Flyback_EP13_PLACEHOLDER", desc="PoE flyback transformer 30 W, 5 V out (pin map per final part)",
                         pins=named("PA:PRI_A PB:PRI_B XA:AUX_A XB:AUX_B SA:SEC_A SB:SEC_B")),
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
    "HDR1x4": dict(fp="Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical", desc="pin header 1x4 2.54 mm", pins=named("1:GND 2:TX 3:RX 4:3V3")),
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
    "XTAL2": dict(fp="Crystal:Crystal_SMD_3215-2Pin_3.2x1.5mm", two="xtal", desc="32.768 kHz crystal, 3215"),
}
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
    for path in sorted(glob.glob(os.path.join(netdir, "*.net"))):
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
