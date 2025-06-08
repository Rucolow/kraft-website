import sqlite3

# データベースの初期化
def init_db():
    conn = sqlite3.connect("quests.db")
    cursor = conn.cursor()
    
    # クエストテーブルの作成
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS quests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        quest_type TEXT,
        content TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

# クエストを保存
def save_quest(user_id, quest_type, content):
    conn = sqlite3.connect("quests.db")
    cursor = conn.cursor()
    
    cursor.execute("INSERT INTO quests (user_id, quest_type, content) VALUES (?, ?, ?)", (user_id, quest_type, content))
    
    conn.commit()
    conn.close()

# ユーザーのクエストを取得
def get_quests(user_id):
    conn = sqlite3.connect("quests.db")
    cursor = conn.cursor()
    
    cursor.execute("SELECT quest_type, content FROM quests WHERE user_id = ?", (user_id,))
    quests = cursor.fetchall()
    
    conn.close()
    return quests