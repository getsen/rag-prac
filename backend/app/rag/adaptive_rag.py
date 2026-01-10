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
from sentence_transformers import SentenceTransformer

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


class AdaptiveRAG:
    """Adaptive RAG system using LangGraph for self-correcting retrieval and generation."""
    
    def __init__(
        self,
        db_dir: str = "chroma_db",
        chunks_collection: str = "runbook_chunks",
        embed_model: str = "BAAI/bge-small-en-v1.5",
        ollama_model: str = "llama2",
        temperature: float = 0.2,
        max_retrieval_attempts: int = 3,
    ):
        """Initialize adaptive RAG system."""
        self.rag_engine = RAGQueryEngine(db_dir, chunks_collection, embed_model)
        self.ollama_model = ollama_model
        self.temperature = temperature
        self.max_attempts = max_retrieval_attempts
        
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

    def _retrieve_documents(self, state: AdaptiveRAGState) -> Dict[str, Any]:
        """Retrieve relevant documents using adaptive strategies."""
        logger.debug(f"Retrieving documents for query: {state['query']}")
        
        query = state['query']
        analysis = state.get('query_analysis', {})
        
        # Adaptive retrieval: adjust k based on intent
        intent = analysis.get('intent', 'search')
        k = 12 if intent == 'comprehensive' else 8
        
        try:
            # Use direct semantic search to bypass strict distance filtering
            
            col = self.rag_engine.client.get_collection(name=self.rag_engine.chunks_collection)
            model = SentenceTransformer(self.rag_engine.embed_model)
            qemb = model.encode([query], normalize_embeddings=True).tolist()
            
            res = col.query(
                query_embeddings=qemb,
                n_results=k,
                where=None,
                include=["documents", "metadatas", "distances"],
            )
            
            docs_list = res["documents"][0] if res.get("documents") else []
            metas_list = res["metadatas"][0] if res.get("metadatas") else []
            dists = res["distances"][0] if res.get("distances") else []
            
            # Convert to hit format with decoded metadata
            hits = []
            for doc_text, md, dist in zip(docs_list, metas_list, dists):
                # Decode metadata (same as RAGQueryEngine)
                commands = json.loads(md.get("commands_json", "[]"))
                section_path = json.loads(md.get("section_path_json", "[]"))
                
                hits.append({
                    "text": doc_text,
                    "metadata": {**md, "commands": commands, "section_path": section_path},
                    "distance": dist,
                })
            
            logger.info(f"Retrieved {len(hits)} documents (distances: {[h['distance'] for h in hits[:3]]})")
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
        query = state['query']
        
        if not docs:
            llm_response = "I could not find relevant information to answer your question. Please rephrase your query."
            logger.warning(f"No documents retrieved for query: {query}")
            return {"llm_response": llm_response}
        
        # Build context using the RAGQueryEngine's context builder
        context = self.rag_engine.build_context(docs)
        
        system_prompt = """You are a helpful technical assistant. Answer questions based ONLY on the provided context.
        If the context doesn't contain information to answer the question, say so explicitly.
        Be concise but comprehensive."""
                
        user_prompt = f"""Context:
        {context['context_text']}

        Question: {query}

        Provide a clear, direct answer using only the context provided."""
        
        try:
            llm_response = self._call_llm(
                prompt=user_prompt,
                system=system_prompt,
                temperature=self.temperature,
            )
            logger.debug(f"Generated response length: {len(llm_response)}")
            
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
        
        # Check for negative indicators
        negative_phrases = [
            "could not find",
            "not found",
            "don't have",
            "not available",
            "no information",
        ]
        
        is_negative = any(phrase in response.lower() for phrase in negative_phrases)
        doc_coverage = len(docs) > 0
        
        # Evaluate: accept if positive response or no docs, or if we've tried max times
        is_relevant = (not is_negative or not doc_coverage) or attempts >= state.get('max_attempts', 3)
        
        logger.debug(f"Response evaluation - Negative: {is_negative}, Has docs: {doc_coverage}, Relevant: {is_relevant}")
        
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
            
            return {
                "response": final_state.get('final_response', ''),
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

    def query_sync(self, query: str) -> Dict[str, Any]:
        """Synchronous version of query for non-async contexts."""
        logger.info(f"Starting adaptive RAG query (sync): {query}")
        
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
            final_state = self.graph.invoke(initial_state)
            
            return {
                "response": final_state.get('final_response', ''),
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
