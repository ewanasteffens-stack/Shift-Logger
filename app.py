import os
import re
import threading
import discord
from discord.ext import commands
from flask import Flask
import requests

app = Flask(__name__)

# We just need a dummy web page so Render doesn't crash the service
@app.route('/')
def home():
    return "Bot is running and listening to Discord!"

active_shifts = {
    "dps": [], "dpd": [], "dfd": [], "dcso": []
}

WEBHOOKS = {
    "dps": os.environ.get("WEBHOOK_DPS"),
    "dpd": os.environ.get("WEBHOOK_DPD"),
    "dfd": os.environ.get("WEBHOOK_DFD"),
    "dcso": os.environ.get("WEBHOOK_DCSO")
}
DEFAULT_WEBHOOK = os.environ.get("WEBHOOK_DEFAULT")

intents = discord.Intents.default()
intents.message_content = True 
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_message(message):
    # ERLC sends logs as Discord embeds. This checks if the message has an embed.
    if message.embeds:
        for embed in message.embeds:
            description = embed.description or ""
            lower_desc = description.lower()
            
            # If the bot spots the custom log command in the hidden channel
            if ":log shift start" in lower_desc or ":log shift end" in lower_desc:
                player_match = re.search(r'\*\*Player:\*\* (.*)', description)
                text_match = re.search(r'\*\*(?:Command|Message):\*\* (.*)', description, re.IGNORECASE)
                
                player = player_match.group(1).strip() if player_match else "Unknown"
                
                if text_match:
                    typed_text = text_match.group(1).strip().lower()
                    
                    if typed_text.startswith(":log shift start"):
                        action = "start"
                        division = typed_text.replace(":log shift start", "").strip()
                        if division in active_shifts and player not in active_shifts[division]:
                            active_shifts[division].append(player)
                        elif division not in active_shifts:
                            active_shifts[division] = [player]
                            
                    elif typed_text.startswith(":log shift end"):
                        action = "end"
                        division = typed_text.replace(":log shift end", "").strip()
                        if division in active_shifts and player in active_shifts[division]:
                            active_shifts[division].remove(player)
                    else:
                        continue
                        
                    # Find where to send the final clean message
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
                        # Forward the clean embed to the correct department channel
                        requests.post(target_webhook, json=payload)
                        
    # Ensure commands like !active still work
    await bot.process_commands(message)

@bot.command()
async def active(ctx):
    embed = discord.Embed(title="📋 Current Active Shifts", color=0x3498DB)
    total_active = 0
    for division, players in active_shifts.items():
        if players:
            embed.add_field(name=division.upper(), value="\n".join(players), inline=False)
            total_active += len(players)
            
    if total_active == 0:
        embed.description = "Nobody is currently on shift."
        
    await ctx.send(content=f"Here is the active shift list, {ctx.author.mention}:", embed=embed)

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, use_reloader=False)

if __name__ == '__main__':
    threading.Thread(target=run_flask).start()
    TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
    if TOKEN:
        bot.run(TOKEN)
