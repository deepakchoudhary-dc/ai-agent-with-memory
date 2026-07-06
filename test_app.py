#!/usr/bin/env python3
"""
Test script for Local AI Chat App components
"""

import os
import sys
import unittest
import tempfile
import sqlite3
from unittest.mock import Mock, patch

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import ChatHistoryManager, MemorySystem, LocalModelInterface

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

    def test_session_rename_and_delete(self):
        """Test renaming and deleting sessions."""
        session_id = "test_session"
        self.chat_manager.add_message(session_id, "user", "Hello memory search")

        renamed = self.chat_manager.rename_session(session_id, "Renamed Chat")
        self.assertTrue(renamed)

        sessions = self.chat_manager.get_all_sessions()
        self.assertEqual(sessions[0]['title'], "Renamed Chat")

        deleted = self.chat_manager.delete_session(session_id)
        self.assertTrue(deleted)
        self.assertEqual(self.chat_manager.get_all_sessions(), [])

    def test_session_search(self):
        """Test searching sessions by content."""
        first_session = "session_one"
        second_session = "session_two"
        self.chat_manager.add_message(first_session, "user", "Talk about project planning")
        self.chat_manager.add_message(second_session, "user", "Discuss vacation plans")

        results = self.chat_manager.search_sessions("project")

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['session_id'], first_session)
        self.assertIn("project", results[0]['snippet'].lower())

    def test_attachment_storage(self):
        """Test storing and retrieving session attachments."""
        session_id = "attachment_session"
        self.chat_manager.add_attachment(session_id, "notes.txt", "hello attachment", "text/plain")

        attachments = self.chat_manager.get_session_attachments(session_id)

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]['filename'], "notes.txt")
        self.assertEqual(attachments[0]['content'], "hello attachment")
    
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

class TestLocalModelInterface(unittest.TestCase):
    def setUp(self):
        self.model_interface = LocalModelInterface()
    
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
        response = self.model_interface.generate_response(messages)
        
        self.assertIsInstance(response, dict)
        self.assertEqual(response["answer"], "Test response")
        mock_post.assert_called_once()
    
    @patch('utils.requests.post')
    def test_generate_response_failure(self, mock_post):
        """Test response generation failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response
        
        messages = [{"role": "user", "content": "Hello"}]
        response = self.model_interface.generate_response(messages)
        
        self.assertIsNone(response)
    
    @patch('utils.requests.get')
    def test_health_check(self, mock_get):
        """Test health check functionality."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'models': [{'name': 'your-model-name'}]
        }
        mock_get.return_value = mock_response
        
        health_status = self.model_interface.check_health()
        
        self.assertTrue(health_status)

    @patch('utils.requests.post')
    def test_stream_response(self, mock_post):
        """Test streamed response generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Hel"}, "done": false}',
            b'{"message": {"content": "lo"}, "done": false}',
            b'{"done": true}'
        ]
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        chunks = list(self.model_interface.stream_response(messages))

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["type"], "chunk")
        self.assertEqual(chunks[-1]["type"], "done")
        self.assertEqual(chunks[-1]["answer"], "Hello")

def run_tests():
    """Run all tests."""
    print("Running Local AI Chat App Tests...")
    print("=" * 50)
    
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test cases
    suite.addTests(loader.loadTestsFromTestCase(TestChatHistoryManager))
    suite.addTests(loader.loadTestsFromTestCase(TestMemorySystem))
    suite.addTests(loader.loadTestsFromTestCase(TestLocalModelInterface))
    
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
