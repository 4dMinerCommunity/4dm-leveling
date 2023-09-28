import sqlite3
from pymongo import MongoClient

# Connect to the SQLite database
sqlite_conn = sqlite3.connect("sqlite.db")
sqlite_cursor = sqlite_conn.cursor()

# Connect to the MongoDB database
mongo_client = MongoClient("mongodb://localhost:27017")  
mongo_db = mongo_client["4DM-Leveling"] 

# Define a dictionary to hold combined user data
combined_userdata = {}

# Fetch data from SQLite and combine it into a flat structure
sqlite_cursor.execute("SELECT * FROM levels")
levels_data = sqlite_cursor.fetchall()


usersettings = {
    "pingme": {
        'description': "Toggle getting pinged when you level up (default is off)",
        'onmessage': "you will now get pinged upon levelup",
        'offmessage': "you will no longer get pinged on levelup"
    },
    "snitchtome": {
        'description': "Toggle getting pinged when someone queries your rank (default is off)",
        'onmessage': "I will now snitch to you when someone queries your rank",
        'offmessage': "you will no longer get notified when someone queries your rank"
    },
}

for setting_name in usersettings:
    sqlite_cursor.execute(f"SELECT id FROM {setting_name}_users")
    for row in sqlite_cursor.fetchall():
        user_id = row[0]
        if user_id not in combined_userdata:
            combined_userdata[user_id] = {
                "id": user_id,
            }
        combined_userdata[user_id][setting_name] = True

# Populate levels data in the combined dictionary
for user_id, level, xp in levels_data:
    if user_id in combined_userdata:
        combined_userdata[user_id]["level"] = level
        combined_userdata[user_id]["xp"] = xp

# Convert the dictionary values into a list of documents
userdata_list = list(combined_userdata.values())

# Insert the combined user data into MongoDB
mongo_db["users"].insert_many(userdata_list)

# Close database connections
sqlite_conn.close()
mongo_client.close()