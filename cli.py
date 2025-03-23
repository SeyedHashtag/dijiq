#!/usr/bin/env python3

import os
import sys
import subprocess
import click
from pathlib import Path
import json
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Initialize rich console
console = Console()

# Set path to the project root
PROJECT_ROOT = Path(__file__).parent.absolute()

def get_version():
    """Get the current version from VERSION file."""
    version_file = PROJECT_ROOT / 'VERSION'
    if version_file.exists():
        with open(version_file, 'r') as f:
            return f.read().strip()
    return "unknown"

def check_for_updates():
    """Check if updates are available."""
    current_version = get_version()
    
    try:
        # Simulate remote version check - in production this would check GitHub or another source
        # For demo purposes, we'll just return the current version
        latest_version = current_version
        
        # Uncomment to simulate an available update
        # latest_version = "1.1.0"
        
        is_update_available = latest_version != current_version
        return current_version, latest_version, is_update_available
    except Exception as e:
        click.echo(f"Error checking for updates: {e}", err=True)
        return current_version, current_version, False

def get_changelog():
    """Get the changelog content."""
    changelog_file = PROJECT_ROOT / 'CHANGELOG.md'
    if changelog_file.exists():
        with open(changelog_file, 'r') as f:
            return f.read()
    return "Changelog not available."

def get_service_status():
    """Check the systemd service status."""
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

def run_system_command(command, success_message, error_message):
    """Run a system command and handle the result."""
    try:
        subprocess.run(command, check=True)
        click.secho(success_message, fg="green")
        return True
    except subprocess.CalledProcessError:
        click.secho(error_message, fg="red")
        return False

@click.group()
def cli():
    """Dijiq VPN Bot CLI - Manage your VPN user management bot."""
    pass

@cli.command('status')
def status():
    """Show the current status of the bot."""
    service_status = get_service_status()
    current_version, latest_version, is_update_available = check_for_updates()
    
    # Create a status table
    table = Table(title="Dijiq VPN Bot Status")
    table.add_column("Component", style="cyan")
    table.add_column("Status", style="white")
    
    # Add service status with appropriate color
    status_color = {
        "running": "green",
        "stopped": "red",
        "unknown": "yellow"
    }.get(service_status, "yellow")
    
    table.add_row("Service", f"[{status_color}]{service_status}[/{status_color}]")
    table.add_row("Version", current_version)
    
    # Add update status
    if is_update_available:
        table.add_row("Updates", f"[yellow]Available: {latest_version}[/yellow]")
    else:
        table.add_row("Updates", "[green]Up to date[/green]")
    
    console.print(table)
    
    if is_update_available:
        click.secho(f"\nNew version {latest_version} is available! Run 'dijiq update' to update.", fg="yellow")

@cli.command('start')
def start():
    """Start the Dijiq service."""
    return run_system_command(
        ["sudo", "systemctl", "start", "dijiq"],
        "Service started successfully!",
        "Failed to start service. Check 'systemctl status dijiq' for details."
    )

@cli.command('stop')
def stop():
    """Stop the Dijiq service."""
    return run_system_command(
        ["sudo", "systemctl", "stop", "dijiq"],
        "Service stopped successfully!",
        "Failed to stop service. Check 'systemctl status dijiq' for details."
    )

@cli.command('restart')
def restart():
    """Restart the Dijiq service."""
    return run_system_command(
        ["sudo", "systemctl", "restart", "dijiq"],
        "Service restarted successfully!",
        "Failed to restart service. Check 'systemctl status dijiq' for details."
    )

@cli.command('update')
@click.option('--force', is_flag=True, help='Force update even if already up to date')
def update(force):
    """Check for updates and apply if available."""
    current_version, latest_version, is_update_available = check_for_updates()
    
    if not is_update_available and not force:
        click.secho(f"You're already running the latest version ({current_version}).", fg="green")
        return
    
    if force:
        click.secho("Forcing update...", fg="yellow")
    else:
        click.secho(f"Update available: {current_version} → {latest_version}", fg="yellow")
    
    # Display changelog
    changelog = get_changelog()
    console.print(Panel(changelog, title="[bold]Changelog[/bold]", expand=False))
    
    if not click.confirm("Would you like to update now?"):
        click.echo("Update canceled.")
        return
    
    # Perform the update
    click.echo("Updating Dijiq VPN Bot...")
    
    try:
        # Navigate to installation directory
        os.chdir("/opt/dijiq")
        
        # Pull latest changes
        click.echo("Pulling latest changes from repository...")
        subprocess.run(["sudo", "git", "pull"], check=True)
        
        # Update dependencies
        click.echo("Updating dependencies...")
        subprocess.run([
            "sudo", "bash", "-c", 
            "source venv/bin/activate && pip install -r requirements.txt"
        ], check=True)
        
        # Ask to restart service
        if click.confirm("Update complete! Restart the service to apply changes?"):
            restart()
        else:
            click.secho("Remember to restart the service with 'dijiq restart' to apply changes.", fg="yellow")
        
        click.secho("Update completed successfully!", fg="green")
        
    except subprocess.CalledProcessError as e:
        click.secho(f"Error during update: {e}", fg="red")
        click.echo("You may need to resolve conflicts manually.")

@cli.command('version')
def version():
    """Show the current version and check for updates."""
    current_version, latest_version, is_update_available = check_for_updates()
    
    click.echo(f"Current version: {current_version}")
    
    if is_update_available:
        click.secho(f"New version available: {latest_version}", fg="yellow")
        click.echo("Run 'dijiq update' to update to the latest version.")
    else:
        click.secho("You're running the latest version!", fg="green")

@cli.command('changelog')
def changelog():
    """Show the changelog."""
    content = get_changelog()
    console.print(Panel(content, title="[bold]Changelog[/bold]", expand=False))

if __name__ == '__main__':
    cli()
