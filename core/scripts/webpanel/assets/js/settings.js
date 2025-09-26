$(document).ready(function () {
    const contentSection = document.querySelector('.content');

    const API_URLS = {
        serverServicesStatus: contentSection.dataset.serverServicesStatusUrl,
        getIp: contentSection.dataset.getIpUrl,
        getAllNodes: contentSection.dataset.getAllNodesUrl,
        addNode: contentSection.dataset.addNodeUrl,
        deleteNode: contentSection.dataset.deleteNodeUrl,
        getAllExtraConfigs: contentSection.dataset.getAllExtraConfigsUrl,
        addExtraConfig: contentSection.dataset.addExtraConfigUrl,
        deleteExtraConfig: contentSection.dataset.deleteExtraConfigUrl,
        normalSubGetSubpath: contentSection.dataset.normalSubGetSubpathUrl,
        telegramGetInterval: contentSection.dataset.telegramGetIntervalUrl,
        getIpLimitConfig: contentSection.dataset.getIpLimitConfigUrl,
        normalSubEditSubpath: contentSection.dataset.normalSubEditSubpathUrl,
        setupDecoy: contentSection.dataset.setupDecoyUrl,
        stopDecoy: contentSection.dataset.stopDecoyUrl,
        getDecoyStatus: contentSection.dataset.getDecoyStatusUrl,
        telegramStart: contentSection.dataset.telegramStartUrl,
        telegramStop: contentSection.dataset.telegramStopUrl,
        telegramSetInterval: contentSection.dataset.telegramSetIntervalUrl,
        normalSubStart: contentSection.dataset.normalSubStartUrl,
        normalSubStop: contentSection.dataset.normalSubStopUrl,
        editIp: contentSection.dataset.editIpUrl,
        backup: contentSection.dataset.backupUrl,
        restore: contentSection.dataset.restoreUrl,
        startIpLimit: contentSection.dataset.startIpLimitUrl,
        stopIpLimit: contentSection.dataset.stopIpLimitUrl,
        configIpLimit: contentSection.dataset.configIpLimitUrl,
        statusWarp: contentSection.dataset.statusWarpUrl,
        installWarp: contentSection.dataset.installWarpUrl,
        uninstallWarp: contentSection.dataset.uninstallWarpUrl,
        configureWarp: contentSection.dataset.configureWarpUrl
    };

    initUI();
    fetchDecoyStatus();
    fetchNodes();
    fetchExtraConfigs();

    function escapeHtml(text) {
        var map = {
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        };
        if (text === null || typeof text === 'undefined') {
            return '';
        }
        return String(text).replace(/[&<>"']/g, function(m) { return map[m]; });
    }

    function isValidURI(uri) {
        if (!uri) return false;
        const lowerUri = uri.toLowerCase();
        return lowerUri.startsWith("vmess://") || lowerUri.startsWith("vless://") || lowerUri.startsWith("ss://") || lowerUri.startsWith("trojan://");
    }

    function isValidPath(path) {
        if (!path) return false;
        return path.trim() !== '';
    }

    function isValidDomain(domain) {
        if (!domain) return false;
        const lowerDomain = domain.toLowerCase();
        return !lowerDomain.startsWith("http://") && !lowerDomain.startsWith("https://");
    }

    function isValidPort(port) {
        if (!port) return false;
        return /^[0-9]+$/.test(port) && parseInt(port) > 0 && parseInt(port) <= 65535;
    }

    function isValidSubPath(subpath) {
        if (!subpath) return false;
        return /^[a-zA-Z0-9]+$/.test(subpath);
    }

    function isValidIPorDomain(input) {
        if (input === null || typeof input === 'undefined') return false;
        input = input.trim();
        if (input === '') return false;

        const ipV4Regex = /^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$/;
        const ipV6Regex = /^(([0-9a-fA-F]{1,4}:){7,7}([0-9a-fA-F]{1,4}|:)|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$/;
        const domainRegex = /^(?!-)(?:[a-zA-Z\d-]{0,62}[a-zA-Z\d]\.){1,126}(?!\d+$)[a-zA-Z\d]{1,63}$/;
        const lowerInput = input.toLowerCase();

        return ipV4Regex.test(input) || ipV6Regex.test(input) || domainRegex.test(lowerInput);
    }

    function isValidPositiveNumber(value) {
        if (!value) return false;
        return /^[0-9]+$/.test(value) && parseInt(value) > 0;
    }

    function confirmAction(actionName, callback) {
        Swal.fire({
            title: `Are you sure?`,
            text: `Do you really want to ${actionName}?`,
            icon: "warning",
            showCancelButton: true,
            confirmButtonColor: "#3085d6",
            cancelButtonColor: "#d33",
            confirmButtonText: "Yes, proceed!",
            cancelButtonText: "Cancel"
        }).then((result) => {
            if (result.isConfirmed) {
                callback();
            }
        });
    }

    function sendRequest(url, type, data, successMessage, buttonSelector, showReload = true, postSuccessCallback = null) {
        $.ajax({
            url: url,
            type: type,
            contentType: "application/json",
            data: data ? JSON.stringify(data) : null,
            beforeSend: function() {
                if (buttonSelector) {
                    $(buttonSelector).prop('disabled', true);
                     $(buttonSelector + ' .spinner-border').show();
                }
            },
            success: function (response) {
                Swal.fire("Success!", successMessage, "success").then(() => {
                    if (showReload) {
                        location.reload();
                    } else {
                        if (postSuccessCallback) {
                            postSuccessCallback(response);
                        }
                    }
                });
            },
            error: function (xhr, status, error) {
                let errorMessage = "An unexpected error occurred.";
                if (xhr.responseJSON && xhr.responseJSON.detail) {
                    const detail = xhr.responseJSON.detail;
                    if (Array.isArray(detail)) {
                        errorMessage = detail.map(err => `Error in '${err.loc[1]}': ${err.msg}`).join('\n');
                    } else if (typeof detail === 'string') {
                        let userMessage = detail;
                        const failMarker = 'failed with exit code';
                        const markerIndex = detail.indexOf(failMarker);
                        if (markerIndex > -1) {
                            const colonIndex = detail.indexOf(':', markerIndex);
                            if (colonIndex > -1) {
                                userMessage = detail.substring(colonIndex + 1).trim();
                            }
                        }
                        errorMessage = userMessage;
                    }
                }
                Swal.fire("Error!", errorMessage, "error");
                console.error("AJAX Error:", status, error, xhr.responseText);
            },
            complete: function() {
                if (buttonSelector) {
                    $(buttonSelector).prop('disabled', false);
                    $(buttonSelector + ' .spinner-border').hide();
                }
            }
        });
    }

    function validateForm(formId) {
        let isValid = true;
        $(`#${formId} .form-control:visible`).each(function () {
            const input = $(this);
            const id = input.attr('id');
            let fieldValid = true;

            if (id === 'normal_domain' || id === 'decoy_domain') {
                fieldValid = isValidDomain(input.val());
            } else if (id === 'normal_port') {
                fieldValid = isValidPort(input.val());
            } else if (id === 'normal_subpath_input') {
                fieldValid = isValidSubPath(input.val());
            } else if (id === 'ipv4' || id === 'ipv6') {
                fieldValid = (input.val().trim() === '') ? true : isValidIPorDomain(input.val());
            } else if (id === 'node_ip') {
                fieldValid = isValidIPorDomain(input.val());
            } else if (id === 'node_name' || id === 'extra_config_name') {
                fieldValid = input.val().trim() !== "";
            } else if (id === 'extra_config_uri') {
                fieldValid = isValidURI(input.val());
            } else if (id === 'block_duration' || id === 'max_ips' || id === 'telegram_backup_interval') {
                if (input.val().trim() === '' && id === 'telegram_backup_interval') {
                   fieldValid = true;
                } else {
                   fieldValid = isValidPositiveNumber(input.val());
                }
            } else if (id === 'decoy_path') {
                fieldValid = isValidPath(input.val());
            } else {
                if (input.attr('placeholder') && input.attr('placeholder').includes('Enter') && !input.attr('id').startsWith('ipv')) {
                     fieldValid = input.val().trim() !== "";
                }
            }

            if (!fieldValid) {
                input.addClass('is-invalid');
                isValid = false;
            } else {
                input.removeClass('is-invalid');
            }
        });
        return isValid;
    }

    function initUI() {
        $.ajax({
            url: API_URLS.serverServicesStatus,
            type: "GET",
            success: function (data) {
                updateServiceUI(data);
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch service status:", error, xhr.responseText);
                 Swal.fire("Error!", "Could not fetch service statuses.", "error");
            }
        });

         $.ajax({
            url: API_URLS.getIp,
            type: "GET",
            success: function (data) {
                $("#ipv4").val(data.ipv4 || "");
                $("#ipv6").val(data.ipv6 || "");
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch IP addresses:", error, xhr.responseText);
            }
        });
    }

    function fetchNodes() {
        $.ajax({
            url: API_URLS.getAllNodes,
            type: "GET",
            success: function (nodes) {
                renderNodes(nodes);
            },
            error: function(xhr) {
                Swal.fire("Error!", "Failed to fetch external nodes list.", "error");
                console.error("Error fetching nodes:", xhr.responseText);
            }
        });
    }

    function renderNodes(nodes) {
        const tableBody = $("#nodes_table tbody");
        tableBody.empty();

        if (nodes && nodes.length > 0) {
            $("#nodes_table").show();
            $("#no_nodes_message").hide();
            nodes.forEach(node => {
                const row = `<tr>
                                <td>${escapeHtml(node.name)}</td>
                                <td>${escapeHtml(node.ip)}</td>
                                <td>
                                    <button class="btn btn-xs btn-danger delete-node-btn" data-name="${escapeHtml(node.name)}">
                                        <i class="fas fa-trash"></i> Delete
                                    </button>
                                </td>
                            </tr>`;
                tableBody.append(row);
            });
        } else {
            $("#nodes_table").hide();
            $("#no_nodes_message").show();
        }
    }

    function addNode() {
        if (!validateForm('add_node_form')) return;

        const name = $("#node_name").val().trim();
        const ip = $("#node_ip").val().trim();

        confirmAction(`add the node '${name}'`, function () {
            sendRequest(
                API_URLS.addNode,
                "POST",
                { name: name, ip: ip },
                `Node '${name}' added successfully!`,
                "#add_node_btn",
                false,
                function() {
                    $("#node_name").val('');
                    $("#node_ip").val('');
                    $("#add_node_form .form-control").removeClass('is-invalid');
                    fetchNodes();
                }
            );
        });
    }

    function deleteNode(nodeName) {
         confirmAction(`delete the node '${nodeName}'`, function () {
            sendRequest(
                API_URLS.deleteNode,
                "POST",
                { name: nodeName },
                `Node '${nodeName}' deleted successfully!`,
                null,
                false,
                fetchNodes
            );
        });
    }

    function fetchExtraConfigs() {
        $.ajax({
            url: API_URLS.getAllExtraConfigs,
            type: "GET",
            success: function (configs) {
                renderExtraConfigs(configs);
            },
            error: function(xhr) {
                Swal.fire("Error!", "Failed to fetch extra configurations.", "error");
                console.error("Error fetching extra configs:", xhr.responseText);
            }
        });
    }

    function renderExtraConfigs(configs) {
        const tableBody = $("#extra_configs_table tbody");
        tableBody.empty();

        if (configs && configs.length > 0) {
            $("#extra_configs_table").show();
            $("#no_extra_configs_message").hide();
            configs.forEach(config => {
                const shortUri = config.uri.length > 50 ? config.uri.substring(0, 50) + '...' : config.uri;
                const row = `<tr>
                                <td>${escapeHtml(config.name)}</td>
                                <td title="${escapeHtml(config.uri)}">${escapeHtml(shortUri)}</td>
                                <td>
                                    <button class="btn btn-xs btn-danger delete-extra-config-btn" data-name="${escapeHtml(config.name)}">
                                        <i class="fas fa-trash"></i> Delete
                                    </button>
                                </td>
                            </tr>`;
                tableBody.append(row);
            });
        } else {
            $("#extra_configs_table").hide();
            $("#no_extra_configs_message").show();
        }
    }

    function addExtraConfig() {
        if (!validateForm('add_extra_config_form')) return;

        const name = $("#extra_config_name").val().trim();
        const uri = $("#extra_config_uri").val().trim();

        confirmAction(`add the configuration '${name}'`, function () {
            sendRequest(
                API_URLS.addExtraConfig,
                "POST",
                { name: name, uri: uri },
                `Configuration '${name}' added successfully!`,
                "#add_extra_config_btn",
                false,
                function() {
                    $("#extra_config_name").val('');
                    $("#extra_config_uri").val('');
                    $("#add_extra_config_form .form-control").removeClass('is-invalid');
                    fetchExtraConfigs();
                }
            );
        });
    }

    function deleteExtraConfig(configName) {
         confirmAction(`delete the configuration '${configName}'`, function () {
            sendRequest(
                API_URLS.deleteExtraConfig,
                "POST",
                { name: configName },
                `Configuration '${configName}' deleted successfully!`,
                null,
                false,
                fetchExtraConfigs
            );
        });
    }

    function updateServiceUI(data) {
         const servicesMap = {
            "hysteria_telegram_bot": "#telegram_form",
            "hysteria_normal_sub": "#normal_sub_service_form",
            "hysteria_iplimit": "#ip-limit-service",
            "hysteria_warp": "#warp_service"
        };

        Object.keys(servicesMap).forEach(serviceKey => {
            let isRunning = data[serviceKey];

            if (serviceKey === "hysteria_telegram_bot") {
                const $form = $("#telegram_form");
                if (isRunning) {
                    $form.find('[data-group="start-only"]').hide();
                    $("#telegram_start").hide();
                    $("#telegram_stop").show();
                    $("#telegram_save_interval").show();
                    if ($form.find(".alert-info").length === 0) {
                       $form.prepend(`<div class='alert alert-info'>Service is running. You can stop it or change the backup interval.</div>`);
                    }
                    fetchTelegramBackupInterval();
                } else {
                    $form.find('[data-group="start-only"]').show();
                    $("#telegram_start").show();
                    $("#telegram_stop").hide();
                    $("#telegram_save_interval").hide();
                    $form.find(".alert-info").remove();
                    $("#telegram_backup_interval").val("");
                }

            } else if (serviceKey === "hysteria_normal_sub") {
                const $normalForm = $("#normal_sub_service_form");
                const $normalFormGroups = $normalForm.find(".form-group");
                const $normalStartBtn = $("#normal_start");
                const $normalStopBtn = $("#normal_stop");
                const $normalSubConfigTabLi = $(".normal-sub-config-tab-li");

                if (isRunning) {
                    $normalFormGroups.hide();
                    $normalStartBtn.hide();
                    $normalStopBtn.show();
                    if ($normalForm.find(".alert-info").length === 0) {
                        $normalForm.prepend(`<div class='alert alert-info'>NormalSub service is running. You can stop it or configure its subpath.</div>`);
                    }
                    $normalSubConfigTabLi.show();
                    fetchNormalSubPath();
                } else {
                    $normalFormGroups.show();
                    $normalStartBtn.show();
                    $normalStopBtn.hide();
                    $normalForm.find(".alert-info").remove();
                    $normalSubConfigTabLi.hide();
                    if ($('#normal-sub-config-link-tab').hasClass('active')) {
                        $('#normal-tab').tab('show');
                    }
                    $("#normal_subpath_input").val("");
                    $("#normal_subpath_input").removeClass('is-invalid');
                }
            } else if (serviceKey === "hysteria_iplimit") {
                const $ipLimitServiceForm = $("#ip_limit_service_form");
                const $configTabLi = $(".ip-limit-config-tab-li");
                if (isRunning) {
                   $("#ip_limit_start").hide();
                   $("#ip_limit_stop").show();
                   $configTabLi.show();
                   fetchIpLimitConfig();
                   if ($ipLimitServiceForm.find(".alert-info").length === 0) {
                       $ipLimitServiceForm.prepend(`<div class='alert alert-info'>IP-Limit service is running. You can stop it if needed.</div>`);
                   }
                } else {
                   $("#ip_limit_start").show();
                   $("#ip_limit_stop").hide();
                   $configTabLi.hide();
                   if ($('#ip-limit-config-tab').hasClass('active')) {
                       $('#ip-limit-service-tab').tab('show');
                   }
                   $ipLimitServiceForm.find(".alert-info").remove();
                   $("#block_duration").val("");
                   $("#max_ips").val("");
                   $("#block_duration, #max_ips").removeClass('is-invalid');
                }
            } else if (serviceKey === "hysteria_warp") {
                const isWarpServiceRunning = data[serviceKey];
                if (isWarpServiceRunning) {
                    $("#warp_initial_controls").hide();
                    $("#warp_active_controls").show();
                    fetchWarpFullStatusAndConfig();
                } else {
                    $("#warp_initial_controls").show();
                    $("#warp_active_controls").hide();
                    if ($("#warp_config_form").length > 0) {
                       $("#warp_config_form")[0].reset();
                    }
                }
            }
        });
    }

    function fetchNormalSubPath() {
        $.ajax({
            url: API_URLS.normalSubGetSubpath,
            type: "GET",
            success: function (data) {
                $("#normal_subpath_input").val(data.subpath || "");
                if (data.subpath) {
                    $("#normal_subpath_input").removeClass('is-invalid');
                }
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch NormalSub subpath:", error, xhr.responseText);
                $("#normal_subpath_input").val("");
            }
        });
    }

    function fetchTelegramBackupInterval() {
        $.ajax({
            url: API_URLS.telegramGetInterval,
            type: "GET",
            success: function (data) {
                if (data.backup_interval) {
                    $("#telegram_backup_interval").val(data.backup_interval);
                } else {
                    $("#telegram_backup_interval").val("");
                }
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch Telegram backup interval:", error, xhr.responseText);
                $("#telegram_backup_interval").val("");
            }
        });
    }

    function fetchIpLimitConfig() {
        $.ajax({
            url: API_URLS.getIpLimitConfig,
            type: "GET",
            success: function (data) {
                $("#block_duration").val(data.block_duration || "");
                $("#max_ips").val(data.max_ips || "");
                if (data.block_duration) $("#block_duration").removeClass('is-invalid');
                if (data.max_ips) $("#max_ips").removeClass('is-invalid');
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch IP Limit config:", error, xhr.responseText);
                $("#block_duration").val("");
                $("#max_ips").val("");
            }
        });
    }

    function editNormalSubPath() {
        if (!validateForm('normal_sub_config_form')) return;
        const subpath = $("#normal_subpath_input").val();

        confirmAction("change the NormalSub subpath to '" + subpath + "'", function () {
            sendRequest(
                API_URLS.normalSubEditSubpath,
                "PUT",
                { subpath: subpath },
                "NormalSub subpath updated successfully!",
                "#normal_subpath_save_btn",
                false,
                fetchNormalSubPath
            );
        });
    }

    function setupDecoy() {
        if (!validateForm('decoy_form')) return;
        const domain = $("#decoy_domain").val();
        const path = $("#decoy_path").val();
        confirmAction("set up the decoy site", function () {
            sendRequest(
                API_URLS.setupDecoy,
                "POST",
                { domain: domain, decoy_path: path },
                "Decoy site setup initiated successfully!",
                "#decoy_setup",
                false,
                function() { setTimeout(fetchDecoyStatus, 1000); }
            );
        });
    }

    function stopDecoy() {
        confirmAction("stop the decoy site", function () {
            sendRequest(
                API_URLS.stopDecoy,
                "POST",
                null,
                "Decoy site stop initiated successfully!",
                "#decoy_stop",
                false,
                function() { setTimeout(fetchDecoyStatus, 1000); }
            );
        });
    }

    function fetchDecoyStatus() {
        $.ajax({
            url: API_URLS.getDecoyStatus,
            type: "GET",
            success: function (data) {
                updateDecoyStatusUI(data);
            },
            error: function (xhr, status, error) {
                $("#decoy_status_message").html('<div class="alert alert-danger">Failed to fetch decoy status.</div>');
                console.error("Failed to fetch decoy status:", error, xhr.responseText);
            }
        });
    }

    function updateDecoyStatusUI(data) {
        const $form = $("#decoy_form");
        const $formGroups = $form.find(".form-group");
        const $setupBtn = $("#decoy_setup");
        const $stopBtn = $("#decoy_stop");
        const $alertInfo = $form.find(".alert-info");

        if (data.active) {
            $formGroups.hide();
            $setupBtn.hide();
            $stopBtn.show();
            if ($alertInfo.length === 0) {
                $form.prepend(`<div class='alert alert-info'>Decoy site is running. You can stop it if needed.</div>`);
            } else {
                $alertInfo.text('Decoy site is running. You can stop it if needed.');
            }
            $("#decoy_status_message").html(`
                <strong>Status:</strong> <span class="text-success">Active</span><br>
                <strong>Path:</strong> ${data.path || 'N/A'}
            `);
        } else {
            $formGroups.show();
            $setupBtn.show();
            $stopBtn.hide();
            $alertInfo.remove();
            $("#decoy_status_message").html('<strong>Status:</strong> <span class="text-danger">Not Active</span>');
        }
    }

    function startTelegram() {
        if (!validateForm('telegram_form')) return;
        const apiToken = $("#telegram_api_token").val();
        const adminId = $("#telegram_admin_id").val();
        let backupInterval = $("#telegram_backup_interval").val();

        const data = {
            token: apiToken,
            admin_id: adminId
        };
        if (backupInterval) {
            data.backup_interval = parseInt(backupInterval);
        }

        confirmAction("start the Telegram bot", function () {
            sendRequest(
                API_URLS.telegramStart,
                "POST",
                data,
                "Telegram bot started successfully!",
                "#telegram_start"
            );
        });
    }

    function stopTelegram() {
        confirmAction("stop the Telegram bot", function () {
            sendRequest(
                API_URLS.telegramStop,
                "DELETE",
                null,
                "Telegram bot stopped successfully!",
                "#telegram_stop"
            );
        });
    }

    function saveTelegramInterval() {
        if (!validateForm('telegram_form')) return;
        let backupInterval = $("#telegram_backup_interval").val();

        if (!backupInterval) {
             Swal.fire("Error!", "Backup interval cannot be empty.", "error");
            return;
        }

        const data = {
            backup_interval: parseInt(backupInterval)
        };

        confirmAction(`change the backup interval to ${backupInterval} hours`, function () {
            sendRequest(
                API_URLS.telegramSetInterval,
                "POST",
                data,
                "Backup interval updated successfully!",
                "#telegram_save_interval",
                false,
                fetchTelegramBackupInterval
            );
        });
    }


    function startNormal() {
        if (!validateForm('normal_sub_service_form')) return;
        const domain = $("#normal_domain").val();
        const port = $("#normal_port").val();
        confirmAction("start the normal subscription", function () {
            sendRequest(
                API_URLS.normalSubStart,
                "POST",
                { domain: domain, port: port },
                "Normal subscription started successfully!",
                "#normal_start"
            );
        });
    }

    function stopNormal() {
        confirmAction("stop the normal subscription", function () {
            sendRequest(
                API_URLS.normalSubStop,
                "DELETE",
                null,
                "Normal subscription stopped successfully!",
                "#normal_stop"
            );
        });
    }

    function saveIP() {
        if (!validateForm('change_ip_form')) return;
        const ipv4 = $("#ipv4").val().trim() || null;
        const ipv6 = $("#ipv6").val().trim() || null;
        confirmAction("save the new IP settings", function () {
            sendRequest(
                API_URLS.editIp,
                "POST",
                { ipv4: ipv4, ipv6: ipv6 },
                "IP settings saved successfully!",
                "#ip_change"
            );
        });
    }

    function downloadBackup() {
        window.location.href = API_URLS.backup;
         Swal.fire("Starting Download", "Your backup download should start shortly.", "info");
    }

    function uploadBackup() {
        var fileInput = document.getElementById('backup_file');
        var file = fileInput.files[0];

        if (!file) {
            Swal.fire("Error!", "Please select a file to upload.", "error");
            return;
        }
        if (!file.name.toLowerCase().endsWith('.zip')) {
           Swal.fire("Error!", "Only .zip files are allowed for restore.", "error");
           return;
        }

        confirmAction(`restore the system from the selected backup file (${file.name})`, function() {
            var formData = new FormData();
            formData.append('file', file);

            var progressBar = document.getElementById('backup_progress_bar');
            var progressContainer = progressBar.parentElement;
            var statusDiv = document.getElementById('backup_status');

            progressContainer.style.display = 'block';
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            statusDiv.innerText = 'Uploading...';
            statusDiv.className = 'mt-2';

            $.ajax({
                url: API_URLS.restore,
                type: "POST",
                data: formData,
                processData: false,
                contentType: false,
                xhr: function() {
                    var xhr = new window.XMLHttpRequest();
                    xhr.upload.addEventListener("progress", function(evt) {
                        if (evt.lengthComputable) {
                            var percentComplete = Math.round((evt.loaded / evt.total) * 100);
                            progressBar.style.width = percentComplete + '%';
                            progressBar.setAttribute('aria-valuenow', percentComplete);
                            statusDiv.innerText = `Uploading... ${percentComplete}%`;
                        }
                    }, false);
                    return xhr;
                },
                success: function(response) {
                    progressBar.style.width = '100%';
                    progressBar.classList.add('bg-success');
                    statusDiv.innerText = 'Backup restored successfully! Reloading page...';
                    statusDiv.className = 'mt-2 text-success';
                    Swal.fire("Success!", "Backup restored successfully!", "success").then(() => {
                            location.reload();
                    });
                    console.log("Restore Success:", response);
                },
                error: function(xhr, status, error) {
                    progressBar.classList.add('bg-danger');
                    let detail = (xhr.responseJSON && xhr.responseJSON.detail) ? xhr.responseJSON.detail : 'Check console for details.';
                    statusDiv.innerText = `Error restoring backup: ${detail}`;
                    statusDiv.className = 'mt-2 text-danger';
                    Swal.fire("Error!", `Failed to restore backup. ${detail}`, "error");
                    console.error("Restore Error:", status, error, xhr.responseText);
                },
                complete: function() {
                   fileInput.value = '';
                }
            });
        });
    }

    function startIPLimit() {
         confirmAction("start the IP Limit service", function () {
            sendRequest(
                API_URLS.startIpLimit,
                "POST",
                null,
                "IP Limit service started successfully!",
                "#ip_limit_start"
            );
        });
    }

    function stopIPLimit() {
         confirmAction("stop the IP Limit service", function () {
            sendRequest(
                API_URLS.stopIpLimit,
                "POST",
                null,
                "IP Limit service stopped successfully!",
                "#ip_limit_stop"
            );
        });
    }

    function configIPLimit() {
        if (!validateForm('ip_limit_config_form')) return;
        const blockDuration = $("#block_duration").val();
        const maxIps = $("#max_ips").val();
         confirmAction("save the IP Limit configuration", function () {
            sendRequest(
                API_URLS.configIpLimit,
                "POST",
                { block_duration: parseInt(blockDuration), max_ips: parseInt(maxIps) },
                "IP Limit configuration saved successfully!",
                "#ip_limit_change_config",
                false,
                fetchIpLimitConfig
            );
        });
    }

    function fetchWarpFullStatusAndConfig() {
        $.ajax({
            url: API_URLS.statusWarp,
            type: "GET",
            success: function (data) {
                $("#warp_all_traffic").prop('checked', data.all_traffic_via_warp || false);
                $("#warp_popular_sites").prop('checked', data.popular_sites_via_warp || false);
                $("#warp_domestic_sites").prop('checked', data.domestic_sites_via_warp || false);
                $("#warp_block_adult_sites").prop('checked', data.block_adult_content || false);

                $("#warp_initial_controls").hide();
                $("#warp_active_controls").show();
            },
            error: function (xhr, status, error) {
                let errorMsg = "Failed to fetch WARP configuration.";
                 if (xhr.responseJSON && xhr.responseJSON.detail) {
                    errorMsg = xhr.responseJSON.detail;
                }
                console.error("Error fetching WARP config:", errorMsg, xhr.responseText);

                if (xhr.status === 404) {
                    $("#warp_initial_controls").show();
                    $("#warp_active_controls").hide();
                    if ($("#warp_config_form").length > 0) {
                       $("#warp_config_form")[0].reset();
                    }
                    Swal.fire("Info", "WARP service might not be fully configured. Please try reinstalling if issues persist.", "info");
                } else {
                     if ($("#warp_config_form").length > 0) {
                       $("#warp_config_form")[0].reset();
                    }
                     Swal.fire("Warning", "Could not load current WARP configuration values. Please check manually or re-save.", "warning");
                }
            }
        });
    }

    $("#warp_start_btn").on("click", function() {
        confirmAction("install and start WARP", function () {
            sendRequest(
                API_URLS.installWarp,
                "POST",
                null,
                "WARP installation request sent. The page will reload.",
                "#warp_start_btn",
                true
            );
        });
    });

    $("#warp_stop_btn").on("click", function() {
        confirmAction("stop and uninstall WARP", function () {
            sendRequest(
                API_URLS.uninstallWarp,
                "DELETE",
                null,
                "WARP uninstallation request sent. The page will reload.",
                "#warp_stop_btn",
                true
            );
        });
    });

    $("#warp_save_config_btn").on("click", function() {
        const configData = {
            all: $("#warp_all_traffic").is(":checked"),
            popular_sites: $("#warp_popular_sites").is(":checked"),
            domestic_sites: $("#warp_domestic_sites").is(":checked"),
            block_adult_sites: $("#warp_block_adult_sites").is(":checked")
        };
        confirmAction("save WARP configuration", function () {
            sendRequest(
                API_URLS.configureWarp,
                "POST",
                configData,
                "WARP configuration saved successfully!",
                "#warp_save_config_btn",
                false,
                fetchWarpFullStatusAndConfig
            );
        });
    });

    $("#telegram_start").on("click", startTelegram);
    $("#telegram_stop").on("click", stopTelegram);
    $("#telegram_save_interval").on("click", saveTelegramInterval);
    $("#normal_start").on("click", startNormal);
    $("#normal_stop").on("click", stopNormal);
    $("#normal_subpath_save_btn").on("click", editNormalSubPath);
    $("#ip_change").on("click", saveIP);
    $("#download_backup").on("click", downloadBackup);
    $("#upload_backup").on("click", uploadBackup);
    $("#ip_limit_start").on("click", startIPLimit);
    $("#ip_limit_stop").on("click", stopIPLimit);
    $("#ip_limit_change_config").on("click", configIPLimit);
    $("#decoy_setup").on("click", setupDecoy);
    $("#decoy_stop").on("click", stopDecoy);
    $("#add_node_btn").on("click", addNode);
    $("#nodes_table").on("click", ".delete-node-btn", function() {
        const nodeName = $(this).data("name");
        deleteNode(nodeName);
    });
    $("#add_extra_config_btn").on("click", addExtraConfig);
    $("#extra_configs_table").on("click", ".delete-extra-config-btn", function() {
        const configName = $(this).data("name");
        deleteExtraConfig(configName);
    });

    $('#normal_domain, #decoy_domain').on('input', function () {
        if (isValidDomain($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).removeClass('is-invalid');
        }
    });

    $('#normal_port').on('input', function () {
         if (isValidPort($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).removeClass('is-invalid');
        }
    });

    $('#normal_subpath_input').on('input', function () {
         if (isValidSubPath($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).removeClass('is-invalid');
        }
    });

    $('#ipv4, #ipv6, #node_ip').on('input', function () {
        const isLocalIpField = $(this).attr('id') === 'ipv4' || $(this).attr('id') === 'ipv6';
        if (isLocalIpField && $(this).val().trim() === '') {
             $(this).removeClass('is-invalid');
        } else if (isValidIPorDomain($(this).val())) {
             $(this).removeClass('is-invalid');
        } else {
            $(this).addClass('is-invalid');
        }
    });

    $('#node_name, #extra_config_name').on('input', function() {
        if ($(this).val().trim() !== "") {
            $(this).removeClass('is-invalid');
        } else {
            $(this).addClass('is-invalid');
        }
    });

    $('#extra_config_uri').on('input', function () {
        if (isValidURI($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        }
    });

    $('#telegram_api_token, #telegram_admin_id').on('input', function () {
        if ($(this).val().trim() !== "") {
            $(this).removeClass('is-invalid');
        } else {
             $(this).addClass('is-invalid');
        }
    });
     $('#block_duration, #max_ips, #telegram_backup_interval').on('input', function () {
        if ($(this).attr('id') === 'telegram_backup_interval' && $(this).val().trim() === '') {
            $(this).removeClass('is-invalid');
            return;
        }
        if (isValidPositiveNumber($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).addClass('is-invalid');
        }
    });

    $('#decoy_path').on('input', function () {
        if (isValidPath($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).addClass('is-invalid');
        }
    });
});