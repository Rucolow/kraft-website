# level_commands.py
# レベル関連のSlash Commandを定義（不要コマンド削除済み）

import discord
from discord import app_commands
from discord.ext import commands
import firebase_admin
from firebase_admin import firestore

db = None

def get_db():
    global db
    if db is None:
        db = firestore.client()
    return db

class LevelCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @app_commands.command(name="xpガイド", description="経験値システムについての説明を表示します")
    async def xp_guide(self, interaction: discord.Interaction):
        """経験値獲得方法とレベルシステムについてのガイドを表示します"""
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="✨ XP獲得ガイド",
            description="KRAFTでの経験値(XP)獲得方法と仕組みについての説明です。",
            color=discord.Color.blurple()
        )
        
        embed.add_field(
            name="📝 メッセージ投稿",
            value=(
                "• 基本: 1投稿につき **10 XP**\n"
                "• 長文ボーナス: 15文字ごとに **+1 XP** (最大 **+20 XP**)\n"
                "• 連続投稿: 1日に10回以上で **+20 XP**\n"
                "• クールダウン: 30秒間隔でXP獲得可能\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🎯 クエスト達成",
            value=(
                "• 週間クエスト: **200 XP**\n"
                "• 月間クエスト: **600 XP**\n"
                "• 年間クエスト: **2000 XP**\n"
                "• 連続達成: 3回連続達成で **+200 XP**\n"
                "• 早期達成ボーナス: 期日前達成で **+30%**\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💰 コミュニティ貢献",
            value=(
                "• 寄付: 100KRにつき **10 XP**\n"
                "• 送金: 100KRにつき **5 XP**\n"
                "• 注: これらは日次上限の対象外\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🔄 ボーナスタイム",
            value=(
                "• 月初/月末: 月の初日・最終日の5日間は **2倍 XP**\n"
                "• 称号ボーナス: 称号によって **追加XP**\n"
                "• 連続投稿: 1日10回以上の投稿で **+20 XP**\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📊 日次XP上限",
            value=(
                "レベル1-10: **1,000 XP/日**\n"
                "レベル11-30: **2,000 XP/日**\n"
                "レベル31-60: **3,000 XP/日**\n"
                "レベル61+: **4,000 XP/日**\n"
                "※クエスト達成は上限対象外\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="🏅 マイルストーン称号",
            value=(
                "レベル1: `偉大なる一歩`\n"
                "レベル5: `新人冒険者` - メッセージXP +5%\n"
                "レベル10: `冒険者` - 日次XP上限 +5%\n"
                "レベル20: `熟練冒険者` - クエストXP +5%\n"
                "レベル30: `探求者` - 送金XP +10%\n"
                "レベル50: `達人` - すべてのXP +5%\n"
                "レベル100: `生きる伝説` - すべてのXP +15%\n"
            ),
            inline=False
        )
        
        embed.add_field(
            name="💡 効率的なレベルアップのコツ",
            value=(
                "• 毎日コンスタントにメッセージ投稿\n"
                "• クエストを積極的に設定・達成\n"
                "• 月初・月末の2倍期間を活用\n"
                "• 長文投稿でボーナスXPを狙う\n"
                "• コミュニティ貢献（寄付・送金）も有効\n"
            ),
            inline=False
        )
        
        embed.set_footer(text="詳細な情報は /プロフィール で確認できます")
        
        await interaction.followup.send(embed=embed)

# Botへの登録関数
def setup(bot):
    bot.add_cog(LevelCommands(bot))