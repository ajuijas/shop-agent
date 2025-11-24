import os
from flask import Flask, request, jsonify
from src.config import config
from src.agent import AgentComponents, HybridSearchAgent


# ============================================================================
# API SERVER
# ============================================================================

app = Flask(__name__)
agent_components = None
agent = None

@app.before_request
def initialize():
    """Initialize agent on first request"""
    global agent_components, agent
    agent_components = AgentComponents()
    agent = HybridSearchAgent(agent_components)
    if agent_components is None:
        print("Initializing agent components...")
        print("Agent ready!")

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "hybrid-search-agent"})

@app.route('/query', methods=['POST'])
def query():
    """Main query endpoint"""
    data = request.get_json()
    user_message = data.get('message', '')
    
    if not user_message:
        return jsonify({"error": "No message provided"}), 400
    
    # Run agent
    response = agent.run(user_message)
    
    return jsonify({
        "success": True,
        "query": user_message,
        "response": response
    })
    

@app.route('/rebuild-index', methods=['POST'])
def rebuild_index():
    """Rebuild FAISS index from current database"""
    try:
        global agent_components
        if os.path.exists(config.FAISS_INDEX_PATH):
            os.remove(config.FAISS_INDEX_PATH)
        if os.path.exists(config.PRODUCT_ID_MAP_PATH):
            os.remove(config.PRODUCT_ID_MAP_PATH)
        
        agent_components.faiss_index, agent_components.product_id_map = \
            agent_components._create_new_index()
        
        return jsonify({
            "success": True,
            "message": f"Index rebuilt with {len(agent_components.product_id_map)} products"
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    app.run(host='0.0.0.0', port=port, debug=False)