$(function () {
    const darkModeToggle = $("#darkModeToggle");
    const darkModeIcon = $("#darkModeIcon");
    const isDarkMode = localStorage.getItem("darkMode") === "enabled";

    setDarkMode(isDarkMode);
    updateIcon(isDarkMode);

    darkModeToggle.on("click", function (e) {
        e.preventDefault();
        const enabled = $("body").hasClass("dark-mode");
        localStorage.setItem("darkMode", enabled ? "disabled" : "enabled");
        setDarkMode(!enabled);
        updateIcon(!enabled);
    });

    function setDarkMode(enabled) {
        $("body").toggleClass("dark-mode", enabled);

        if (enabled) {
            $(".main-header").addClass("navbar-dark").removeClass("navbar-light navbar-white");
            $(".card").addClass("bg-dark");
        } else {
            $(".main-header").addClass("navbar-white navbar-light").removeClass("navbar-dark");
            $(".card").removeClass("bg-dark");
        }
    }

    function updateIcon(enabled) {
        darkModeIcon.removeClass("fa-moon fa-sun")
            .addClass(enabled ? "fa-sun" : "fa-moon");
    }

    const versionUrl = $('body').data('version-url');
    $.ajax({
        url: versionUrl,
        type: 'GET',
        success: function (response) {
             $('#panel-version').text(`Version: ${response.current_version || 'N/A'}`);
        },
        error: function (error) {
            console.error("Error fetching version:", error);
            $('#panel-version').text('Version: Error');
        }
    });

    function shouldCheckForUpdates() {
        const lastCheck = localStorage.getItem('lastUpdateCheck');
        const updateDismissed = localStorage.getItem('updateDismissed');
        const now = Date.now();
        const checkInterval = 24 * 60 * 60 * 1000;
        
        if (!lastCheck) return true;
        if (updateDismissed && now - parseInt(updateDismissed) < 2 * 60 * 60 * 1000) return false;
        
        return now - parseInt(lastCheck) > checkInterval;
    }

    function showUpdateBar(version, changelog) {
        $('#updateMessage').text(`Version ${version} is now available`);
        
        const converter = new showdown.Converter();
        const htmlChangelog = changelog ? converter.makeHtml(changelog) : '<p>No changelog available.</p>';
        $('#changelogText').html(htmlChangelog);

        $('#updateBar').slideDown(300);
        
        $('#viewRelease').off('click').on('click', function(e) {
            e.preventDefault();
            window.open('https://github.com/ReturnFI/Blitz/releases/latest', '_blank');
        });
        
        $('#showChangelog').off('click').on('click', function() {
            const $content = $('#changelogContent');
            const $icon = $(this).find('i');
            
            if ($content.is(':visible')) {
                $content.slideUp(250);
                $icon.removeClass('fa-chevron-up').addClass('fa-chevron-down');
                $(this).css('opacity', '0.8');
            } else {
                $content.slideDown(250);
                $icon.removeClass('fa-chevron-down').addClass('fa-chevron-up');
                $(this).css('opacity', '1');
            }
        });
        
        $('.dropdown-toggle').dropdown();
        
        $('#remindLater').off('click').on('click', function(e) {
            e.preventDefault();
            $('#updateBar').slideUp(350);
        });
        
        $('#skipVersion').off('click').on('click', function(e) {
            e.preventDefault();
            localStorage.setItem('dismissedVersion', version);
            localStorage.setItem('updateDismissed', Date.now().toString());
            $('#updateBar').slideUp(350);
        });
        
        $('#closeUpdateBar').off('click').on('click', function() {
            $('#updateBar').slideUp(350);
        });
    }

    function checkForUpdates() {
        if (!shouldCheckForUpdates()) return;

        const checkVersionUrl = $('body').data('check-version-url');
        $.ajax({
            url: checkVersionUrl,
            type: 'GET',
            timeout: 10000,
            success: function (response) {
                localStorage.setItem('lastUpdateCheck', Date.now().toString());
                
                if (response.is_latest) {
                    localStorage.removeItem('updateDismissed');
                    return;
                }

                const dismissedVersion = localStorage.getItem('dismissedVersion');
                if (dismissedVersion === response.latest_version) return;

                showUpdateBar(response.latest_version, response.changelog);
            },
            error: function (xhr, status, error) {
                if (status !== 'timeout') {
                    console.warn("Update check failed:", error);
                }
                localStorage.setItem('lastUpdateCheck', Date.now().toString());
            }
        });
    }

    setTimeout(checkForUpdates, 2000);
});