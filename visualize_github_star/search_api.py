from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
import json
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass
import difflib
from collections import defaultdict
import math

@dataclass
class SearchResult:
    """Search result with scoring"""
    repo: Dict[str, Any]
    score: float
    matched_fields: List[str]
    snippets: Dict[str, str]

class AdvancedSearchEngine:
    """Advanced search engine with fuzzy matching and content scoring"""
    
    def __init__(self, db_path: str = "repo_index.db"):
        self.db_path = db_path
        
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def normalize_query(self, query: str) -> str:
        """Normalize search query"""
        # Convert to lowercase and remove special characters
        normalized = re.sub(r'[^\w\s]', ' ', query.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return normalized
    
    def extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        if not text:
            return []
        
        # Simple keyword extraction
        words = re.findall(r'\b\w{3,}\b', text.lower())
        # Filter out common stop words
        stop_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'she', 'use', 'her', 'way', 'many', 'some', 'time', 'very', 'when', 'much', 'then', 'them', 'well', 'were'}
        return [word for word in words if word not in stop_words]
    
    def calculate_text_similarity(self, query_words: List[str], text: str) -> Tuple[float, List[str]]:
        """Calculate similarity between query and text"""
        if not text or not query_words:
            return 0.0, []
        
        text_words = self.extract_keywords(text)
        if not text_words:
            return 0.0, []
        
        matches = []
        total_score = 0.0
        
        for query_word in query_words:
            best_match_score = 0.0
            best_match = None
            
            for text_word in text_words:
                # Exact match
                if query_word == text_word:
                    score = 1.0
                # Substring match
                elif query_word in text_word or text_word in query_word:
                    score = 0.8
                # Fuzzy match using difflib
                else:
                    score = difflib.SequenceMatcher(None, query_word, text_word).ratio()
                    if score < 0.6:  # Threshold for fuzzy matching
                        score = 0.0
                
                if score > best_match_score:
                    best_match_score = score
                    best_match = text_word
            
            if best_match_score > 0:
                total_score += best_match_score
                matches.append(best_match)
        
        # Normalize score
        if query_words:
            total_score = total_score / len(query_words)
        
        return total_score, matches
    
    def extract_snippet(self, text: str, query_words: List[str], max_length: int = 200) -> str:
        """Extract relevant snippet from text"""
        if not text or not query_words:
            return text[:max_length] + "..." if len(text) > max_length else text
        
        text_lower = text.lower()
        best_pos = 0
        best_score = 0
        
        # Find the position with most query word matches
        for i in range(0, len(text), 50):
            snippet = text_lower[i:i+max_length]
            score = sum(1 for word in query_words if word in snippet)
            if score > best_score:
                best_score = score
                best_pos = i
        
        snippet = text[best_pos:best_pos+max_length]
        if best_pos > 0:
            snippet = "..." + snippet
        if best_pos + max_length < len(text):
            snippet = snippet + "..."
        
        return snippet
    
    def score_repository(self, repo: sqlite3.Row, query: str) -> SearchResult:
        """Score a repository based on query relevance"""
        normalized_query = self.normalize_query(query)
        query_words = self.extract_keywords(normalized_query)
        
        if not query_words:
            return SearchResult(
                repo=dict(repo),
                score=0.0,
                matched_fields=[],
                snippets={}
            )
        
        scores = {}
        matched_fields = []
        snippets = {}
        
        # Score different fields with different weights
        fields_weights = {
            'name': 3.0,
            'full_name': 2.5,
            'description': 2.0,
            'readme_content': 1.5,
            'topics': 2.5
        }
        
        total_score = 0.0
        
        for field, weight in fields_weights.items():
            field_value = repo[field] or ""
            
            if field == 'topics':
                # Topics are stored as JSON string
                try:
                    topics_list = json.loads(field_value) if field_value else []
                    field_value = " ".join(topics_list)
                except:
                    field_value = ""
            
            if field_value:
                similarity, matches = self.calculate_text_similarity(query_words, field_value)
                if similarity > 0:
                    field_score = similarity * weight
                    total_score += field_score
                    scores[field] = field_score
                    matched_fields.append(field)
                    
                    # Generate snippet for content fields
                    if field in ['description', 'readme_content']:
                        snippets[field] = self.extract_snippet(field_value, query_words)
        
        # Boost score based on repository popularity (stars)
        stars = repo['stars'] or 0
        popularity_boost = min(math.log10(stars + 1) * 0.1, 0.5)
        total_score += popularity_boost
        
        # Penalty for archived repositories
        if repo['archived']:
            total_score *= 0.7
        
        return SearchResult(
            repo=dict(repo),
            score=total_score,
            matched_fields=matched_fields,
            snippets=snippets
        )
    
    def search(self, query: str, limit: int = 50, min_score: float = 0.1) -> List[SearchResult]:
        """Perform advanced search"""
        if not query.strip():
            return self.get_all_repos(limit)
        
        normalized_query = self.normalize_query(query)
        query_words = self.extract_keywords(normalized_query)
        
        if not query_words:
            return self.get_all_repos(limit)
        
        results = []
        
        with self.get_connection() as conn:
            # First try FTS search for exact matches
            fts_query = " OR ".join(query_words)
            try:
                cursor = conn.execute('''
                    SELECT r.* 
                    FROM repo_fts fts
                    JOIN repo_index r ON r.rowid = fts.rowid
                    WHERE repo_fts MATCH ?
                    ORDER BY r.stars DESC
                ''', (fts_query,))
                
                fts_results = cursor.fetchall()
                
                # Score FTS results
                for repo in fts_results:
                    result = self.score_repository(repo, query)
                    if result.score >= min_score:
                        results.append(result)
            
            except sqlite3.OperationalError:
                # FTS query failed, fall back to fuzzy search
                pass
            
            # If we don't have enough results, do fuzzy search on all repos
            if len(results) < limit // 2:
                cursor = conn.execute('''
                    SELECT * FROM repo_index 
                    ORDER BY stars DESC
                ''')
                
                all_repos = cursor.fetchall()
                
                for repo in all_repos:
                    # Skip if already in results
                    if any(r.repo['full_name'] == repo['full_name'] for r in results):
                        continue
                    
                    result = self.score_repository(repo, query)
                    if result.score >= min_score:
                        results.append(result)
        
        # Sort by score and return top results
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def get_all_repos(self, limit: int = 50) -> List[SearchResult]:
        """Get all repositories sorted by stars"""
        results = []
        
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM repo_index 
                ORDER BY stars DESC 
                LIMIT ?
            ''', (limit,))
            
            for repo in cursor.fetchall():
                results.append(SearchResult(
                    repo=dict(repo),
                    score=0.0,
                    matched_fields=[],
                    snippets={}
                ))
        
        return results
    
    def get_suggestions(self, query: str, limit: int = 10) -> List[str]:
        """Get search suggestions based on repository content"""
        suggestions = set()
        normalized_query = self.normalize_query(query)
        
        if len(normalized_query) < 2:
            return []
        
        with self.get_connection() as conn:
            # Get suggestions from repository names and topics
            cursor = conn.execute('''
                SELECT name, topics FROM repo_index 
                WHERE name LIKE ? OR topics LIKE ?
                LIMIT ?
            ''', (f'%{normalized_query}%', f'%{normalized_query}%', limit * 3))
            
            for row in cursor.fetchall():
                # Add matching repository names
                if normalized_query in row['name'].lower():
                    suggestions.add(row['name'])
                
                # Add matching topics
                try:
                    topics = json.loads(row['topics']) if row['topics'] else []
                    for topic in topics:
                        if normalized_query in topic.lower():
                            suggestions.add(topic)
                except:
                    pass
        
        return list(suggestions)[:limit]

# Flask API
app = Flask(__name__)
CORS(app)

search_engine = AdvancedSearchEngine()

@app.route('/api/search')
def search():
    """Search API endpoint"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 50)), 100)
    min_score = float(request.args.get('min_score', 0.1))
    
    try:
        results = search_engine.search(query, limit, min_score)
        
        response_data = []
        for result in results:
            repo_data = result.repo.copy()
            repo_data['search_score'] = result.score
            repo_data['matched_fields'] = result.matched_fields
            repo_data['snippets'] = result.snippets
            
            # Parse topics JSON
            try:
                repo_data['topics'] = json.loads(repo_data['topics']) if repo_data['topics'] else []
            except:
                repo_data['topics'] = []
            
            response_data.append(repo_data)
        
        return jsonify({
            'success': True,
            'query': query,
            'total': len(response_data),
            'results': response_data
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/suggestions')
def suggestions():
    """Search suggestions API endpoint"""
    query = request.args.get('q', '').strip()
    limit = min(int(request.args.get('limit', 10)), 20)
    
    try:
        suggestions = search_engine.get_suggestions(query, limit)
        return jsonify({
            'success': True,
            'suggestions': suggestions
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats')
def stats():
    """Get index statistics"""
    try:
        with search_engine.get_connection() as conn:
            cursor = conn.execute('SELECT COUNT(*) as total FROM repo_index')
            total = cursor.fetchone()['total']
            
            cursor = conn.execute('SELECT COUNT(*) as with_readme FROM repo_index WHERE readme_content != ""')
            with_readme = cursor.fetchone()['with_readme']
            
            cursor = conn.execute('SELECT COUNT(DISTINCT language) as languages FROM repo_index WHERE language != ""')
            languages = cursor.fetchone()['languages']
        
        return jsonify({
            'success': True,
            'stats': {
                'total_repositories': total,
                'repositories_with_readme': with_readme,
                'unique_languages': languages,
                'readme_coverage': round(with_readme / total * 100, 1) if total > 0 else 0
            }
        })
    
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    print("🚀 Starting Advanced Search API Server...")
    print("📚 Endpoints:")
    print("  GET /api/search?q=<query>&limit=<limit>&min_score=<score>")
    print("  GET /api/suggestions?q=<query>&limit=<limit>")
    print("  GET /api/stats")
    print("\n🌐 Server running on http://localhost:5000")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
