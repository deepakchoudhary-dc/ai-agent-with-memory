#!/usr/bin/env python3
"""
Utility classes for Qwen Chat App with Human-like Memory
"""

import sqlite3
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Any
import threading

import requests
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss

logger = logging.getLogger(__name__)

class ChatHistoryManager:
    """Manages chat history storage and retrieval using SQLite."""
    
    def __init__(self, db_path: str = 'chat_history.db'):
        self.db_path = db_path
        self.lock = threading.Lock()
    
    def initialize_database(self):
        """Initialize the SQLite database with required tables."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Create messages table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    embedding BLOB
                )
            ''')
            
            # Create sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_activity DATETIME DEFAULT CURRENT_TIMESTAMP,
                    title TEXT
                )
            ''')
            
            # Create indexes for better performance
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_session_id ON messages(session_id)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON messages(timestamp)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_role ON messages(role)')
            
            conn.commit()
            conn.close()
            logger.info("Database initialized successfully")
    
    def add_message(self, session_id: str, role: str, content: str) -> str:
        """Add a new message to the database."""
        message_id = str(uuid.uuid4())
        timestamp = datetime.now()
        
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Insert message
            cursor.execute('''
                INSERT INTO messages (id, session_id, role, content, timestamp)
                VALUES (?, ?, ?, ?, ?)
            ''', (message_id, session_id, role, content, timestamp))
            
            # Update or create session
            cursor.execute('''
                INSERT OR REPLACE INTO sessions (session_id, last_activity, title)
                VALUES (?, ?, ?)
            ''', (session_id, timestamp, self._generate_session_title(content, role)))
            
            conn.commit()
            conn.close()
        
        logger.debug(f"Added message {message_id} to session {session_id}")
        return message_id
    
    def store_embedding(self, message_id: str, embedding: np.ndarray):
        """Store message embedding in the database."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Convert numpy array to bytes
            embedding_bytes = embedding.astype(np.float32).tobytes()
            
            cursor.execute('''
                UPDATE messages SET embedding = ? WHERE id = ?
            ''', (embedding_bytes, message_id))
            
            conn.commit()
            conn.close()
    
    def get_session_messages(self, session_id: str, limit: Optional[int] = None) -> List[Dict]:
        """Get all messages for a specific session."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT id, role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp ASC
            '''
            
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query, (session_id,))
            rows = cursor.fetchall()
            conn.close()
        
        messages = []
        for row in rows:
            messages.append({
                'id': row[0],
                'role': row[1],
                'content': row[2],
                'timestamp': row[3]
            })
        
        return messages
    
    def get_recent_messages(self, session_id: str, limit: int = 10) -> List[Dict]:
        """Get recent messages from a session."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, role, content, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            ''', (session_id, limit))
            
            rows = cursor.fetchall()
            conn.close()
        
        messages = []
        for row in reversed(rows):  # Reverse to get chronological order
            messages.append({
                'id': row[0],
                'role': row[1],
                'content': row[2],
                'timestamp': row[3]
            })
        
        return messages
    
    def get_all_sessions(self) -> List[Dict]:
        """Get all chat sessions with metadata."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT s.session_id, s.created_at, s.last_activity, s.title,
                       COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON s.session_id = m.session_id
                GROUP BY s.session_id
                ORDER BY s.last_activity DESC
            ''')
            
            rows = cursor.fetchall()
            conn.close()
        
        sessions = []
        for row in rows:
            sessions.append({
                'session_id': row[0],
                'created_at': row[1],
                'last_activity': row[2],
                'title': row[3] or 'New Chat',
                'message_count': row[4]
            })
        
        return sessions
    
    def get_messages_with_embeddings(self, exclude_session: str = None) -> List[Dict]:
        """Get all messages with embeddings for similarity search."""
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            query = '''
                SELECT id, session_id, role, content, timestamp, embedding
                FROM messages
                WHERE embedding IS NOT NULL
            '''
            
            params = []
            if exclude_session:
                query += ' AND session_id != ?'
                params.append(exclude_session)
            
            query += ' ORDER BY timestamp DESC'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
        
        messages = []
        for row in rows:
            embedding = np.frombuffer(row[5], dtype=np.float32) if row[5] else None
            messages.append({
                'id': row[0],
                'session_id': row[1],
                'role': row[2],
                'content': row[3],
                'timestamp': row[4],
                'embedding': embedding
            })
        
        return messages
    
    def _generate_session_title(self, content: str, role: str) -> str:
        """Generate a title for the session based on the first user message."""
        if role == 'user':
            # Take first 50 characters of user message as title
            title = content[:50].strip()
            if len(content) > 50:
                title += '...'
            return title
        return None
    
    def check_health(self) -> bool:
        """Check if database is accessible."""
        try:
            with self.lock:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                cursor.execute('SELECT 1')
                conn.close()
            return True
        except Exception as e:
            logger.error(f"Database health check failed: {str(e)}")
            return False

class MemorySystem:
    """Manages semantic memory using sentence transformers and FAISS."""
    
    def __init__(self, model_name: str = 'sentence-transformers/all-MiniLM-L6-v2'):
        self.model_name = model_name
        self.model = None
        self.embedding_dim = 384  # Default for all-MiniLM-L6-v2
        self.chat_manager = None
    
    def initialize(self):
        """Initialize the sentence transformer model."""
        try:
            logger.info(f"Loading sentence transformer model: {self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            self.embedding_dim = self.model.get_sentence_embedding_dimension()
            logger.info(f"Model loaded successfully. Embedding dimension: {self.embedding_dim}")
        except Exception as e:
            logger.error(f"Failed to load sentence transformer model: {str(e)}")
            raise
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for a text string."""
        if not self.model:
            raise RuntimeError("Model not initialized")
        
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.astype(np.float32)
        except Exception as e:
            logger.error(f"Failed to get embedding: {str(e)}")
            raise
    
    def search_relevant_memories(self, query_embedding: np.ndarray, 
                                current_session_id: str, k: int = 5) -> List[Dict]:
        """
        Search for relevant memories using semantic similarity.
        
        Args:
            query_embedding: Embedding of the current query
            current_session_id: Current session ID to exclude from search
            k: Number of top similar memories to return
        
        Returns:
            List of relevant memories with similarity scores        """
        if not self.chat_manager:
            raise RuntimeError("Chat manager not initialized")
        
        # Get all messages with embeddings (excluding current session)
        messages = self.chat_manager.get_messages_with_embeddings(exclude_session=current_session_id)
        
        if not messages:
            return []
        
        # Prepare embeddings matrix
        embeddings = []
        valid_messages = []
        
        for msg in messages:
            if msg['embedding'] is not None and len(msg['embedding']) == self.embedding_dim:
                embeddings.append(msg['embedding'])
                valid_messages.append(msg)
        
        if not embeddings:
            return []
        
        embeddings_matrix = np.vstack(embeddings)
        
        # Create FAISS index
        index = faiss.IndexFlatIP(self.embedding_dim)  # Inner product for cosine similarity
        
        # Normalize embeddings for cosine similarity
        faiss.normalize_L2(embeddings_matrix)
        query_embedding_normalized = query_embedding.copy()
        faiss.normalize_L2(query_embedding_normalized.reshape(1, -1))
        
        index.add(embeddings_matrix)
        
        # Search for similar memories
        similarities, indices = index.search(query_embedding_normalized.reshape(1, -1), 
                                           min(k, len(valid_messages)))
        
        # Prepare results
        relevant_memories = []
        for i, (similarity, idx) in enumerate(zip(similarities[0], indices[0])):
            if similarity > 0.3:  # Threshold for relevance
                memory = valid_messages[idx].copy()
                memory['similarity'] = similarity
                relevant_memories.append(memory)
        
        # Sort by similarity (descending)
        relevant_memories.sort(key=lambda x: x['similarity'], reverse=True)
        
        logger.debug(f"Found {len(relevant_memories)} relevant memories")
        return relevant_memories
    
    def check_health(self) -> bool:
        """Check if memory system is working properly."""
        try:
            if not self.model:
                return False
            
            # Test embedding generation
            test_embedding = self.get_embedding("test")
            return len(test_embedding) == self.embedding_dim
        except Exception as e:
            logger.error(f"Memory system health check failed: {str(e)}")
            return False

class QwenModelInterface:
    """Interface for communicating with Qwen model via Ollama."""
    
    def __init__(self, base_url: str = 'http://localhost:11434', model_name: str = 'qwen3:1.7b'):
        self.base_url = base_url.rstrip('/')
        self.model_name = model_name
        self.api_url = f"{self.base_url}/api/chat"
    
    def generate_response(self, messages: List[Dict[str, str]], 
                         max_tokens: int = 1000, temperature: float = 0.7) -> Optional[Dict[str, str]]:
        """
        Generate response from Qwen model with thinking process.
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature
        
        Returns:
            Dictionary with 'thinking' and 'answer' keys, or None if failed
        """
        try:
            # First, get the thinking process
            thinking_messages = messages + [{
                "role": "user", 
                "content": "Before answering, please think through this step by step. Start your response with <think> and end the thinking part with </think>, then provide your actual answer."
            }]
            
            payload = {
                "model": self.model_name,
                "messages": thinking_messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            logger.debug(f"Sending request to Ollama: {len(thinking_messages)} messages")
            
            response = requests.post(
                self.api_url,
                json=payload,
                timeout=60,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'message' in result and 'content' in result['message']:
                    full_response = result['message']['content'].strip()
                    return self._parse_thinking_response(full_response)
                else:
                    logger.error(f"Unexpected response format: {result}")
                    return None
            else:
                logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Request to Ollama failed: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error in generate_response: {str(e)}")
            return None
    
    def _parse_thinking_response(self, response: str) -> Dict[str, str]:
        """
        Parse response to separate thinking process from final answer.
        
        Args:
            response: Full response from the model
            
        Returns:
            Dictionary with 'thinking' and 'answer' keys
        """
        import re
        
        # Try to extract thinking part between <think> and </think>
        think_match = re.search(r'<think>(.*?)</think>', response, re.DOTALL | re.IGNORECASE)
        
        if think_match:
            thinking = think_match.group(1).strip()
            # Remove the thinking part from the response to get the answer
            answer = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL | re.IGNORECASE).strip()
        else:
            # If no <think> tags, try to split by common patterns
            if "I think" in response or "Let me think" in response:
                # Try to find natural thinking patterns
                parts = response.split('\n\n', 1)
                if len(parts) == 2 and any(word in parts[0].lower() for word in ['think', 'consider', 'analyze']):
                    thinking = parts[0].strip()
                    answer = parts[1].strip()
                else:
                    thinking = "Let me process this request..."
                    answer = response
            else:
                thinking = "Processing your request..."
                answer = response
        
        return {
            'thinking': thinking,
            'answer': answer
        }
    
    def check_health(self) -> bool:
        """Check if Ollama is accessible and has the required model."""
        try:
            # Check if Ollama is running
            health_url = f"{self.base_url}/api/tags"
            response = requests.get(health_url, timeout=5)
            
            if response.status_code == 200:
                models = response.json().get('models', [])
                model_names = [model.get('name', '') for model in models]
                
                # Check if our model is available
                if any(self.model_name in name for name in model_names):
                    logger.info(f"Qwen model {self.model_name} is available")
                    return True
                else:
                    logger.warning(f"Model {self.model_name} not found. Available models: {model_names}")
                    return False
            else:
                logger.error(f"Ollama health check failed: {response.status_code}")
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to connect to Ollama: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error in health check: {str(e)}")
            return False

def truncate_context(messages: List[Dict], max_length: int = 4000) -> List[Dict]:
    """
    Truncate context to fit within model's context window.
    
    Args:
        messages: List of message dictionaries
        max_length: Maximum number of characters to keep
    
    Returns:
        Truncated list of messages
    """
    # Rough estimation: 1 token ≈ 4 characters for most languages
    max_chars = max_length * 4
    
    total_length = sum(len(msg['content']) for msg in messages)
    
    if total_length <= max_chars:
        return messages
    
    # Keep system message and recent messages
    if messages and messages[0].get('role') == 'system':
        system_msg = messages[0]
        other_messages = messages[1:]
    else:
        system_msg = None
        other_messages = messages
    
    # Calculate available space
    system_length = len(system_msg['content']) if system_msg else 0
    available_length = max_chars - system_length
    
    # Keep recent messages that fit within available space
    kept_messages = []
    current_length = 0
    
    for msg in reversed(other_messages):
        msg_length = len(msg['content'])
        if current_length + msg_length <= available_length:
            kept_messages.insert(0, msg)
            current_length += msg_length
        else:
            break
    
    # Combine system message with kept messages
    result = []
    if system_msg:
        result.append(system_msg)
    result.extend(kept_messages)
    
    logger.debug(f"Truncated context from {len(messages)} to {len(result)} messages")
    return result
