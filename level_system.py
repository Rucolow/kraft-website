# level_system.py
# レベルシステムの中核機能

import discord
import firebase_admin
from firebase_admin import firestore
import datetime
from typing import Dict, Any, Tuple, List, Optional
from xp_calculator import calculate_xp_for_level, check_and_update_daily_xp, get_daily_xp_cap

# Firestore参照をグローバル変数として定義
db = None

def get_db():
    global db
    if db is None:
        db = firestore.client()
    return db

async def add_xp_and_check_level_up(
    user_id: str, 
    xp_amount: int, 
    is_exempt: bool = False
) -> Tuple[bool, int, int, int, List[str]]:
    """
    ユーザーにXPを追加し、レベルアップを確認する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        xp_amount: 追加するXP量
        is_exempt: 日次上限の対象外かどうか
        
    Returns:
        Tuple[bool, int, int, int, List[str]]: (レベルアップしたか, 現在のレベル, 以前のレベル, 獲得したKR, 新しい称号リスト)
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    # ユーザーデータがない場合は新規作成
    if not user_doc.exists:
        user_data = {
            "level": 1,
            "xp": 0,
            "balance": 0,
            "titles": ["偉大なる一歩"],  # レベル1の称号を初期付与
            "today_xp_earned": 0,
            "last_xp_reset": datetime.datetime.utcnow().isoformat()
        }
    else:
        user_data = user_doc.to_dict()
        
        # 称号がない場合は初期化
        if "titles" not in user_data:
            user_data["titles"] = ["偉大なる一歩"]  # レベル1の称号を付与
    
    # 現在のレベルと経験値を取得
    current_level = user_data.get("level", 1)
    previous_level = current_level
    
    # XP追加と日次上限チェック
    actual_xp_added, reached_cap = check_and_update_daily_xp(user_data, xp_amount, is_exempt)
    
    # レベルアップ判定
    level_up = False
    kr_reward = 0
    new_titles = []
    
    while True:
        xp_for_next_level = calculate_xp_for_level(current_level)
        
        if user_data["xp"] >= xp_for_next_level:
            # レベルアップ
            current_level += 1
            level_up = True
            
            # KR報酬計算
            level_reward = get_level_reward(current_level)
            kr_reward += level_reward
            user_data["balance"] = user_data.get("balance", 0) + level_reward
            
            # 特定レベルでの称号付与
            new_title = await check_and_assign_level_titles(user_id, current_level, user_data)
            if new_title:
                new_titles.extend(new_title)
        else:
            break
    
    # レベル更新
    if level_up:
        user_data["level"] = current_level
    
    # データベース更新
    user_ref.set(user_data)
    
    return level_up, current_level, previous_level, kr_reward, new_titles

def get_level_reward(level: int) -> int:
    """レベルアップ時のKR報酬を計算する関数"""
    # 標準報酬: 100 × レベル + 50 (75→100に変更)
    base_reward = 100 * level + 50
    
    # マイルストーンレベルでの特別報酬
    if level == 100:
        return 15000  # 7500→15000に変更
    elif level == 50:
        return 7500   # 4000→7500に変更
    elif level == 25:
        return 3500   # 2000→3500に変更
    elif level == 10:
        return 1500   # 1000→1500に変更
    elif level == 5:
        return 750    # 500→750に変更
    
    return base_reward

async def check_and_assign_level_titles(
    user_id: str, 
    level: int, 
    user_data: Dict[str, Any]
) -> List[str]:
    """
    レベルに基づいて称号を付与する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        level: 現在のレベル
        user_data: ユーザーデータ
        
    Returns:
        List[str]: 新たに付与された称号のリスト
    """
    db = get_db()
    titles = set(user_data.get("titles", []))
    new_titles = []
    
    # レベルに応じた称号
    if level >= 100 and "生きる伝説" not in titles:
        titles.add("生きる伝説")
        new_titles.append("生きる伝説")
    elif level >= 90 and "仙人" not in titles:
        titles.add("仙人")
        new_titles.append("仙人")
    elif level >= 80 and "守護者" not in titles:
        titles.add("守護者")
        new_titles.append("守護者")
    elif level >= 70 and "王者" not in titles:
        titles.add("王者")
        new_titles.append("王者")
    elif level >= 60 and "英雄" not in titles:
        titles.add("英雄")
        new_titles.append("英雄")
    elif level >= 50 and "達人" not in titles:
        titles.add("達人")
        new_titles.append("達人")
    elif level >= 40 and "賢者" not in titles:
        titles.add("賢者")
        new_titles.append("賢者")
    elif level >= 30 and "探求者" not in titles:
        titles.add("探求者")
        new_titles.append("探求者")
    elif level >= 20 and "熟練冒険者" not in titles:
        titles.add("熟練冒険者")
        new_titles.append("熟練冒険者")
    elif level >= 10 and "冒険者" not in titles:
        titles.add("冒険者")
        new_titles.append("冒険者")
    elif level >= 5 and "新人冒険者" not in titles:
        titles.add("新人冒険者")
        new_titles.append("新人冒険者")
    
    # 称号が追加された場合、データベースを更新
    if new_titles:
        user_data["titles"] = list(titles)
        db.collection("users").document(user_id).set(user_data)
    
    return new_titles

async def get_level_info(user_id: str) -> Dict[str, Any]:
    """
    ユーザーのレベル情報を取得する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        
    Returns:
        Dict[str, Any]: レベル情報
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return {
            "level": 1,
            "xp": 0,
            "next_level_xp": calculate_xp_for_level(1),
            "progress_percent": 0,
            "titles": ["偉大なる一歩"],  # レベル1の称号を初期付与
            "balance": 0,
            "completed_quests": 0,
            "login_streak": 0,
            "today_xp_earned": 0,
            "daily_xp_cap": get_daily_xp_cap(1)
        }
    
    user_data = user_doc.to_dict()
    
    level = user_data.get("level", 1)
    xp = user_data.get("xp", 0)
    next_level_xp = calculate_xp_for_level(level)
    
    # 前のレベルまでの累積XPを計算
    previous_levels_xp = 0
    for l in range(1, level):
        previous_levels_xp += calculate_xp_for_level(l)
    
    # 現在のレベルでの進捗
    current_level_progress = xp - previous_levels_xp
    progress_percent = min(100, int((current_level_progress / next_level_xp) * 100))
    
    # 称号がない場合は初期化
    if "titles" not in user_data or not user_data["titles"]:
        user_data["titles"] = ["偉大なる一歩"]
        user_ref.set(user_data, merge=True)
    
    return {
        "level": level,
        "xp": xp,
        "current_level_xp": current_level_progress,
        "next_level_xp": next_level_xp,
        "progress_percent": progress_percent,
        "titles": user_data.get("titles", ["偉大なる一歩"]),
        "balance": user_data.get("balance", 0),
        "completed_quests": user_data.get("completed_quests", 0),
        "login_streak": user_data.get("login_streak", 0),
        "today_xp_earned": user_data.get("today_xp_earned", 0),
        "daily_xp_cap": get_daily_xp_cap(level)
    }

async def get_level_ranking(limit: int = 10) -> List[Dict[str, Any]]:
    """
    レベルランキングを取得する関数
    
    Args:
        limit: 取得する上位ユーザー数
        
    Returns:
        List[Dict[str, Any]]: ランキングデータ
    """
    db = get_db()
    users_ref = db.collection("users").order_by("level", direction=firestore.Query.DESCENDING).order_by("xp", direction=firestore.Query.DESCENDING).limit(limit)
    users = users_ref.stream()
    
    ranking = []
    for i, user in enumerate(users):
        user_data = user.to_dict()
        
        # Discordユーザー情報を取得
        discord_user = None
        try:
            from bot import bot  # botインスタンスをインポート
            discord_user = await bot.fetch_user(int(user.id))
        except Exception as e:
            print(f"ユーザー情報取得エラー: {e}")
        
        ranking.append({
            "position": i + 1,
            "user_id": user.id,
            "username": discord_user.name if discord_user else user_data.get("username", "Unknown"),
            "level": user_data.get("level", 1),
            "xp": user_data.get("xp", 0),
            "avatar_url": str(discord_user.avatar.url) if discord_user and discord_user.avatar else None
        })
    
    return ranking