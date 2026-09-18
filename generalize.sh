#!/bin/bash

# --- 1. System Identity Cleanup (Machine-ID) ---
# Ensures each clone gets a unique IP via DHCP
echo "Resetting Machine-ID..."
sudo truncate -s 0 /etc/machine-id
if [ -f /var/lib/dbus/machine-id ]; then
    sudo rm -f /var/lib/dbus/machine-id
fi
sudo ln -s /etc/machine-id /var/lib/dbus/machine-id

# --- 2. Security Cleanup (SSH Host Keys) ---
# Forces the system to regenerate unique keys on first boot
echo "Removing old SSH host keys..."
sudo rm -f /etc/ssh/ssh_host_*

# --- 3. Network Cleanup (RHEL/CentOS/Rocky only) ---
# Removes persistent identifiers from network configurations
if [ -d /etc/sysconfig/network-scripts/ ]; then
    echo "Cleaning network UUIDs (RHEL-based)..."
    sudo find /etc/sysconfig/network-scripts/ -name "ifcfg-*" -exec sed -i '/^HWADDR/d; /^UUID/d' {} +
fi

# --- 4. Logs and Traces Cleanup ---
echo "Clearing temporary logs..."
sudo find /var/log -type f -exec truncate -s 0 {} +

# --- 5. Final Step: History Cleanup and Shutdown ---
# Delete the physical Bash and Zsh history files
echo "Wiping command history..."
rm -f ~/.bash_history ~/.zsh_history
find /home -name ".*_history" -exec rm -rf {} + 2>/dev/null

# Clear current session memory, write the empty state, and power off
history -c && history -w && sudo poweroff