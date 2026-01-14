"""
Adaptive RAG implementation using LangGraph.
This implements self-correcting RAG with query analysis, retrieval, and routing.
"""

import json
import logging
from typing import Any, Dict, List, Optional, TypedDict

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import StateGraph, START, END
from langchain_core.output_parsers import JsonOutputParser
from sentence_transformers import SentenceTransformer, CrossEncoder

from app.rag.hybrid_search import HybridSearchStrategy
from app.config import settings
from app.rag.rag_query import RAGQueryEngine
from app.llm.ollama.ollama_client import OllamaClient

logger = logging.getLogger(__name__)


class AdaptiveRAGState(TypedDict):
    """State for adaptive RAG workflow."""
    query: str
    messages: List[Dict[str, str]]
    retrieved_docs: List[Dict[str, Any]]
    query_analysis: Dict[str, Any]
    llm_response: str
    is_relevant: bool
    attempts: int
    max_attempts: int
    final_response: str
    sources: List[Dict[str, Any]]
    conversation_context: str  # Full enriched context for response generation


class AdaptiveRAG:
    """Adaptive RAG system using LangGraph for self-correcting retrieval and generation."""
    
    def __init__(
        self,
        db_dir: str = "chroma_db",
        chunks_collection: str = "runbook_chunks",
        embed_model: str = "BAAI/bge-large-en-v1.5",
        ollama_model: str = "llama2",
        temperature: float = 0.2,
        max_retrieval_attempts: int = 3,
    ):
        """Initialize adaptive RAG system."""
        self.rag_engine = RAGQueryEngine(db_dir, chunks_collection, embed_model)
        self.ollama_model = ollama_model
        self.temperature = temperature
        self.max_attempts = max_retrieval_attempts
        
        # Initialize hybrid search strategy
        self.hybrid_search = HybridSearchStrategy()
        logger.info("Hybrid search strategy initialized")
        
        # Initialize re-ranker for better document ranking
        try:
            self.reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-12-v2')
            logger.info("Re-ranker initialized: cross-encoder/ms-marco-MiniLM-L-12-v2")
        except Exception as e:
            logger.warning(f"Could not load re-ranker: {e}. Proceeding without re-ranking.")
            self.reranker = None
        
        # Initialize LLM based on cloud mode
        if settings.use_ollama_cloud:
            if not settings.ollama_api_key:
                raise ValueError("ollama_api_key is required when use_ollama_cloud=True")
            # Use OllamaClient for cloud mode (supports bearer token auth)
            self.ollama_client = OllamaClient(
                base_url=settings.ollama_base_url,
                use_cloud=True,
                api_key=settings.ollama_api_key,
            )
            self.use_cloud = True
            logger.info("AdaptiveRAG using Ollama Cloud mode")
        else:
            # Use ChatOllama for local mode (simpler, better integrated with LangChain)
            self.ollama_client = None
            self.use_cloud = False
            logger.info(f"AdaptiveRAG using local Ollama at {settings.ollama_base_url}")
        
        # Only initialize ChatOllama for local mode
        if not self.use_cloud:
            self.llm = ChatOllama(
                model=ollama_model,
                temperature=temperature,
                base_url=settings.ollama_base_url,
            )
        else:
            self.llm = None
        
        # Build workflow graph
        self.graph = self._build_graph()
        cloud_mode = "Cloud" if settings.use_ollama_cloud else "Local"
        logger.info(f"AdaptiveRAG initialized - mode={cloud_mode}, model={ollama_model}, max_attempts={max_retrieval_attempts}")

    def _call_llm(
        self,
        prompt: str,
        system: str,
        temperature: float,
        return_raw: bool = True,
    ) -> str:
        """
        Call LLM using appropriate client (cloud or local).
        
        Args:
            prompt: Main prompt text
            system: System prompt
            temperature: Sampling temperature
            return_raw: If True, return raw string. If False, extract .content from response.
            
        Returns:
            Generated text response
        """
        if self.use_cloud and self.ollama_client:
            # Use OllamaClient for cloud mode
            return self.ollama_client.generate(
                model=self.ollama_model,
                prompt=prompt,
                system=system,
                temperature=temperature,
            )
        else:
            # Use ChatOllama for local mode
            response = self.llm.invoke([
                SystemMessage(content=system),
                HumanMessage(content=prompt)
            ])
            return response.content

    def _build_graph(self) -> Any:
        """Build the LangGraph workflow for adaptive RAG."""
        workflow = StateGraph(AdaptiveRAGState)
        
        # Add nodes
        workflow.add_node("analyze_query", self._analyze_query)
        workflow.add_node("retrieve_docs", self._retrieve_documents)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("evaluate_response", self._evaluate_response)
        workflow.add_node("refine_query", self._refine_query)
        workflow.add_node("format_output", self._format_output)
        
        # Add edges
        workflow.add_edge(START, "analyze_query")
        workflow.add_edge("analyze_query", "retrieve_docs")
        workflow.add_edge("retrieve_docs", "generate_response")
        workflow.add_edge("generate_response", "evaluate_response")
        
        # Conditional edges
        workflow.add_conditional_edges(
            "evaluate_response",
            self._should_refine,
            {
                "refine": "refine_query",
                "accept": "format_output",
            }
        )
        workflow.add_edge("refine_query", "retrieve_docs")
        workflow.add_edge("format_output", END)
        
        return workflow.compile()

    def _extract_reference_indicators(self, query: str) -> List[str]:
        """
        Dynamically extract reference indicators from the query.
        
        Instead of hard-coding patterns, this method detects common reference types:
        - Ordinal references: "first", "second", "third", "#2", "3rd", etc.
        - Pronouns: "this", "that", "these", "those"
        - Positional: "previous", "last", "next", "above", "below"
        - Quantifiers: "another", "one more", "additional"
        
        Args:
            query: The user query to analyze
            
        Returns:
            List of detected reference indicators found in the query
        """
        import re
        
        # Define reference indicator patterns dynamically
        reference_patterns = {
            'ordinal_numbers': r'\b(first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth)\b',
            'numbered_format': r'(#\d+|\d+(?:st|nd|rd|th))\b',
            'pronouns': r'\b(this|that|these|those|it)\b',
            'positional': r'\b(previous|last|next|above|below|earlier|mentioned)\b',
            'quantifiers': r'\b(another|one more|additional|more about|tell me about)\b',
        }
        
        detected_indicators = []
        query_lower = query.lower()
        
        for indicator_type, pattern in reference_patterns.items():
            matches = re.findall(pattern, query_lower)
            if matches:
                # Flatten tuples from regex groups
                flat_matches = [m if isinstance(m, str) else m[0] for m in matches]
                detected_indicators.extend(flat_matches)
                logger.debug(f"  Reference type '{indicator_type}': {flat_matches}")
        
        # Deduplicate while preserving order
        seen = set()
        unique_indicators = []
        for indicator in detected_indicators:
            if indicator.lower() not in seen:
                seen.add(indicator.lower())
                unique_indicators.append(indicator)
        
        return unique_indicators

    def _analyze_query(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Analyze query to extract intent and requirements."""
        logger.debug(f"Analyzing query: {state['query']}")
        
        analysis_prompt = """Analyze this query and provide:
        1. Intent (search, command, explanation, debug)
        2. Key topics
        3. Preferred result type (code, explanation, steps)
        4. Required depth (brief, detailed, comprehensive)

        Query: {query}

        Respond in JSON format."""
        
        try:
            response_text = self._call_llm(
                prompt=analysis_prompt.format(query=state['query']),
                system="You are a query analyzer. Respond only in valid JSON.",
                temperature=0.2,
            )
            
            # Parse JSON response
            parser = JsonOutputParser()
            query_analysis = parser.parse(response_text)
            logger.debug(f"Query analysis: {query_analysis}")
            
            return {"query_analysis": query_analysis, "attempts": 0}
        except Exception as e:
            logger.error(f"Error analyzing query: {e}")
            return {"query_analysis": {"intent": "search", "topics": []}, "attempts": 0}

    def _rerank_documents(self, query: str, documents: List[Dict[str, Any]], top_k: int = 30) -> List[Dict[str, Any]]:
        """
        Re-rank documents using cross-encoder for better relevance.
        
        Args:
            query: The original query
            documents: List of retrieved documents with 'text' and 'metadata'
            top_k: Number of top documents to return (default: 30 for comprehensive coverage)
            
        Returns:
            Re-ranked documents
        """
        if not self.reranker or not documents:
            logger.debug(f"Skipping re-ranking (reranker={self.reranker}, docs={len(documents)})")
            return documents[:top_k]
        
        try:
            # Prepare pairs for cross-encoder
            pairs = [[query, doc['text']] for doc in documents]
            
            # Get re-ranking scores
            scores = self.reranker.predict(pairs)
            
            # Log all scores before sorting
            logger.debug(f"Re-ranking {len(documents)} documents:")
            for doc, score in zip(documents, scores):
                section_path = doc['metadata'].get('section_path', [])
                logger.debug(f"  - {section_path}: {score:.3f}")
            
            # Sort by score (descending)
            ranked_docs = sorted(
                zip(documents, scores),
                key=lambda x: x[1],
                reverse=True
            )
            
            # Return top-k documents with new ranking scores
            result = []
            for doc, score in ranked_docs[:top_k]:
                result.append({**doc, "rerank_score": float(score)})
            
            logger.info(f"Re-ranked {len(documents)} documents -> top {top_k} (scores: {[f'{s:.2f}' for _, s in ranked_docs[:3]]})")
            return result
            
        except Exception as e:
            logger.warning(f"Error during re-ranking: {e}. Returning original order.")
            return documents[:top_k]

    def _retrieve_documents(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Retrieve relevant documents using adaptive strategies."""
        logger.debug(f"Retrieving documents for query: {state['query']}")
        
        query_with_context = state['query']
        analysis = state.get('query_analysis', {})
        full_context = state.get('conversation_context', '')  # Get the full enriched context
        
        # Strip context from query for retrieval
        # The query comes as "user question\n\nContext: ..." and we need just the question part
        if '\n\nContext:' in query_with_context:
            query = query_with_context.split('\n\nContext:')[0].strip()
        else:
            query = query_with_context.strip()
        
        # For follow-up questions, enhance the retrieval query with context
        # This helps resolve pronouns like "this", "that", "the third point", etc.
        if full_context and query != state['query']:
            # If we have a follow-up question with context, enhance the retrieval query
            logger.info(f"Enhancing retrieval with conversation context for follow-up question")
            
            # Dynamically extract reference terms from the query (e.g., "3rd", "third", "#2", "first")
            # instead of hard-coding patterns
            reference_indicators = self._extract_reference_indicators(query)
            
            if reference_indicators:
                logger.info(f"Detected reference indicators in follow-up question: {reference_indicators}")
                # Extract the actual numbered items from the previous context to include in retrieval
                # This gives semantic search better hints about what we're looking for
                query = f"{query}\n\nReferencing previous list items from: {full_context}"
            else:
                query = f"{query}\n\nBased on previous discussion about: {full_context}"
        
        # Use hybrid search analysis to determine if query is comprehensive
        # This is more reliable than LLM-based analysis when Ollama is not available
        hybrid_analysis = self.hybrid_search.analyze_query(query)
        is_comprehensive = hybrid_analysis.get('is_comprehensive', False)
        
        # Adaptive retrieval: adjust k based on query type
        # For comprehensive queries, retrieve more documents to ensure coverage from multiple sources
        # Increased to 50 to ensure we capture all relevant instances from all available sources
        # This is critical for queries like "list all api endpoints" that should return results from ALL API docs
        k = 50 if is_comprehensive else 20
        
        try:
            # Use direct semantic search to bypass strict distance filtering
            
            col = self.rag_engine.client.get_collection(name=self.rag_engine.chunks_collection)
            model = SentenceTransformer(self.rag_engine.embed_model)
            
            # Use hybrid search strategy to decompose and expand queries
            queries_to_search = self.hybrid_search.get_search_queries(query)
            
            # If we have conversation context, add context-aware searches
            # Handle both old format '[CONVERSATION CONTEXT]' and new compacted formats '[PREVIOUS CONTEXT SUMMARY]', '[RECENT CONVERSATION]'
            if full_context and ('[CONVERSATION CONTEXT]' in full_context or '[PREVIOUS CONTEXT SUMMARY]' in full_context):
                # Extract conversation context to find key topics
                context_part = ""
                
                # Try old format first: split by '[CURRENT QUERY]'
                if '[CURRENT QUERY]' in full_context:
                    parts = full_context.split('[CURRENT QUERY]')
                    if len(parts) == 2:
                        context_part = parts[0]
                # Try new format: split by '[RECENT CONVERSATION]'
                elif '[RECENT CONVERSATION]' in full_context:
                    parts = full_context.split('[RECENT CONVERSATION]')
                    if len(parts) >= 1:
                        context_part = parts[0]
                
                if context_part:
                    # Try to extract key terms from context (look for previous topics)
                    # For example, if context mentions "linux", add that to searches
                    context_lower = context_part.lower()
            
            # Perform searches and aggregate results with source diversity
            # For comprehensive queries, maintain results from multiple sources
            all_hits = {}
            search_order = {}  # Track which search query found each document
            source_diversity = {}  # Track which sources found each document
            
            for search_idx, search_query in enumerate(queries_to_search):
                logger.info(f"Searching with query: {search_query}")
                qemb = model.encode([search_query], normalize_embeddings=True).tolist()
                
                res = col.query(
                    query_embeddings=qemb,
                    n_results=k,
                    where=None,
                    include=["documents", "metadatas", "distances"],
                )
                
                docs_list = res["documents"][0] if res.get("documents") else []
                metas_list = res["metadatas"][0] if res.get("metadatas") else []
                dists = res["distances"][0] if res.get("distances") else []
                
                logger.info(f"  Found {len(docs_list)} results for '{search_query}'")
                
                # Convert to hit format with decoded metadata
                for doc_idx, (doc_text, md, dist) in enumerate(zip(docs_list, metas_list, dists)):
                    # Decode metadata (same as RAGQueryEngine)
                    commands = json.loads(md.get("commands_json", "[]"))
                    section_path = json.loads(md.get("section_path_json", "[]"))
                    
                    # Use doc_id as source (contains filename like "docs/analytics_api.json")
                    source = md.get("doc_id", "unknown")
                    # For comprehensive queries: use source as primary key, section_path as secondary
                    # This ensures we get results from ALL sources, not deduplicated away
                    hit_id = source + "_" + str(section_path)
                    
                    # Combined score for ranking: distance (lower is better) + slight penalty for later searches
                    combined_score = dist + (search_idx * 0.01)  # Slightly prefer earlier/more specific searches
                    
                    if hit_id not in all_hits:
                        all_hits[hit_id] = {
                            "text": doc_text,
                            "metadata": {**md, "commands": commands, "section_path": section_path},
                            "distance": dist,
                            "combined_score": combined_score,
                            "source": source,
                        }
                        search_order[hit_id] = search_idx
                        source_diversity[hit_id] = {source}
                    else:
                        # For comprehensive queries, track if document found in multiple searches
                        # But keep the best score
                        if combined_score < all_hits[hit_id]["combined_score"]:
                            all_hits[hit_id].update({
                                "distance": dist,
                                "combined_score": combined_score,
                            })
                        # Track source diversity
                        if source not in source_diversity.get(hit_id, set()):
                            source_diversity[hit_id].add(source)
            
            logger.info(f"Total aggregated documents before sorting: {len(all_hits)}")
            
            # Sort by combined score and return top k
            # For comprehensive queries, prefer documents with diversity (found in multiple searches)
            sorted_hits = sorted(all_hits.values(), key=lambda x: x['combined_score'])
            logger.info(f"Top {min(k, len(sorted_hits))} of {len(sorted_hits)} after sorting by combined_score (k={k})")
            
            # Log first and last few combined scores
            if sorted_hits:
                lowest_scores = [f"{h['combined_score']:.4f}" for h in sorted_hits[:3]]
                logger.info(f"  Lowest scores (best): {lowest_scores}")
                highest_scores = [f"{h['combined_score']:.4f}" for h in sorted_hits[-3:]]
                logger.info(f"  Highest scores (worst): {highest_scores}")
                if k < len(sorted_hits):
                    cutoff_doc = sorted_hits[k-1]
                    next_doc = sorted_hits[k]
                    logger.info(f"  Cutoff at k={k}: score {cutoff_doc['combined_score']:.4f} vs next {next_doc['combined_score']:.4f}")
            
            hits = sorted_hits[:k]
            
            logger.info(f"Retrieved {len(hits)} unique documents (k={k}, total candidates={len(all_hits)})")
            if hits:
                logger.info(f"  Distance range: [{hits[0]['distance']:.4f}, {hits[-1]['distance']:.4f}]")
            
            # Log all GET endpoints found (for debugging)
            get_endpoints = [h for h in hits if 'get' in h['text'].lower() or 'GET' in h['metadata'].get('commands_json', '')]
            logger.info(f"  GET endpoints in retrieval (before reranking): {len(get_endpoints)}")
            for ep in get_endpoints:
                section_path = ep['metadata'].get('section_path', [])
                logger.info(f"    - {section_path} (distance: {ep['distance']:.3f})")
            
            # Apply re-ranking to improve relevance
            if self.reranker and len(hits) > 0:
                hits_before_rerank = len(hits)
                # For comprehensive queries, keep more results after reranking
                rerank_top_k = k if is_comprehensive else min(8, k)
                hits = self._rerank_documents(query, hits, top_k=rerank_top_k)
                logger.info(f"After re-ranking: {len(hits)} documents (before: {hits_before_rerank}, rerank_top_k: {rerank_top_k})")
                
                # Log GET endpoints after re-ranking
                get_endpoints_after = [h for h in hits if 'get' in h['text'].lower() or 'GET' in h['metadata'].get('commands_json', '')]
                logger.info(f"  GET endpoints after re-ranking: {len(get_endpoints_after)}")
                for ep in get_endpoints_after:
                    section_path = ep['metadata'].get('section_path', [])
                    score = ep.get('rerank_score', 'N/A')
                    logger.info(f"    - {section_path} (rerank_score: {score})")
                
                # Log GET endpoints after re-ranking
                get_endpoints_after = [h for h in hits if 'get' in h['text'].lower() or 'GET' in h['metadata'].get('commands_json', '')]
                logger.debug(f"  GET endpoints after re-ranking: {len(get_endpoints_after)}")
                for ep in get_endpoints_after:
                    rerank_score = ep.get('rerank_score', 'N/A')
                    logger.debug(f"    - {ep['metadata'].get('section_path_json', 'unknown')} (rerank_score: {rerank_score})")
            
            return {"retrieved_docs": hits}
            
        except Exception as e:
            logger.error(f"Error retrieving documents: {e}")
            import traceback
            traceback.print_exc()
            return {"retrieved_docs": []}

    def _generate_response(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Generate response using retrieved context."""
        logger.debug("Generating response")
        
        docs = state.get('retrieved_docs', [])
        full_query = state.get('conversation_context', state['query'])  # Use enriched context if available
        original_query = state['query'].split('\n\nContext:')[0] if '\n\nContext:' in state['query'] else state['query']
        
        if not docs:
            llm_response = "I could not find relevant information to answer your question. Please rephrase your query."
            logger.warning(f"No documents retrieved for query: {original_query}")
            return {"llm_response": llm_response}
        
        # Build context using the RAGQueryEngine's context builder
        context = self.rag_engine.build_context(docs)
        
        system_prompt = """You are a helpful and friendly technical assistant answering questions about runbooks and operational procedures.

        CRITICAL INSTRUCTIONS FOR FOLLOW-UP QUESTIONS:
        When the user asks about "the #3 point", "third point", "the third item", etc.:
        1. FIRST: Look at the CONVERSATION HISTORY section to find the numbered list from the previous response
        2. THEN: Find the specific item they're referring to (e.g., 3rd item in the list)
        3. FINALLY: Use the documentation provided to explain details about that specific item
        
        IMPORTANT INSTRUCTIONS:
        1. Answer ONLY using the provided documentation context below
        2. When you see conversation history, use it to understand pronouns and vague references
        3. DO NOT say "the provided documentation does not contain" if relevant docs are provided
        4. Be direct and helpful - cite sources when relevant
        5. For follow-up questions like "explain about X point" or "explain about this", refer back to previous answers to understand the context
        6. End every response with a friendly closing that invites further questions

        When answering follow-up questions:
        - "#3 point" or "third point" refers to the 3rd item in a numbered list from the previous response
        - "this" or "that" refers to the topic from the previous question
        - "the Nth point" refers to the Nth item in the previous list
        - Always first identify what item from the previous response is being referenced
        - Use conversation context to disambiguate vague questions
        - Answer what is being asked in the context of the conversation
        
        RESPONSE FORMAT:
        - Start with a brief, friendly greeting if this is the beginning of conversation
        - Provide a clear, comprehensive answer to the question
        - End with: "Is there anything else you'd like to know?" or similar helpful closing"""
                
        user_prompt = f"""DOCUMENTATION:
        {context['context_text']}

        CONVERSATION HISTORY AND CURRENT QUESTION:
        {full_query}

        INSTRUCTIONS:
        - For follow-up questions about a numbered list (e.g., "Explain about #3 point"):
          1. Look at the CONVERSATION HISTORY section above to find the previous numbered list
          2. Identify the specific item being referenced
          3. Use the documentation to provide details about that item
        - Answer the question directly using the documentation provided
        - If this is a follow-up question, use the conversation context to understand what topic or item is being referenced, then answer about it from the documentation
        - Always end your response by asking if there's anything else the user needs help with
        - Be conversational and friendly in tone"""
        
        try:
            llm_response = self._call_llm(
                prompt=user_prompt,
                system=system_prompt,
                temperature=self.temperature,
            )
            logger.debug(f"Generated response length: {len(llm_response)}")
            logger.info(f"LLM response: {llm_response[:100]}...")
            
            return {
                "llm_response": llm_response,
                "sources": context.get('sources', [])
            }
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            import traceback
            traceback.print_exc()
            return {"llm_response": f"Error generating response: {str(e)}", "sources": []}

    def _evaluate_response(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Evaluate if response is sufficient or needs refinement."""
        logger.debug("Evaluating response quality")
        
        response = state.get('llm_response', '')
        query = state['query']
        docs = state.get('retrieved_docs', [])
        attempts = state.get('attempts', 0)
        max_attempts = state.get('max_attempts', 3)
        
        # Check for negative indicators (low quality response)
        negative_phrases = [
            "could not find",
            "not found",
            "don't have",
            "not available",
            "no information",
            "unable to",
            "i'm sorry",
            "i apologize",
        ]
        
        is_negative = any(phrase in response.lower() for phrase in negative_phrases)
        has_docs = len(docs) > 0
        
        # Get the clean query (strip context)
        if '\n\nContext:' in query:
            clean_query = query.split('\n\nContext:')[0].strip()
        else:
            clean_query = query.strip()
        
        # Use hybrid search analysis to determine if query is comprehensive
        # This is more reliable than LLM-based analysis
        hybrid_analysis = self.hybrid_search.analyze_query(clean_query)
        is_comprehensive = hybrid_analysis.get('is_comprehensive', False)
        
        if is_comprehensive:
            # For comprehensive queries, be stricter - keep trying if response is negative and we have attempts left
            is_relevant = (not is_negative and has_docs) or attempts >= max_attempts
        else:
            # For specific queries, accept if response is not negative or max attempts reached
            is_relevant = (not is_negative) or attempts >= max_attempts
        
        logger.info(f"Response evaluation - Negative: {is_negative}, Has docs: {has_docs}, Comprehensive: {is_comprehensive}, Relevant: {is_relevant}, Attempts: {attempts}/{max_attempts}")
        
        return {"is_relevant": is_relevant, "attempts": attempts + 1}

    def _refine_query(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Refine query based on previous attempt."""
        logger.debug("Refining query for retry")
        
        original_query = state['query']
        
        refinement_prompt = f"""The previous answer to this query wasn't satisfactory:
        "{original_query}"

        Suggest an improved query that might get better results. Respond with just the refined query."""
        
        try:
            refined_query = self._call_llm(
                prompt=refinement_prompt,
                system="You are a search query optimizer.",
                temperature=0.3,
            )
            
            refined_query = refined_query.strip()
            logger.debug(f"Refined query: {refined_query}")
            
            return {"query": refined_query}
        except Exception as e:
            logger.error(f"Error refining query: {e}")
            # If refinement fails, use original query with different strategy
            return {"query": original_query}

    def _format_output(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Format final output."""
        logger.debug("Formatting output")
        
        return {
            "final_response": state.get('llm_response', ''),
            "sources": state.get('sources', [])
        }

    def _should_refine(self, state: AdaptiveRAGState) -> str:
        """Determine if query should be refined or response accepted."""
        is_relevant = state.get('is_relevant', True)
        attempts = state.get('attempts', 0)
        max_attempts = state.get('max_attempts', 3)
        
        if is_relevant or attempts >= max_attempts:
            return "accept"
        return "refine"

    async def query(self, query: str) -> Dict[str, Any]:
        """Execute adaptive RAG query."""
        logger.info(f"Starting adaptive RAG query: {query}")
        
        initial_state: AdaptiveRAGState = {
            "query": query,
            "messages": [],
            "retrieved_docs": [],
            "query_analysis": {},
            "llm_response": "",
            "is_relevant": False,
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "final_response": "",
            "sources": [],
        }
        
        try:
            final_state = await self.graph.ainvoke(initial_state)
            
            # Ensure we have a response - fall back to llm_response if final_response wasn't set
            final_response = final_state.get('final_response', '') or final_state.get('llm_response', '')
            
            return {
                "response": final_response,
                "sources": final_state.get('sources', []),
                "attempts": final_state.get('attempts', 1),
                "query_analysis": final_state.get('query_analysis', {}),
            }
        except Exception as e:
            logger.error(f"Error in adaptive RAG query: {e}")
            return {
                "response": f"Error processing query: {str(e)}",
                "sources": [],
                "attempts": 1,
                "error": str(e),
            }

    def query_sync(self, query: str, conversation_context: str = "") -> Dict[str, Any]:
        """
        Synchronous version of query for non-async contexts.
        
        Args:
            query: The user query
            conversation_context: Optional conversation history for context
            
        Returns:
            Dictionary with response, sources, and metadata
        """
        logger.info(f"Starting adaptive RAG query (sync): {query}")
        
        # Store conversation context separately for use in response generation
        # For retrieval, we'll use the original query to get better semantic matches
        retrieval_query = query
        enriched_query = query
        
        if conversation_context:
            enriched_query = f"[CONVERSATION CONTEXT]\n{conversation_context}\n\n[CURRENT QUERY]\n{query}"
            logger.info(f"Using conversation context ({len(conversation_context)} chars) for response generation")
            # For retrieval, combine context with current query to improve semantic search
            # But use mostly the current query to avoid diluting the semantic signal
            retrieval_query = f"{query}\n\nContext: {conversation_context}"
        
        initial_state: AdaptiveRAGState = {
            "query": retrieval_query,
            "messages": [],
            "retrieved_docs": [],
            "query_analysis": {},
            "llm_response": "",
            "is_relevant": False,
            "attempts": 0,
            "max_attempts": self.max_attempts,
            "final_response": "",
            "sources": [],
            "conversation_context": enriched_query,  # Store full enriched context for response generation
        }
        
        try:
            final_state = self.graph.invoke(initial_state)
            
            # Ensure we have a response - fall back to llm_response if final_response wasn't set
            final_response = final_state.get('final_response', '') or final_state.get('llm_response', '')
            
            return {
                "response": final_response,
                "sources": final_state.get('sources', []),
                "attempts": final_state.get('attempts', 1),
                "query_analysis": final_state.get('query_analysis', {}),
            }
        except Exception as e:
            logger.error(f"Error in adaptive RAG query: {e}")
            return {
                "response": f"Error processing query: {str(e)}",
                "sources": [],
                "attempts": 1,
                "error": str(e),
            }


# Global instance
_adaptive_rag = None


def get_adaptive_rag() -> AdaptiveRAG:
    """Get or create global adaptive RAG instance."""
    global _adaptive_rag
    if _adaptive_rag is None:
        _adaptive_rag = AdaptiveRAG(
            db_dir=settings.chroma_db_dir,
            chunks_collection=settings.chroma_chunks_collection,
            embed_model=settings.chroma_embed_model,
            ollama_model=settings.ollama_model,
            temperature=0.2,
        )
    return _adaptive_rag
