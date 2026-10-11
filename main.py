from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from neo4j import GraphDatabase
from google import genai
import os
import time
import random

app = FastAPI(title="Xanctum Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

NEO4J_URI = "neo4j+ssc://dc2b9930.databases.neo4j.io"  # Copy exact URI from Aura Console
NEO4J_USER = "dc2b9930"
NEO4J_PASSWORD = "5I7s_LLmfW-pwvm6OlRHVX7Wq-S7fGymMaR0g5Y8Dg4"
GEMINI_API_KEY = "AQ.Ab8RN6Jw_QwozL8SvGViJe1fd7Ule7mLka-fimEdpJynSgooog"

driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
client = genai.Client(api_key=GEMINI_API_KEY)

# 1. Interactive Web Interface at Root (/)
@app.get("/", response_class=HTMLResponse)
def home_ui():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Xanctum Engine</title>
        <style>
            body { font-family: sans-serif; background: #0f172a; color: #f8fafc; padding: 2rem; max-width: 800px; margin: auto; }
            input, textarea, button { width: 100%; padding: 10px; margin: 8px 0; border-radius: 6px; border: 1px solid #334155; background: #1e293b; color: #fff; }
            button { background: #3b82f6; cursor: pointer; font-weight: bold; border: none; margin-top: 15px; }
            #output { background: #1e293b; padding: 15px; border-radius: 8px; white-space: pre-wrap; margin-top: 20px; }
        </style>
    </head>
    <body>
        <h2>🚀 Xanctum Agentic Curation Engine</h2>
        <label>Username (Neo4j):</label>
        <input id="username" value="Hardik"/>
        
        <label>Candidate Topics / Articles (1 per line):</label>
        <textarea id="candidates" rows="4">GraphRAG for Generative AI
Deploying FastAPI backends to Render
Advanced Prompt Engineering techniques</textarea>
        
        <button onclick="runCuration()">Curate Content</button>
        
        <h3>Curated Output Feed:</h3>
        <div id="output">Click 'Curate Content' to assess relevance against graph profile...</div>

        <script>
            async function runCuration() {
                const username = document.getElementById('username').value;
                const lines = document.getElementById('candidates').value.split('\\n').filter(Boolean);
                const candidates = lines.map(t => ({ title: t, snippet: `Article about ${t}` }));
                
                document.getElementById('output').innerText = "⏳ Querying Neo4j & running Gemini assessment...";
                
                try {
                    const res = await fetch('/curate', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ username, candidates })
                    });
                    const data = await res.json();
                    document.getElementById('output').innerText = data.curated_feed || JSON.stringify(data);
                } catch(e) {
                    document.getElementById('output').innerText = "Error: " + e;
                }
            }
        </script>
    </body>
    </html>
    """

# 2. Curation API Endpoint
@app.post("/curate")
def curate_endpoint(payload: dict):
    username = payload.get("username", "Hardik")
    candidates = payload.get("candidates", [])
    
    query = "MATCH (u:User {name: \$name}) RETURN u.name AS name, u.role AS job"
    try:
        with driver.session() as session:
            result = session.run(query, name=username).single()
            user_context = result.data() if result else {"name": username}
    except Exception:
        user_context = {"name": username}

    prompt = f"""
    You are the core intelligence engine for Xanctum. 
    User Profile: {user_context}
    Candidate Articles: {candidates}
    Filter and rank the top relevant items with a short justification based on the user profile.
    """

    max_retries = 6
    base_delay = 2
    response_text = None

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt
            )
            response_text = response.text
            break
        except Exception as e:
            error_str = str(e)
            if "503" in error_str or "UNAVAILABLE" in error_str:
                if attempt == max_retries - 1:
                    response_text = f"[Xanctum Fallback] Relevant items for {username}:\n- " + "\n- ".join([c.get('title', '') for c in candidates])
                else:
                    sleep_time = (base_delay ** attempt) + random.uniform(0.5, 1.5)
                    time.sleep(sleep_time)
            else:
                raise HTTPException(status_code=500, detail=error_str)

    return {"curated_feed": response_text}