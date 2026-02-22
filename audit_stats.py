import requests

API_KEY = "a9a1130a-bed8-441b-a318-c052e4ad7aa5"
headers = {"Authorization": API_KEY}

def find_gg():
    cursor = None
    print("--- Searching All Active 2025-26 Rosters ---")
    
    # We loop through pages until we find him or run out of players
    while True:
        url = "https://api.balldontlie.io/nba/v1/players/active"
        params = {'cursor': cursor} if cursor else {}
        
        response = requests.get(url, headers=headers, params=params).json()
        players = response.get('data', [])
        
        for p in players:
            full_name = f"{p['first_name']} {p['last_name']}".lower()
            if "gregory" in full_name or "gg jackson" in full_name:
                print(f"🎯 FOUND: {p['first_name']} {p['last_name']} | ID: {p['id']} | Team: {p['team']['abbreviation']}")
                return p['id']
        
        cursor = response.get('meta', {}).get('next_cursor')
        if not cursor:
            break
    
    print("❌ GG Jackson not found on active rosters.")
    return None

def get_stats(player_id):
    url = f"https://api.balldontlie.io/nba/v1/stats?player_ids[]={player_id}&seasons[]=2025"
    data = requests.get(url, headers=headers).json()
    logs = data.get('data', [])
    
    print(f"\n--- G.G. Jackson 2025-26 Stats ({len(logs)} games) ---")
    for game in logs:
        date = game['game']['date'].split('T')[0]
        print(f"Date: {date} | Pts: {game['pts']}")

# Execution
gg_id = find_gg()
if gg_id:
    get_stats(gg_id)