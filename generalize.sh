#!/bin/bash

# --- 1. Limpieza de Identidad de Sistema (Machine-ID) ---
# Esto asegura que cada clon obtenga una IP única por DHCP
echo "Reseteando Machine-ID..."
sudo truncate -s 0 /etc/machine-id
if [ -f /var/lib/dbus/machine-id ]; then
    sudo rm -f /var/lib/dbus/machine-id
fi
sudo ln -s /etc/machine-id /var/lib/dbus/machine-id

# --- 2. Limpieza de Seguridad (SSH Host Keys) ---
# Esto obliga al sistema a regenerar llaves únicas al primer arranque
echo "Eliminando llaves SSH antiguas..."
sudo rm -f /etc/ssh/ssh_host_*

# --- 3. Limpieza de Red (Solo para RHEL/CentOS/Rocky) ---
# Elimina identificadores persistentes en configuraciones de red
if [ -d /etc/sysconfig/network-scripts/ ]; then
    echo "Limpiando UUIDs de red (RHEL-based)..."
    sudo find /etc/sysconfig/network-scripts/ -name "ifcfg-*" -exec sed -i '/^HWADDR/d; /^UUID/d' {} +
fi

# --- 4. Limpieza de Rastros y Logs ---
echo "Limpiando logs temporales..."
sudo find /var/log -type f -exec truncate -s 0 {} +

# --- 5. El Golpe Final: Limpieza de Historial y Apagado ---
# Borramos los archivos físicos de historial de Bash y Zsh
echo "Borrando historial de comandos..."
rm -f ~/.bash_history ~/.zsh_history
find /home -name ".*_history" -exec rm -rf {} + 2>/dev/null

# Limpiamos la memoria actual, guardamos el vacío y apagamos
history -c && history -w && sudo poweroff