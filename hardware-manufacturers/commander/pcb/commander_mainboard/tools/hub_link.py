"""The link between the mainboard and the hub board (branch m2-hub): one M.2 Key M position list, used for both
sides so the socket on the mainboard (J41) and the card edge of the hub board (J90) can never disagree.

M.2 numbering: 75 positions at 0.5 mm, Key M removes 59-66, which leaves 67 contacts.  Odd numbers are on the
card's top face, even numbers on its bottom face.  This is NOT a PCIe / SATA slot: the pinout is our own and a
standard M.2 card plugged in would see 5 V on its 3.3 V pins.  The high-speed pairs sit on the positions the M.2
standard gives the PCIe lanes, with the standard ground pins between them.

Socket: LOTES APCI0146-P002A (LCSC C841645 is the -P001A), top mount, 2.06 mm tall; the card rests 0.3 mm above the
mainboard.  0.5 A per contact, 25 mating cycles.  The bays and the hub's own supplies share the 802.3at budget,
about 4 A at 5 V in all, so VCC5V_BUS gets 12 contacts (6 A) and ground 31.
"""

# position -> net (the same net name on both boards)
PINS = {
    # ---- top face (odd): signals, ground between the pairs ----
    1: "GND", 3: "GND",
    5: "HUB3_UP_RXN", 7: "HUB3_UP_RXP",                    # SuperSpeed SoC -> hub (AC-coupled on the mainboard)
    9: "GND",
    11: "USB3_HOST1_SSRXN", 13: "USB3_HOST1_SSRXP",        # SuperSpeed hub -> SoC (AC-coupled on the hub board)
    15: "GND",
    17: "USB3_HOST1_DM", 19: "USB3_HOST1_DP",              # USB 2 half of the USB5744 upstream port
    21: "GND",
    23: "USB2_HOST2_DM", 25: "USB2_HOST2_DP",              # USB2517 upstream
    27: "GND",
    29: "USB_AUX_DM", 31: "USB_AUX_DP",                    # USB2517 port 6 back to the front battery port J40
    33: "GND",
    35: "SDMMC0_CLK",                                      # microSD (the slot is on the hub board, at the front edge)
    37: "GND",
    39: "SDMMC0_CMD", 41: "SDMMC0_D0", 43: "SDMMC0_D1",
    45: "GND",
    47: "SDMMC0_D2", 49: "SDMMC0_D3",
    51: "GND",
    53: "SDMMC0_DET_L", 55: "HUB_RESET_SOC_N",
    57: "GND",
    67: "I2C3_SCL_M1", 69: "I2C3_SDA_M1",                  # optional SMBus access to the USB5744 (resistors DNP)
    71: "GND", 73: "GND", 75: "GND",
    # ---- bottom face (even): power ----
    **{n: "VCC5V_BUS" for n in range(2, 25, 2)},           # 12 contacts (0.5 A each): the nine bays' VBUS switches
    **{n: "GND" for n in range(26, 37, 2)},
    38: "VCC_SYS", 40: "VCC_SYS",                          # the hub's 3.3 V / 1.2 V bucks
    42: "GND",
    44: "VCC3V3_SYS", 46: "VCC3V3_SYS",                    # microSD supply
    **{n: "GND" for n in range(48, 59, 2)},
    **{n: "GND" for n in range(68, 75, 2)},
}
POSITIONS = [n for n in range(1, 76) if not 59 <= n <= 66]
assert sorted(PINS) == POSITIONS, "every one of the 67 Key M positions needs exactly one net"


def statement(ref, part):
    """Netlist lines connecting all 67 positions of part `ref` (cpmodel syntax)."""
    items = ["%d=%s" % (n, PINS[n]) for n in POSITIONS]
    lines = ["%s %s %s" % (ref, part, " ".join(items[:12]))]
    for i in range(12, len(items), 12):
        lines.append("P %s %s" % (ref, " ".join(items[i:i + 12])))
    return "\n".join(lines) + "\n"


def pin_names():
    """(pin, name) for the symbol: position number and its net, so the schematic shows the pinout."""
    return [(str(n), "%d_%s" % (n, PINS[n])) for n in POSITIONS]
