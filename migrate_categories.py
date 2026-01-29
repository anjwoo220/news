#!/usr/bin/env python3
"""
migrate_categories.py - Batch convert existing news data to standardized categories.

Usage:
    python migrate_categories.py --dry-run  # Preview changes without saving
    python migrate_categories.py            # Apply changes

This script:
1. Reads news data from Google Sheets (news_db)
2. Normalizes all category values to 4 standard categories
3. Updates the Google Sheet with normalized categories
"""

import argparse
import json
import os
import sys

# Add parent directory to path for utils import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import normalize_category, CATEGORY_MAPPING, DISPLAY_LABELS

def load_local_news():
    """Load news from local JSON file if exists."""
    news_file = "data/news.json"
    if os.path.exists(news_file):
        with open(news_file, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                return {}
    return {}

def migrate_local_news(dry_run=False):
    """Migrate local news.json categories."""
    news_data = load_local_news()
    
    if not news_data:
        print("No local news.json found or empty.")
        return 0
    
    changes = 0
    
    for date_key, articles in news_data.items():
        if isinstance(articles, list):
            for article in articles:
                old_cat = article.get('category', '')
                new_cat = normalize_category(old_cat)
                
                if old_cat != new_cat:
                    changes += 1
                    print(f"  [{date_key}] '{article.get('title', '')[:30]}...'")
                    print(f"      {old_cat} → {new_cat}")
                    
                    if not dry_run:
                        article['category'] = new_cat
    
    if not dry_run and changes > 0:
        with open("data/news.json", 'w', encoding='utf-8') as f:
            json.dump(news_data, f, ensure_ascii=False, indent=2)
        print(f"\n✅ Saved {changes} changes to data/news.json")
    
    return changes

def migrate_gsheets_news(dry_run=False):
    """Migrate Google Sheets news_db categories."""
    try:
        import streamlit as st
        import gspread
        from oauth2client.service_account import ServiceAccountCredentials
        
        # Load secrets
        try:
            import toml
            secrets = toml.load(".streamlit/secrets.toml")
        except:
            print("Cannot load secrets.toml")
            return 0
        
        creds_info = secrets.get("GOOGLE_SHEETS_KEY")
        if not creds_info:
            creds_info = secrets.get("connections", {}).get("gsheets_news", {})
        
        if not creds_info:
            print("No GSheets credentials found")
            return 0
        
        if isinstance(creds_info, str):
            creds_dict = json.loads(creds_info)
        else:
            creds_dict = dict(creds_info)
        
        # Clean up for gspread
        valid_keys = [
            "type", "project_id", "private_key_id", "private_key",
            "client_email", "client_id", "auth_uri", "token_uri",
            "auth_provider_x509_cert_url", "client_x509_cert_url", "universe_domain"
        ]
        gspread_creds = {k: v for k, v in creds_dict.items() if k in valid_keys}
        
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(gspread_creds, scope)
        client = gspread.authorize(creds)
        
        # Open news sheet
        sh = client.open("news_db")
        sheet = sh.get_worksheet(0)
        
        all_records = sheet.get_all_records()
        changes = 0
        updates = []
        
        print(f"\nScanning {len(all_records)} rows in GSheets...")
        
        for row_idx, record in enumerate(all_records, start=2):  # Row 1 is header
            old_cat = record.get('category', '')
            new_cat = normalize_category(old_cat)
            
            if old_cat != new_cat:
                changes += 1
                print(f"  [Row {row_idx}] '{record.get('title', '')[:30]}...'")
                print(f"      {old_cat} → {new_cat}")
                
                if not dry_run:
                    updates.append((row_idx, new_cat))
        
        # Find category column index
        if not dry_run and updates:
            headers = sheet.row_values(1)
            try:
                cat_col = headers.index('category') + 1  # 1-indexed
            except ValueError:
                print("Cannot find 'category' column in sheet")
                return changes
            
            # Batch update
            for row_idx, new_cat in updates:
                sheet.update_cell(row_idx, cat_col, new_cat)
            
            print(f"\n✅ Updated {len(updates)} rows in GSheets")
        
        return changes
        
    except Exception as e:
        print(f"GSheets Error: {e}")
        return 0

def main():
    parser = argparse.ArgumentParser(description="Migrate news categories to standard format")
    parser.add_argument('--dry-run', action='store_true', help='Preview changes without saving')
    args = parser.parse_args()
    
    print("=" * 60)
    print("📋 Category Migration Tool")
    print("=" * 60)
    
    print("\n📖 Standard Categories:")
    for code, label in DISPLAY_LABELS.items():
        aliases = CATEGORY_MAPPING.get(code, [])
        print(f"  {label} ({code})")
        print(f"      Aliases: {', '.join(aliases[:5])}...")
    
    if args.dry_run:
        print("\n🔍 DRY RUN MODE - No changes will be saved\n")
    else:
        print("\n⚡ LIVE MODE - Changes will be saved\n")
    
    print("-" * 60)
    print("📁 Local news.json Migration:")
    print("-" * 60)
    local_changes = migrate_local_news(dry_run=args.dry_run)
    
    print("-" * 60)
    print("☁️ Google Sheets Migration:")
    print("-" * 60)
    gsheets_changes = migrate_gsheets_news(dry_run=args.dry_run)
    
    print("\n" + "=" * 60)
    print(f"📊 Summary: {local_changes + gsheets_changes} total changes")
    if args.dry_run:
        print("   (Run without --dry-run to apply changes)")
    print("=" * 60)

if __name__ == "__main__":
    main()
