#!/usr/bin/env python3
"""Generates src/netlist/31_usb3_hub.net and 32_usb2_hub.net (hub board, strip test board) and, for the mainboard,
34_hub_link.net (the M.2 socket to the hub board, plus the keyboard port that stays on the mainboard).

The nine rear bays are repetitive, so they are produced from one template each
(SuperSpeed bay / Hi-Speed bay) instead of being typed out nine times.

Bay numbering: bay 1 is the one nearest the codec column, bay 9 the far end.
  bays 1-4 : USB 3.2 Gen 1 (5 Gb/s) from USB5744 downstream ports 1-4
  bays 5-9 : USB 2.0 from USB2517 downstream ports 1-5
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import cpmodel          # noqa: E402

OUT = cpmodel.NETDIR
STRIP = cpmodel.VARIANT == "strip"
HUB = cpmodel.VARIANT == "hub"          # the hub board of branch m2-hub: the bays, both hubs and the microSD slot
MAIN = cpmodel.VARIANT == "main"        # the mainboard keeps only the keyboard port and the M.2 socket to the hub board
import hub_link                         # noqa: E402  (the socket / card-edge position list, one source for both boards)
# the hub board's bays are sink-mount 24-pin receptacles since 2026-11-16 (tools/hub_midmount_swap.py); the strip test
# board keeps its top-mount ones
RC_SS = "USBC24_SINK" if HUB else "USBC24"
RC_HS = "USBC24_SINK" if HUB else "USBC16"
HS_NC = " A2 A3 A10 A11 B2 B3 B10 B11" if HUB else ""


def vbus_guard(k, b):
    """Hub board (2026-11-16): nothing a user plugs into a bay may push voltage back into the hub.  The switch's
    output (VBUS_SW_Pk) reaches the receptacle (VBUS_Pk) through a 40 V Schottky, so a back-feeding device - a
    charger or power bank on a C-to-C cable, a broken USB-PD source, a bench supply on an adapter, up to 40 V - is
    simply blocked; a 24 V TVS takes ESD on the connector side and stays off at 20 V.  On the connector side only
    20 V-safe parts remain (the TVS, a 50 V capacitor, the 909 k VBUS-detect resistor); the bulk capacitor, the ESD
    array's supply pin and the Rp resistors moved to the supply side.  The diode drops about 0.35 V at 1 A: the PoE
    supply's set point went up to 5.24 V for it (mainboard 30_poe.net, R515).
    Returns (switch-output net, the guard's lines, the ESD array's supply net, the bulk capacitor's net)."""
    if not HUB:
        return f"VBUS_P{k}", "", f"VBUS_P{k}", f"VBUS_P{k}", "100nF"
    lines = (f"\n# back-feed / over-voltage guard (see vbus_guard in tools/gen_usb_netlists.py)\n"
             f"D{b+1} SCHOTTKY_123W:PMEG4030ER A=VBUS_SW_P{k} K=VBUS_P{k}\n"
             f"D{b+2} TVS:SMF24CA VBUS_P{k} GND")
    return f"VBUS_SW_P{k}", lines, "VCC5V_BUS", f"VBUS_SW_P{k}", "100nF_50V"


def ss_bay(k):
    """SuperSpeed bay k (1..4) on USB5744 downstream port k."""
    b = 630 + k * 10          # reference block: 64x, 65x, 66x, 67x
    q = 1000 + k * 10         # second block for the Type-C controller / mux: 101x .. 104x
    sw, guard, esd_v, bulk, c_out = vbus_guard(k, b)
    return f"""
# ---- bay {k}: USB 3.2 Gen 1 (USB5744 port {k}) ----
J3{k} {RC_SS} A1=GND A12=GND B1=GND B12=GND SH=GND A4=VBUS_P{k} A9=VBUS_P{k} B4=VBUS_P{k} B9=VBUS_P{k}
P J3{k} A5=CC1_P{k} B5=CC2_P{k} A6=USB_P{k}_DP B6=USB_P{k}_DP A7=USB_P{k}_DM B7=USB_P{k}_DM
P J3{k} A2=SSTX1P_P{k} A3=SSTX1N_P{k} B11=SSRX1P_P{k} B10=SSRX1N_P{k} B2=SSTX2P_P{k} B3=SSTX2N_P{k} A11=SSRX2P_P{k} A10=SSRX2N_P{k}
NC J3{k} A8 B8
# Type-C port controller with SuperSpeed 2:1 mux (TI HD3SS3220), wired as in Microchip's USB5744 figure
# "Downstream Port Type-C USB Connections": the controller reads the CC pins, advertises a source
# (PORT high = DFP, default USB current) and switches the hub's single SuperSpeed lane to whichever
# side of the receptacle the plug uses. GPIO mode (ADDR open): no I2C, no software.
U{q+1} HD3SS3220 2=CC1_P{k} 1=CC2_P{k} 6=HUB3_TXCP{k} 7=HUB3_TXCN{k} 9=HUB3_RXP{k} 10=HUB3_RXN{k}
P U{q+1} 17=SSTX1P_P{k} 16=SSTX1N_P{k} 15=SSRX1CP_P{k} 14=SSRX1CN_P{k} 21=SSTX2P_P{k} 20=SSTX2N_P{k} 19=SSRX2CP_P{k} 18=SSRX2CN_P{k}
P U{q+1} 30=VCC5V_BUS 8=VCC3V3_HUB 13=GND 28=GND 31=GND 29=GND 4=TYPEC_PORT_P{k} 5=TYPEC_VBUSDET_P{k} 11=TYPEC_DIR_P{k}
# ID goes low when a device is attached; it also enables the mux (ENn_MUX), so an empty bay is switched off
P U{q+1} 27=TYPEC_ID_N_P{k} 12=TYPEC_ID_N_P{k}
NC U{q+1} 3 22 23 24 25 26
R{q+1} 909K_1% VBUS_P{k} TYPEC_VBUSDET_P{k}
R{q+2} 10K VCC5V_BUS TYPEC_PORT_P{k}
R{q+3} 200K VCC3V3_HUB TYPEC_DIR_P{k}
R{q+4} 200K VCC3V3_HUB TYPEC_ID_N_P{k}
C{q+3} 100nF VCC5V_BUS GND
C{q+4} 10uF VCC5V_BUS GND
C{q+5} 100nF VCC3V3_HUB GND
# AC coupling: 100 nF on the transmit pair (hub side of the mux), 330 nF on each receive pair at the connector
C{b+1} 100nF HUB3_TXP{k} HUB3_TXCP{k}
C{b+2} 100nF HUB3_TXN{k} HUB3_TXCN{k}
C{b+3} 330nF SSRX1P_P{k} SSRX1CP_P{k}
C{b+4} 330nF SSRX1N_P{k} SSRX1CN_P{k}
C{q+1} 330nF SSRX2P_P{k} SSRX2CP_P{k}
C{q+2} 330nF SSRX2N_P{k} SSRX2CN_P{k}
# ESD on the connector side, one part per lane
U{b+1} TPD4E05U06 1=SSTX1P_P{k} 10=SSTX1P_P{k} 2=SSTX1N_P{k} 9=SSTX1N_P{k} 4=SSRX1P_P{k} 7=SSRX1P_P{k} 5=SSRX1N_P{k} 6=SSRX1N_P{k} 3=GND 8=GND
U{q+2} TPD4E05U06 1=SSTX2P_P{k} 10=SSTX2P_P{k} 2=SSTX2N_P{k} 9=SSTX2N_P{k} 4=SSRX2P_P{k} 7=SSRX2P_P{k} 5=SSRX2N_P{k} 6=SSRX2N_P{k} 3=GND 8=GND
U{b+2} USBLC6-2SC6 1=USB_P{k}_DP 6=USB_P{k}_DP 3=USB_P{k}_DM 4=USB_P{k}_DM 2=GND 5={esd_v}
# port power: PRT_CTLx is both the enable output and the over-current input on the USB5744.
# The controller's ID output does not gate VBUS: the bay is powered whenever the hub enables the port.
U{b+3} PWRSW:AP22804AW5 5=VCC5V_BUS 1={sw} 2=GND 4=HUB3_PRT_CTL{k} 3=HUB3_PRT_CTL{k}
C{b+5} 100nF VCC5V_BUS GND
C{b+6} 47uF {bulk} GND
C{b+7} {c_out} VBUS_P{k} GND{guard}"""


def hs_bay(k):
    """Hi-Speed bay k (5..9) on USB2517 downstream port k-4."""
    n = k - 4
    b = 700 + k * 10          # reference block: 75x .. 79x
    sw, guard, esd_v, bulk, c_out = vbus_guard(k, b)
    rp = "VCC5V_BUS" if HUB else f"VBUS_P{k}"      # Rp (56 k = default USB power) from the supply side
    return f"""
# ---- bay {k}: USB 2.0 (USB2517 port {n}) ----
J3{k} {RC_HS} A1=GND A12=GND B1=GND B12=GND SH=GND A4=VBUS_P{k} A9=VBUS_P{k} B4=VBUS_P{k} B9=VBUS_P{k}
P J3{k} A5=CC1_P{k} B5=CC2_P{k} A6=USB_P{k}_DP B6=USB_P{k}_DP A7=USB_P{k}_DM B7=USB_P{k}_DM
NC J3{k} A8 B8{HS_NC}
U{b+2} USBLC6-2SC6 1=USB_P{k}_DP 6=USB_P{k}_DP 3=USB_P{k}_DM 4=USB_P{k}_DM 2=GND 5={esd_v}
R{b+5} 56K {rp} CC1_P{k}
R{b+6} 56K {rp} CC2_P{k}
U{b+3} PWRSW:AP22804AW5 5=VCC5V_BUS 1={sw} 2=GND 4=HUB2_PRTPWR{n} 3=HUB2_OCS{n}_N
C{b+5} 100nF VCC5V_BUS GND
C{b+6} 47uF {bulk} GND
C{b+7} {c_out} VBUS_P{k} GND{guard}"""


USB3 = """# NEW for the Commander: USB 3.2 Gen 1 hub (Microchip USB5744) on the RK3566 USB3 HOST1 port.
# Replaces the single Type-C USB3 port of the Radxa ZERO 3E (CH482D mux + ET7301B, sheet 14).
# Runs from its internal ROM defaults: no SPI flash, no SMBus pull-ups, all ports removable, no battery charging.
SHEET usb3_hub
U40 USB5744 45=USB3_HOST1_DP 46=USB3_HOST1_DM 47=HUB3_UP_TXP 48=HUB3_UP_TXN 50=HUB3_UP_RXP 51=HUB3_UP_RXN
P U40 1=USB_P1_DP 2=USB_P1_DM 3=HUB3_TXP1 4=HUB3_TXN1 6=HUB3_RXP1 7=HUB3_RXN1
P U40 8=USB_P2_DP 9=USB_P2_DM 10=HUB3_TXP2 11=HUB3_TXN2 13=HUB3_RXP2 14=HUB3_RXN2
P U40 17=USB_P3_DP 18=USB_P3_DM 19=HUB3_TXP3 20=HUB3_TXN3 22=HUB3_RXP3 23=HUB3_RXN3
P U40 24=USB_P4_DP 25=USB_P4_DM 26=HUB3_TXP4 27=HUB3_TXN4 29=HUB3_RXP4 30=HUB3_RXN4
P U40 36=HUB3_PRT_CTL1 35=HUB3_PRT_CTL2 34=HUB3_PRT_CTL3 32=HUB3_PRT_CTL4
P U40 37=HUB3_VBUS_DET 38=HUB3_SMCLK 39=HUB3_SMDAT 40=HUB3_CFG_BC_EN 41=HUB3_CFG_NON_REM 42=HUB_RESET_N
P U40 53=HUB3_XO 54=HUB3_XI 56=HUB3_RBIAS 57=GND
NC U40 52
N U40 VCC3V3_HUB 16 31 44 55
N U40 VCC1V2_HUB 5 12 15 21 28 33 43 49
# upstream: AC coupling at each transmitter (SoC TX -> hub RX, hub TX -> SoC RX)
C601 100nF USB3_HOST1_SSTXP HUB3_UP_RXP
C602 100nF USB3_HOST1_SSTXN HUB3_UP_RXN
C603 100nF HUB3_UP_TXP USB3_HOST1_SSRXP
C604 100nF HUB3_UP_TXN USB3_HOST1_SSRXN
# clock, bias, straps
Y40 XTAL4:25MHz 1=HUB3_XI 2=GND 3=HUB3_XO 4=GND
C605 12pF HUB3_XI GND
C606 12pF HUB3_XO GND
R601 12K_1% HUB3_RBIAS GND
R602 200K HUB3_CFG_NON_REM GND
R603 200K HUB3_CFG_BC_EN GND
R604 49.9K_1% VCC_SYS HUB3_VBUS_DET
R605 100K_1% HUB3_VBUS_DET GND
# optional SMBus access from the SoC (I2C3_M1). Leave unpopulated: 10k pull-ups on these two pins at
# reset would park the hub in SMBus-configuration mode waiting for a host command.
R606 DNP I2C3_SCL_M1 HUB3_SMCLK
R607 DNP I2C3_SDA_M1 HUB3_SMDAT
# reset: local RC so the hubs come up without software; the SoC can still pulse it low
R608 4.7K VCC3V3_HUB HUB_RESET_N
C607 1uF HUB_RESET_N GND
R609 0R HUB_RESET_SOC_N HUB_RESET_N
# decoupling
CAPS C608-C611 100nF VCC3V3_HUB GND
C612 4.7uF VCC3V3_HUB GND
CAPS C613-C620 100nF VCC1V2_HUB GND
C621 10uF VCC1V2_HUB GND
# --- hub supplies from the 5 V rail (keeps the hubs off the PMIC's 3.3 V buck) ---
# inductors: 2.2 uH in 2520 size, 1.2 mm tall, saturation current 2.3 A or more (each hub rail draws well under 1 A)
U41 BUCK_SOT235:TLV62569 4=VCC_SYS 1=VCC_SYS 2=GND 3=HUB_SW33 5=HUB_FB33
L41 2.2uH_2520 HUB_SW33 VCC3V3_HUB
R610 453K_1% VCC3V3_HUB HUB_FB33
R611 100K_1% HUB_FB33 GND
C622 10uF VCC_SYS GND
C623 22uF VCC3V3_HUB GND
U42 BUCK_SOT235:TLV62569 4=VCC_SYS 1=VCC_SYS 2=GND 3=HUB_SW12 5=HUB_FB12
L42 2.2uH_2520 HUB_SW12 VCC1V2_HUB
R612 100K_1% VCC1V2_HUB HUB_FB12
R613 100K_1% HUB_FB12 GND
C624 10uF VCC_SYS GND
C625 22uF VCC1V2_HUB GND
"""

USB2 = """# NEW for the Commander: USB 2.0 hub (Microchip USB2517, 7 ports) on the RK3566 USB2 HOST2 port,
# plus the internal keyboard link on USB2 HOST3 (unused on the Radxa ZERO 3E).
# CFG_SEL[2:0] = 110: internal default configuration, strap options disabled, individual port power.
SHEET usb2_hub
U50 USB2517 59=USB2_HOST2_DP 58=USB2_HOST2_DM 44=VCC3V3_HUB 43=HUB_RESET_N 19=GND 61=HUB2_XI 60=HUB2_XO 63=HUB2_RBIAS
P U50 2=USB_P5_DP 1=USB_P5_DM 4=USB_P6_DP 3=USB_P6_DM 7=USB_P7_DP 6=USB_P7_DM 9=USB_P8_DP 8=USB_P8_DM 12=USB_P9_DP 11=USB_P9_DM
P U50 54=USB_AUX_DP 53=USB_AUX_DM
P U50 29=HUB2_PRTPWR1 26=HUB2_PRTPWR2 23=HUB2_PRTPWR3 20=HUB2_PRTPWR4 30=HUB2_PRTPWR5
P U50 28=HUB2_OCS1_N 27=HUB2_OCS2_N 22=HUB2_OCS3_N 21=HUB2_OCS4_N 35=HUB2_OCS5_N
P U50 13=HUB2_CFG_SEL2 42=HUB2_CFG_SEL1 41=HUB2_CFG_SEL0 40=HUB2_SDA 25=HUB2_VDD18 62=HUB2_VDD18PLL 65=GND
N U50 VCC3V3_HUB 46 5 10 52 57 64 24
# port 7 and the LED / indicator pins are unused
NC U50 56 55 36 37 39 38 45 15 17 31 33 47 49 51 14 16 18 32 34 48 50
Y50 XTAL4:24MHz 1=HUB2_XI 2=GND 3=HUB2_XO 4=GND
C701 18pF HUB2_XI GND
C702 18pF HUB2_XO GND
R701 12K_1% HUB2_RBIAS GND
R702 10K VCC3V3_HUB HUB2_CFG_SEL2
R703 10K VCC3V3_HUB HUB2_CFG_SEL1
R704 10K HUB2_CFG_SEL0 GND
R705 10K HUB2_SDA GND
C703 1uF HUB2_VDD18 GND
C704 1uF HUB2_VDD18PLL GND
CAPS C705-C711 100nF VCC3V3_HUB GND
C712 4.7uF VCC3V3_HUB GND
# USB2517 port 6 (USB_AUX) goes to the front battery port J40, see 33_battery_port.net
"""

KEYBOARD = """# --- keyboard link: straight from the SoC (USB2 HOST3), not through a hub.
#     Standard USB-C receptacle (USB 2.0) on the inner edge of the column, facing the keyboard (kept standard so the
#     keyboard can be reused on its own after the device's life).  The board is the host: Rp on both CC pins.
#     The keyboard's power key comes on its own 2-wire cable to J22 (24_power_button.net; on the column's outer edge:
#     this edge has no room left).
#     5 V through a resettable fuse, from VCC5V_BUS: on whenever the device has power, so the keyboard can watch the
#     power key while the board is off.  750 mA like the keyboard's own fuse (2026-11-18: its 84 infra-red LEDs draw
#     ~0.56 A, the 500 mA this had would trip). ---
P U1 Y2=USB2_HOST3_DP Y1=USB2_HOST3_DM
J20 USBC16 A1=GND A12=GND B1=GND B12=GND SH=GND A4=VBUS_KB A9=VBUS_KB B4=VBUS_KB B9=VBUS_KB
P J20 A5=CC1_KB B5=CC2_KB A6=USB2_HOST3_DP B6=USB2_HOST3_DP A7=USB2_HOST3_DM B7=USB2_HOST3_DM
NC J20 A8 B8
R706 56K VBUS_KB CC1_KB
R707 56K VBUS_KB CC2_KB
F1 PTC:750mA VCC5V_BUS VBUS_KB
C713 10uF VBUS_KB GND
U51 USBLC6-2SC6 1=USB2_HOST3_DP 6=USB2_HOST3_DP 3=USB2_HOST3_DM 4=USB2_HOST3_DM 2=GND 5=VBUS_KB
"""
if STRIP:
    # test board: no SoC, so no keyboard port; the upstream AC coupling already sits on the ZERO 3E
    KEYBOARD = ""
    USB3 = USB3.replace("C601 100nF USB3_HOST1_SSTXP HUB3_UP_RXP", "C601 0R USB3_HOST1_SSTXP HUB3_UP_RXP")
    USB3 = USB3.replace("C602 100nF USB3_HOST1_SSTXN HUB3_UP_RXN", "C602 0R USB3_HOST1_SSTXN HUB3_UP_RXN")
    assert USB3.count(" 0R USB3_HOST1_SSTX") == 2

LINK_MAIN = """# NEW (branch m2-hub): the bays, both hubs and the microSD slot moved to their own board (project commander_hub),
# which plugs into this mainboard through an M.2 Key M socket: card-edge fingers on the hub board, no plug part.
# The pinout is in tools/hub_link.py (one source for both boards).  This sheet keeps what stays on the mainboard.
SHEET hub_link
# SuperSpeed SoC -> hub: AC coupling at the transmitter, i.e. here (the hub board couples its own transmitter)
C601 100nF USB3_HOST1_SSTXP HUB3_UP_RXP
C602 100nF USB3_HOST1_SSTXN HUB3_UP_RXN
""" + hub_link.statement("J41", "M2_SOCKET_M") + "P J41 MP=GND\n"

EDGE = """# The hub board's card edge: M.2 Key M fingers on a 0.8 mm board, into socket J41 of the mainboard.
# Pinout: tools/hub_link.py (one source for both boards).  Same net names on both sides.
SHEET hub_link
""" + hub_link.statement("J90", "M2_EDGE_M")

if HUB:
    # the SoC's transmit pair arrives already AC-coupled from the mainboard (C601 / C602 are there)
    for line in ("C601 100nF USB3_HOST1_SSTXP HUB3_UP_RXP\n", "C602 100nF USB3_HOST1_SSTXN HUB3_UP_RXN\n"):
        assert line in USB3
        USB3 = USB3.replace(line, "")
    KEYBOARD = ""                       # the keyboard port stays on the mainboard
    with open(os.path.join(OUT, "40_hub_edge.net"), "w", encoding="utf-8", newline="\n") as f:
        f.write(EDGE)
if MAIN:
    with open(os.path.join(OUT, "34_hub_link.net"), "w", encoding="utf-8", newline="\n") as f:
        f.write(LINK_MAIN + KEYBOARD)
    for name in ("31_usb3_hub.net", "32_usb2_hub.net"):
        if os.path.exists(os.path.join(OUT, name)):
            os.remove(os.path.join(OUT, name))
    print("wrote 34_hub_link.net (the hub sheets are on the hub board now: ../commander_hub)")
    sys.exit(0)

with open(os.path.join(OUT, "31_usb3_hub.net"), "w", encoding="utf-8", newline="\n") as f:
    f.write(USB3 + "".join(ss_bay(k) for k in range(1, 5)) + "\n")
with open(os.path.join(OUT, "32_usb2_hub.net"), "w", encoding="utf-8", newline="\n") as f:
    f.write(USB2 + KEYBOARD + "".join(hs_bay(k) for k in range(5, 10)) + "\n")
print("wrote 31_usb3_hub.net, 32_usb2_hub.net")
