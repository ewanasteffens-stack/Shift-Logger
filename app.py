import os
import requests
import re
from flask import Flask, request, jsonify

app = Flask(__name__)

# This dictionary matches the division name to the correct Webhook URL from Render
WEBHOOKS = {
    "dps": os.environ.get("WEBHOOK_DPS"),
    "dpd": os.environ.get("WEBHOOK_DPD"),
    "dfd": os.environ.get("WEBHOOK_DFD"),
    "dcso": os.environ.get("WEBHOOK_DCSO")
}

# A fallback webhook just in case they type a division that doesn't exist
DEFAULT_WEBHOOK = os.environ.get("WEBHOOK_DEFAULT")

@app.route('/erlc-webhook', methods=['POST'])
def erlc_webhook():
    data = request.json
    
    if not data or "embeds" not in data:
        return jsonify({"status": "ignored"}), 200

    try:
        description = data["embeds"][0].get("description", "")
        lower_desc = description.lower()
        
        if ":log shift start" in lower_desc or ":log shift end" in lower_desc:
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
                
                # Figure out which webhook to use based on the division they typed!
                target_webhook = WEBHOOKS.get(division)
                
                # If they typed a division we don't have, use the default webhook
                if not target_webhook:
                    target_webhook = DEFAULT_WEBHOOK
                    
                # If even the default is missing, we can't send it
                if not target_webhook:
                    return jsonify({"error": "No webhook configured for this division"}), 500

                # Format the custom Discord Embed
                color = 0x2ECC71 if action == "start" else 0xE74C3C 
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
                
                # Send the embed to the SPECIFIC channel's webhook
                requests.post(target_webhook, json=payload)
                return jsonify({"status": "success"}), 200
                
    except Exception as e:
        print(f"Error processing webhook: {e}")
        
    return jsonify({"status": "ignored"}), 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
