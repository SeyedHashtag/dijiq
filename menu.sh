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

# OPTION HANDLERS (ONLY NEEDED ONE)
dijiq_add_user_handler() {
    while true; do
        read -p "Enter the username: " username

        if [[ "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
            if [[ -n $(python3 $CLI_PATH get-user -u "$username") ]]; then
                echo -e "${red}Error:${NC} Username already exists. Please choose another username."
            else
                break
            fi
        else
            echo -e "${red}Error:${NC} Username can only contain letters and numbers."
        fi
    done

    read -p "Enter the traffic limit (in GB): " traffic_limit_GB

    read -p "Enter the expiration days: " expiration_days
    password=$(pwgen -s 32 1)
    creation_date=$(date +%Y-%m-%d)

    python3 $CLI_PATH add-user --username "$username" --traffic-limit "$traffic_limit_GB" --expiration-days "$expiration_days" --password "$password" --creation-date "$creation_date"
}

dijiq_edit_user_handler() {
    # Function to prompt for user input with validation
    prompt_for_input() {
        local prompt_message="$1"
        local validation_regex="$2"
        local default_value="$3"
        local input_variable_name="$4"

        while true; do
            read -p "$prompt_message" input
            if [[ -z "$input" ]]; then
                input="$default_value"
            fi
            if ([[ "$input" =~ $validation_regex ]]; then
                eval "$input_variable_name='$input'"
                break
            else
                echo -e "${red}Error:${NC} Invalid input. Please try again."
            fi
        done
    }

    # Prompt for username
    prompt_for_input "Enter the username you want to edit: " '^[a-zA-Z0-9]+$' '' username

    # Check if user exists
    user_exists_output=$(python3 $CLI_PATH get-user -u "$username" 2>&1)
    if [[ -z "$user_exists_output" ]]; then
        echo -e "${red}Error:${NC} User '$username' not found or an error occurred."
        return 1
    fi

    # Prompt for new username
    prompt_for_input "Enter the new username (leave empty to keep the current username): " '^[a-zA-Z0-9]*$' '' new_username

    # Prompt for new traffic limit
    prompt_for_input "Enter the new traffic limit (in GB) (leave empty to keep the current limit): " '^[0-9]*$' '' new_traffic_limit_GB

    # Prompt for new expiration days
    prompt_for_input "Enter the new expiration days (leave empty to keep the current expiration days): " '^[0-9]*$' '' new_expiration_days

    # Determine if we need to renew password
    while true; do
        read -p "Do you want to generate a new password? (y/n): " renew_password
        case "$renew_password" in
            y|Y) renew_password=true; break ;;
            n|N) renew_password=false; break ;;
            *) echo -e "${red}Error:${NC} Please answer 'y' or 'n'." ;;
        esac
    done

    # Determine if we need to renew creation date
    while true; do
        read -p "Do you want to generate a new creation date? (y/n): " renew_creation_date
        case "$renew_creation_date" in
            y|Y) renew_creation_date=true; break ;;
            n|N) renew_creation_date=false; break ;;
            *) echo -e "${red}Error:${NC} Please answer 'y' or 'n'." ;;
        esac
    done

    # Determine if user should be blocked
    while true; do
        read -p "Do you want to block the user? (y/n): " block_user
        case "$block_user" in
            y|Y) blocked=true; break ;;
            n|N) blocked=false; break ;;
            *) echo -e "${red}Error:${NC} Please answer 'y' or 'n'." ;;
        esac
    done

    # Construct the arguments for the edit-user command
    args=()
    if [[ -n "$new_username" ]]; then args+=("--new-username" "$new_username"); fi
    if [[ -n "$new_traffic_limit_GB" ]]; then args+=("--new-traffic-limit" "$new_traffic_limit_GB"); fi
    if [[ -n "$new_expiration_days" ]]; then args+=("--new-expiration-days" "$new_expiration_days"); fi
    if [[ "$renew_password" == "true" ]]; then args+=("--renew-password"); fi
    if [[ "$renew_creation_date" == "true" ]]; then args+=("--renew-creation-date"); fi
    if [[ "$blocked" == "true" ]]; then args+=("--blocked"); fi

    # Call the edit-user script with the constructed arguments
    python3 $CLI_PATH edit-user --username "$username" "${args[@]}"
}

dijiq_remove_user_handler() {
    while true; do
        read -p "Enter the username: " username

        if [[ "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
            break
        else
            echo -e "${red}Error:${NC} Username can only contain letters and numbers."
        fi
    done
    python3 $CLI_PATH remove-user --username "$username"
}

dijiq_get_user_handler() {
    while true; do
        read -p "Enter the username: " username
        if [[ "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
            break
        else
            echo -e "${red}Error:${NC} Username can only contain letters and numbers."
        fi
    done

    user_data=$(python3 "$CLI_PATH" get-user --username "$username" 2>/dev/null)

    if [[ $? -ne 0 ]]; then
        echo -e "${red}Error:${NC} User '$username' not found."
        return 1
    fi

    password=$(echo "$user_data" | jq -r '.password // "N/A"')
    max_download_bytes=$(echo "$user_data" | jq -r '.max_download_bytes // 0')
    upload_bytes=$(echo "$user_data" | jq -r '.upload_bytes // 0')
    download_bytes=$(echo "$user_data" | jq -r '.download_bytes // 0')
    account_creation_date=$(echo "$user_data" | jq -r '.account_creation_date // "N/A"')
    expiration_days=$(echo "$user_data" | jq -r '.expiration_days // 0')
    blocked=$(echo "$user_data" | jq -r '.blocked // false')
    status=$(echo "$user_data" | jq -r '.status // "N/A"')
    total_usage=$((upload_bytes + download_bytes))
    max_download_gb=$(echo "scale=2; $max_download_bytes / 1073741824" | bc)
    upload_gb=$(echo "scale=2; $upload_bytes / 1073741824" | bc)
    download_gb=$(echo "scale=2; $download_bytes / 1073741824" | bc)
    total_usage_gb=$(echo "scale=2; $total_usage / 1073741824" | bc)
    expiration_date=$(date -d "$account_creation_date + $expiration_days days" +"%Y-%m-%d")
    current_date=$(date +"%Y-%m-%d")
    used_days=$(( ( $(date -d "$current_date" +%s) - $(date -d "$account_creation_date" +%s) ) / 86400 ))

    if [[ $used_days -gt $expiration_days ]]; then
        used_days=$expiration_days
    fi

    echo -e "${green}User Details:${NC}"
    echo -e "Username:         $username"
    echo -e "Password:         $password"
    echo -e "Total Traffic:    $max_download_gb GB"
    echo -e "Total Usage:      $total_usage_gb GB"
    echo -e "Time Expiration:  $expiration_date ($used_days/$expiration_days Days)"
    echo -e "Blocked:          $blocked"
    echo -e "Status:           $status"
}

dijiq_list_users_handler() {
    users_json=$(python3 $CLI_PATH list-users 2>/dev/null)
    if [ $? -ne 0 ] || [ -z "$users_json" ]; then
        echo -e "${red}Error:${NC} Failed to list users."
        return 1
    fi

    # Extract keys (usernames) from JSON
    users_keys=$(echo "$users_json" | jq -r 'keys[]')

    if [ -z "$users_keys" ]; then
        echo -e "${red}Error:${NC} No users found."
        return 1
    fi

    # Print headers
    printf "%-20s %-20s %-15s %-20s %-30s %-10s\n" "Username" "Traffic Limit (GB)" "Expiration (Days)" "Creation Date" "Password" "Blocked"

    # Print user details
    for key in $users_keys; do
        echo "$users_json" | jq -r --arg key "$key" '
            "\($key) \(.[$key].max_download_bytes / 1073741824) \(.[$key].expiration_days) \(.[$key].account_creation_date) \(.[$key].password) \(.[$key].blocked)"' | \
        while IFS= read -r line; do
            IFS=' ' read -r username traffic_limit expiration_date creation_date password blocked <<< "$line"
            printf "%-20s %-20s %-15s %-20s %-30s %-10s\n" "$username" "$traffic_limit" "$expiration_date" "$creation_date" "$password" "$blocked"
        done
    done
}

dijiq_reset_user_handler() {
    while true; do
        read -p "Enter the username: " username

        if [[ "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
            break
        else
            echo -e "${red}Error:${NC} Username can only contain letters and numbers."
        fi
    done
    python3 $CLI_PATH reset-user --username "$username"
}

dijiq_show_user_uri_handler() {
    check_service_active() {
        systemctl is-active --quiet "$1"
    }

    while true; do
        read -p "Enter the username: " username
        if [[ "$username" =~ ^[a-zA-Z0-9]+$ ]]; then
            break
        else
            echo -e "${red}Error:${NC} Username can only contain letters and numbers."
        fi
    done

    flags=""
    
    if check_service_active "dijiq-singbox.service"; then
        flags+=" -s"
    fi

    if check_service_active "dijiq-normal-sub.service"; then
        flags+=" -n"
    fi

    if [[ -n "$flags" ]]; then
        python3 $CLI_PATH show-user-uri -u "$username" -a -qr $flags
    else
        python3 $CLI_PATH show-user-uri -u "$username" -a -qr
    fi
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
                        read -e -p "Enter the API URL (e.g., http://example.com): " api_url
                        if [ -z "$api_url" ]; then
                            echo "API URL cannot be empty. Please try again."
                        else
                            break
                        fi
                    done
                    
                    while true; do
                        read -e -p "Enter the API key: " api_key
                        if [ -z "$api_key" ]; then
                            echo "API key cannot be empty. Please try again."
                        else
                            break
                        fi
                    done
                    
                    while true; do
                        read -e -p "Enter the subscription URL (e.g., http://example.com/sub): " sub_url
                        if [ -z "$sub_url" ]; then
                            echo "Subscription URL cannot be empty. Please try again."
                        else
                            break
                        fi
                    done

                    python3 $CLI_PATH telegram -a start -t "$token" -aid "$admin_ids" -u "$api_url" -k "$api_key" -s "$sub_url"
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
    echo -e "${green}[1] ${NC}↝ dijiq Menu"
    echo -e "${cyan}[2] ${NC}↝ Advance Menu"
    echo -e "${cyan}[3] ${NC}↝ Update Panel"
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
            1) dijiq_menu ;;
            2) advance_menu ;;
            3) dijiq_upgrade ;;
            0) exit 0 ;;
            *) echo "Invalid option. Please try again." ;;
        esac
        echo
        read -rp "Press Enter to continue..."
    done
}

# Function to display the dijiq menu
display_dijiq_menu() {
    clear
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"

    echo -e "${yellow}                   ☼ dijiq Menu ☼                   ${NC}"

    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"

    echo -e "${green}[1] ${NC}↝ Install and Configure dijiq"
    echo -e "${cyan}[2] ${NC}↝ Add User"
    echo -e "${cyan}[3] ${NC}↝ Edit User"
    echo -e "${cyan}[4] ${NC}↝ Reset User"
    echo -e "${cyan}[5] ${NC}↝ Remove User"
    echo -e "${cyan}[6] ${NC}↝ Get User"
    echo -e "${cyan}[7] ${NC}↝ List Users"
    echo -e "${cyan}[8] ${NC}↝ Check Traffic Status"
    echo -e "${cyan}[9] ${NC}↝ Show User URI"

    echo -e "${red}[0] ${NC}↝ Back to Main Menu"

    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"

    echo -ne "${yellow}➜ Enter your option: ${NC}"
}

# Function to handle dijiq menu options
dijiq_menu() {
    clear
    local choice
    while true; do
        get_system_info
        display_dijiq_menu
        read -r choice
        case $choice in
            1) dijiq_install_handler ;;
            2) dijiq_add_user_handler ;;
            3) dijiq_edit_user_handler ;;
            4) dijiq_reset_user_handler ;;
            5) dijiq_remove_user_handler  ;;
            6) dijiq_get_user_handler ;;
            7) dijiq_list_users_handler ;;
            8) python3 $CLI_PATH traffic-status ;;
            9) dijiq_show_user_uri_handler ;;
            0) return ;;
            *) echo "Invalid option. Please try again." ;;
        esac
        echo
        read -rp "Press Enter to continue..."
    done
}

# Function to get Advance menu
display_advance_menu() {
    clear
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -e "${yellow}                   ☼ Advance Menu ☼                   ${NC}"
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -e "${green}[5] ${NC}↝ Telegram Bot"
    echo -e "${cyan}[12] ${NC}↝ Change IPs(4-6)"
    echo -e "${cyan}[15] ${NC}↝ Restart dijiq"
    echo -e "${cyan}[16] ${NC}↝ Update Core dijiq"
    echo -e "${red}[18] ${NC}↝ Uninstall dijiq"
    echo -e "${red}[0] ${NC}↝ Back to Main Menu"
    echo -e "${LPurple}◇──────────────────────────────────────────────────────────────────────◇${NC}"
    echo -ne "${yellow}➜ Enter your option: ${NC}"
}

# Function to handle Advance menu options
advance_menu() {
    clear
    local choice
    while true; do
        display_advance_menu
        read -r choice
        case $choice in
            5) telegram_bot_handler ;;
            12) edit_ips ;;
            15) python3 $CLI_PATH restart-dijiq ;;
            16) python3 $CLI_PATH update-dijiq ;;
            18) python3 $CLI_PATH uninstall-dijiq ;;
            0) return ;;
            *) echo "Invalid option. Please try again." ;;
        esac
        echo
        read -rp "Press Enter to continue..."
    done
}
# Main function to run the script
define_colors
main_menu
