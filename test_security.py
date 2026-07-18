#!/usr/bin/env python3
"""
Comprehensive Security and Isolation Test Suite for Local AI Chat App
"""

import json
import os
import sys
import tempfile
import unittest

# Add the project directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from utils import ChatHistoryManager, truncate_context


class TestAuthentication(unittest.TestCase):
    def setUp(self):
        # Set up a temporary database file
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "DATABASE_PATH": self.db_path, "MOCK_MODELS": True}
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_unauthenticated_redirect(self):
        """Verify unauthenticated requests to protected endpoints are redirected to login."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.location)

        # JSON api endpoint should return 401 Unauthorized instead of redirecting
        response_json = self.client.get("/sessions")
        self.assertEqual(response_json.status_code, 401)

    def test_registration_validation(self):
        """Verify password complexity validation on registration."""
        # Test short password
        response = self.client.post("/register", data={"username": "testuser", "password": "123"})
        self.assertIn(b"Password must be at least 8 characters long", response.data)

        # Test empty credentials
        response = self.client.post("/register", data={"username": "", "password": ""})
        self.assertIn(b"Username and password are required", response.data)

    def test_successful_registration_and_login_flow(self):
        """Verify successful user registration, login, and logout flow."""
        # 1. Register a user
        response = self.client.post(
            "/register", data={"username": "secureuser", "password": "supersecretpassword123"}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Chat Session", response.data)  # Main chat index page

        # 2. Log out
        response_logout = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(response_logout.status_code, 200)
        self.assertIn(b"Log In", response_logout.data)

        # 3. Access home again (should redirect to login)
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)

        # 4. Log back in with wrong credentials
        response = self.client.post("/login", data={"username": "secureuser", "password": "wrongpassword"})
        self.assertEqual(response.status_code, 200)  # Renders login page with error
        self.assertIn(b"Invalid username or password", response.data)

        # 5. Log back in with correct credentials
        response = self.client.post(
            "/login", data={"username": "secureuser", "password": "supersecretpassword123"}, follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Chat Session", response.data)


class TestCSRFProtection(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {
                "TESTING": True,
                "WTF_CSRF_ENABLED": True,  # Enable CSRF explicitly
                "DATABASE_PATH": self.db_path,
                "MOCK_MODELS": True,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_mutating_request_without_csrf_fails(self):
        """Verify POST requests to mutating endpoints without a CSRF token are blocked."""
        # Register and log in
        self.client.post("/register", data={"username": "csrfuser", "password": "csrfpassword123"})

        # Try to send a chat message without CSRF header (should fail with 400 Bad Request)
        response = self.client.post("/chat", json={"message": "hello security test", "stream": False})
        self.assertEqual(response.status_code, 400)


class TestUserIsolation(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "DATABASE_PATH": self.db_path, "MOCK_MODELS": True}
        )
        self.client = self.app.test_client()
        self.chat_manager = ChatHistoryManager(self.db_path)

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def register_and_login(self, username, password):
        # Helper to register and return client with active session
        client = self.app.test_client()
        client.post("/register", data={"username": username, "password": password})
        return client

    def test_user_isolation(self):
        """Verify that data boundaries prevent cross-user data leakage."""
        client_a = self.register_and_login("user_a", "password123a")
        client_b = self.register_and_login("user_b", "password123b")

        # 1. User A creates a session and posts a message
        # Get active session ID from main page
        res = client_a.get("/")
        self.assertEqual(res.status_code, 200)

        # Manually create session for User A
        res_session = client_a.post("/new_session")
        session_id_a = json.loads(res_session.data)["session_id"]

        # Add message under User A
        user_a_db_user = self.chat_manager.get_user_by_username("user_a")
        user_a_id = user_a_db_user["id"]
        self.chat_manager.add_message(session_id_a, "user", "Top Secret Message from A", user_id=user_a_id)

        # 2. User B queries sessions (User A's session should NOT appear)
        res_b_sessions = client_b.get("/sessions")
        self.assertEqual(res_b_sessions.status_code, 200)
        sessions_b = json.loads(res_b_sessions.data)["sessions"]
        session_ids_b = [s["session_id"] for s in sessions_b]
        self.assertNotIn(session_id_a, session_ids_b)

        # 3. User B queries messages for User A's session (should return empty list)
        res_b_history = client_b.get(f"/history/{session_id_a}")
        self.assertEqual(res_b_history.status_code, 200)
        messages_b = json.loads(res_b_history.data)["messages"]
        self.assertEqual(len(messages_b), 0)

        # 4. User B attempts to rename User A's session (should fail)
        res_b_rename = client_b.post(f"/sessions/{session_id_a}/rename", json={"title": "Hacked Title"})
        self.assertEqual(res_b_rename.status_code, 404)

        # 5. User B attempts to delete User A's session (should fail)
        res_b_delete = client_b.delete(f"/sessions/{session_id_a}")
        self.assertEqual(res_b_delete.status_code, 404)


class TestContextTruncation(unittest.TestCase):
    def test_truncate_context_within_limit(self):
        """Verify context truncation logic budgets messages within limits."""
        messages = [
            {"role": "system", "content": "Keep this"},
            {"role": "user", "content": "Large message " * 100},
            {"role": "assistant", "content": "Another message"},
            {"role": "user", "content": "Immediate question"},
        ]
        # Set max_length small enough to trigger truncation on the middle messages
        truncated = truncate_context(messages, max_length=125)

        # System message and last user message must always be preserved
        self.assertEqual(truncated[0]["role"], "system")
        self.assertEqual(truncated[-1]["content"], "Immediate question")

        # Verify total character length is within bounds
        total_len = sum(len(m["content"]) for m in truncated)
        self.assertLessEqual(total_len, 500)


class TestMemoryGovernance(unittest.TestCase):
    def setUp(self):
        self.db_fd, self.db_path = tempfile.mkstemp()
        self.app = create_app(
            {"TESTING": True, "WTF_CSRF_ENABLED": False, "DATABASE_PATH": self.db_path, "MOCK_MODELS": True}
        )
        self.client = self.app.test_client()
        self.chat_manager = ChatHistoryManager(self.db_path)

        # Create a test user and log them in
        self.client.post("/register", data={"username": "govuser", "password": "govpassword123"})
        db_user = self.chat_manager.get_user_by_username("govuser")
        self.user_id = db_user["id"]

    def tearDown(self):
        os.close(self.db_fd)
        os.unlink(self.db_path)

    def test_memory_candidates_lifecycle(self):
        """Verify the lifecycle of proposed memory candidates (Inbox, Approve, Reject)."""
        # 1. Initially no candidates
        res = self.client.get("/memory/candidates")
        self.assertEqual(res.status_code, 200)
        candidates = json.loads(res.data)["candidates"]
        self.assertEqual(len(candidates), 0)

        # 2. Add an ADD candidate fact
        cand_id1 = self.chat_manager.add_memory_candidate(self.user_id, "User lives in Paris", "ADD")
        self.assertIsNotNone(cand_id1)

        # 3. Retrieve candidates, verify it appears in inbox
        res = self.client.get("/memory/candidates")
        candidates = json.loads(res.data)["candidates"]
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["fact"], "User lives in Paris")
        self.assertEqual(candidates[0]["action"], "ADD")

        # 4. Approve the ADD candidate fact
        res_approve = self.client.post(f"/memory/candidates/{cand_id1}/approve")
        self.assertEqual(res_approve.status_code, 200)

        # 5. Verify the candidate status is approved and the fact was added to user_facts
        candidates_db = self.chat_manager.get_pending_candidates(self.user_id)
        self.assertEqual(len(candidates_db), 0)  # No longer pending

        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact"], "User lives in Paris")
        fact_id = facts[0]["id"]

        # 6. Add an UPDATE candidate fact for the existing fact
        cand_id2 = self.chat_manager.add_memory_candidate(
            self.user_id, "User lives in Berlin", "UPDATE", existing_fact_id=fact_id
        )

        # Approve the UPDATE candidate fact
        res_approve2 = self.client.post(f"/memory/candidates/{cand_id2}/approve")
        self.assertEqual(res_approve2.status_code, 200)

        # Verify fact was updated
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["fact"], "User lives in Berlin")

        # 7. Add a DELETE candidate fact
        cand_id3 = self.chat_manager.add_memory_candidate(
            self.user_id, "User lives in Berlin", "DELETE", existing_fact_id=fact_id
        )

        # Reject candidate
        res_reject = self.client.post(f"/memory/candidates/{cand_id3}/reject")
        self.assertEqual(res_reject.status_code, 200)

        # Fact should still exist
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 1)

        # Approve DELETE candidate
        cand_id4 = self.chat_manager.add_memory_candidate(
            self.user_id, "User lives in Berlin", "DELETE", existing_fact_id=fact_id
        )
        res_approve3 = self.client.post(f"/memory/candidates/{cand_id4}/approve")
        self.assertEqual(res_approve3.status_code, 200)

        # Fact should now be deleted
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 0)

    def test_memory_provenance_and_message_deletion(self):
        """Verify memory provenance joins and message deletion for regeneration."""
        # Create session
        res_sess = self.client.post("/new_session")
        session_id = json.loads(res_sess.data)["session_id"]

        # Add user & assistant messages
        msg_id1 = self.chat_manager.add_message(
            session_id, "user", "My favorite language is Rust", user_id=self.user_id
        )
        self.chat_manager.add_message(session_id, "assistant", "I noted that you like Rust", user_id=self.user_id)

        # Add fact with provenance
        self.chat_manager.add_fact("User prefers Rust", self.user_id, source_message_id=msg_id1)

        # Verify fact provenance returns correct message and session context
        facts = self.chat_manager.get_all_facts(self.user_id)
        self.assertEqual(len(facts), 1)
        self.assertEqual(facts[0]["source_message_id"], msg_id1)
        self.assertEqual(facts[0]["source_content"], "My favorite language is Rust")

        # Test deleting last messages
        res_del = self.client.delete(f"/sessions/{session_id}/messages/last")
        self.assertEqual(res_del.status_code, 200)

        # Both user and assistant last messages should be deleted
        history_res = self.client.get(f"/history/{session_id}")
        history = json.loads(history_res.data)["messages"]
        self.assertEqual(len(history), 0)


def run_tests():
    """Run security tests."""
    print("Running App Security and User Isolation Tests...")
    print("=" * 50)

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestAuthentication))
    suite.addTests(loader.loadTestsFromTestCase(TestCSRFProtection))
    suite.addTests(loader.loadTestsFromTestCase(TestUserIsolation))
    suite.addTests(loader.loadTestsFromTestCase(TestContextTruncation))
    suite.addTests(loader.loadTestsFromTestCase(TestMemoryGovernance))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
