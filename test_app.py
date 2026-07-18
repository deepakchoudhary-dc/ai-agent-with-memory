#!/usr/bin/env python3
"""
Test script for Local AI Chat App components
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils import ChatHistoryManager, LocalModelInterface, MemorySystem


class TestChatHistoryManager(unittest.TestCase):
    def setUp(self):
        # Create a temporary database for testing
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.chat_manager = ChatHistoryManager(self.temp_db.name)
        self.chat_manager.initialize_database()
        self.user_id = "test_user"

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_add_message(self):
        """Test adding a message to the database."""
        session_id = "test_session"
        message_id = self.chat_manager.add_message(session_id, "user", "Hello!", self.user_id)

        self.assertIsNotNone(message_id)

        # Verify message was stored
        messages = self.chat_manager.get_session_messages(session_id, self.user_id)
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "Hello!")
        self.assertEqual(messages[0]["role"], "user")

    def test_session_management(self):
        """Test session creation and retrieval."""
        session_id = "test_session"
        self.chat_manager.add_message(session_id, "user", "Test message", self.user_id)

        sessions = self.chat_manager.get_all_sessions(self.user_id)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0]["session_id"], session_id)

    def test_session_rename_and_delete(self):
        """Test renaming and deleting sessions."""
        session_id = "test_session"
        self.chat_manager.add_message(session_id, "user", "Hello memory search", self.user_id)

        renamed = self.chat_manager.rename_session(session_id, "Renamed Chat", self.user_id)
        self.assertTrue(renamed)

        sessions = self.chat_manager.get_all_sessions(self.user_id)
        self.assertEqual(sessions[0]["title"], "Renamed Chat")

        deleted = self.chat_manager.delete_session(session_id, self.user_id)
        self.assertTrue(deleted)
        self.assertEqual(self.chat_manager.get_all_sessions(self.user_id), [])

    def test_session_search(self):
        """Test searching sessions by content."""
        first_session = "session_one"
        second_session = "session_two"
        self.chat_manager.add_message(first_session, "user", "Talk about project planning", self.user_id)
        self.chat_manager.add_message(second_session, "user", "Discuss vacation plans", self.user_id)

        results = self.chat_manager.search_sessions("project", self.user_id)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["session_id"], first_session)
        self.assertIn("project", results[0]["snippet"].lower())

    def test_attachment_storage(self):
        """Test storing and retrieving session attachments."""
        session_id = "attachment_session"
        self.chat_manager.add_attachment(session_id, "notes.txt", "hello attachment", "text/plain", self.user_id)

        attachments = self.chat_manager.get_session_attachments(session_id, self.user_id)

        self.assertEqual(len(attachments), 1)
        self.assertEqual(attachments[0]["filename"], "notes.txt")
        self.assertEqual(attachments[0]["content"], "hello attachment")

    def test_database_health(self):
        """Test database health check."""
        self.assertTrue(self.chat_manager.check_health())

    def test_user_facts(self):
        """Test adding, getting, and deleting user profile facts."""
        fact_id = self.chat_manager.add_fact("User likes Python", self.user_id)
        self.assertIsNotNone(fact_id)

        # Test duplicate addition (should be ignored / return None)
        duplicate_id = self.chat_manager.add_fact("User likes Python", self.user_id)
        self.assertIsNone(duplicate_id)

        # Test getting all facts
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact"], "User likes Python")

        # Test deleting fact
        deleted = self.chat_manager.delete_fact(fact_id, self.user_id)
        self.assertTrue(deleted)

        # Test getting all facts after delete
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 0)


class TestMemorySystem(unittest.TestCase):
    def setUp(self):
        self.memory_system = MemorySystem()

    @patch("utils.SentenceTransformer")
    def test_initialization(self, mock_transformer):
        """Test memory system initialization."""
        mock_model = Mock()
        mock_model.get_sentence_embedding_dimension.return_value = 384
        mock_transformer.return_value = mock_model

        self.memory_system.initialize()

        self.assertIsNotNone(self.memory_system.model)
        self.assertEqual(self.memory_system.embedding_dim, 384)

    @patch("utils.SentenceTransformer")
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

    @patch("utils.requests.post")
    def test_generate_response_success(self, mock_post):
        """Test successful response generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"message": {"content": "Test response"}}
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        response = self.model_interface.generate_response(messages)

        self.assertIsInstance(response, dict)
        self.assertEqual(response["answer"], "Test response")
        mock_post.assert_called_once()

    @patch("utils.requests.post")
    def test_generate_response_failure(self, mock_post):
        """Test response generation failure."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        response = self.model_interface.generate_response(messages)

        self.assertIsNone(response)

    @patch("utils.requests.get")
    def test_health_check(self, mock_get):
        """Test health check functionality."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"models": [{"name": "your-model-name"}]}
        mock_get.return_value = mock_response

        health_status = self.model_interface.check_health()

        self.assertTrue(health_status)

    @patch("utils.requests.post")
    def test_stream_response(self, mock_post):
        """Test streamed response generation."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.iter_lines.return_value = [
            b'{"message": {"content": "Hel"}, "done": false}',
            b'{"message": {"content": "lo"}, "done": false}',
            b'{"done": true}',
        ]
        mock_post.return_value = mock_response

        messages = [{"role": "user", "content": "Hello"}]
        chunks = list(self.model_interface.stream_response(messages))

        self.assertGreaterEqual(len(chunks), 2)
        self.assertEqual(chunks[0]["type"], "chunk")
        self.assertEqual(chunks[-1]["type"], "done")
        self.assertEqual(chunks[-1]["answer"], "Hello")


class TestContextBudgeting(unittest.TestCase):
    def setUp(self):
        # Set up a mock chat_manager on the app module
        import app

        self.original_chat_manager = app.chat_manager
        app.chat_manager = Mock()
        self.mock_chat_manager = app.chat_manager

    def tearDown(self):
        import app

        app.chat_manager = self.original_chat_manager

    def test_build_context_basic(self):
        """Test build_context constructs messages correctly under simple budget."""
        from app import build_context

        self.mock_chat_manager.get_all_facts.return_value = [{"fact": "User prefers python"}]

        relevant_memories = [
            {"timestamp": "2026-07-18", "role": "user", "content": "I like memory search"},
            {"timestamp": "2026-07-18", "role": "assistant", "content": "FAISS search is great"},
        ]
        recent_messages = [{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}]
        attachments = [{"filename": "code.py", "content": "print('hello')"}]

        context = build_context(
            relevant_memories=relevant_memories,
            recent_messages=recent_messages,
            user_message="Test message",
            attachments=attachments,
            user_id="test_user",
            max_length=4096,
        )

        # Verify first message is system prompt
        self.assertEqual(context[0]["role"], "system")
        self.assertIn("helpful AI assistant", context[0]["content"])

        # Verify facts section
        self.assertEqual(context[1]["role"], "system")
        self.assertIn("User prefers python", context[1]["content"])

        # Verify memories section
        self.assertEqual(context[2]["role"], "system")
        self.assertIn("I like memory search", context[2]["content"])

        # Verify attachments section
        self.assertEqual(context[3]["role"], "system")
        self.assertIn("code.py", context[3]["content"])

        # Verify history section
        self.assertEqual(context[4]["role"], "user")
        self.assertEqual(context[4]["content"], "Hi")
        self.assertEqual(context[5]["role"], "assistant")
        self.assertEqual(context[5]["content"], "Hello")

        # Verify last message is current user message
        self.assertEqual(context[-1]["role"], "user")
        self.assertEqual(context[-1]["content"], "Test message")

    def test_build_context_truncation(self):
        """Test build_context truncates long attachments and limits history to fit max_length."""
        from app import build_context

        self.mock_chat_manager.get_all_facts.return_value = []

        attachments = [{"filename": "huge.txt", "content": "A" * 20000}]

        context = build_context(
            relevant_memories=[],
            recent_messages=[],
            user_message="Tiny message",
            attachments=attachments,
            user_id="test_user",
            max_length=1000,
        )

        # The attachment context must be present but truncated
        attachment_msg = [msg for msg in context if "huge.txt" in msg["content"]][0]
        self.assertLess(len(attachment_msg["content"]), 4000)
        self.assertIn("[File truncated to fit context budget...]", attachment_msg["content"])


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
    suite.addTests(loader.loadTestsFromTestCase(TestContextBudgeting))

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
