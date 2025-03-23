import os
import sys
import subprocess
import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from src.utils.version import check_for_updates, get_current_version, get_changelog

console = Console()

def get_service_status():
    """Get the systemd service status."""
    try:
        result = subprocess.run(
            ["systemctl", "status", "dijiq"],
            capture_output=True,
            text=True
        )
        if "Active: active (running)" in result.stdout:
            return "running"
        elif "Active: inactive" in result.stdout:
            return "stopped"
        else:
            return "unknown"
    except Exception:
        return "unknown"

def start_service():
    """Start the dijiq service."""
    # Check if the service is already running to prevent conflicts
    if get_service_status() == "running":
        console.print("[yellow]The bot service is already running.[/yellow]")
        return
        
    try:
        subprocess.run(["sudo", "systemctl", "start", "dijiq"], check=True)
        console.print("[green]Service started successfully![/green]")
    except subprocess.CalledProcessError:
        console.print("[red]Failed to start service. Check 'systemctl status dijiq' for details.[/red]")

def stop_service():
    """Stop the dijiq service."""
    try:
        subprocess.run(["sudo", "systemctl", "stop", "dijiq"], check=True)
        console.print("[green]Service stopped successfully![/green]")
    except subprocess.CalledProcessError:
        console.print("[red]Failed to stop service. Check 'systemctl status dijiq' for details.[/red]")

def restart_service():
    """Restart the dijiq service."""
    try:
        subprocess.run(["sudo", "systemctl", "restart", "dijiq"], check=True)
        console.print("[green]Service restarted successfully![/green]")
    except subprocess.CalledProcessError:
        console.print("[red]Failed to restart service. Check 'systemctl status dijiq' for details.[/red]")

def check_updates():
    """Check for updates and display changelog if available."""
    console.print("Checking for updates...", end="")
    current_version = get_current_version()
    latest_version, is_update_available = check_for_updates()
    
    if is_update_available:
        console.print(f"\n[green]Update available![/green] Current: {current_version}, Latest: {latest_version}")
        
        # Display changelog
        changelog = get_changelog(current_version, latest_version)
        if (changelog):
            console.print(Panel(
                changelog,
                title="[bold]Changelog[/bold]",
                expand=False
            ))
        
        # Ask if user wants to update
        if console.input("Would you like to update now? (y/n): ").lower() == 'y':
            console.print("Updating...")
            update_bot()
    else:
        console.print(f"\n[green]You're up to date![/green] Current version: {current_version}")

def update_bot():
    """Update the bot to the latest version."""
    try:
        # Navigate to installation directory
        os.chdir("/opt/dijiq")
        
        # Pull latest changes
        console.print("Pulling latest changes from repository...")
        subprocess.run(["sudo", "git", "pull"], check=True)
        
        # Update dependencies
        console.print("Updating dependencies...")
        subprocess.run([
            "sudo", "bash", "-c", 
            "source venv/bin/activate && pip install -r requirements.txt"
        ], check=True)
        
        # Ask to restart service
        if console.input("Update complete! Restart the service to apply changes? (y/n): ").lower() == 'y':
            restart_service()
        else:
            console.print("[yellow]Remember to restart the service with 'dijiq restart' to apply changes.[/yellow]")
    
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error during update: {e}[/red]")
        console.print("You may need to resolve conflicts manually.")

def show_status():
    """Show the current status of the bot."""
    status = get_service_status()
    
    # Create a status table
    table = Table(title="Dijiq VPN Bot Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="green")
    
    # Add service status
    status_color = {
        "running": "green",
        "stopped": "red",
        "unknown": "yellow"
    }.get(status, "yellow")
    
    table.add_row("Service", f"[{status_color}]{status}[/{status_color}]")
    
    # Add version information
    current_version = get_current_version()
    table.add_row("Version", current_version)
    
    # Check for updates
    latest_version, is_update_available = check_for_updates()
    update_status = f"[yellow]Update available: {latest_version}[/yellow]" if is_update_available else "[green]Up to date[/green]"
    table.add_row("Updates", update_status)
    
    console.print(table)
    
    # Add helpful command hints
    console.print("\n[bold]Available commands:[/bold]")
    console.print("  [cyan]dijiq start[/cyan]    - Start the bot service")
    console.print("  [cyan]dijiq stop[/cyan]     - Stop the bot service")
    console.print("  [cyan]dijiq restart[/cyan]  - Restart the bot service")
    console.print("  [cyan]dijiq update[/cyan]   - Check for and apply updates")
    console.print("  [cyan]dijiq status[/cyan]   - Show this status screen")
    
    if is_update_available:
        console.print("\n[yellow]Update available! Run: dijiq update[/yellow]")

def run_cli():
    """Run the CLI application."""
    parser = argparse.ArgumentParser(description='Dijiq VPN Bot CLI')
    subparsers = parser.add_subparsers(dest='command', help='Commands')
    
    # Status command
    subparsers.add_parser('status', help='Show the current status')
    
    # Start command
    subparsers.add_parser('start', help='Start the service')
    
    # Stop command
    subparsers.add_parser('stop', help='Stop the service')
    
    # Restart command
    subparsers.add_parser('restart', help='Restart the service')
    
    # Update command
    subparsers.add_parser('update', help='Check for updates and update if available')
    
    # If no arguments, show status by default
    if len(sys.argv) == 1:
        show_status()
        return
    
    args = parser.parse_args()
    
    # Execute the appropriate command
    if args.command == 'status':
        show_status()
    elif args.command == 'start':
        start_service()
    elif args.command == 'stop':
        stop_service()
    elif args.command == 'restart':
        restart_service()
    elif args.command == 'update':
        check_updates()
