#!/bin/bash

check_os_version() {
    local os_name os_version

    if [ -f /etc/os-release ]; then
        os_name=$(grep '^ID=' /etc/os-release | cut -d= -f2)
        os_version=$(grep '^VERSION_ID=' /etc/os-release | cut -d= -f2 | tr -d '"')
    else
        echo "Unsupported OS or unable to determine OS version."
        exit 1
    fi

    if ! command -v bc &> /dev/null; then
        apt update && apt install -y bc
    fi

    if [[ "$os_name" == "ubuntu" && $(echo "$os_version >= 22" | bc) -eq 1 ]] ||
       [[ "$os_name" == "debian" && $(echo "$os_version >= 11" | bc) -eq 1 ]]; then
        return 0
    else
        echo "This script is only supported on Ubuntu 22+ or Debian 11+."
        exit 1
    fi
}

if [ "$(id -u)" -ne 0 ]; then
    echo "This script must be run as root."
    exit 1
fi

check_os_version

REQUIRED_PACKAGES=("jq" "qrencode" "curl" "pwgen" "python3" "python3-pip" "python3-venv" "git" "bc" "zip" "cron" "lsof")
MISSING_PACKAGES=()
heavy_checkmark=$(printf "\xE2\x9C\x85")

for package in "${REQUIRED_PACKAGES[@]}"; do
    if ! command -v "$package" &> /dev/null; then
        MISSING_PACKAGES+=("$package")
    else
        echo "Install $package $heavy_checkmark"
    fi
done

if [ ${#MISSING_PACKAGES[@]} -ne 0 ]; then
    echo "The following packages are missing and will be installed: ${MISSING_PACKAGES[@]}"
    apt update -qq && apt upgrade -y -qq
    for package in "${MISSING_PACKAGES[@]}"; do
        apt install -y -qq "$package" &> /dev/null && echo "Install $package $heavy_checkmark"
    done
else
    echo "All required packages are already installed."
fi

git clone https://github.com/SeyedHashtag/dijiq /etc/dijiq

cd /etc/dijiq
python3 -m venv dijiq_venv
source /etc/dijiq/dijiq_venv/bin/activate
pip install -r requirements.txt &> /dev/null && echo "Install Python requirements ✅"

if ! grep -q "alias dijiq='source /etc/dijiq/dijiq_venv/bin/activate && /etc/dijiq/menu.sh'" ~/.bashrc; then
    echo "alias dijiq='source /etc/dijiq/dijiq_venv/bin/activate && /etc/dijiq/menu.sh'" >> ~/.bashrc
    source ~/.bashrc
fi
sleep 5
cd /etc/dijiq
chmod +x menu.sh
./menu.sh
