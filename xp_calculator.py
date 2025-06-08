# xp_calculator.py
# XP獲得量計算のための関数群

import datetime
from typing import Dict, Tuple, List, Any, Optional

def calculate_xp_for_level(level: int) -> int:
    """レベルアップに必要なXPを計算する関数"""
    if level <= 10:
        return 50 * (level ** 1.8)  # 初期レベルは達成しやすく
    elif level <= 30:
        return 80 * (level ** 1.9)  # 中盤は標準的な難易度
    elif level <= 60:
        return 75 * (level ** 2) + 200 * (level - 30)  # 後半は徐々に難化
    else:
        return 75 * (level ** 2) + 200 * 30 + 100 * (level - 60)  # 最終段階は長期目標に

def get_message_xp(message_content: str, user_data: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """メッセージ投稿からのXP獲得量を計算する関数"""
    now = datetime.datetime.utcnow()
    
    # 基本XP
    base_xp = 10  # 3→10に変更
    
    # 長文ボーナス: 15文字ごとに+1XP (上限20XP)
    length_bonus = min(len(message_content) // 15, 20)  # 20→15に変更、上限10→20に変更
    
    # 称号ボーナス (非累積)
    titles = user_data.get("titles", [])
    title_bonus = 1.0
    
    # 最高レベルの称号のみボーナスを適用
    max_level = 0
    max_level_title = None
    
    for title in titles:
        if title == "エミネム":
            # 特殊称号は別処理
            title_bonus = 1.3  # 長文投稿XP +30%
            break
        elif title == "よく喋る人":
            title_bonus = 1.2  # メッセージXP +20%
            break
        # マイルストーン称号の処理
        elif title == "生きる伝説":
            if max_level < 100:
                max_level = 100
                max_level_title = title
        elif title == "仙人":
            if max_level < 90:
                max_level = 90
                max_level_title = title
        elif title == "守護者":
            if max_level < 80:
                max_level = 80
                max_level_title = title
        elif title == "王者":
            if max_level < 70:
                max_level = 70
                max_level_title = title
        elif title == "英雄":
            if max_level < 60:
                max_level = 60
                max_level_title = title
        elif title == "達人":
            if max_level < 50:
                max_level = 50
                max_level_title = title
        elif title == "探求者":
            if max_level < 30:
                max_level = 30
                max_level_title = title
        elif title == "熟練冒険者":
            if max_level < 20:
                max_level = 20
                max_level_title = title
        elif title == "冒険者":
            if max_level < 10:
                max_level = 10
                max_level_title = title
        elif title == "新人冒険者":
            if max_level < 5:
                max_level = 5
                max_level_title = title
    
    # マイルストーン称号によるボーナス適用
    if max_level_title and title_bonus == 1.0:
        if max_level == 100:
            title_bonus = 1.15  # すべてのXP +15%
        elif max_level == 50:
            title_bonus = 1.05  # すべてのXP +5%
        elif max_level == 10:
            title_bonus = 1.05  # 日次XP上限 +5%（ここでは計算に含めない）
        elif max_level == 5:
            title_bonus = 1.05  # メッセージXP +5%
    
    # 時期ボーナス
    month_bonus = 1.0
    
    # 月初/月末ボーナス (月の初日と最終日の5日間は2倍) - 1.5→2.0に変更
    if now.day <= 5 or now.day >= (now.replace(day=28) + datetime.timedelta(days=4)).day - 5:
        month_bonus = 2.0
    
    # 連続投稿ボーナス (1日10件以上の投稿で+20XP) - 5→20に変更
    today_messages = user_data.get("today_messages", 0)
    continuous_bonus = 20 if today_messages >= 10 else 0
    
    # 合計XP計算
    total_xp = int((base_xp + length_bonus) * title_bonus * month_bonus) + continuous_bonus
    
    # 詳細情報（デバッグ用）
    details = {
        "base_xp": base_xp,
        "length_bonus": length_bonus,
        "title_bonus": title_bonus,
        "month_bonus": month_bonus,
        "continuous_bonus": continuous_bonus,
        "total_xp": total_xp
    }
    
    return total_xp, details

def get_quest_xp(quest_type: str, elapsed_time_ratio: float, streak_count: int, user_data: Dict[str, Any]) -> int:
    """クエスト達成からのXP獲得量を計算する関数"""
    # 基本XP報酬
    base_rewards = {
        "weekly": 200,   # 120→200に変更
        "monthly": 600,  # 400→600に変更
        "yearly": 2000   # 3000→2000に変更
    }
    
    base_xp = base_rewards.get(quest_type, 0)
    
    # 連続達成ボーナス (3回以上の連続達成で+200XP) - 100→200に変更
    streak_bonus = 200 if streak_count >= 3 else 0
    
    # 称号ボーナス
    titles = user_data.get("titles", [])
    title_bonus = 1.0
    
    # マイルストーン称号の処理
    max_level = 0
    
    for title in titles:
        # 特定の称号の処理
        if title == "クエストマスター":
            title_bonus = 1.2  # +20%
            break
            
        # マイルストーン称号の処理
        elif title == "生きる伝説":
            if max_level < 100:
                max_level = 100
        elif title == "仙人":
            if max_level < 90:
                max_level = 90
        elif title == "熟練冒険者":
            if max_level < 20:
                max_level = 20
                
    # マイルストーン称号によるボーナス適用
    if title_bonus == 1.0 and max_level == 20:
        title_bonus = 1.05  # クエストXP +5%
    
    # 最終計算
    total_xp = int(base_xp * title_bonus) + streak_bonus
    
    return total_xp

def get_daily_xp_cap(level: int) -> int:
    """レベルに応じた1日あたりのXP上限を取得する関数"""
    if level <= 10:
        return 1000  # 500→1000に変更
    elif level <= 30:
        return 2000  # 1000→2000に変更
    elif level <= 60:
        return 3000  # 1500→3000に変更
    else:
        return 4000  # 2000→4000に変更

def check_and_update_daily_xp(user_data: Dict[str, Any], xp_to_add: int, is_exempt: bool = False) -> Tuple[int, bool]:
    """
    1日あたりのXP上限をチェックし、XPを加算する関数
    
    Args:
        user_data: ユーザーデータ
        xp_to_add: 加算するXP量
        is_exempt: 上限対象外かどうか（クエスト報酬など）
        
    Returns:
        Tuple[int, bool]: (実際に加算されたXP, 上限に達したかどうか)
    """
    now = datetime.datetime.utcnow()
    last_reset_str = user_data.get("last_xp_reset", "2000-01-01T00:00:00")
    
    # ISO形式の文字列からdatetimeに変換
    try:
        last_reset = datetime.datetime.fromisoformat(last_reset_str)
    except ValueError:
        # 互換性のために旧形式もサポート
        last_reset = datetime.datetime.strptime(last_reset_str, "%Y-%m-%dT%H:%M:%S")
    
    # 日付が変わっていればリセット
    if now.date() > last_reset.date():
        user_data["today_xp_earned"] = 0
        user_data["last_xp_reset"] = now.isoformat()
    
    # 免除対象（クエスト達成など）の場合は上限チェックをスキップ
    if is_exempt:
        user_data["xp"] = user_data.get("xp", 0) + xp_to_add
        return xp_to_add, False
    
    # 現在の日次XP獲得量
    today_xp = user_data.get("today_xp_earned", 0)
    
    # 上限を計算
    level = user_data.get("level", 1)
    daily_cap = get_daily_xp_cap(level)
    
    # 称号による上限増加ボーナス適用
    titles = user_data.get("titles", [])
    cap_bonus = 1.0
    
    # 最高レベルの称号のみボーナスを適用
    max_level = 0
    
    for title in titles:
        if title == "守護者":
            cap_bonus = 1.1  # 日次XP上限 +10%
            break
        elif title == "冒険者" and max_level < 10:
            max_level = 10
            cap_bonus = 1.05  # 日次XP上限 +5%
    
    # 上限にボーナスを適用
    daily_cap = int(daily_cap * cap_bonus)
    
    # 上限に達しているかチェック
    if today_xp >= daily_cap:
        return 0, True  # 上限に達した場合、0XPを返し、上限フラグをTrue
    
    # 上限を超えないように調整
    actual_xp_to_add = min(xp_to_add, daily_cap - today_xp)
    
    # XPを追加して更新
    user_data["xp"] = user_data.get("xp", 0) + actual_xp_to_add
    user_data["today_xp_earned"] = today_xp + actual_xp_to_add
    
    # 上限に達したかどうか
    reached_cap = (today_xp + actual_xp_to_add) >= daily_cap
    
    return actual_xp_to_add, reached_cap