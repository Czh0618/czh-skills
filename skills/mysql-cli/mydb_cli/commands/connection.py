"""Connection profile management commands: mydb conn add/list/use/test/remove."""

from __future__ import annotations

import click

from .. import profiles
from ..client import MyDbClient
from ..formatter_utils import console, maybe_print_structured, print_success, success_payload
from ._common import (
    command_profile_option,
    handle_errors,
    profile_override,
    structured_output_options,
)


@click.group()
def conn():
    """Manage connection profiles (~/.mydb-cli/profiles.yaml)."""


@conn.command("add")
@click.argument("name")
@click.option("--host", required=True, help="MySQL host")
@click.option("--port", default=3306, type=int, show_default=True)
@click.option("--user", required=True, help="MySQL user (prefer a read-only account)")
@click.option("--db", default=None, help="Default database")
@click.option("--password-env", default=None, help="Env var holding the password (default: MYDB_PWD_<NAME>)")
@click.option("--readonly-locked", is_flag=True, help="Lock this profile to read-only forever")
@structured_output_options
def add(name, host, port, user, db, password_env, readonly_locked, as_json, as_yaml):
    """Add or update a connection profile (passwords are never stored)."""
    profiles.add_profile(
        name,
        host=host,
        port=port,
        user=user,
        db=db,
        password_env=password_env,
        readonly_locked=readonly_locked,
    )
    env_name = profiles.env_name_for(name, profiles.get_profile(name))
    data = {"added": name, "password_env": env_name, "readonly_locked": readonly_locked}
    if not maybe_print_structured(success_payload(data), as_json=as_json, as_yaml=as_yaml):
        print_success(f"Profile '{name}' saved. Set the password via: export {env_name}=...")


@conn.command("list")
@structured_output_options
def list_(as_json, as_yaml):
    """List profiles and the current one (passwords are never shown)."""
    store = profiles.load_profiles()
    data = {"current": store["current"], "profiles": store["profiles"]}
    if maybe_print_structured(success_payload(data), as_json=as_json, as_yaml=as_yaml):
        return
    if not store["profiles"]:
        console.print("[dim]No profiles. Add one with: mydb conn add <name> ...[/dim]")
        return
    for pname, prof in store["profiles"].items():
        marker = "[green]*[/green]" if pname == store["current"] else " "
        lock = " [yellow](read-only locked)[/yellow]" if prof.get("readonly_locked") else ""
        console.print(f"{marker} [bold]{pname}[/bold] — {prof['user']}@{prof['host']}:{prof.get('port', 3306)}"
                      f"/{prof.get('db', '')}{lock}")


@conn.command("use")
@click.argument("name")
@structured_output_options
def use(name, as_json, as_yaml):
    """Set the current/default profile."""
    def _fn():
        profiles.use_profile(name)
        if not maybe_print_structured(success_payload({"current": name}), as_json=as_json, as_yaml=as_yaml):
            print_success(f"Current profile: {name}")
    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml)


@conn.command("test")
@click.argument("name", required=False)
@command_profile_option
@structured_output_options
@click.pass_context
def test(ctx, name, as_json, as_yaml):
    """Test connectivity (runs SELECT 1)."""
    def _fn():
        pname, profile = profiles.resolve(name or profile_override(ctx))
        with MyDbClient(pname, profile, readonly=True) as client:
            client.run("SELECT 1", limit=1)
        data = {"profile": pname, "connected": True}
        if not maybe_print_structured(success_payload(data), as_json=as_json, as_yaml=as_yaml):
            print_success(f"Connected: {pname}")
    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml, prefix="Connection test failed")


@conn.command("remove")
@click.argument("name")
@structured_output_options
def remove(name, as_json, as_yaml):
    """Delete a connection profile."""
    def _fn():
        profiles.remove_profile(name)
        if not maybe_print_structured(success_payload({"removed": name}), as_json=as_json, as_yaml=as_yaml):
            print_success(f"Removed profile: {name}")
    handle_errors(_fn, as_json=as_json, as_yaml=as_yaml)
