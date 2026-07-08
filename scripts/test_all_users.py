#!/usr/bin/env python3
"""
Comprehensive User Testing Script
Tests all user accounts and their specific functionalities
"""

import asyncio
import httpx
import json
import sys
import os
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Test configuration
BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 30.0

# Test users
TEST_USERS = [
    {"username": "admin", "password": "admin123", "role": "admin", "expected_features": ["balance_any", "transfer_any", "audit_read", "system_write"]},
    {"username": "alice", "password": "alice123", "role": "customer", "expected_features": ["balance_own", "transfer_own"]},
    {"username": "bob", "password": "bob123", "role": "customer", "expected_features": ["balance_own", "transfer_own"]}
]

class UserTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.client = httpx.Client(timeout=TIMEOUT)
        
    def __del__(self):
        if hasattr(self, 'client'):
            self.client.close()
    
    def print_section(self, title: str):
        print(f"\n{'='*60}")
        print(f" {title}")
        print('='*60)
    
    def print_test(self, test_name: str, status: str, details: str = ""):
        status_emoji = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{status_emoji} {test_name:<40} [{status}]")
        if details:
            print(f"   {details}")
    
    def test_login(self, username: str, password: str) -> dict:
        """Test user login and return tokens"""
        try:
            response = self.client.post(
                f"{self.base_url}/token",
                json={"username": username, "password": password}
            )
            
            if response.status_code == 200:
                data = response.json()
                self.print_test(f"Login {username}", "PASS", f"Got access token")
                return {
                    "access_token": data.get("access_token"),
                    "refresh_token": data.get("refresh_token")
                }
            else:
                self.print_test(f"Login {username}", "FAIL", f"Status: {response.status_code}, {response.text}")
                return None
                
        except Exception as e:
            self.print_test(f"Login {username}", "FAIL", f"Exception: {e}")
            return None
    
    def test_chat_message(self, token: str, message: str, username: str) -> str:
        """Test sending a chat message"""
        try:
            response = self.client.post(
                f"{self.base_url}/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "message": message,
                    "session_id": f"test-session-{username}"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get("response", "")
                self.print_test(f"Chat: '{message[:30]}...'", "PASS", f"Response length: {len(ai_response)} chars")
                return ai_response
            else:
                self.print_test(f"Chat: '{message[:30]}...'", "FAIL", f"Status: {response.status_code}")
                return ""
                
        except Exception as e:
            self.print_test(f"Chat: '{message[:30]}...'", "FAIL", f"Exception: {e}")
            return ""
    
    def test_balance_query(self, token: str, query: str, username: str, should_work: bool = True) -> str:
        """Test balance queries with permission checking"""
        try:
            response = self.client.post(
                f"{self.base_url}/chat",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "message": query,
                    "session_id": f"test-balance-{username}"
                }
            )
            
            if response.status_code == 200:
                ai_response = response.json().get("response", "")
                
                if should_work:
                    if "balance" in ai_response.lower() or "ETB" in ai_response or "1000" in ai_response:
                        self.print_test(f"Balance Query: {query}", "PASS", "Got balance information")
                    else:
                        self.print_test(f"Balance Query: {query}", "WARN", "No balance info in response")
                else:
                    if "access denied" in ai_response.lower() or "unauthorized" in ai_response.lower():
                        self.print_test(f"Balance Query: {query}", "PASS", "Correctly denied access")
                    else:
                        self.print_test(f"Balance Query: {query}", "WARN", "Expected access denial")
                
                return ai_response
            else:
                self.print_test(f"Balance Query: {query}", "FAIL", f"Status: {response.status_code}")
                return ""
                
        except Exception as e:
            self.print_test(f"Balance Query: {query}", "FAIL", f"Exception: {e}")
            return ""
    
    def test_policy_questions(self, token: str, username: str):
        """Test policy and HR questions"""
        policy_questions = [
            "What is the vacation policy?",
            "How many sick days do I get?",
            "Tell me about the 401k matching program",
            "What is the dress code policy?"
        ]
        
        for question in policy_questions:
            response = self.test_chat_message(token, question, username)
            # Basic check - should contain relevant information
            if len(response) > 50:  # Reasonable response length
                self.print_test(f"Policy Q: '{question[:25]}...'", "PASS", f"Got {len(response)} char response")
            else:
                self.print_test(f"Policy Q: '{question[:25]}...'", "WARN", "Short response")
    
    def test_refresh_token(self, refresh_token: str, username: str) -> str:
        """Test refresh token functionality"""
        try:
            response = self.client.post(
                f"{self.base_url}/refresh",
                json={"refresh_token": refresh_token}
            )
            
            if response.status_code == 200:
                data = response.json()
                new_token = data.get("access_token")
                self.print_test(f"Token Refresh {username}", "PASS", "Got new access token")
                return new_token
            else:
                self.print_test(f"Token Refresh {username}", "FAIL", f"Status: {response.status_code}")
                return ""
                
        except Exception as e:
            self.print_test(f"Token Refresh {username}", "FAIL", f"Exception: {e}")
            return ""
    
    def test_health_endpoint(self):
        """Test the health endpoint"""
        try:
            response = self.client.get(f"{self.base_url}/health")
            if response.status_code == 200:
                self.print_test("Health Check", "PASS", "Backend is healthy")
                return True
            else:
                self.print_test("Health Check", "FAIL", f"Status: {response.status_code}")
                return False
        except Exception as e:
            self.print_test("Health Check", "FAIL", f"Exception: {e}")
            return False
    
    def test_user_comprehensive(self, user_data: dict):
        """Run comprehensive tests for a specific user"""
        username = user_data["username"]
        password = user_data["password"]
        role = user_data["role"]
        
        self.print_section(f"Testing User: {username} ({role})")
        
        # 1. Test login
        tokens = self.test_login(username, password)
        if not tokens:
            print(f"❌ Cannot continue testing {username} - login failed")
            return
        
        access_token = tokens["access_token"]
        refresh_token = tokens["refresh_token"]
        
        # 2. Test basic chat functionality
        basic_response = self.test_chat_message(access_token, "Hello, how are you?", username)
        
        # 3. Test policy questions (should work for all users)
        self.test_policy_questions(access_token, username)
        
        # 4. Test balance queries based on role
        if role == "admin":
            # Admin should be able to check any balance
            self.test_balance_query(access_token, "balance of alice", username, should_work=True)
            self.test_balance_query(access_token, "balance of bob", username, should_work=True)
            self.test_balance_query(access_token, f"balance of {username}", username, should_work=True)
        else:
            # Customers should only check their own balance
            self.test_balance_query(access_token, f"balance of {username}", username, should_work=True)
            # Try to access other user's balance (should be denied)
            other_user = "alice" if username == "bob" else "bob"
            self.test_balance_query(access_token, f"balance of {other_user}", username, should_work=False)
        
        # 5. Test token refresh
        new_token = self.test_refresh_token(refresh_token, username)
        if new_token:
            # Test that new token works
            self.test_chat_message(new_token, "Testing refreshed token", username)
        
        # 6. Test role-specific features
        if role == "admin":
            # Test admin-specific queries
            admin_queries = [
                "Show me audit logs",
                "What system settings are available?",
                "List all user accounts"
            ]
            for query in admin_queries:
                self.test_chat_message(access_token, query, username)
        
        print(f"\n✅ Completed testing for {username}")
    
    def run_all_tests(self):
        """Run complete test suite"""
        print("🧪 Starting Comprehensive User Testing")
        print(f"Testing against: {self.base_url}")
        print(f"Timestamp: {datetime.now()}")
        
        # Test backend health first
        if not self.test_health_endpoint():
            print("❌ Backend health check failed - aborting tests")
            return
        
        # Test each user
        for user_data in TEST_USERS:
            try:
                self.test_user_comprehensive(user_data)
            except Exception as e:
                print(f"❌ Error testing user {user_data['username']}: {e}")
        
        # Summary
        self.print_section("Test Summary")
        print("✅ All user tests completed!")
        print("\n📋 Expected Behaviors:")
        print("- Admin can access any user's balance")
        print("- Customers can only access their own balance") 
        print("- All users can ask policy questions")
        print("- Token refresh should work for all users")
        print("- All responses should be contextual and helpful")

def main():
    """Main test function"""
    tester = UserTester(BASE_URL)
    try:
        tester.run_all_tests()
    finally:
        if hasattr(tester, 'client'):
            tester.client.close()

if __name__ == "__main__":
    main()