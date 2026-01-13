import logging
import re
from typing import List, Dict, Any, Tuple, Set
from dataclasses import dataclass
from collections import Counter

logger = logging.getLogger(__name__)


@dataclass
class SearchQuery:
    """Represents a decomposed search query."""
    original: str
    decomposed: List[str]
    intent: str
    is_comprehensive: bool


class QueryDecomposer:
    """
    Decomposes user queries into multiple search strategies using generic NLP techniques.
    
    Completely data-agnostic approach:
    1. Extracts key terms and phrases from the query dynamically
    2. Removes stop words to identify meaningful concepts
    3. Creates semantic variations at different levels of specificity
    4. Generates sub-queries by combining terms in different ways
    
    Works with ANY domain/document type without hardcoded patterns or concepts.
    """
    
    # Generic stop words (language-level, not domain-specific)
    STOP_WORDS = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
        'do', 'does', 'did', 'will', 'would', 'could', 'should', 'may', 'might',
        'must', 'can', 'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she',
        'it', 'we', 'they', 'what', 'which', 'who', 'when', 'where', 'why', 'how',
        'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other', 'some',
        'such', 'no', 'nor', 'not', 'only', 'same', 'so', 'than', 'too', 'very',
        'just', 'my', 'me', 'your', 'him', 'her', 'its', 'our', 'their',
    }
    
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """
        Tokenize text into words, preserving quoted phrases.
        
        Example: 'list all api with "authentication": "Bearer token"'
        Returns: ['list', 'all', 'api', 'with', 'authentication', 'Bearer token']
        """
        tokens = []
        # Extract quoted phrases first
        quoted_pattern = r'"([^"]+)"'
        quoted_phrases = re.findall(quoted_pattern, text)
        tokens.extend(quoted_phrases)
        
        # Remove quoted content and split remaining text
        text_without_quotes = re.sub(quoted_pattern, '', text)
        # Split on non-word characters but keep alphanumeric and underscores
        words = re.findall(r'\b[\w]+\b', text_without_quotes.lower())
        tokens.extend(words)
        
        return tokens
    
    @staticmethod
    def _extract_key_terms(query: str) -> List[str]:
        """
        Extract meaningful key terms by removing stop words.
        
        Example: "list all api with authentication Bearer token"
        Returns: ['api', 'authentication', 'bearer', 'token']
        """
        tokens = QueryDecomposer._tokenize(query)
        # Filter out stop words
        key_terms = [t for t in tokens if t.lower() not in QueryDecomposer.STOP_WORDS and len(t) > 1]
        return list(dict.fromkeys(key_terms))  # Remove duplicates while preserving order
    
    @staticmethod
    def is_comprehensive_query(query: str) -> bool:
        """Detect if query asks for comprehensive/multiple results."""
        query_lower = query.lower()
        comprehensive_indicators = [
            r'\ball\b', r'\blist\b', r'\bshow\b', r'\benumerate\b',
            r'\bwhat are\b', r'\bfind all\b', r'\bget all\b'
        ]
        return any(re.search(pattern, query_lower) for pattern in comprehensive_indicators)
    
    @staticmethod
    def detect_intent(query: str) -> str:
        """Detect the intent of the query."""
        query_lower = query.lower()
        
        if re.search(r'\bhow to\b|\bsteps\b|\bprocedure', query_lower):
            return 'procedural'
        elif re.search(r'\ball\b|\blist\b|\bshow\b|\benumerate\b', query_lower):
            return 'comprehensive'
        elif re.search(r'\bwhy\b|\bexplain\b', query_lower):
            return 'explanatory'
        elif re.search(r'\bwhat (is|are)\b', query_lower):
            return 'explanatory'
        elif re.search(r'\bfind\b|\bget\b|\bfetch\b', query_lower):
            return 'specific'
        else:
            return 'general'
    
    @staticmethod
    def _generate_sub_queries(key_terms: List[str]) -> List[str]:
        """
        Generate sub-queries from key terms using different combination strategies.
        
        Strategies:
        1. Individual terms
        2. Pairs of adjacent terms
        3. All terms together
        4. Non-adjacent pairs
        5. 3-term sequences
        
        Example: ['api', 'authentication', 'bearer']
        Returns: ['api', 'authentication', 'bearer', 'api authentication', 
                  'authentication bearer', 'api authentication bearer', ...]
        """
        if not key_terms:
            return []
        
        sub_queries = []
        
        # Strategy 1: Individual terms
        sub_queries.extend(key_terms)
        
        # Strategy 2: Pairs of adjacent terms
        for i in range(len(key_terms) - 1):
            pair = f"{key_terms[i]} {key_terms[i + 1]}"
            sub_queries.append(pair)
        
        # Strategy 3: All terms together (if more than 1 term)
        if len(key_terms) > 1:
            all_terms = ' '.join(key_terms)
            sub_queries.append(all_terms)
        
        # Strategy 4: Non-adjacent pairs (skip one)
        for i in range(len(key_terms) - 2):
            skip_pair = f"{key_terms[i]} {key_terms[i + 2]}"
            sub_queries.append(skip_pair)
        
        # Strategy 5: 3-term sequences
        for i in range(len(key_terms) - 2):
            triplet = f"{key_terms[i]} {key_terms[i + 1]} {key_terms[i + 2]}"
            sub_queries.append(triplet)
        
        return sub_queries
    
    @classmethod
    def decompose_comprehensive_query(cls, query: str) -> List[str]:
        """
        Decompose comprehensive queries into focused sub-queries.
        
        Generic approach:
        1. Extract key terms (non-stop words)
        2. Generate combinations at different specificity levels
        3. Include original query
        4. Remove duplicates and limit to 8
        
        Example: "list all api with authentication Bearer token"
        Returns: ['list all api with authentication Bearer token', 'api', 'authentication',
                  'bearer', 'token', 'api authentication', 'authentication bearer', ...]
        """
        sub_queries = [query]  # Always include original
        
        # Extract key terms dynamically
        key_terms = cls._extract_key_terms(query)
        
        # Generate multiple variations
        if key_terms:
            generated = cls._generate_sub_queries(key_terms)
            sub_queries.extend(generated)
        
        # Remove duplicates (case-insensitive) while preserving order
        seen = set()
        unique_queries = []
        for q in sub_queries:
            q_lower = q.lower()
            if q_lower not in seen:
                seen.add(q_lower)
                unique_queries.append(q)
        
        return unique_queries[:8]  # Limit to 8 queries
    
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
        
        # Use comprehensive decomposition for comprehensive, procedural, and explanatory queries
        if is_comprehensive or intent in ['comprehensive', 'procedural', 'explanatory']:
            decomposed = cls.decompose_comprehensive_query(clean_query)
        else:
            # For specific queries, use key term extraction
            key_terms = cls._extract_key_terms(clean_query)
            decomposed = cls._generate_sub_queries(key_terms)
            if not decomposed:  # Fallback to original if no key terms extracted
                decomposed = [clean_query]
        
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
        }
