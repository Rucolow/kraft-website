# level_display.py
# レベル情報の表示関連の処理

import discord
from discord.ext import commands
from typing import Dict, Any, List
import datetime
from xp_calculator import get_daily_xp_cap

def create_level_embed(user: discord.Member, level_info: Dict[str, Any]) -> discord.Embed:
    """
    ユーザーのレベル情報を表示するEmbedを作成する関数
    
    Args:
        user: 表示対象のDiscordユーザー
        level_info: レベル情報のデータ
        
    Returns:
        discord.Embed: 表示用Embed
    """
    level = level_info["level"]
    xp = level_info["xp"]
    current_level_xp = level_info["current_level_xp"]
    next_level_xp = level_info["next_level_xp"]
    progress_percent = level_info["progress_percent"]
    titles = level_info["titles"]
    balance = level_info["balance"]
    completed_quests = level_info["completed_quests"]
    login_streak = level_info["login_streak"]
    today_xp = level_info["today_xp_earned"]
    daily_cap = level_info["daily_xp_cap"]
    
    # プログレスバーの作成
    progress_bar = "■" * (progress_percent // 5) + "□" * ((100 - progress_percent) // 5)
    
    # メインカラー（レベルに応じた色）
    if level >= 100:
        color = discord.Color.gold()  # 金色 (レベル100+)
    elif level >= 50:
        color = discord.Color.purple()  # 紫色 (レベル50-99)
    elif level >= 30:
        color = discord.Color.blue()  # 青色 (レベル30-49)
    elif level >= 10:
        color = discord.Color.green()  # 緑色 (レベル10-29)
    else:
        color = discord.Color.light_grey()  # 淡い灰色 (レベル1-9)
    
    embed = discord.Embed(
        title=f"🔰 {user.display_name} さんのレベル情報",
        color=color
    )
    
    embed.add_field(
        name="📊 レベル情報",
        value=(
            f"🏆 レベル: **{level}**\n"
            f"✨ 経験値: **{xp:,}** XP\n"
            f"📈 進捗: {progress_bar} ({progress_percent}%)\n"
            f"🔄 次のレベルまで: あと **{next_level_xp - current_level_xp:,}** XP\n"
            f"📅 本日の獲得XP: **{today_xp:,}** / **{daily_cap:,}** XP"
        ),
        inline=False
    )
    
    embed.add_field(
        name="👤 ユーザー情報",
        value=(
            f"💰 所持KR: **{balance:,}** KR\n"
            f"📝 クエスト達成: **{completed_quests}** 回\n"
            f"📱 ログイン日数: **{login_streak}** 日連続"
        ),
        inline=False
    )
    
    # 最高レベルの称号を見つける
    highest_level_title = "偉大なる一歩"  # デフォルト
    milestone_titles = {
        "生きる伝説": 100,
        "仙人": 90,
        "守護者": 80,
        "王者": 70,
        "英雄": 60,
        "達人": 50,
        "賢者": 40,
        "探求者": 30,
        "熟練冒険者": 20,
        "冒険者": 10,
        "新人冒険者": 5,
        "偉大なる一歩": 1
    }
    
    highest_level = 0
    for title in titles:
        if title in milestone_titles and milestone_titles[title] > highest_level:
            highest_level = milestone_titles[title]
            highest_level_title = title
    
    # 称号をカテゴリ分け
    milestone_title_list = []
    special_title_list = []
    
    for title in titles:
        if title in milestone_titles:
            milestone_title_list.append(title)
        else:
            special_title_list.append(title)
    
    embed.add_field(
        name="🏅 最高称号",
        value=f"**「{highest_level_title}」**",
        inline=False
    )
    
    if milestone_title_list:
        embed.add_field(
            name="📈 マイルストーン称号",
            value=", ".join([f"`{title}`" for title in milestone_title_list]),
            inline=False
        )
    
    if special_title_list:
        embed.add_field(
            name="🎖️ 特殊称号",
            value=", ".join([f"`{title}`" for title in special_title_list]),
            inline=False
        )
    
    embed.set_thumbnail(url=user.display_avatar.url)
    embed.set_footer(text=f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} • KRAFT")
    
    return embed

def create_ranking_embed(ranking_data: List[Dict[str, Any]]) -> discord.Embed:
    """
    レベルランキングを表示するEmbedを作成する関数
    
    Args:
        ranking_data: ランキングデータのリスト
        
    Returns:
        discord.Embed: 表示用Embed
    """
    embed = discord.Embed(
        title="🏆 サーバーレベルランキング TOP 10",
        color=discord.Color.gold()
    )
    
    # ランク表示用の絵文字
    rank_emojis = ["👑", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    # ランキングデータがない場合
    if not ranking_data:
        embed.description = "ランキングデータがありません。"
        return embed
    
    # ランキング情報を整形
    ranking_text = ""
    for i, user in enumerate(ranking_data):
        emoji = rank_emojis[i] if i < len(rank_emojis) else "•"
        ranking_text += f"{emoji} **{user['position']}位** {user['username']} - レベル **{user['level']}** (XP: {user['xp']:,})\n"
    
    embed.description = ranking_text
    embed.set_footer(text=f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} • KRAFT")
    
    return embed
