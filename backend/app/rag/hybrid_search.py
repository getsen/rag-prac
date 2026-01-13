import logging
import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """Represents a decomposed search query."""
    original: str
    decomposed: List[str]
    intent: str
    is_comprehensive: bool


class QueryDecomposer:
    """Decomposes user queries into multiple search strategies."""
    
    # Patterns for detecting query intents
    COMPREHENSIVE_PATTERNS = [
        r'\ball\b',
        r'\blist\b',
        r'\bshow\b',
        r'\benumerate\b',
        r'\bwhat are\b',
        r'\ball.*types\b',
        r'\ball.*kinds\b',
    ]
    
    SPECIFIC_PATTERNS = [
        r'\bfind\b',
        r'\bget\b',
        r'\bspecific\b',
        r'\bparticular\b',
        r'\bhow to\b',
        r'\bsteps\b',
    ]
    
    # Synonym maps for query expansion
    SYNONYMS = {
        'endpoint': ['route', 'service', 'api', 'operation', 'path', 'url'],
        'method': ['verb', 'http method', 'operation type', 'request method'],
        'api': ['endpoint', 'service', 'interface', 'rest', 'web service'],
        'delete': ['remove', 'destroy', 'eliminate', 'drop'],
        'create': ['add', 'new', 'initialize', 'make', 'generate'],
        'get': ['retrieve', 'fetch', 'obtain', 'read'],
        'update': ['modify', 'change', 'edit', 'patch', 'put'],
        'list': ['all', 'enumerate', 'show', 'display', 'retrieve all'],
        'configuration': ['settings', 'config', 'setup', 'options', 'parameters'],
        'database': ['db', 'storage', 'persistence', 'data store'],
        'authentication': ['auth', 'login', 'credentials', 'security', 'token'],
        'report': ['analytics', 'metrics', 'statistics', 'data', 'summary'],
    }
    
    @staticmethod
    def is_comprehensive_query(query: str) -> bool:
        """Detect if query is asking for comprehensive results."""
        query_lower = query.lower()
        for pattern in QueryDecomposer.COMPREHENSIVE_PATTERNS:
            if re.search(pattern, query_lower):
                return True
        return False
    
    @staticmethod
    def detect_intent(query: str) -> str:
        """Detect the intent of the query."""
        query_lower = query.lower()
        
        if re.search(r'\bhow to\b|\bsteps\b', query_lower):
            return 'procedural'
        elif re.search(r'\bwhy\b|\bwhat is\b|\bexplain\b', query_lower):
            return 'explanatory'
        elif re.search(r'\ball\b|\blist\b|\bshow\b', query_lower):
            return 'comprehensive'
        elif re.search(r'\bfind\b|\bget\b|\bfetch\b', query_lower):
            return 'specific'
        else:
            return 'general'
    
    @staticmethod
    def expand_with_synonyms(query: str) -> List[str]:
        """Expand query with synonyms."""
        expanded = [query]
        query_lower = query.lower()
        
        for word, synonyms in QueryDecomposer.SYNONYMS.items():
            if word in query_lower:
                # Create variants with each synonym
                for synonym in synonyms:
                    variant = re.sub(r'\b' + word + r'\b', synonym, query_lower, flags=re.IGNORECASE)
                    if variant not in expanded and variant != query_lower:
                        expanded.append(variant)
        
        return expanded[:5]  # Limit to 5 variants to avoid explosion
    
    @staticmethod
    def decompose_comprehensive_query(query: str) -> List[str]:
        """
        Decompose comprehensive queries into focused sub-queries.
        
        Example: "list all api endpoints with get method"
        Returns: [
            "api endpoints with GET method",
            "GET endpoints",
            "api routes",
            "services",
        ]
        """
        sub_queries = [query]  # Always include original
        query_lower = query.lower()
        
        # Extract key concepts
        concepts = []
        if re.search(r'\bendpoint', query_lower):
            concepts.append('endpoint')
        if re.search(r'\bapi\b', query_lower):
            concepts.append('api')
        if re.search(r'\bmethod|HTTP', query_lower):
            concepts.append('method')
        if re.search(r'\bget|post|delete|put|patch', query_lower):
            http_method = re.search(r'\b(get|post|delete|put|patch)\b', query_lower, re.IGNORECASE)
            if http_method:
                concepts.append(http_method.group(1).upper())
        if re.search(r'\bconfiguration|config|settings', query_lower):
            concepts.append('configuration')
        if re.search(r'\breport|analytics', query_lower):
            concepts.append('analytics')
        
        # Create focused sub-queries from concepts
        for concept in concepts:
            sub_queries.append(f"{concept}")
            
            # Pair complementary concepts
            if 'endpoint' in concepts and 'method' in concepts:
                sub_queries.append("endpoint methods")
                sub_queries.append("HTTP endpoints")
            
            if 'api' in concepts and concept != 'api':
                sub_queries.append(f"{concept} API")
        
        # Add broad searches for comprehensive queries
        if 'endpoint' in concepts or 'api' in concepts:
            sub_queries.append("endpoints")
            sub_queries.append("services")
            sub_queries.append("operations")
        
        return list(dict.fromkeys(sub_queries))[:8]  # Remove duplicates, limit to 8
    
    @classmethod
    def decompose(cls, query: str) -> SearchQuery:
        """
        Main decomposition method.
        
        Returns SearchQuery with:
        - original: Original query
        - decomposed: List of search queries to try
        - intent: Detected intent
        - is_comprehensive: Whether query asks for multiple results
        """
        # Strip context if present (format: "query\n\nContext: ...")
        if '\n\nContext:' in query:
            clean_query = query.split('\n\nContext:')[0].strip()
        else:
            clean_query = query.strip()
        
        intent = cls.detect_intent(clean_query)
        is_comprehensive = cls.is_comprehensive_query(clean_query)
        
        if is_comprehensive:
            decomposed = cls.decompose_comprehensive_query(clean_query)
        else:
            # For specific queries, use synonym expansion
            decomposed = cls.expand_with_synonyms(clean_query)
        
        return SearchQuery(
            original=clean_query,
            decomposed=decomposed,
            intent=intent,
            is_comprehensive=is_comprehensive,
        )


class BM25Search:
    """Implements BM25 (Best Matching 25) keyword-based search."""
    
    def __init__(self, documents: List[Dict[str, Any]] = None):
        """
        Initialize BM25 search.
        
        Args:
            documents: List of documents with 'text' and 'metadata' keys
        """
        self.documents = documents or []
        self.inverted_index = {}
        self.doc_lengths = []
        self.average_length = 0
        self._build_index()
    
    def _build_index(self):
        """Build inverted index from documents."""
        if not self.documents:
            return
        
        for doc_id, doc in enumerate(self.documents):
            text = doc.get('text', '').lower()
            tokens = self._tokenize(text)
            self.doc_lengths.append(len(tokens))
            
            # Build inverted index
            for token in set(tokens):
                if token not in self.inverted_index:
                    self.inverted_index[token] = []
                self.inverted_index[token].append(doc_id)
        
        if self.doc_lengths:
            self.average_length = sum(self.doc_lengths) / len(self.doc_lengths)
    
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Simple tokenizer."""
        # Convert to lowercase and split on non-alphanumeric
        tokens = re.findall(r'\w+', text.lower())
        return tokens
    
    def search(self, query: str, top_k: int = 8) -> List[Tuple[int, float]]:
        """
        BM25 search returning document IDs and scores.
        
        Args:
            query: Search query
            top_k: Number of top results to return
            
        Returns:
            List of (doc_id, score) tuples
        """
        if not self.documents:
            return []
        
        tokens = self._tokenize(query)
        scores = {}
        k1 = 1.5  # BM25 parameter
        b = 0.75  # BM25 parameter
        
        for token in tokens:
            if token not in self.inverted_index:
                continue
            
            idf = len(self.documents) / len(self.inverted_index[token])
            
            for doc_id in self.inverted_index[token]:
                # Count token frequency in document
                doc_text = self.documents[doc_id].get('text', '').lower()
                freq = len([t for t in self._tokenize(doc_text) if t == token])
                
                # BM25 formula
                doc_len = self.doc_lengths[doc_id]
                norm_len = doc_len / self.average_length if self.average_length > 0 else 1
                
                score = idf * (freq * (k1 + 1)) / (freq + k1 * (1 - b + b * norm_len))
                
                scores[doc_id] = scores.get(doc_id, 0) + score
        
        # Return top-k results
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return ranked[:top_k]


class HybridSearchStrategy:
    """Combines semantic search, keyword search, and query decomposition."""
    
    def __init__(self, documents: List[Dict[str, Any]] = None):
        """
        Initialize hybrid search.
        
        Args:
            documents: List of documents for BM25 indexing
        """
        self.decomposer = QueryDecomposer()
        self.bm25 = BM25Search(documents)
    
    def get_search_queries(self, query: str) -> List[str]:
        """
        Get list of queries to execute for comprehensive search.
        
        Args:
            query: User query
            
        Returns:
            List of search queries to try
        """
        search_query = self.decomposer.decompose(query)
        logger.info(f"Query decomposition - Intent: {search_query.intent}, Comprehensive: {search_query.is_comprehensive}")
        logger.info(f"Sub-queries: {search_query.decomposed}")
        
        return search_query.decomposed
    
    def analyze_query(self, query: str) -> Dict[str, Any]:
        """
        Analyze query for better search strategy.
        
        Args:
            query: User query
            
        Returns:
            Dictionary with analysis results
        """
        search_query = self.decomposer.decompose(query)
        
        return {
            'original': query,
            'intent': search_query.intent,
            'is_comprehensive': search_query.is_comprehensive,
            'sub_queries': search_query.decomposed,
            'should_expand': search_query.is_comprehensive,
            'should_use_bm25': 'method' in query.lower() or 'get' in query.lower() or 'post' in query.lower(),
        }
