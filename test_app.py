#!/usr/bin/env python3
"""
Test script for Qwen Chat App components
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from unittest.mock import Mock, patch

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import ChatHistoryManager, MemorySystem, QwenModelInterface

class TestChatHistoryManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        self.temp_db.close()
        self.chat_manager = ChatHistoryManager(self.temp_db.name)
        self.chat_manager.initialize_database()
    
    def tearDown(self):
        os.unlink(self.temp_db.name)
    
    def test_add_message(self):
        """Test adding a message to the database."""
        session_id = "test_session"
        message_id = self.chat_manager.add_message(session_id, "user", "Hello!")
        
        self.assertIsNotNone(message_id)
        
        # Verify message was stored
        messages = self.chat_manager.get_session_messages(session_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]['content'], "Hello!")
        self.assertEqual(messages[0]['role'], "user")
    
    def test_session_management(self):
        """Test session creation and retrieval."""
        session_id = "test_session"
        self.chat_manager.add_message(session_id, "user", "Test message")
        
        sessions = self.chat_manager.get_all_sessions()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]['session_id'], session_id)
    
    def test_database_health(self):
        """Test database health check."""
        self.assertTrue(self.chat_manager.check_health())

class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self.memory_system = MemorySystem()
    
    @patch('utils.SentenceTransformer')
    def test_initialization(self, mock_transformer):
        """Test memory system initialization."""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model
        
        self.memory_system.initialize()
        
        self.assertIsNotNone(self.memory_system.model)
        self.assertEqual(self.memory_system.embedding_dim, 384)
    
    @patch('utils.SentenceTransformer')
    def test_get_embedding(self, mock_transformer):
        """Test embedding generation."""
        mock_model = Mock()
        mock_model.encode.return_value = [0.1, 0.2, 0.3]
        mock_transformer.return_value = mock_model
        
        self.memory_system.initialize()
        embedding = self.memory_system.get_embedding("test text")
        
        self.assertIsNotNone(embedding)
        mock_model.encode.assert_called_once_with("test text", convert_to_numpy=True)

class TestQwenModelInterface(unittest.TestCase):
    def setUp(self):
        self.qwen_interface = QwenModelInterface()
    
    @patch('utils.requests.post')
    def test_generate_response_success(self, mock_post):
        """Test successful response generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'message': {'content': 'Test response'}
        }
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        response = self.qwen_interface.generate_response(messages)
        
        self.assertEqual(response, "Test response")
        mock_post.assert_called_once()
    
    @patch('utils.requests.post')
    def test_generate_response_failure(self, mock_post):
        """Test response generation failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        response = self.qwen_interface.generate_response(messages)
        
        self.assertIsNone(response)
    
    @patch('utils.requests.get')
    def test_health_check(self, mock_get):
        """Test health check functionality."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [{'name': 'qwen:7b'}]
        }
        mock_get.return_value = mock_response
        
        health_status = self.qwen_interface.check_health()
        
        self.assertTrue(health_status)

def run_tests():
    """Run all tests."""
    print("Running Qwen Chat App Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestChatHistoryManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMemorySystem))
    suite.addTests(loader.loadTestsFromTestCase(TestQwenModelInterface))
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "=" * 50)
    if result.wasSuccessful():
        print("✅ All tests passed!")
    else:
        print(f"❌ {len(result.failures)} test(s) failed, {len(result.errors)} error(s)")
        
        if result.failures:
            print("\nFailures:")
            for test, error in result.failures:
                print(f"- {test}: {error}")
        
        if result.errors:
            print("\nErrors:")
            for test, error in result.errors:
                print(f"- {test}: {error}")
    
    return result.wasSuccessful()

if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
