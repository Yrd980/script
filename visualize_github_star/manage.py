#!/usr/bin/env python3
"""
Enhanced GitHub Stars Management Script
Provides easy commands to build index, start server, and manage the search system.
"""

import argparse
import subprocess
import sys
import os
import sqlite3
import json
from pathlib import Path

def check_requirements():
    """Check if required packages are installed"""
    required_packages = ['requests', 'tqdm', 'flask', 'flask_cors']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ Missing required packages: {', '.join(missing_packages)}")
        print("📦 Please install them with:")
        print(f"   pip install {' '.join(missing_packages)}")
        return False
    
    return True

def check_token():
    """Check if GitHub token is configured"""
    try:
        from enhanced_github_indexer import TOKEN
        if not TOKEN or TOKEN.strip() == "":
            print("❌ GitHub token not configured")
            print("🔑 Please edit enhanced_github_indexer.py and add your GitHub token")
            print("   Get a token from: https://github.com/settings/tokens")
            print("   Required scopes: repo (or public_repo for public repos only)")
            return False
        return True
    except ImportError:
        print("❌ enhanced_github_indexer.py not found")
        return False

def build_index(force_refresh=False):
    """Build the repository content index"""
    print("🚀 Building repository index...")
    
    if not check_requirements():
        return False
    
    if not check_token():
        return False
    
    try:
        from enhanced_github_indexer import ContentIndexer
        
        indexer = ContentIndexer()
        indexer.build_index(force_refresh=force_refresh)
        indexer.close()
        
        print("✅ Index built successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to build index: {e}")
        return False

def start_search_server():
    """Start the search API server"""
    print("🌐 Starting search API server...")
    
    if not check_requirements():
        return False
    
    if not os.path.exists("repo_index.db"):
        print("❌ No search index found. Please build the index first:")
        print("   python manage.py build")
        return False
    
    try:
        subprocess.run([sys.executable, "search_api.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Search server stopped")
    except Exception as e:
        print(f"❌ Failed to start server: {e}")
        return False

def start_web_server():
    """Start the web interface server"""
    print("🌐 Starting web interface server...")
    
    try:
        print("📂 Starting HTTP server on port 8000...")
        print("🔗 Open: http://localhost:8000/enhanced_index.html")
        subprocess.run([sys.executable, "-m", "http.server", "8000"], check=True)
    except KeyboardInterrupt:
        print("\n👋 Web server stopped")
    except Exception as e:
        print(f"❌ Failed to start web server: {e}")
        return False

def show_stats():
    """Show index statistics"""
    if not os.path.exists("repo_index.db"):
        print("❌ No search index found. Please build the index first.")
        return
    
    try:
        conn = sqlite3.connect("repo_index.db")
        
        # Get basic stats
        cursor = conn.execute("SELECT COUNT(*) FROM repo_index")
        total_repos = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(*) FROM repo_index WHERE readme_content != ''")
        repos_with_readme = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT COUNT(DISTINCT language) FROM repo_index WHERE language != ''")
        unique_languages = cursor.fetchone()[0]
        
        cursor = conn.execute("SELECT language, COUNT(*) as count FROM repo_index WHERE language != '' GROUP BY language ORDER BY count DESC LIMIT 10")
        top_languages = cursor.fetchall()
        
        cursor = conn.execute("SELECT AVG(stars) FROM repo_index")
        avg_stars = cursor.fetchone()[0] or 0
        
        cursor = conn.execute("SELECT full_name, stars FROM repo_index ORDER BY stars DESC LIMIT 5")
        top_repos = cursor.fetchall()
        
        conn.close()
        
        print("📊 Repository Index Statistics")
        print("=" * 40)
        print(f"📦 Total repositories: {total_repos}")
        print(f"📖 With README content: {repos_with_readme} ({repos_with_readme/total_repos*100:.1f}%)")
        print(f"💻 Programming languages: {unique_languages}")
        print(f"⭐ Average stars: {avg_stars:.1f}")
        
        print(f"\n🔥 Top Programming Languages:")
        for lang, count in top_languages:
            print(f"   {lang}: {count} repos")
        
        print(f"\n⭐ Most Starred Repositories:")
        for name, stars in top_repos:
            print(f"   {name}: {stars:,} stars")
        
        # Check index freshness
        cursor = conn.execute("SELECT MIN(last_indexed), MAX(last_indexed) FROM repo_index")
        min_indexed, max_indexed = cursor.fetchone()
        if min_indexed and max_indexed:
            print(f"\n🕒 Index updated: {max_indexed[:19]} UTC")
        
    except Exception as e:
        print(f"❌ Failed to get stats: {e}")

def search_repositories(query, limit=10):
    """Search repositories from command line"""
    if not os.path.exists("repo_index.db"):
        print("❌ No search index found. Please build the index first.")
        return
    
    try:
        from search_api import AdvancedSearchEngine
        
        engine = AdvancedSearchEngine()
        results = engine.search(query, limit=limit)
        
        if not results:
            print(f"🔍 No results found for: {query}")
            return
        
        print(f"🔍 Search results for: {query}")
        print("=" * 50)
        
        for i, result in enumerate(results, 1):
            repo = result.repo
            score = result.score
            print(f"\n{i}. {repo['full_name']} (Score: {score:.2f})")
            print(f"   ⭐ {repo['stars']:,} stars | 💻 {repo['language'] or 'N/A'}")
            print(f"   🔗 {repo['html_url']}")
            
            if repo['description']:
                description = repo['description'][:100] + "..." if len(repo['description']) > 100 else repo['description']
                print(f"   📝 {description}")
            
            if result.matched_fields:
                print(f"   🎯 Matched: {', '.join(result.matched_fields)}")
    
    except Exception as e:
        print(f"❌ Search failed: {e}")

def cleanup():
    """Clean up generated files"""
    files_to_remove = [
        "repo_index.db",
        "enhanced_starred_repos.json",
        "starred_repos.json",
        "starred_repos.csv",
    ]
    
    cache_dir = Path("cache")
    
    removed_count = 0
    
    for file_path in files_to_remove:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"🗑️  Removed {file_path}")
            removed_count += 1
    
    if cache_dir.exists():
        import shutil
        shutil.rmtree(cache_dir)
        print(f"🗑️  Removed cache directory")
        removed_count += 1
    
    if removed_count == 0:
        print("✨ No files to clean up")
    else:
        print(f"✅ Cleaned up {removed_count} items")

def main():
    parser = argparse.ArgumentParser(description="Enhanced GitHub Stars Management")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Build command
    build_parser = subparsers.add_parser('build', help='Build repository content index')
    build_parser.add_argument('--force', action='store_true', help='Force refresh all content')
    
    # Server command
    subparsers.add_parser('server', help='Start search API server')
    
    # Web command
    subparsers.add_parser('web', help='Start web interface server')
    
    # Stats command
    subparsers.add_parser('stats', help='Show index statistics')
    
    # Search command
    search_parser = subparsers.add_parser('search', help='Search repositories from command line')
    search_parser.add_argument('query', help='Search query')
    search_parser.add_argument('--limit', type=int, default=10, help='Number of results to show')
    
    # Cleanup command
    subparsers.add_parser('cleanup', help='Clean up generated files')
    
    # Check command
    subparsers.add_parser('check', help='Check system requirements')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    if args.command == 'build':
        build_index(force_refresh=args.force)
    elif args.command == 'server':
        start_search_server()
    elif args.command == 'web':
        start_web_server()
    elif args.command == 'stats':
        show_stats()
    elif args.command == 'search':
        search_repositories(args.query, args.limit)
    elif args.command == 'cleanup':
        cleanup()
    elif args.command == 'check':
        print("🔍 Checking system requirements...")
        
        req_ok = check_requirements()
        token_ok = check_token()
        
        if req_ok and token_ok:
            print("✅ All requirements satisfied!")
            print("\n🚀 Quick start:")
            print("   1. python manage.py build     # Build the index")
            print("   2. python manage.py server    # Start search API (in new terminal)")
            print("   3. python manage.py web       # Start web interface (in new terminal)")
        else:
            print("❌ Some requirements are not satisfied")

if __name__ == "__main__":
    main()
