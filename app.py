#!/usr/bin/env python3
"""
Qwen Chat App with Human-like Memory
A Flask application providing ChatGPT-like interface with semantic memory capabilities.
"""

import os
import json
import sqlite3
import uuid
from datetime import datetime
from typing import List, Dict, Tuple, Optional
import logging

from flask import Flask, render_template, request, jsonify, session, Response
import requests
import numpy as np
from sentence_transformers import SentenceTransformer
import faiss
from dotenv import load_dotenv

from utils import ChatHistoryManager, MemorySystem, QwenModelInterface

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'your-secret-key-change-this')

# Configuration
OLLAMA_BASE_URL = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
QWEN_MODEL_NAME = os.getenv('QWEN_MODEL_NAME', 'qwen3:1.7b')
MAX_CONTEXT_LENGTH = int(os.getenv('MAX_CONTEXT_LENGTH', '4096'))
TOP_K_MEMORIES = int(os.getenv('TOP_K_MEMORIES', '5'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'chat_history.db')

# Initialize components
chat_manager = ChatHistoryManager(DATABASE_PATH)
memory_system = MemorySystem()
qwen_interface = QwenModelInterface(OLLAMA_BASE_URL, QWEN_MODEL_NAME)

# Set up the memory system reference to chat manager
memory_system.chat_manager = chat_manager

@app.route('/')
def index():
    """Main chat interface."""
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    
    return render_template('index.html', session_id=session['session_id'])

@app.route('/chat', methods=['POST'])
def chat():
    """Handle chat messages and return AI responses."""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()
        session_id = session.get('session_id', str(uuid.uuid4()))
        
        if not user_message:
            return jsonify({'error': 'Empty message'}), 400
        
        logger.info(f"Processing message for session {session_id}: {user_message[:50]}...")
        
        # Store user message
        user_msg_id = chat_manager.add_message(
            session_id=session_id,
            role='user',
            content=user_message
        )
        
        # Get user message embedding
        user_embedding = memory_system.get_embedding(user_message)
        chat_manager.store_embedding(user_msg_id, user_embedding)
        
        # Retrieve relevant memories
        relevant_memories = memory_system.search_relevant_memories(
            user_embedding, 
            session_id, 
            k=TOP_K_MEMORIES
        )
        
        # Get recent conversation context
        recent_messages = chat_manager.get_recent_messages(session_id, limit=10)
        
        # Build context for Qwen
        context_messages = build_context(relevant_memories, recent_messages, user_message)
          # Get AI response
        ai_response_data = qwen_interface.generate_response(context_messages)
        
        if ai_response_data:
            thinking = ai_response_data.get('thinking', '')
            answer = ai_response_data.get('answer', '')
            
            # Store AI response (store the answer part)
            ai_msg_id = chat_manager.add_message(
                session_id=session_id,
                role='assistant',
                content=answer
            )
            
            # Get AI response embedding (use answer for embedding)
            ai_embedding = memory_system.get_embedding(answer)
            chat_manager.store_embedding(ai_msg_id, ai_embedding)
            
            # Prepare response with memory context for transparency
            memory_context = [
                {
                    'content': mem['content'][:100] + '...' if len(mem['content']) > 100 else mem['content'],                    'timestamp': mem['timestamp'],
                    'similarity': float(mem['similarity'])
                }
                for mem in relevant_memories
            ]
            
            return jsonify({
                'thinking': thinking,
                'response': answer,
                'session_id': session_id,
                'memories_used': memory_context,
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({'error': 'Failed to generate response'}), 500
    
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        return jsonify({'error': 'Internal server error'}), 500

@app.route('/history/<session_id>')
def get_history(session_id):
    """Get chat history for a session."""
    try:
        messages = chat_manager.get_session_messages(session_id)
        return jsonify({'messages': messages})
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({'error': 'Failed to get history'}), 500

@app.route('/sessions')
def get_sessions():
    """Get list of all chat sessions."""
    try:
        query = request.args.get('q', '').strip()
        sessions = chat_manager.search_sessions(query) if query else chat_manager.get_all_sessions()
        return jsonify({'sessions': sessions})
    except Exception as e:
        logger.error(f"Error getting sessions: {str(e)}")
        return jsonify({'error': 'Failed to get sessions'}), 500

@app.route('/sessions/<session_id>/rename', methods=['POST'])
def rename_session(session_id):
    """Rename an existing chat session."""
    try:
        data = request.get_json(force=True) or {}
        title = data.get('title', '').strip()

        if not title:
            return jsonify({'error': 'Session title cannot be empty'}), 400

        if not chat_manager.rename_session(session_id, title):
            return jsonify({'error': 'Session not found'}), 404

        return jsonify({'session_id': session_id, 'title': title})
    except Exception as e:
        logger.error(f"Error renaming session: {str(e)}")
        return jsonify({'error': 'Failed to rename session'}), 500

@app.route('/sessions/<session_id>', methods=['DELETE'])
def delete_session(session_id):
    """Delete a chat session and its messages."""
    try:
        deleted = chat_manager.delete_session(session_id)
        if not deleted:
            return jsonify({'error': 'Session not found'}), 404

        if session.get('session_id') == session_id:
            new_session_id = str(uuid.uuid4())
            session['session_id'] = new_session_id
            return jsonify({'deleted': True, 'new_session_id': new_session_id})

        return jsonify({'deleted': True})
    except Exception as e:
        logger.error(f"Error deleting session: {str(e)}")
        return jsonify({'error': 'Failed to delete session'}), 500

@app.route('/new_session', methods=['POST'])
def new_session():
    """Start a new chat session."""
    try:
        new_session_id = str(uuid.uuid4())
        session['session_id'] = new_session_id
        return jsonify({'session_id': new_session_id})
    except Exception as e:
        logger.error(f"Error creating new session: {str(e)}")
        return jsonify({'error': 'Failed to create new session'}), 500

@app.route('/export/<session_id>')
def export_session(session_id):
    """Export a session as Markdown or JSON."""
    try:
        messages = chat_manager.get_session_messages(session_id)
        sessions = chat_manager.get_all_sessions()
        session_data = next((item for item in sessions if item['session_id'] == session_id), None)

        if not session_data:
            return jsonify({'error': 'Session not found'}), 404

        export_format = request.args.get('format', 'markdown').lower()

        if export_format == 'json':
            return jsonify({
                'session': session_data,
                'messages': messages
            })

        markdown_lines = [
            f"# {session_data.get('title') or 'New Chat'}",
            '',
            f"- Session ID: {session_id}",
            f"- Created: {session_data.get('created_at')}",
            f"- Last activity: {session_data.get('last_activity')}",
            ''
        ]

        for message in messages:
            role_label = 'User' if message['role'] == 'user' else 'Assistant'
            markdown_lines.extend([
                f"## {role_label}",
                '',
                message['content'],
                ''
            ])

        export_body = '\n'.join(markdown_lines).strip() + '\n'
        return Response(
            export_body,
            mimetype='text/markdown',
            headers={
                'Content-Disposition': f'attachment; filename=session-{session_id}.md'
            }
        )
    except Exception as e:
        logger.error(f"Error exporting session: {str(e)}")
        return jsonify({'error': 'Failed to export session'}), 500

def build_context(relevant_memories: List[Dict], recent_messages: List[Dict], user_message: str) -> List[Dict]:
    """
    Build context for Qwen model including relevant memories and recent conversation.
    
    Args:
        relevant_memories: List of relevant past messages
        recent_messages: List of recent messages from current session
        user_message: Current user message
    
    Returns:
        List of formatted messages for the model
    """
    context_messages = []
      # Add system prompt
    system_prompt = """You are Qwen, a helpful AI assistant with access to conversation history. 
    You can remember and reference past conversations to provide more personalized and contextual responses. 
    
    IMPORTANT: Before giving your final answer, please think through your response step by step. 
    Start your thinking process with <think> and end it with </think>, then provide your actual answer.
    
    Example format:
    <think>
    The user is asking about... I should consider... Based on our previous conversations... My approach will be...
    </think>
    
    [Your actual response here]
    
    When relevant, you may reference previous discussions, but keep your responses natural and conversational."""
    
    context_messages.append({"role": "system", "content": system_prompt})
    
    # Add relevant memories if available
    if relevant_memories:
        memory_context = "Here are some relevant parts of our previous conversations:\n\n"
        for memory in relevant_memories:
            memory_context += f"[{memory['timestamp']}] {memory['role']}: {memory['content']}\n"
        
        context_messages.append({"role": "system", "content": memory_context})
    
    # Add recent conversation context
    for msg in recent_messages[-8:]:  # Last 8 messages for immediate context
        context_messages.append({
            "role": msg['role'],
            "content": msg['content']
        })
    
    # Add current user message
    context_messages.append({"role": "user", "content": user_message})
    
    return context_messages

@app.route('/health')
def health_check():
    """Health check endpoint."""
    try:
        # Check if Ollama is accessible
        ollama_status = qwen_interface.check_health()
        
        # Check database connection
        db_status = chat_manager.check_health()
        
        # Check memory system
        memory_status = memory_system.check_health()
        
        return jsonify({
            'status': 'healthy',
            'ollama': ollama_status,
            'database': db_status,
            'memory_system': memory_status,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    # Initialize database and memory system
    try:
        chat_manager.initialize_database()
        memory_system.initialize()
        logger.info("Application initialized successfully")
        
        # Check if Ollama is running
        if not qwen_interface.check_health():
            logger.warning("Ollama is not accessible. Please ensure it's running with Qwen model loaded.")
        
        app.run(debug=True, host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Failed to initialize application: {str(e)}")
        raise
