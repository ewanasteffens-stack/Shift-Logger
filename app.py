import os
import requests
import re
import threading
import discord
from discord.ext import commands
from flask import Flask, request, jsonify

app = Flask(__name__)

# --- SHIFT MEMORY ---
# This dictionary stores who is currently on shift.
# Note: If your free Render server goes to sleep, this list will reset!
active_shifts = {
    "dps": [],
    "dpd": [],
    "dfd": [],
    "dcso": []
}

# --- WEBHOOKS ---
WEBHOOKS = {
    "dps": os.environ.get("WEBHOOK_DPS"),
    "dpd": os.environ.get("WEBHOOK_DPD"),
    "dfd": os.environ.get("WEBHOOK_DFD"),
    "dcso": os.environ.get("WEBHOOK_DCSO")
}
DEFAULT_WEBHOOK = os.environ.get("WEBHOOK_DEFAULT")

# --- FLASK WEB SERVER (ERLC PROXY) ---
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
                
                # Check for start shift
                if typed_text.startswith(":log shift start"):
                    action = "start"
                    division = typed_text.replace(":log shift start", "").strip()
                    
                    # Add player to active memory list
                    if division in active_shifts and player not in active_shifts[division]:
                        active_shifts[division].append(player)
                    elif division not in active_shifts:
                        active_shifts[division] = [player]
                        
                # Check for end shift
                elif typed_text.startswith(":log shift end"):
                    action = "end"
                    division = typed_text.replace(":log shift end", "").strip()
                    
                    # Remove player from active memory list
                    if division in active_shifts and player in active_shifts[division]:
                        active_shifts[division].remove(player)
                else:
                    return jsonify({"status": "ignored"}), 200
                
                # Send Webhook to Discord
                target_webhook = WEBHOOKS.get(division, DEFAULT_WEBHOOK)
                if target_webhook:
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
                            ]
                        }]
                    }
                    requests.post(target_webhook, json=payload)
                    
                return jsonify({"status": "success"}), 200
    except Exception as e:
        print(f"Error: {e}")
        
    return jsonify({"status": "ignored"}), 200


# --- DISCORD BOT ---
intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.command()
async def active(ctx):
    # This creates a nice embed showing everyone on shift
    embed = discord.Embed(title="📋 Current Active Shifts", color=0x3498DB)
    
    total_active = 0
    for division, players in active_shifts.items():
        if players: # Only show divisions that have people on duty
            embed.add_field(name=division.upper(), value="\n".join(players), inline=False)
            total_active += len(players)
            
    if total_active == 0:
        embed.description = "Nobody is currently on shift."
        
    # Send the list and mention (ping) the user who asked
    await ctx.send(content=f"Here is the active shift list, {ctx.author.mention}:", embed=embed)

# --- RUN BOTH TOGETHER ---
def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    # 1. Start the Flask server in the background
    threading.Thread(target=run_flask).start()
    
    # 2. Start the Discord Bot on the main thread
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("ERROR: DISCORD_BOT_TOKEN is missing!")
