import os
import threading
import time
from datetime import datetime, timedelta
import requests
from flask import Flask, request, jsonify
import google.generativeai as genai

app = Flask(__name__)

# নতুন API Key ব্যবহার করা হলো
API_KEY = "AIzaSyDTovjgpg8zjzRFoCufjeYvRidcXSIInvQ"
genai.configure(api_key=API_KEY)

# /td এন্ডপয়েন্টের জন্য নির্দিষ্ট কনফিগারেশন
generation_config_td = {
    "temperature": 0.2,
    "top_p": 0.85,
    "top_k": 30,
    "max_output_tokens": 50,  # আনুমানিক ২০ শব্দের মধ্যে সীমিত
    "response_mime_type": "text/plain",
}

# মডেল কনফিগার করা
model_td = genai.GenerativeModel(
    model_name="gemini-2.0-flash",
    generation_config=generation_config_td,
)

# ইউজার সেশন সংরক্ষণ করার জন্য ডিকশনারি
user_sessions = {}
SESSION_TIMEOUT = timedelta(hours=6)  # 6 ঘণ্টা পর সেশন টাইমআউট হবে

@app.route("/td", methods=["GET"])
def ai_response():
    """ ইউজার ইনপুটের ভিত্তিতে এআই রেসপন্স প্রদান করে। """
    question = request.args.get("q")
    user_id = request.args.get("id")

    if not question:
        return jsonify({"error": "Missing 'q' parameter"}), 400
    if not user_id:
        return jsonify({"error": "Missing 'id' parameter"}), 400

    # নতুন ইউজারের জন্য সেশন তৈরি করা
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "history": [],
            "last_active": datetime.now()
        }

    # সেশনের সর্বশেষ সক্রিয় সময় আপডেট করা
    user_sessions[user_id]["last_active"] = datetime.now()

    # ইউজারের প্রশ্ন ইতিহাসে সংযোজন করা
    user_sessions[user_id]["history"].append({"role": "user", "parts": [question]})

    try:
        # পূর্ববর্তী ইতিহাস সহ চ্যাট সেশন তৈরি করা
        chat_session = model_td.start_chat(history=user_sessions[user_id]["history"])

        # এআই-এর রেসপন্স নেওয়া
        response = chat_session.send_message(question)

        if response.text:
            # রেসপন্স ইতিহাসে সংযোজন করা
            user_sessions[user_id]["history"].append({"role": "model", "parts": [response.text]})
            return jsonify({"response": response.text})
        else:
            return jsonify({"error": "AI did not return any response"}), 500

    except Exception as e:
        return jsonify({"error": f"Internal Server Error: {str(e)}"}), 500

@app.route('/ping', methods=['GET'])
def ping():
    """ সার্ভারের স্ট্যাটাস চেক করার জন্য একটি পিং এন্ডপয়েন্ট। """
    return jsonify({"status": "alive"})

def clean_inactive_sessions():
    """অ্যাকটিভ না থাকা সেশনগুলো পরিষ্কার করে।"""
    while True:
        current_time = datetime.now()
        for user_id, session_data in list(user_sessions.items()):
            if current_time - session_data["last_active"] > SESSION_TIMEOUT:
                print(f"🧹 Removing inactive session for user {user_id}")
                del user_sessions[user_id]
        time.sleep(300)  # প্রতি ৫ মিনিট পর চেক করবে

def keep_alive():
    """ সার্ভার সক্রিয় রাখতে প্রতি ৫ মিনিট পর পিং পাঠায়। """
    url = "https://new-ai-buxr.onrender.com/ping"
    while True:
        time.sleep(300)
        try:
            response = requests.get(url)
            if response.status_code == 200:
                print("✅ Keep-Alive Ping Successful")
            else:
                print(f"⚠️ Keep-Alive Ping Failed: Status Code {response.status_code}")
        except requests.exceptions.RequestException as e:
            print(f"❌ Keep-Alive Error: {e}")

# ব্যাকগ্রাউন্ড থ্রেড চালু করা
clean_up_thread = threading.Thread(target=clean_inactive_sessions, daemon=True)
clean_up_thread.start()

keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
keep_alive_thread.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
