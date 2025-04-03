source /etc/dijiq/core/scripts/path.sh || true 

echo "Uninstalling dijiq..."

SERVICES=(
    "dijiq-server.service"
    "dijiq-telegram-bot.service"
)

echo "Running uninstallation script..."
bash <(curl -fsSL https://get.hy2.sh/) --remove >/dev/null 2>&1

echo "Removing dijiq folder..."
rm -rf /etc/dijiq >/dev/null 2>&1

echo "Deleting dijiq user..."
userdel -r dijiq >/dev/null 2>&1 || true 

echo "Stop/Disabling dijiq Services..."
for service in "${SERVICES[@]}" "dijiq-server@*.service"; do
    echo "Stopping and disabling $service..."
    systemctl stop "$service" > /dev/null 2>&1 || true  
    systemctl disable "$service" > /dev/null 2>&1 || true 
done

echo "Removing systemd service files..."
for service in "${SERVICES[@]}" "dijiq-server@*.service"; do
    echo "Removing service file: $service"
    rm -f "/etc/systemd/system/$service" "/etc/systemd/system/multi-user.target.wants/$service" >/dev/null 2>&1
done

echo "Reloading systemd daemon..."
systemctl daemon-reload >/dev/null 2>&1

echo "Removing cron jobs..."
if crontab -l 2>/dev/null | grep -q "dijiq"; then 
    (crontab -l | grep -v "dijiq" | crontab -) >/dev/null 2>&1
fi

echo "Removing alias 'dijiq' from .bashrc..."
sed -i '/alias dijiq=.*\/etc\/dijiq\/menu.sh/d' ~/.bashrc 2>/dev/null || true 

echo "dijiq uninstalled!"
echo ""
