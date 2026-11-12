#!/usr/bin/env python3
"""Generates src/netlist/31_usb3_hub.net and 32_usb2_hub.net.

The nine rear bays are repetitive, so they are produced from one template each
(SuperSpeed bay / Hi-Speed bay) instead of being typed out nine times.

Bay numbering: bay 1 is the one nearest the codec column, bay 9 the far end.
  bays 1-4 : USB 3.2 Gen 1 (5 Gb/s) from USB5744 downstream ports 1-4
  bays 5-9 : USB 2.0 from USB2517 downstream ports 1-5
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "src", "netlist")


def ss_bay(k):
    """SuperSpeed bay k (1..4) on USB5744 downstream port k."""
    b = 630 + k * 10          # reference block: 64x, 65x, 66x, 67x
    return f"""
# ---- bay {k}: USB 3.2 Gen 1 (USB5744 port {k}) ----
J3{k} USBC24 A1=GND A12=GND B1=GND B12=GND SH=GND A4=VBUS_P{k} A9=VBUS_P{k} B4=VBUS_P{k} B9=VBUS_P{k}
P J3{k} A5=CC1_P{k} B5=CC2_P{k} A6=USB_P{k}_DP B6=USB_P{k}_DP A7=USB_P{k}_DM B7=USB_P{k}_DM
P J3{k} A2=SSTX1P_P{k} A3=SSTX1N_P{k} B11=SSRX1P_P{k} B10=SSRX1N_P{k} B2=SSTX2P_P{k} B3=SSTX2N_P{k} A11=SSRX2P_P{k} A10=SSRX2N_P{k}
NC J3{k} A8 B8
# SuperSpeed lane select by BOM: Framework cards only ever seat one way, so no mux is fitted.
# Default stuffing = lane 1 (A2/A3, B11/B10). If the chassis seats the cards flipped, move the
# four parts to the DNP positions (lane 2).
C{b+1} 100nF HUB3_TXP{k} SSTX1P_P{k}
C{b+2} 100nF HUB3_TXN{k} SSTX1N_P{k}
C{b+3} DNP HUB3_TXP{k} SSTX2P_P{k}
C{b+4} DNP HUB3_TXN{k} SSTX2N_P{k}
R{b+1} 0R HUB3_RXP{k} SSRX1P_P{k}
R{b+2} 0R HUB3_RXN{k} SSRX1N_P{k}
R{b+3} DNP HUB3_RXP{k} SSRX2P_P{k}
R{b+4} DNP HUB3_RXN{k} SSRX2N_P{k}
U{b+1} TPD4E05U06 1=SSTX1P_P{k} 10=SSTX1P_P{k} 2=SSTX1N_P{k} 9=SSTX1N_P{k} 4=SSRX1P_P{k} 7=SSRX1P_P{k} 5=SSRX1N_P{k} 6=SSRX1N_P{k} 3=GND 8=GND
U{b+2} USBLC6-2SC6 1=USB_P{k}_DP 6=USB_P{k}_DP 3=USB_P{k}_DM 4=USB_P{k}_DM 2=GND 5=VBUS_P{k}
R{b+5} 56K VBUS_P{k} CC1_P{k}
R{b+6} 56K VBUS_P{k} CC2_P{k}
# port power: PRT_CTLx is both the enable output and the over-current input on the USB5744
U{b+3} PWRSW:AP22804AW5 5=VCC5V_BUS 1=VBUS_P{k} 2=GND 4=HUB3_PRT_CTL{k} 3=HUB3_PRT_CTL{k}
C{b+5} 100nF VCC5V_BUS GND
C{b+6} 47uF VBUS_P{k} GND
C{b+7} 100nF VBUS_P{k} GND"""


def hs_bay(k):
    """Hi-Speed bay k (5..9) on USB2517 downstream port k-4."""
    n = k - 4
    b = 700 + k * 10          # reference block: 75x .. 79x
    return f"""
# ---- bay {k}: USB 2.0 (USB2517 port {n}) ----
J3{k} USBC16 A1=GND A12=GND B1=GND B12=GND SH=GND A4=VBUS_P{k} A9=VBUS_P{k} B4=VBUS_P{k} B9=VBUS_P{k}
P J3{k} A5=CC1_P{k} B5=CC2_P{k} A6=USB_P{k}_DP B6=USB_P{k}_DP A7=USB_P{k}_DM B7=USB_P{k}_DM
NC J3{k} A8 B8
U{b+2} USBLC6-2SC6 1=USB_P{k}_DP 6=USB_P{k}_DP 3=USB_P{k}_DM 4=USB_P{k}_DM 2=GND 5=VBUS_P{k}
R{b+5} 56K VBUS_P{k} CC1_P{k}
R{b+6} 56K VBUS_P{k} CC2_P{k}
U{b+3} PWRSW:AP22804AW5 5=VCC5V_BUS 1=VBUS_P{k} 2=GND 4=HUB2_PRTPWR{n} 3=HUB2_OCS{n}_N
C{b+5} 100nF VCC5V_BUS GND
C{b+6} 47uF VBUS_P{k} GND
C{b+7} 100nF VBUS_P{k} GND"""


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
U41 BUCK_SOT235:TLV62569 4=VCC_SYS 1=VCC_SYS 2=GND 3=HUB_SW33 5=HUB_FB33
L41 2.2uH_2A HUB_SW33 VCC3V3_HUB
R610 453K_1% VCC3V3_HUB HUB_FB33
R611 100K_1% HUB_FB33 GND
C622 10uF VCC_SYS GND
C623 22uF VCC3V3_HUB GND
U42 BUCK_SOT235:TLV62569 4=VCC_SYS 1=VCC_SYS 2=GND 3=HUB_SW12 5=HUB_FB12
L42 2.2uH_2A HUB_SW12 VCC1V2_HUB
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
# --- keyboard link: straight from the SoC (USB2 HOST3), not through a hub ---
P U1 Y2=USB2_HOST3_DP Y1=USB2_HOST3_DM
J20 JST_SH4 1=VBUS_KB 2=USB2_HOST3_DM 3=USB2_HOST3_DP 4=GND
F1 PTC:500mA VCC5V_BUS VBUS_KB
C713 10uF VBUS_KB GND
U51 USBLC6-2SC6 1=USB2_HOST3_DP 6=USB2_HOST3_DP 3=USB2_HOST3_DM 4=USB2_HOST3_DM 2=GND 5=VBUS_KB
# USB2517 port 6 (USB_AUX) goes to the front battery port J40, see 33_battery_port.net
"""

with open(os.path.join(OUT, "31_usb3_hub.net"), "w", encoding="utf-8", newline="\n") as f:
    f.write(USB3 + "".join(ss_bay(k) for k in range(1, 5)) + "\n")
with open(os.path.join(OUT, "32_usb2_hub.net"), "w", encoding="utf-8", newline="\n") as f:
    f.write(USB2 + "".join(hs_bay(k) for k in range(5, 10)) + "\n")
print("wrote 31_usb3_hub.net, 32_usb2_hub.net")
