#!/bin/bash

source /etc/dijiq/core/scripts/utils.sh
source /etc/dijiq/core/scripts/path.sh
source /etc/dijiq/core/scripts/services_status.sh >/dev/null 2>&1

check_services() {
    for service in "${services[@]}"; do
        service_base_name=$(basename "$service" .service)

        display_name=$(echo "$service_base_name" | sed -E 's/([^-]+)-?/\u\1/g') 

        if systemctl is-active --quiet "$service"; then
            echo -e "${NC}${display_name}:${green} Active${NC}"
        else
            echo -e "${NC}${display_name}:${red} Inactive${NC}"
        fi
    done
}

edit_ips() {
    while true; do
        echo "======================================"
        echo "      IP/Domain Address Manager      "
        echo "======================================"
        echo "1. Change IPv4 or Domain"
        echo "2. Change IPv6 or Domain"
        echo "0. Back"
        echo "======================================"
        read -p "Enter your choice [0-2]: " choice

        case $choice in
            1)
                read -p "Enter the new IPv4 address or domain: " new_ip4_or_domain
                if [[ $new_ip4_or_domain =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
                    if [[ $(echo "$new_ip4_or_domain" | awk -F. '{for (i=1;i<=NF;i++) if ($i>255) exit 1}') ]]; then
                        echo "Error: Invalid IPv4 address. Values must be between 0 and 255."
                    else
                        python3 "$CLI_PATH" ip-address --edit -4 "$new_ip4_or_domain"
                        echo "IPv4 address has been updated to $new_ip4_or_domain."
                    fi
                elif [[ $new_ip4_or_domain =~ ^[a-zA-Z0-9.-]+$ ]] && [[ ! $new_ip4_or_domain =~ [/:] ]]; then
                    python3 "$CLI_PATH" ip-address --edit -4 "$new_ip4_or_domain"
                    echo "Domain has been updated to $new_ip4_or_domain."
                else
                    echo "Error: Invalid IPv4 or domain format."
                fi
                break
                ;;
            2)
                read -p "Enter the new IPv6 address or domain: " new_ip6_or_domain
                if [[ $new_ip6_or_domain =~ ^(([0-9a-fA-F]{1,4}:){7}([0-9a-fA-F]{1,4}|:)|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:))$ ]]; then
                    python3 "$CLI_PATH" ip-address --edit -6 "$new_ip6_or_domain"
                    echo "IPv6 address has been updated to $new_ip6_or_domain."
                elif [[ $new_ip6_or_domain =~ ^[a-zA-Z0-9.-]+$ ]] && [[ ! $new_ip6_or_domain =~ [/:] ]]; then
                    python3 "$CLI_PATH" ip-address --edit -6 "$new_ip6_or_domain"
                    echo "Domain has been updated to $new_ip6_or_domain."
                else
                    echo "Error: Invalid IPv6 or domain format."
                fi
                break
                ;;
            0)
                break
                ;;
            *)
                echo "Invalid option. Please try again."
                break
                ;;
        esac
        echo "======================================"
        read -p "Press Enter to continue..."
    done
}

dijiq_upgrade(){
    bash <(curl https://raw.githubusercontent.com/SeyedHashtag/dijiq/main/upgrade.sh)
}

telegram_bot_handler() {
    while true; do
        echo -e "${cyan}1.${NC} Start Telegram bot service"
        echo -e "${red}2.${NC} Stop Telegram bot service"
        echo "0. Back"
        read -p "Choose an option: " option

        case $option in
            1)
                if systemctl is-active --quiet dijiq-telegram-bot.service; then
                    echo "The dijiq-telegram-bot.service is already active."
                else
                    while true; do
                        read -e -p "Enter the Telegram bot token: " token
                        if [ -z "$token" ]; then
                            echo "Token cannot be empty. Please try again."
                        else
                            break
                        fi
                    done

                    while true; do
                        read -e -p "Enter the admin IDs (comma-separated): " admin_ids
                        if [[ ! "$admin_ids" =~ ^[0-9,]+$ ]]; then
                            echo "Admin IDs can only contain numbers and commas. Please try again."
                        elif [ -z "$admin_ids" ]; then
                            echo "Admin IDs cannot be empty. Please try again."
                        else
                            break
                        fi
                    done
                    
                    while true; do
                        read -e -p "How many VPN servers do you want to configure? [1]: " server_count
                        server_count=${server_count:-1}
                        if [[ "$server_count" =~ ^[0-9]+$ ]] && [ "$server_count" -ge 1 ]; then
                            break
                        else
                            echo "Server count must be a positive number. Please try again."
                        fi
                    done

                    server_args=()
                    for ((i=1; i<=server_count; i++)); do
                        default_id="server$i"
                        if [ "$i" -eq 1 ]; then
                            default_id="primary"
                        fi

                        read -e -p "Enter server $i ID [$default_id]: " server_id
                        server_id=${server_id:-$default_id}

                        while true; do
                            read -e -p "Enter server $i API URL (e.g., http://example.com): " current_api_url
                            if [ -z "$current_api_url" ]; then
                                echo "API URL cannot be empty. Please try again."
                            else
                                break
                            fi
                        done

                        while true; do
                            read -e -p "Enter server $i API key: " current_api_key
                            if [ -z "$current_api_key" ]; then
                                echo "API key cannot be empty. Please try again."
                            else
                                break
                            fi
                        done

                        while true; do
                            read -e -p "Enter server $i balancing weight [1]: " current_weight
                            current_weight=${current_weight:-1}
                            if [[ "$current_weight" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
                                break
                            else
                                echo "Weight must be a positive number. Please try again."
                            fi
                        done

                        while true; do
                            read -e -p "Enable server $i for new configs? [y/n, default y]: " current_enabled
                            current_enabled=${current_enabled:-y}
                            case "$current_enabled" in
                                y|Y|yes|YES) current_enabled="true"; break ;;
                                n|N|no|NO) current_enabled="false"; break ;;
                                *) echo "Please answer y or n." ;;
                            esac
                        done

                        if [ "$i" -eq 1 ]; then
                            api_url="$current_api_url"
                            api_key="$current_api_key"
                        fi
                        server_args+=(--server "$server_id=$current_api_url,$current_api_key,$current_weight,$current_enabled")
                    done

                    python3 $CLI_PATH telegram -a start -t "$token" -aid "$admin_ids" -u "$api_url" -k "$api_key" "${server_args[@]}"
                fi
                ;;
            2)
                python3 $CLI_PATH telegram -a stop
                ;;
            0)
                break
                ;;
            *)
                echo "Invalid option. Please try again."
                ;;
        esac
    done
}

# Function to display the main menu
display_main_menu() {
    clear
    tput setaf 7 ; tput setab 4 ; tput bold
    echo -e "◇────────────────🚀 Welcome To dijiq Management 🚀─────────────────◇"
    tput sgr0
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"

    printf "\033[0;32m• OS:  \033[0m%-25s \033[0;32m• ARCH:  \033[0m%-25s\n" "$OS" "$ARCH"
    printf "\033[0;32m• ISP: \033[0m%-25s \033[0;32m• CPU:   \033[0m%-25s\n" "$ISP" "$CPU"
    printf "\033[0;32m• IP:  \033[0m%-25s \033[0;32m• RAM:   \033[0m%-25s\n" "$IP" "$RAM"

    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
        check_core_version
        check_version
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -e "${yellow}                   ☼ Services Status ☼                   ${NC}"
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"

        check_services
        
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -e "${yellow}                   ☼ Main Menu ☼                   ${NC}"

    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -e "${green}[1] ${NC}↝ Server Info"
    echo -e "${cyan}[2] ${NC}↝ Telegram Bot"
    echo -e "${cyan}[3] ${NC}↝ Change IPs / Domains"
    echo -e "${cyan}[4] ${NC}↝ Update Panel"
    echo -e "${red}[0] ${NC}↝ Exit"
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -ne "${yellow}➜ Enter your option: ${NC}"
}

# Function to handle main menu options
main_menu() {
    clear
    local choice
    while true; do
        get_system_info
        display_main_menu
        read -r choice
        case $choice in
            1) python3 "$CLI_PATH" server-info ;;
            2) telegram_bot_handler ;;
            3) edit_ips ;;
            4) dijiq_upgrade ;;
            0) exit 0 ;;
            *) echo "Invalid option. Please try again." ;;
        esac
        echo
        read -rp "Press Enter to continue..."
    done
}

# Main function to run the script
define_colors
main_menu
