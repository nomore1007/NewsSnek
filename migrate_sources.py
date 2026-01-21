#!/usr/bin/env python3
"""
Migration script to convert sources.txt to sources.json format.
Run this script to migrate your existing sources.txt file to the new JSON format.
"""

import json
import sys
import os
from pathlib import Path

def migrate_sources_txt_to_json(txt_file: str = "sources.txt", json_file: str = "sources.json"):
    """
    Convert sources.txt to sources.json format.

    Args:
        txt_file: Path to the text sources file
        json_file: Path to write the JSON sources file
    """
    if not os.path.exists(txt_file):
        print(f"❌ Sources file not found: {txt_file}")
        return False

    try:
        with open(txt_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # Parse the text format
        groups = {}
        current_group = None
        current_urls = []
        current_channels = []
        current_prompt = None

        lines = content.split('\n')

        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            if line.startswith('[') and line.endswith(']'):
                # Save previous group if exists
                if current_group and current_urls:
                    groups[current_group] = {
                        "description": f"Imported from {txt_file}",
                        "channels": current_channels,
                        "prompt": current_prompt,
                        "sources": current_urls
                    }

                # Start new group
                group_header = line[1:-1]  # Remove brackets

                # Parse group header: [name:channels:prompt] or [name:channels] or [name]
                parts = group_header.split(':')
                group_name = parts[0]

                current_channels = []
                current_prompt = None

                if len(parts) >= 2:
                    # Has channels specification
                    channels_str = parts[1]
                    current_channels = [c.strip() for c in channels_str.split(',') if c.strip()]

                if len(parts) >= 3:
                    # Has prompt specification
                    current_prompt = ':'.join(parts[2:])  # Rejoin in case prompt contains colons

                current_group = group_name
                current_urls = []
            elif current_group:
                # URL in current group
                current_urls.append(line)

        # Save final group
        if current_group and current_urls:
            groups[current_group] = {
                "description": f"Imported from {txt_file}",
                "channels": current_channels,
                "prompt": current_prompt,
                "sources": current_urls
            }

        # Write JSON format
        json_data = {"groups": groups}

        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)

        print(f"✅ Successfully migrated {txt_file} to {json_file}")
        print(f"📊 Migrated {len(groups)} groups with {sum(len(g['sources']) for g in groups.values())} total sources")

        # Show summary
        for group_name, group_data in groups.items():
            channels = group_data['channels']
            channel_info = f" -> {', '.join(channels)}" if channels else " -> all channels"
            print(f"  • {group_name}: {len(group_data['sources'])} sources{channel_info}")

        return True

    except Exception as e:
        print(f"❌ Error during migration: {e}")
        return False

def main():
    """Main migration function."""
    print("🔄 NewsSnek Sources Migration Tool")
    print("===================================")

    # Check for existing files
    txt_exists = os.path.exists("sources.txt")
    json_exists = os.path.exists("sources.json")

    if json_exists:
        print("⚠️  sources.json already exists!")
        response = input("Overwrite existing sources.json? (y/N): ").strip().lower()
        if response != 'y':
            print("Migration cancelled.")
            return

    if not txt_exists:
        print("❌ No sources.txt file found to migrate.")
        print("💡 Create a sources.txt file first, or run the application to generate a default one.")
        return

    # Perform migration
    success = migrate_sources_txt_to_json()

    if success:
        print("\n📋 Next steps:")
        print("1. Update your settings.json to use 'sources.json' instead of 'sources.txt'")
        print("2. Test the new configuration with: python3 nwsreader.py --file sources.json --overview")
        print("3. Optionally backup and remove the old sources.txt file")

        # Backup suggestion
        backup_name = "sources.txt.backup"
        if not os.path.exists(backup_name):
            print(f"4. Consider backing up: cp sources.txt {backup_name}")

if __name__ == "__main__":
    main()