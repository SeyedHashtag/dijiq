function updateServerInfo() {
    const serverStatusUrl = document.querySelector('.content').dataset.serverStatusUrl;
    fetch(serverStatusUrl)
        .then(response => response.json())
        .then(data => {
            document.getElementById('cpu-usage').textContent = data.cpu_usage;
            document.getElementById('ram-usage').textContent = `${data.ram_usage} / ${data.total_ram}`;
            document.getElementById('online-users').textContent = data.online_users;
            document.getElementById('uptime').textContent = data.uptime;

            document.getElementById('server-ipv4').textContent = `IPv4: ${data.server_ipv4 || 'N/A'}`;
            document.getElementById('server-ipv6').textContent = `IPv6: ${data.server_ipv6 || 'N/A'}`;

            document.getElementById('download-speed').textContent = `🔽 Download: ${data.download_speed}`;
            document.getElementById('upload-speed').textContent = `🔼 Upload: ${data.upload_speed}`;
            document.getElementById('tcp-connections').textContent = `TCP: ${data.tcp_connections}`;
            document.getElementById('udp-connections').textContent = `UDP: ${data.udp_connections}`;

            document.getElementById('reboot-uploaded-traffic').textContent = data.reboot_uploaded_traffic;
            document.getElementById('reboot-downloaded-traffic').textContent = data.reboot_downloaded_traffic;
            document.getElementById('reboot-total-traffic').textContent = data.reboot_total_traffic;

            document.getElementById('user-uploaded-traffic').textContent = data.user_uploaded_traffic;
            document.getElementById('user-downloaded-traffic').textContent = data.user_downloaded_traffic;
            document.getElementById('user-total-traffic').textContent = data.user_total_traffic;
        })
        .catch(error => console.error('Error fetching server info:', error));
}

function updateServiceStatuses() {
    const servicesStatusUrl = document.querySelector('.content').dataset.servicesStatusUrl;
    fetch(servicesStatusUrl)
        .then(response => response.json())
        .then(data => {
            updateServiceBox('hysteria2', data.hysteria_server);
            updateServiceBox('telegrambot', data.hysteria_telegram_bot);
            updateServiceBox('iplimit', data.hysteria_iplimit);
            updateServiceBox('normalsub', data.hysteria_normal_sub);
        })
        .catch(error => console.error('Error fetching service statuses:', error));
}

function updateServiceBox(serviceName, status) {
    const statusElement = document.getElementById(serviceName + '-status');
    const statusBox = document.getElementById(serviceName + '-status-box');

    if (status === true) {
        statusElement.textContent = 'Active';
        statusBox.classList.remove('bg-danger');
        statusBox.classList.add('bg-success');
    } else {
        statusElement.textContent = 'Inactive';
        statusBox.classList.remove('bg-success');
        statusBox.classList.add('bg-danger');
    }
}

document.addEventListener('DOMContentLoaded', function () {
    updateServerInfo();
    updateServiceStatuses();
    setInterval(updateServerInfo, 2000);
    setInterval(updateServiceStatuses, 10000);

    const toggleIpBtn = document.getElementById('toggle-ip-visibility');
    const ipAddressesDiv = document.getElementById('ip-addresses');
    toggleIpBtn.addEventListener('click', function(e) {
        e.preventDefault();
        const isBlurred = ipAddressesDiv.style.filter === 'blur(5px)';
        ipAddressesDiv.style.filter = isBlurred ? 'none' : 'blur(5px)';
        toggleIpBtn.querySelector('i').classList.toggle('fa-eye');
        toggleIpBtn.querySelector('i').classList.toggle('fa-eye-slash');
    });
});