import json
import faiss
from typing import List, Dict, Any

from src.schema import DB_SCHEMA, SCHEMA_MAPPER

# ============================================================================
# AGENT TOOLS
# ============================================================================

class SQLGeneratorTool:
    """Generates safe SQL queries from natural language"""
    
    def __init__(self, llm_model):
        self.model = llm_model
        self.name = "sql_generator"
    
    def run(self, query: str) -> str:
        """Generate SQL from natural language query"""
        prompt = f"""You are a SQL expert. Convert the user's natural language query into a safe PostgreSQL SELECT query.
Think from pov of a salesperson, not a database expert.
        
Database Schema:
{DB_SCHEMA}

Rules:
1. Only generate SELECT queries (no INSERT, UPDATE, DELETE)
2. Use proper WHERE clauses for filters
3. Handle price ranges, categories and other filters appropriately
4. Use ILIKE for case-insensitive text matching
5. Return only the SQL query, no explanations
6. Always select all fields using "SELECT * "
7. Always quote the column name in with double quotes (e.g., "column_name")

User Query: {query}

SQL Query:"""
        
        response = self.model.generate_content(prompt)
        sql = response.text.strip()
        # Clean up markdown code blocks if present
        sql = sql.replace('```sql', '').replace('```', '').strip().rstrip(";")
        return sql


class SQLExecutorTool:
    """Executes SQL queries against Supabase"""
    
    def __init__(self, supabase_client):
        self.supabase = supabase_client
        self.name = "sql_executor"
    
    def run(self, sql: str) -> List[Dict[str, Any]]:
        """Execute SQL query safely"""
        # Use Supabase RPC or direct query
        response = self.supabase.rpc("run_sql", {"query": sql}).execute()
        
        # Return max 4 results. Do not raise error if no results
        return response.data[:4]



class VectorQueryTool:
    """Converts natural language to semantic search description"""
    
    def __init__(self, llm_model):
        self.model = llm_model
        self.name = "vector_query"
    
    def run(self, query: str) -> str:
        """Generate semantic search text"""
        prompt = f"""Convert the user's query into a concise semantic description for similarity search.
Focus on product characteristics, features, and user intent.
Remove specific filters like price, brand, category - focus only on semantic meaning.
Remember, the goal is to find products that are similar to the user's query from product descriptions and features.

Keep the semantic description short and to the point.

User Query: {query}

Semantic Description:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Vector query error: {e}")
            return query  # Fallback to original query


class VectorSearchTool:
    """Performs FAISS vector similarity search"""
    
    def __init__(self, faiss_index, product_id_map, embedding_model):
        self.index = faiss_index
        self.id_map = product_id_map
        self.embedding_model = embedding_model
        self.name = "vector_search"
    
    def run(self, semantic_text: str, k: int = 5) -> List[int]:  # TODO: dynamic k
        """Search for similar products using FAISS"""
        if self.index.ntotal == 0:
            return []
        
        try:
            # Generate embedding
            emb = self.embedding_model.encode(semantic_text).astype('float32')
            emb = emb.reshape(1, -1)
            faiss.normalize_L2(emb)
            
            # Search
            k = min(k, self.index.ntotal)
            distances, indices = self.index.search(emb, k)
            
            # Map indices to product IDs
            product_ids = [self.id_map[idx] for idx in indices[0] if idx < len(self.id_map)]
            return product_ids
        except Exception as e:
            print(f"Vector search error: {e}")
            return []


class IntentClassifierTool:
    """Classifies user intent to determine which search methods to use"""
    
    def __init__(self, llm_model):
        self.model = llm_model
        self.name = "intent_classifier"
    
    def run(self, query: str) -> Dict[str, bool]:
        """Classify user intent"""
        prompt = f"""
Analyze the user query and determine **how** to apply the available search methods.
Instead, identify which methods should be activated and how they contribute.
Prioritize semantic understanding over structured filters.
Also state whether the search methods should be applied as an intersection (AND) or union (OR).

User Query: {query}

Return a JSON object with these boolean flags:
{{
  "sql": true/false,            // For explicit structured filters such as price, brand, category, numeric comparison, sorting, etc.
  "vector": true/false,         // For semantic understanding: inferring category, extracting product features, fuzzy matching, user-described attributes, etc.
  "reasoning": "brief explanation of why each method is or isn’t needed"
  "is_intersection": true/false // Should the search methods be applied as an intersection (AND) or union (OR)
}}

JSON Response:
"""
        
        response = self.model.generate_content(prompt)
        text = response.text.strip()
        # Extract JSON
        json_start = text.find('{')
        json_end = text.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            result = json.loads(text[json_start:json_end])
            return result
        else:
            # Default: use both
            return {"needs_sql": True, "needs_vector": True, "reasoning": "Default"}


class ResponseFormatterTool:
    """Formats final results into user-friendly response"""
    
    def __init__(self, llm_model):
        self.model = llm_model
        self.name = "response_formatter"
    
    def run(self, products: List[Dict], query: str) -> str:
        """Format products into natural language response"""
        if not products:
            return "I couldn't find any products matching your query. Please try with different criteria."
        
        # Limit to top 5 for formatting
        top_products = products[:5]
        fields = [
            'title',
            'price',
            'description'
        ]
        
        # Generate text
        products_text = "\n".join([f"Product {i+1}: {', '.join([f'{key}: {value}' for key, value in p.items() if key in fields])}" for i, p in enumerate(top_products)])
        
        prompt = f"""Format these product recommendations for the user in a friendly, conversational way.

Keep the response short and to the point.
You are provided with a list of products and features.
Point out key features of each product which the user might be interested in.

User Query: {query}

Products Found:
{products_text}

------------------------------------------
You may provided with irrelvant products.
If so, please ignore them.
------------------------------------------

Instructions:
1. Start with a brief acknowledgment of their request
2. Highlight the top 3-5 recommendations
3. For each product, mention: title, price, and 2-3 key features
4. Use a warm, helpful tone
5. End with a helpful note


Response:"""
        
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            print(f"Response formatting error: {e}")
            # Fallback formatting
            result = f"I found {len(products)} products for your query:\n\n"
            for i, p in enumerate(top_products, 1):
                result += f"{i}. {p[SCHEMA_MAPPER['title']]} - ₹{p[SCHEMA_MAPPER['price']]}\n"
            return result
