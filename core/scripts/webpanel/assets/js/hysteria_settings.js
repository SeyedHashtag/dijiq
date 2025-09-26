$(document).ready(function () {
    const contentSection = document.querySelector('.content');

    const API_URLS = {
        getPort: contentSection.dataset.getPortUrl,
        getSni: contentSection.dataset.getSniUrl,
        checkObfs: contentSection.dataset.checkObfsUrl,
        enableObfs: contentSection.dataset.enableObfsUrl,
        disableObfs: contentSection.dataset.disableObfsUrl,
        setPortTemplate: contentSection.dataset.setPortUrlTemplate,
        setSniTemplate: contentSection.dataset.setSniUrlTemplate,
        updateGeoTemplate: contentSection.dataset.updateGeoUrlTemplate
    };

    function isValidDomain(domain) {
        if (!domain) return false;
        const lowerDomain = domain.toLowerCase();
        return !lowerDomain.startsWith("http://") && !lowerDomain.startsWith("https://");
    }

    function isValidPort(port) {
        if (!port) return false;
        return /^[0-9]+$/.test(port) && parseInt(port) > 0 && parseInt(port) <= 65535;
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

            if (id === 'sni_domain') {
                fieldValid = isValidDomain(input.val());
            } else if (id === 'hysteria_port') {
                fieldValid = isValidPort(input.val());
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
            url: API_URLS.getPort,
            type: "GET",
            success: function (data) {
                $("#hysteria_port").val(data.port || "");
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch port:", error, xhr.responseText);
            }
        });

        $.ajax({
            url: API_URLS.getSni,
            type: "GET",
            success: function (data) {
                $("#sni_domain").val(data.sni || "");
            },
            error: function (xhr, status, error) {
                console.error("Failed to fetch SNI domain:", error, xhr.responseText);
            }
        });
    }

    function fetchObfsStatus() {
        $.ajax({
            url: API_URLS.checkObfs,
            type: "GET",
            success: function (data) {
                updateObfsUI(data.obfs);
            },
            error: function (xhr, status, error) {
                $("#obfs_status_message").html('<span class="text-danger">Failed to fetch OBFS status.</span>');
                console.error("Failed to fetch OBFS status:", error, xhr.responseText);
                 $("#obfs_enable_btn").hide();
                $("#obfs_disable_btn").hide();
            }
        });
    }

    function updateObfsUI(statusMessage) {
        $("#obfs_status_message").text(statusMessage);
        if (statusMessage === "OBFS is active.") {
            $("#obfs_enable_btn").hide();
            $("#obfs_disable_btn").show();
            $("#obfs_status_container").removeClass("border-danger border-warning alert-danger alert-warning").addClass("border-success alert-success");
        } else if (statusMessage === "OBFS is not active.") {
            $("#obfs_enable_btn").show();
            $("#obfs_disable_btn").hide();
            $("#obfs_status_container").removeClass("border-success border-danger alert-success alert-danger").addClass("border-warning alert-warning");
        } else {
            $("#obfs_enable_btn").hide();
            $("#obfs_disable_btn").hide();
            $("#obfs_status_container").removeClass("border-success border-warning alert-success alert-warning").addClass("border-danger alert-danger");
        }
    }

    function enableObfs() {
        confirmAction("enable OBFS", function () {
            sendRequest(
                API_URLS.enableObfs,
                "GET",
                null,
                "OBFS enabled successfully!",
                "#obfs_enable_btn",
                false,
                fetchObfsStatus
            );
        });
    }

    function disableObfs() {
        confirmAction("disable OBFS", function () {
            sendRequest(
                API_URLS.disableObfs,
                "GET",
                null,
                "OBFS disabled successfully!",
                "#obfs_disable_btn",
                false,
                fetchObfsStatus
            );
        });
    }

    function changePort() {
        if (!validateForm('port_form')) return;
        const port = $("#hysteria_port").val();
        const url = API_URLS.setPortTemplate.replace("PORT_PLACEHOLDER", port);
        confirmAction("change the port", function () {
            sendRequest(url, "GET", null, "Port changed successfully!", "#port_change");
        });
    }

    function changeSNI() {
        if (!validateForm('sni_form')) return;
        const domain = $("#sni_domain").val();
        const url = API_URLS.setSniTemplate.replace("SNI_PLACEHOLDER", domain);
        confirmAction("change the SNI", function () {
            sendRequest(url, "GET", null, "SNI changed successfully!", "#sni_change");
        });
    }

    function updateGeo(country) {
        const countryName = country.charAt(0).toUpperCase() + country.slice(1);
        const buttonId = `#geo_update_${country}`;
        const url = API_URLS.updateGeoTemplate.replace('COUNTRY_PLACEHOLDER', country);

        confirmAction(`update the Geo files for ${countryName}`, function () {
            sendRequest(
                url,
                "GET",
                null,
                `Geo files for ${countryName} updated successfully!`,
                buttonId,
                false,
                null
            );
        });
    }

    initUI();
    fetchObfsStatus();

    $("#port_change").on("click", changePort);
    $("#sni_change").on("click", changeSNI);
    $("#obfs_enable_btn").on("click", enableObfs);
    $("#obfs_disable_btn").on("click", disableObfs);
    $("#geo_update_iran").on("click", function() { updateGeo('iran'); });
    $("#geo_update_china").on("click", function() { updateGeo('china'); });
    $("#geo_update_russia").on("click", function() { updateGeo('russia'); });

    $('#sni_domain').on('input', function () {
        if (isValidDomain($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).removeClass('is-invalid');
        }
    });

    $('#hysteria_port').on('input', function () {
         if (isValidPort($(this).val())) {
            $(this).removeClass('is-invalid');
        } else if ($(this).val().trim() !== "") {
            $(this).addClass('is-invalid');
        } else {
             $(this).removeClass('is-invalid');
        }
    });
});