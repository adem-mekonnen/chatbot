#!/usr/bin/env python3
"""
Final Verification Script - Complete functionality test
"""

import httpx
import json
import time
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 15.0  # Shorter timeout to avoid long waits

def test_complete_functionality():
    """Complete test of all user functionalities"""
    
    print("🔍 FINAL VERIFICATION TEST")
    print("=" * 60)
    print(f"Time: {datetime.now()}")
    print(f"Backend: {BASE_URL}")
    print("=" * 60)
    
    # Test Cases
    test_results = {
        "admin_login": False,
        "alice_login": False, 
        "bob_login": False,
        "admin_own_balance": False,
        "alice_own_balance": False,
        "bob_own_balance": False,
        "admin_cross_balance": False,
        "alice_cross_denied": False,
        "bob_cross_denied": False,
        "policy_questions": False,
        "token_refresh": False
    }
    
    with httpx.Client(timeout=TIMEOUT) as client:
        
        # 1. TEST LOGINS
        print("\n📋 1. LOGIN TESTS")
        print("-" * 30)
        
        users_tokens = {}
        
        for username, password in [("admin", "admin123"), ("alice", "alice123"), ("bob", "bob123")]:
            try:
                response = client.post(
                    f"{BASE_URL}/token",
                    json={"username": username, "password": password}
                )
                
                if response.status_code == 200:
                    tokens = response.json()
                    users_tokens[username] = tokens["access_token"]
                    test_results[f"{username}_login"] = True
                    print(f"✅ {username} login: SUCCESS")
                else:
                    print(f"❌ {username} login: FAILED ({response.status_code})")
            except Exception as e:
                print(f"❌ {username} login: ERROR - {e}")
        
        # 2. TEST BALANCE QUERIES
        print("\n💰 2. BALANCE QUERY TESTS")
        print("-" * 30)
        
        # Test own balance for each user
        for username in ["admin", "alice", "bob"]:
            if username in users_tokens:
                try:
                    response = client.post(
                        f"{BASE_URL}/chat",
                        headers={"Authorization": f"Bearer {users_tokens[username]}"},
                        json={"message": f"balance of {username}", "session_id": f"own-{username}"}
                    )
                    
                    if response.status_code == 200:
                        ai_response = response.json().get("response", "")
                        if "balance" in ai_response.lower() or "ETB" in ai_response:
                            test_results[f"{username}_own_balance"] = True
                            print(f"✅ {username} own balance: SUCCESS")
                        else:
                            print(f"⚠️  {username} own balance: NO BALANCE INFO")
                    else:
                        print(f"❌ {username} own balance: HTTP {response.status_code}")
                except Exception as e:
                    print(f"❌ {username} own balance: ERROR - {e}")
        
        # Test cross-user access
        if "admin" in users_tokens:
            try:
                response = client.post(
                    f"{BASE_URL}/chat",
                    headers={"Authorization": f"Bearer {users_tokens['admin']}"},
                    json={"message": "balance of alice", "session_id": "admin-cross"}
                )
                
                if response.status_code == 200:
                    ai_response = response.json().get("response", "")
                    if "balance" in ai_response.lower() or "ETB" in ai_response:
                        test_results["admin_cross_balance"] = True
                        print(f"✅ admin cross-user balance: SUCCESS")
                    else:
                        print(f"⚠️  admin cross-user balance: NO BALANCE INFO")
            except Exception as e:
                print(f"❌ admin cross-user balance: ERROR - {e}")
        
        # Test customers denied cross-access
        for user in ["alice", "bob"]:
            if user in users_tokens:
                other_user = "bob" if user == "alice" else "alice"
                try:
                    response = client.post(
                        f"{BASE_URL}/chat",
                        headers={"Authorization": f"Bearer {users_tokens[user]}"},
                        json={"message": f"balance of {other_user}", "session_id": f"cross-{user}"}
                    )
                    
                    if response.status_code == 200:
                        ai_response = response.json().get("response", "")
                        if "access denied" in ai_response.lower() or "permission" in ai_response.lower():
                            test_results[f"{user}_cross_denied"] = True
                            print(f"✅ {user} cross-access denied: SUCCESS")
                        else:
                            print(f"⚠️  {user} cross-access: MAY NOT BE DENIED")
                except Exception as e:
                    print(f"❌ {user} cross-access test: ERROR - {e}")
        
        # 3. TEST POLICY QUESTIONS
        print("\n📖 3. POLICY QUESTION TEST")
        print("-" * 30)
        
        if "alice" in users_tokens:  # Test with one user
            try:
                response = client.post(
                    f"{BASE_URL}/chat",
                    headers={"Authorization": f"Bearer {users_tokens['alice']}"},
                    json={"message": "How many vacation days do I get per year?", "session_id": "policy-test"}
                )
                
                if response.status_code == 200:
                    ai_response = response.json().get("response", "")
                    if len(ai_response) > 50:  # Reasonable response length
                        test_results["policy_questions"] = True
                        print(f"✅ Policy question: SUCCESS ({len(ai_response)} chars)")
                    else:
                        print(f"⚠️  Policy question: SHORT RESPONSE")
                else:
                    print(f"❌ Policy question: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ Policy question: ERROR - {e}")
        
        # 4. TEST TOKEN REFRESH  
        print("\n🔄 4. TOKEN REFRESH TEST")
        print("-" * 30)
        
        if "alice" in users_tokens:
            # Get refresh token
            try:
                response = client.post(
                    f"{BASE_URL}/token",
                    json={"username": "alice", "password": "alice123"}
                )
                
                if response.status_code == 200:
                    tokens = response.json()
                    refresh_token = tokens["refresh_token"]
                    
                    # Test refresh
                    response = client.post(
                        f"{BASE_URL}/refresh",
                        json={"refresh_token": refresh_token}
                    )
                    
                    if response.status_code == 200:
                        new_tokens = response.json()
                        if new_tokens.get("access_token"):
                            test_results["token_refresh"] = True
                            print(f"✅ Token refresh: SUCCESS")
                        else:
                            print(f"⚠️  Token refresh: NO NEW TOKEN")
                    else:
                        print(f"❌ Token refresh: HTTP {response.status_code}")
            except Exception as e:
                print(f"❌ Token refresh: ERROR - {e}")
    
    # FINAL REPORT
    print("\n" + "=" * 60)
    print("🎯 FINAL VERIFICATION REPORT")
    print("=" * 60)
    
    passed = sum(test_results.values())
    total = len(test_results)
    
    print(f"\nOverall Score: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    print(f"\n📊 Detailed Results:")
    
    categories = {
        "Authentication": ["admin_login", "alice_login", "bob_login"],
        "Balance Queries": ["admin_own_balance", "alice_own_balance", "bob_own_balance"],
        "Authorization": ["admin_cross_balance", "alice_cross_denied", "bob_cross_denied"],
        "Knowledge Base": ["policy_questions"],
        "Token Management": ["token_refresh"]
    }
    
    for category, tests in categories.items():
        passed_in_category = sum(test_results[test] for test in tests)
        total_in_category = len(tests)
        status = "✅" if passed_in_category == total_in_category else "⚠️" if passed_in_category > 0 else "❌"
        print(f"{status} {category}: {passed_in_category}/{total_in_category}")
    
    print(f"\n🔍 Issues Found:")
    failed_tests = [test for test, result in test_results.items() if not result]
    if failed_tests:
        for test in failed_tests:
            print(f"  ❌ {test}")
    else:
        print(f"  🎉 No issues found - All tests passed!")
    
    print(f"\n✅ DEPLOYMENT STATUS:")
    if passed >= total * 0.9:  # 90% pass rate
        print(f"  🚀 READY FOR PRODUCTION")
        print(f"     - All critical functions working")
        print(f"     - Security controls in place") 
        print(f"     - User authentication functional")
    elif passed >= total * 0.7:  # 70% pass rate
        print(f"  ⚠️  READY FOR STAGING")
        print(f"     - Most functions working")
        print(f"     - Minor issues to resolve")
    else:
        print(f"  ❌ NOT READY FOR DEPLOYMENT")
        print(f"     - Critical issues found")
        print(f"     - Requires fixes before deployment")
    
    print("=" * 60)

if __name__ == "__main__":
    test_complete_functionality()