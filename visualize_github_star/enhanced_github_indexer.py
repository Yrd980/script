import requests
import json
import csv
import os
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from tqdm import tqdm
import re
from typing import Dict, List, Optional, Any
import sqlite3
from dataclasses import dataclass, asdict
import base64

# Configuration
TOKEN = ""  # Replace with your GitHub Token
HEADERS = {"Authorization": f"token {TOKEN}"}
PER_PAGE = 100
TIMEOUT = 15
MAX_RETRIES = 3
CACHE_DIR = "cache"
INDEX_DB = "repo_index.db"

@dataclass
class RepoContent:
    """Repository content structure"""
    full_name: str
    name: str
    description: str
    language: str
    stars: int
    updated_at: str
    html_url: str
    owner_login: str
    owner_avatar: str
    archived: bool
    readme_content: str = ""
    topics: List[str] = None
    last_indexed: str = ""
    
    def __post_init__(self):
        if self.topics is None:
            self.topics = []

class ContentIndexer:
    """Enhanced GitHub repository content indexer with caching"""
    
    def __init__(self):
        self.session = self._setup_session()
        self.cache_dir = Path(CACHE_DIR)
        self.cache_dir.mkdir(exist_ok=True)
        self._setup_database()
    
    def _setup_session(self) -> requests.Session:
        """Setup session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504, 403, 429]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session
    
    def _setup_database(self):
        """Setup SQLite database for content indexing"""
        self.conn = sqlite3.connect(INDEX_DB)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS repo_index (
                full_name TEXT PRIMARY KEY,
                name TEXT,
                description TEXT,
                language TEXT,
                stars INTEGER,
                updated_at TEXT,
                html_url TEXT,
                owner_login TEXT,
                owner_avatar TEXT,
                archived BOOLEAN,
                readme_content TEXT,
                topics TEXT,
                last_indexed TEXT,
                content_hash TEXT
            )
        ''')
        
        # Create full-text search virtual table
        self.conn.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS repo_fts USING fts5(
                full_name,
                name,
                description,
                readme_content,
                topics,
                content='repo_index',
                content_rowid='rowid'
            )
        ''')
        
        # Create triggers to keep FTS table in sync
        self.conn.executescript('''
            DROP TRIGGER IF EXISTS repo_ai;
            DROP TRIGGER IF EXISTS repo_ad;
            DROP TRIGGER IF EXISTS repo_au;
            
            CREATE TRIGGER repo_ai AFTER INSERT ON repo_index BEGIN
                INSERT INTO repo_fts(rowid, full_name, name, description, readme_content, topics)
                VALUES (new.rowid, new.full_name, new.name, new.description, new.readme_content, new.topics);
            END;
            
            CREATE TRIGGER repo_ad AFTER DELETE ON repo_index BEGIN
                INSERT INTO repo_fts(repo_fts, rowid, full_name, name, description, readme_content, topics)
                VALUES('delete', old.rowid, old.full_name, old.name, old.description, old.readme_content, old.topics);
            END;
            
            CREATE TRIGGER repo_au AFTER UPDATE ON repo_index BEGIN
                INSERT INTO repo_fts(repo_fts, rowid, full_name, name, description, readme_content, topics)
                VALUES('delete', old.rowid, old.full_name, old.name, old.description, old.readme_content, old.topics);
                INSERT INTO repo_fts(rowid, full_name, name, description, readme_content, topics)
                VALUES (new.rowid, new.full_name, new.name, new.description, new.readme_content, new.topics);
            END;
        ''')
        
        self.conn.commit()
    
    def fetch_starred_repos(self) -> List[Dict]:
        """Fetch all starred repositories"""
        page = 1
        repos = []
        
        print("🚀 Fetching starred repositories...")
        with tqdm(desc="📥 Fetching pages", unit="page") as pbar:
            while True:
                url = f"https://api.github.com/user/starred?per_page={PER_PAGE}&page={page}"
                try:
                    response = self.session.get(url, headers=HEADERS, timeout=TIMEOUT)
                    response.raise_for_status()
                    data = response.json()
                    
                    if not data:
                        break
                    
                    repos.extend(data)
                    pbar.set_postfix({"repos": len(repos)})
                    pbar.update(1)
                    page += 1
                    
                    # Rate limiting
                    time.sleep(0.1)
                    
                except Exception as e:
                    print(f"\n⚠️ Error on page {page}: {str(e)}")
                    break
        
        return repos
    
    def fetch_readme_content(self, repo_data: Dict) -> str:
        """Fetch README content from repository"""
        full_name = repo_data['full_name']
        
        # Check cache first
        cache_file = self.cache_dir / f"{full_name.replace('/', '_')}_readme.txt"
        if cache_file.exists():
            repo_updated = datetime.fromisoformat(repo_data['updated_at'].replace('Z', '+00:00'))
            cache_modified = datetime.fromtimestamp(cache_file.stat().st_mtime, tz=timezone.utc)
            
            if cache_modified > repo_updated:
                return cache_file.read_text(encoding='utf-8', errors='ignore')
        
        # Fetch from GitHub API
        readme_files = ['README.md', 'readme.md', 'README.rst', 'README.txt', 'README']
        
        for readme_file in readme_files:
            try:
                url = f"https://api.github.com/repos/{full_name}/contents/{readme_file}"
                response = self.session.get(url, headers=HEADERS, timeout=TIMEOUT)
                
                if response.status_code == 200:
                    content_data = response.json()
                    if content_data.get('type') == 'file' and content_data.get('content'):
                        # Decode base64 content
                        content = base64.b64decode(content_data['content']).decode('utf-8', errors='ignore')
                        
                        # Clean markdown content for better searching
                        cleaned_content = self._clean_markdown(content)
                        
                        # Cache the content
                        cache_file.write_text(cleaned_content, encoding='utf-8')
                        return cleaned_content
                        
                time.sleep(0.1)  # Rate limiting
                
            except Exception as e:
                continue
        
        return ""
    
    def _clean_markdown(self, content: str) -> str:
        """Clean markdown content for better searching"""
        # Remove markdown syntax but keep the content
        content = re.sub(r'```[\s\S]*?```', '', content)  # Remove code blocks
        content = re.sub(r'`[^`]+`', '', content)  # Remove inline code
        content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)  # Convert links to text
        content = re.sub(r'[#*_`\[\](){}]', '', content)  # Remove markdown symbols
        content = re.sub(r'\n+', '\n', content)  # Normalize newlines
        content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
        return content.strip()
    
    def process_repository(self, repo_data: Dict) -> RepoContent:
        """Process a single repository and extract all content"""
        readme_content = ""
        
        # Only fetch README for non-archived repos to save API calls
        if not repo_data.get('archived', False):
            readme_content = self.fetch_readme_content(repo_data)
        
        return RepoContent(
            full_name=repo_data['full_name'],
            name=repo_data['name'],
            description=repo_data.get('description') or '',
            language=repo_data.get('language') or '',
            stars=repo_data.get('stargazers_count', 0),
            updated_at=repo_data['updated_at'],
            html_url=repo_data['html_url'],
            owner_login=repo_data['owner']['login'],
            owner_avatar=repo_data['owner']['avatar_url'],
            archived=repo_data.get('archived', False),
            readme_content=readme_content,
            topics=repo_data.get('topics', []),
            last_indexed=datetime.now(timezone.utc).isoformat()
        )
    
    def get_content_hash(self, repo_content: RepoContent) -> str:
        """Generate hash of repository content for change detection"""
        content_str = f"{repo_content.description}{repo_content.readme_content}{repo_content.updated_at}"
        return hashlib.md5(content_str.encode()).hexdigest()
    
    def save_to_database(self, repo_content: RepoContent):
        """Save repository content to database"""
        content_hash = self.get_content_hash(repo_content)
        
        # Check if content has changed
        cursor = self.conn.execute(
            "SELECT content_hash FROM repo_index WHERE full_name = ?",
            (repo_content.full_name,)
        )
        result = cursor.fetchone()
        
        if result and result[0] == content_hash:
            return  # No changes, skip update
        
        # Insert or update
        self.conn.execute('''
            INSERT OR REPLACE INTO repo_index 
            (full_name, name, description, language, stars, updated_at, html_url, 
             owner_login, owner_avatar, archived, readme_content, topics, last_indexed, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            repo_content.full_name,
            repo_content.name,
            repo_content.description,
            repo_content.language,
            repo_content.stars,
            repo_content.updated_at,
            repo_content.html_url,
            repo_content.owner_login,
            repo_content.owner_avatar,
            repo_content.archived,
            repo_content.readme_content,
            json.dumps(repo_content.topics),
            repo_content.last_indexed,
            content_hash
        ))
    
    def build_index(self, force_refresh: bool = False):
        """Build comprehensive content index"""
        print("🔍 Building comprehensive repository index...")
        
        # Fetch repositories
        repos = self.fetch_starred_repos()
        print(f"📦 Found {len(repos)} starred repositories")
        
        # Process each repository
        processed_repos = []
        with tqdm(repos, desc="🔨 Processing repositories", unit="repo") as pbar:
            for repo_data in pbar:
                try:
                    pbar.set_postfix({"repo": repo_data['name'][:30]})
                    repo_content = self.process_repository(repo_data)
                    self.save_to_database(repo_content)
                    processed_repos.append(asdict(repo_content))
                    
                except Exception as e:
                    print(f"\n⚠️ Error processing {repo_data['full_name']}: {e}")
                    continue
        
        self.conn.commit()
        
        # Save to JSON for web interface
        with open("enhanced_starred_repos.json", "w", encoding='utf-8') as f:
            json.dump(processed_repos, f, indent=2, ensure_ascii=False)
        
        print(f"✅ Index built successfully!")
        print(f"📊 Processed {len(processed_repos)} repositories")
        print(f"💾 Database: {INDEX_DB}")
        print(f"📁 JSON file: enhanced_starred_repos.json")
    
    def search_repositories(self, query: str, limit: int = 50) -> List[Dict]:
        """Search repositories using full-text search"""
        if not query.strip():
            # Return all repositories if no query
            cursor = self.conn.execute('''
                SELECT * FROM repo_index 
                ORDER BY stars DESC 
                LIMIT ?
            ''', (limit,))
        else:
            # Use FTS for content search
            cursor = self.conn.execute('''
                SELECT r.*, 
                       fts.rank
                FROM repo_fts fts
                JOIN repo_index r ON r.rowid = fts.rowid
                WHERE repo_fts MATCH ?
                ORDER BY fts.rank
                LIMIT ?
            ''', (query, limit))
        
        results = []
        for row in cursor.fetchall():
            repo_dict = {
                'full_name': row[0],
                'name': row[1],
                'description': row[2],
                'language': row[3],
                'stars': row[4],
                'updated_at': row[5],
                'html_url': row[6],
                'owner_login': row[7],
                'owner_avatar': row[8],
                'archived': row[9],
                'readme_content': row[10],
                'topics': json.loads(row[11]) if row[11] else [],
                'last_indexed': row[12]
            }
            results.append(repo_dict)
        
        return results
    
    def close(self):
        """Close database connection"""
        if hasattr(self, 'conn'):
            self.conn.close()

def main():
    """Main function"""
    indexer = ContentIndexer()
    
    try:
        # Build the index
        indexer.build_index()
        
        # Example search
        print("\n🔍 Example searches:")
        test_queries = ["web framework", "machine learning", "react"]
        
        for query in test_queries:
            results = indexer.search_repositories(query, limit=5)
            print(f"\nQuery: '{query}' - Found {len(results)} results")
            for i, repo in enumerate(results[:3], 1):
                print(f"  {i}. {repo['full_name']} (⭐{repo['stars']})")
    
    finally:
        indexer.close()

if __name__ == "__main__":
    main()
