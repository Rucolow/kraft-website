# title_manager.py
# 新しい称号システム管理モジュール

import discord
import firebase_admin
from firebase_admin import firestore
import datetime
from typing import Dict, Any, Tuple, List, Optional, Set

# Firestore参照
db = None

def get_db():
    global db
    if db is None:
        db = firestore.client()
    return db

async def check_activity_titles(user_id: str, message: discord.Message) -> List[str]:
    """
    アクティビティベース称号をチェック・付与する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        message: 投稿されたメッセージオブジェクト
        
    Returns:
        List[str]: 新たに獲得した称号のリスト
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return []
    
    user_data = user_doc.to_dict()
    titles = set(user_data.get("titles", []))
    new_titles = []
    
    # 月間メッセージ数の更新
    now = datetime.datetime.utcnow()
    last_monthly_reset = user_data.get("last_monthly_reset", "2025-01-01T00:00:00")
    
    try:
        last_reset = datetime.datetime.fromisoformat(last_monthly_reset)
    except ValueError:
        last_reset = datetime.datetime.strptime(last_monthly_reset, "%Y-%m-%dT%H:%M:%S")
    
    # 月が変わっていればリセット
    if now.month != last_reset.month or now.year != last_reset.year:
        user_data["monthly_messages"] = 0
        user_data["active_channels"] = []
        user_data["last_monthly_reset"] = now.isoformat()
    
    # 月間メッセージ数を増加
    monthly_messages = user_data.get("monthly_messages", 0) + 1
    user_data["monthly_messages"] = monthly_messages
    
    # アクティブチャンネルを記録
    active_channels = set(user_data.get("active_channels", []))
    channel_id = str(message.channel.id)
    active_channels.add(channel_id)
    user_data["active_channels"] = list(active_channels)
    
    # よく喋る人・エミネム称号チェック
    if monthly_messages >= 1000 and "エミネム" not in titles:
        titles.add("エミネム")
        new_titles.append("エミネム")
        # よく喋る人も自動で付与
        if "よく喋る人" not in titles:
            titles.add("よく喋る人")
    elif monthly_messages >= 500 and "よく喋る人" not in titles:
        titles.add("よく喋る人")
        new_titles.append("よく喋る人")
    
    # どこにでもいる人称号チェック
    if len(active_channels) >= 10 and "どこにでもいる人" not in titles:
        titles.add("どこにでもいる人")
        new_titles.append("どこにでもいる人")
    
    # データ更新
    user_data["titles"] = list(titles)
    user_ref.set(user_data)
    
    return new_titles

async def check_quest_failure_titles(user_id: str) -> List[str]:
    """
    クエスト失敗関連称号をチェック・付与する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        
    Returns:
        List[str]: 新たに獲得した称号のリスト
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return []
    
    user_data = user_doc.to_dict()
    titles = set(user_data.get("titles", []))
    new_titles = []
    
    consecutive_failures = user_data.get("consecutive_quest_failures", 0)
    
    # 逆にすごい称号チェック（10連続失敗）
    if consecutive_failures >= 10 and "逆にすごい" not in titles:
        titles.add("逆にすごい")
        new_titles.append("逆にすごい")
        # どんまいも自動で付与
        if "どんまい" not in titles:
            titles.add("どんまい")
    # どんまい称号チェック（2連続失敗）
    elif consecutive_failures >= 2 and "どんまい" not in titles:
        titles.add("どんまい")
        new_titles.append("どんまい")
    
    # データ更新
    user_data["titles"] = list(titles)
    user_ref.set(user_data)
    
    return new_titles

async def on_quest_failure(user_id: str) -> List[str]:
    """
    クエスト失敗時に呼び出される関数
    
    Args:
        user_id: ユーザーのDiscord ID
        
    Returns:
        List[str]: 新たに獲得した称号のリスト
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    user_data = user_doc.to_dict() if user_doc.exists else {}
    
    # 連続失敗数を増加
    consecutive_failures = user_data.get("consecutive_quest_failures", 0) + 1
    user_data["consecutive_quest_failures"] = consecutive_failures
    
    user_ref.set(user_data, merge=True)
    
    # 失敗関連称号チェック
    return await check_quest_failure_titles(user_id)

async def on_quest_success(user_id: str):
    """
    クエスト成功時に呼び出される関数（失敗カウンターリセット）
    
    Args:
        user_id: ユーザーのDiscord ID
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    
    # 連続失敗数をリセット
    user_ref.update({"consecutive_quest_failures": 0})

async def remove_deprecated_titles(user_id: str) -> int:
    """
    削除予定の称号を除去する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        
    Returns:
        int: 削除した称号の数
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return 0
    
    user_data = user_doc.to_dict()
    titles = set(user_data.get("titles", []))
    
    # 削除対象の称号
    deprecated_titles = {
        "冒険の始まり",
        "成長の兆し",
        "継続は力なり",
        "成長の上昇気流",
        "コンシステント",
        "村の救世主",
        "ノーリターン",
        "秘密の共有者"
    }
    
    # 削除実行
    original_count = len(titles)
    titles = titles - deprecated_titles
    removed_count = original_count - len(titles)
    
    if removed_count > 0:
        user_data["titles"] = list(titles)
        user_ref.set(user_data)
    
    return removed_count

async def cleanup_all_deprecated_titles() -> Dict[str, int]:
    """
    全ユーザーから削除予定称号を除去する関数
    
    Returns:
        Dict[str, int]: {"total_users": 処理したユーザー数, "total_removed": 削除した称号数}
    """
    db = get_db()
    users_ref = db.collection("users")
    users = users_ref.stream()
    
    total_users = 0
    total_removed = 0
    
    for user_doc in users:
        user_id = user_doc.id
        removed_count = await remove_deprecated_titles(user_id)
        total_users += 1
        total_removed += removed_count
        
        if removed_count > 0:
            print(f"ユーザー {user_id} から {removed_count} 個の称号を削除しました")
    
    return {"total_users": total_users, "total_removed": total_removed}

async def get_user_title_progress(user_id: str) -> Dict[str, Any]:
    """
    ユーザーの称号獲得進捗を取得する関数
    
    Args:
        user_id: ユーザーのDiscord ID
        
    Returns:
        Dict[str, Any]: 進捗情報
    """
    db = get_db()
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    
    if not user_doc.exists:
        return {}
    
    user_data = user_doc.to_dict()
    
    # 現在の進捗
    monthly_messages = user_data.get("monthly_messages", 0)
    active_channels = len(user_data.get("active_channels", []))
    consecutive_failures = user_data.get("consecutive_quest_failures", 0)
    current_titles = user_data.get("titles", [])
    
    # 進捗情報を構築
    progress = {
        "current_titles": current_titles,
        "activity_progress": {
            "monthly_messages": monthly_messages,
            "messages_to_yoku_shaberu": max(0, 500 - monthly_messages) if "よく喋る人" not in current_titles else 0,
            "messages_to_eminem": max(0, 1000 - monthly_messages) if "エミネム" not in current_titles else 0,
            "active_channels": active_channels,
            "channels_to_doko_ni_demo": max(0, 10 - active_channels) if "どこにでもいる人" not in current_titles else 0
        },
        "failure_progress": {
            "consecutive_failures": consecutive_failures,
            "failures_to_donmai": max(0, 3 - consecutive_failures) if "どんまい" not in current_titles else 0,
            "failures_to_gyaku_ni_sugoi": max(0, 10 - consecutive_failures) if "逆にすごい" not in current_titles else 0
        }
    }
    
    return progress

# bot.py への統合用関数
async def integrate_title_system_to_message_handler(message: discord.Message, user_id: str) -> List[str]:
    """
    メッセージハンドラーに統合する称号チェック関数
    
    Args:
        message: Discordメッセージオブジェクト
        user_id: ユーザーID
        
    Returns:
        List[str]: 新たに獲得した称号のリスト
    """
    # アクティビティ関連称号チェック
    new_titles = await check_activity_titles(user_id, message)
    
    return new_titles

# 期限切れクエストチェック時の統合用関数
async def integrate_title_system_to_quest_expiry(expired_quest_users: List[str]) -> Dict[str, List[str]]:
    """期限切れクエスト処理に統合する称号チェック関数"""
    results = {}
    
    for user_id in expired_quest_users:
        new_titles = await on_quest_failure(user_id)
        if new_titles:
            results[user_id] = new_titles
            
            # Discord通知を追加
            try:
                from bot import bot  # botインスタンスをインポート
                user = await bot.fetch_user(int(user_id))
                channel = bot.get_channel(1352859030715891782)
                if channel and user:
                    for title in new_titles:
                        embed = discord.Embed(
                            title="🏅 新称号獲得！",
                            description=f"{user.mention} が称号 **『{title}』** を獲得しました！",
                            color=discord.Color.gold()
                        )
                        await channel.send(embed=embed)
            except Exception as e:
                print(f"通知送信エラー: {e}")
    
    return results