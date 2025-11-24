import os
import json
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer
from src.config import config
from src.schema import SCHEMA_MAPPER
from src.tools import IntentClassifierTool, ResponseFormatterTool, SQLExecutorTool, SQLGeneratorTool, VectorQueryTool, VectorSearchTool
from supabase import create_client, Client
import google.generativeai as genai
from typing import List, Dict


class AgentComponents:
    """Initialize all agent components"""
    
    def __init__(self):
        # Initialize Supabase
        self.supabase: Client = create_client(
            config.SUPABASE_URL, 
            config.SUPABASE_KEY
        )
        
        # Initialize Gemini
        genai.configure(api_key=config.GEMINI_API_KEY)
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Initialize embedding model
        self.embedding_model = SentenceTransformer(config.EMBEDDING_MODEL)
        
        # Load or create FAISS index
        self.faiss_index, self.product_id_map = self._load_or_create_index()
    
    def _load_or_create_index(self):
        """Load existing FAISS index or create new one"""
        if os.path.exists(config.FAISS_INDEX_PATH) and \
           os.path.exists(config.PRODUCT_ID_MAP_PATH):
            print("Loading existing FAISS index...")
            index = faiss.read_index(config.FAISS_INDEX_PATH)
            with open(config.PRODUCT_ID_MAP_PATH, 'r') as f:
                id_map = json.load(f)
            return index, id_map
        else:
            print("Creating new FAISS index...")
            return self._create_new_index()
    
    def _create_new_index(self):
        """Create new FAISS index from database"""
        # Fetch all products
        response = self.supabase.table(SCHEMA_MAPPER['table']).select('*').execute()
        products = response.data
        
        if not products:
            # Create empty index
            index = faiss.IndexFlatIP(config.EMBEDDING_DIM)
            return index, []
        
        # Generate embeddings
        embeddings = []
        id_map = []
        
        for product in products:  # TODO: Take from schema
            text = f"{product[SCHEMA_MAPPER['title']]} {product[SCHEMA_MAPPER['description']]} {product.get(SCHEMA_MAPPER['features'], '')} {product.get(SCHEMA_MAPPER['category'], '')}"
            emb = self.embedding_model.encode(text)
            embeddings.append(emb)
            id_map.append(product[SCHEMA_MAPPER['id']])

        # Create FAISS index
        embeddings_array = np.array(embeddings, dtype='float32')
        faiss.normalize_L2(embeddings_array)  # Normalize for cosine similarity
        
        index = faiss.IndexFlatIP(config.EMBEDDING_DIM)
        index.add(embeddings_array)
        
        # Save index and mapping
        faiss.write_index(index, config.FAISS_INDEX_PATH)
        with open(config.PRODUCT_ID_MAP_PATH, 'w') as f:
            json.dump(id_map, f)
        
        print(f"Created FAISS index with {len(id_map)} products")
        return index, id_map


# ============================================================================
# MAIN AGENT
# ============================================================================

class HybridSearchAgent:
    """Main agent orchestrating hybrid search"""
    
    def __init__(self, components: AgentComponents):
        self.components = components
        
        # Initialize tools
        self.intent_classifier = IntentClassifierTool(components.model)
        self.sql_generator = SQLGeneratorTool(components.model)
        self.sql_executor = SQLExecutorTool(components.supabase)
        self.vector_query = VectorQueryTool(components.model)
        self.vector_search = VectorSearchTool(
            components.faiss_index,
            components.product_id_map,
            components.embedding_model
        )
        self.response_formatter = ResponseFormatterTool(components.model)
    
    def run(self, user_query: str) -> str:
        """Execute hybrid search pipeline"""
        print(f"\n{'='*60}")
        print(f"Processing query: {user_query}")
        print(f"{'='*60}\n")
        
        # Step 1: Classify intent
        print("Step 1: Classifying intent...")
        intent = self.intent_classifier.run(user_query)
        print(f"Intent: {intent}")
        
        sql_results = []
        vector_results = []
        
        print("\nStep 2: SQL Search...")
        sql_query = self.sql_generator.run(user_query)
        print(f"Generated SQL: {sql_query}")
        sql_results = self.sql_executor.run(sql_query)
        print(f"SQL results: {len(sql_results)} products")

        # Step 3: Vector Search (if needed)
        print("\nStep 3: Vector Search...")
        semantic_query = self.vector_query.run(user_query)
        print(f"Semantic query: {semantic_query}")
        vector_ids = self.vector_search.run(semantic_query)
        print(f"Vector results: {len(vector_ids)} product IDs")
        # Fetch full product details
        if vector_ids:
            response = self.components.supabase.table(SCHEMA_MAPPER['table'])\
                .select('*')\
                .in_(SCHEMA_MAPPER['id'], vector_ids)\
                .execute()
            vector_results = response.data
        
        # Step 4: Merge results
        print("\nStep 4: Merging results...")
        final_products = self._merge_results(sql_results, vector_results, intent)
        print(f"Final products: {len(final_products)}")

        # Step 5: Format response
        print("\nStep 5: Formatting response...")
        response = self.response_formatter.run(final_products, user_query)
        
        return response
    
    def _merge_results(self, sql_results: List[Dict], vector_results: List[Dict], 
                       intent: Dict) -> List[Dict]:
        """Merge SQL and vector search results"""
        
        if not sql_results and not vector_results:
            return []
                
        # Both searches performed - intersect
        sql_ids = {p[SCHEMA_MAPPER['id']] for p in sql_results}
        vector_ids = {p[SCHEMA_MAPPER['id']] for p in vector_results}
        
        # # Intersection
        if intent['is_intersection'] == 'true':
            merged_ids = vector_ids.intersection(sql_ids)
        else:
            merged_ids = vector_ids.union(sql_ids)
        
        # Prioritize vector order (semantic relevance)
        result = [p for p in vector_results if p[SCHEMA_MAPPER['id']] in merged_ids]
        print(f"Merged results: {len(result)} products")
        return result
