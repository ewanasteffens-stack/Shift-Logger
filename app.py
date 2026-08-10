import os
import requests
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# Your real Discord Webhook URL saved in Render's Environment Variables
REAL_DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL")

@app.route('/erlc-webhook', methods=['POST'])
def erlc_webhook():
    if not REAL_DISCORD_WEBHOOK:
        return jsonify({"error": "Webhook URL missing"}), 500
        
    data = request.json
    
    # ERLC sends data in Discord embed format. If it's missing, ignore it.
    if not data or "embeds" not in data:
        return jsonify({"status": "ignored"}), 200

    try:
        # Extract the description where ERLC puts the chat/command text
        description = data["embeds"][0].get("description", "")
        
        # Check if the shift command is anywhere in the message
        lower_desc = description.lower()
        if ":log shift start" in lower_desc or ":log shift end" in lower_desc:
            
            # ERLC formats logs like: "**Player:** Username\n**Message:** Text"
            # We use regex to carefully extract the exact player name and the text they typed
            player_match = re.search(r'\*\*Player:\*\* (.*)', description)
            text_match = re.search(r'\*\*(?:Command|Message):\*\* (.*)', description, re.IGNORECASE)
            
            player = player_match.group(1).strip() if player_match else "Unknown"
            
            if text_match:
                typed_text = text_match.group(1).strip().lower()
                
                # Determine action and division
                if typed_text.startswith(":log shift start"):
                    action = "start"
                    division = typed_text.replace(":log shift start", "").strip()
                elif typed_text.startswith(":log shift end"):
                    action = "end"
                    division = typed_text.replace(":log shift end", "").strip()
                else:
                    return jsonify({"status": "ignored"}), 200
                    
                # Format the custom, clean Discord Embed
                color = 0x2ECC71 if action == "start" else 0xE74C3C # Green or Red
                title = "🟢 Shift Started" if action == "start" else "🔴 Shift Ended"
                
                payload = {
                    "embeds": [{
                        "title": title,
                        "color": color,
                        "fields": [
                            {"name": "Officer", "value": player, "inline": True},
                            {"name": "Division", "value": division.upper(), "inline": True},
                            {"name": "Status", "value": action.capitalize(), "inline": True}
                        ],
                        "footer": {"text": "ERLC Shift Logger"}
                    }]
                }
                
                # Send our custom embed to the real Discord Webhook
                requests.post(REAL_DISCORD_WEBHOOK, json=payload)
                return jsonify({"status": "success"}), 200
                
    except Exception as e:
        print(f"Error processing webhook: {e}")
        
    # If the message wasn't a shift log, we just return 200 OK so ERLC knows we got it, but we do nothing.
    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
