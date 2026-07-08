#!/usr/bin/env python3
"""
Focused User Testing Script - Testing key functionalities
"""

import httpx
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 30.0

def test_user_login_and_features():
    """Test login and key features for all users"""
    
    users = [
        {"username": "admin", "password": "admin123", "role": "admin"},
        {"username": "alice", "password": "alice123", "role": "customer"}, 
        {"username": "bob", "password": "bob123", "role": "customer"}
    ]
    
    print(f"🧪 Focused Testing - {datetime.now()}")
    print("="*60)
    
    with httpx.Client(timeout=TIMEOUT) as client:
        for user in users:
            username = user["username"]
            password = user["password"]
            role = user["role"]
            
            print(f"\n👤 Testing {username} ({role})")
            print("-" * 40)
            
            # 1. Test Login
            try:
                response = client.post(
                    f"{BASE_URL}/token",
                    json={"username": username, "password": password}
                )
                
                if response.status_code == 200:
                    tokens = response.json()
                    access_token = tokens["access_token"]
                    print(f"✅ Login successful")
                    
                    # 2. Test Basic Chat
                    response = client.post(
                        f"{BASE_URL}/chat",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={"message": "Hello", "session_id": f"test-{username}"}
                    )
                    
                    if response.status_code == 200:
                        print(f"✅ Basic chat works")
                    else:
                        print(f"❌ Basic chat failed: {response.status_code}")
                    
                    # 3. Test Balance Query
                    balance_query = f"balance of {username}"
                    response = client.post(
                        f"{BASE_URL}/chat",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={"message": balance_query, "session_id": f"balance-{username}"}
                    )
                    
                    if response.status_code == 200:
                        ai_response = response.json().get("response", "")
                        if "balance" in ai_response.lower() or "ETB" in ai_response:
                            print(f"✅ Own balance query works")
                        else:
                            print(f"⚠️  Balance query unclear response: {ai_response[:100]}...")
                    else:
                        print(f"❌ Balance query failed: {response.status_code}")
                    
                    # 4. Test Cross-User Balance (for authorization testing)
                    if username != "admin":
                        other_user = "bob" if username == "alice" else "alice"
                        cross_query = f"balance of {other_user}"
                        
                        response = client.post(
                            f"{BASE_URL}/chat",
                            headers={"Authorization": f"Bearer {access_token}"},
                            json={"message": cross_query, "session_id": f"cross-{username}"}
                        )
                        
                        if response.status_code == 200:
                            ai_response = response.json().get("response", "")
                            if "access denied" in ai_response.lower() or "permission" in ai_response.lower():
                                print(f"✅ Cross-user balance correctly denied")
                            elif "balance" in ai_response.lower():
                                print(f"⚠️  Cross-user balance may be allowed (should be denied)")
                            else:
                                print(f"⚠️  Cross-user response unclear: {ai_response[:100]}...")
                    
                    # 5. Test Policy Question
                    response = client.post(
                        f"{BASE_URL}/chat",
                        headers={"Authorization": f"Bearer {access_token}"},
                        json={"message": "What is the vacation policy?", "session_id": f"policy-{username}"}
                    )
                    
                    if response.status_code == 200:
                        ai_response = response.json().get("response", "")
                        if len(ai_response) > 50:
                            print(f"✅ Policy question answered")
                        else:
                            print(f"⚠️  Policy response too short: {ai_response}")
                    else:
                        print(f"❌ Policy query failed: {response.status_code}")
                    
                    # 6. Admin-specific tests
                    if role == "admin":
                        # Test admin access to other balances
                        response = client.post(
                            f"{BASE_URL}/chat", 
                            headers={"Authorization": f"Bearer {access_token}"},
                            json={"message": "balance of alice", "session_id": f"admin-balance-{username}"}
                        )
                        
                        if response.status_code == 200:
                            ai_response = response.json().get("response", "")
                            if "balance" in ai_response.lower() or "ETB" in ai_response:
                                print(f"✅ Admin can access user balances")
                            else:
                                print(f"⚠️  Admin balance access unclear: {ai_response[:100]}...")
                    
                else:
                    print(f"❌ Login failed: {response.status_code} - {response.text}")
                    continue
                    
            except Exception as e:
                print(f"❌ Error testing {username}: {e}")
    
    print(f"\n{'='*60}")
    print("🎯 Test Summary:")
    print("✅ = Working correctly")
    print("⚠️  = Needs attention") 
    print("❌ = Not working")
    print(f"{'='*60}")

if __name__ == "__main__":
    test_user_login_and_features()