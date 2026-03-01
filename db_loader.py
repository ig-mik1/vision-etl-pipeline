import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize the Supabase REST Client
supabase_url: str = os.getenv("SUPABASE_URL")
supabase_key: str = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

def insert_kills(kill_events: list):
    """Takes the JSON array from the hybrid scraper and inserts it into Postgres."""
    if not kill_events:
        print("⚠️ No kills to insert.")
        return

    print(f"📦 Preparing to load {len(kill_events)} records into Supabase...")
    
    try:
        # The Supabase Python client can insert an entire array in one single network call!
        # Notice how the keys in our JSON exactly match the column names in our SQL table.
        response = supabase.table("kill_feed").insert(kill_events).execute()
        
        print(f"✅ SUCCESS: Inserted {len(response.data)} kills into the cloud database!")
        for record in response.data:
            print(f"   -> Logged: {record['killer_name']} killed {record['victim_name']} with {record['weapon_used']} (Headshot: {record['is_headshot']})")
            
    except Exception as e:
        print(f"❌ ERROR: Database insert failed: {e}")

if __name__ == "__main__":
    # A quick dummy test to make sure the connection works before we link it to the scraper
    dummy_data = [
        {
            "killer_name": "TestPlayer1",
            "victim_name": "TestPlayer2",
            "weapon_used": "Vandal",
            "is_headshot": True
        }
    ]
    insert_kills(dummy_data)