import os
import discord
from discord import app_commands
from discord.ext import commands, tasks
from dotenv import load_dotenv
import firebase_admin
from firebase_admin import credentials, firestore
import asyncio
import datetime
import re
from collections import Counter, defaultdict
from typing import Optional, List, Dict, Any, Union, cast, NoReturn, Awaitable
from discord.types.interactions import (
    ChatInputApplicationCommandInteractionData,
    UserApplicationCommandInteractionData,
    MessageApplicationCommandInteractionData,
    ButtonMessageComponentInteractionData,
    SelectMessageComponentInteractionData,
    ModalSubmitInteractionData
)

# レベルシステム関連のインポート
from level_commands import LevelCommands
from level_display import create_level_embed
from xp_calculator import get_message_xp, get_quest_xp, get_daily_xp_cap

# ニュース生成器（エラーハンドリング追加）
try:
    from news_generator import NewsGenerator
    news_generator: Optional[NewsGenerator] = NewsGenerator()
    NEWS_SYSTEM_ENABLED: bool = True
    print("✅ ニュース生成システム読み込み成功")
except ImportError as e:
    print(f"⚠️ ニュース生成システム読み込み失敗: {e}")
    NEWS_SYSTEM_ENABLED = False
    news_generator = None

import asyncio
import random

# 投資ニュース専用チャンネルID（適切なチャンネルIDに変更してください）
INVESTMENT_NEWS_CHANNEL_ID = 1378237887446777997  # 既存のお知らせチャンネルを使用

# ニュース生成器初期化
news_generator = NewsGenerator()

try:
    from title_manager import (
        integrate_title_system_to_message_handler,
        integrate_title_system_to_quest_expiry,
        on_quest_success,
        cleanup_all_deprecated_titles,
        get_user_title_progress
    )
    TITLE_SYSTEM_ENABLED = True
    print("✅ 称号システムモジュール読み込み成功")
except ImportError as e:
    TITLE_SYSTEM_ENABLED = False
    print(f"⚠️ 称号システムモジュール読み込み失敗: {e}")

# .env を読み込む
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

# Firestore 初期化
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# 称号獲得をDiscordに通知する関数
async def post_title_announcement(bot: discord.Client, user: discord.Member, title: str) -> Optional[discord.Message]:
    """
    指定ユーザーの称号獲得を通知チャンネルに送信します。
    """
    channel_id = 1352859030715891782  # #称号獲得のお知らせチャンネル
    channel = bot.get_channel(channel_id)
    if isinstance(channel, discord.TextChannel):
        return await channel.send(f"🎉 {user.mention} が新しい称号 **『{title}』** を獲得しました！")
    else:
        print(f"⚠️ 通知チャンネルが見つかりません（ID: {channel_id}）")
        return None

# 通知システムのインポート
from notification_system import NotificationSystem

# Bot 定義
class KraftBot(commands.Bot):
    """
    KRAFT Discord Bot本体クラス。
    通知システムの初期化・バッチ管理・コグ登録などを行う。
    """
    notification_system: Optional[NotificationSystem]

    def __init__(self) -> None:
        """
        KraftBotの初期化。
        """
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)
        self.notification_system: Optional[NotificationSystem] = None
    
    async def setup_hook(self) -> None:
        """
        Botの起動時に実行される初期化処理。
        通知システムの初期化とバッチ処理の開始を行う。
        """
        self.notification_system = NotificationSystem(self)
        await self.notification_system.start_batch_processing()

    async def close(self) -> None:
        """
        Botのシャットダウン時に実行される処理。
        通知システムのバッチ処理を停止し、Botを終了する。
        """
        if self.notification_system:
            await self.notification_system.stop_batch_processing()
        await super().close()
    
    async def on_ready(self) -> None:
        """
        BotがDiscordに接続されたときに呼ばれるイベント。
        コグの登録や初期化処理を行う。
        """
        if self.user:
            print(f"{self.user.name} がログインしました！")
        try:
            # コグの登録
            await self.add_cog(LevelCommands(self))
            
            synced = await self.tree.sync()
            print(f"✅ {len(synced)} 個のコマンドが同期されました！")
            
            if not check_expired_quests.is_running():
                check_expired_quests.start()
                print("✅ バックグラウンドタスク開始")

            if not auto_generate_news.is_running():
                auto_generate_news.start()
                print("✅ 自動ニュース生成システム開始")
                
        except Exception as e:
            print(f"❌ コマンド同期エラー: {e}")

    async def _send_message(
        self,
        channel: Union[discord.TextChannel, discord.Thread],
        content: str,
        **kwargs: Any
    ) -> Optional[discord.Message]:
        try:
            return await channel.send(content, **kwargs)
        except discord.Forbidden:
            print(f"メッセージ送信に失敗しました: {channel.name}")
            return None

    async def _add_role(
        self,
        member: discord.Member,
        role: discord.Role
    ) -> bool:
        try:
            await member.add_roles(role)
            return True
        except discord.Forbidden:
            print(f"ロール付与に失敗しました: {member.name}")
            return False

    async def _get_interaction_values(
        self,
        data: Optional[Union[
            ChatInputApplicationCommandInteractionData,
            UserApplicationCommandInteractionData,
            MessageApplicationCommandInteractionData,
            ButtonMessageComponentInteractionData,
            SelectMessageComponentInteractionData,
            ModalSubmitInteractionData
        ]]
    ) -> List[str]:
        if data:
            # TypedDict型はisinstanceで判定できないため、component_typeや特徴的なキーで判定
            if isinstance(data, dict) and data.get('component_type') == 3 and 'values' in data:
                # SelectMessageComponentInteractionData
                return data.get("values", [])
            elif isinstance(data, dict) and data.get('component_type') == 2 and 'custom_id' in data:
                # ButtonMessageComponentInteractionData
                return [data.get("custom_id", "")]
        return []

    async def _handle_donation(
        self,
        interaction: discord.Interaction,
        amount: int,
        user: discord.Member
    ) -> Optional[discord.Message]:
        try:
            channel = self.get_channel(1352859030715891782)
            if isinstance(channel, discord.TextChannel):
                return await channel.send(f"🎁 **{user.display_name}** さんが「{amount}KR」を寄付しました！")
            else:
                print(f"⚠️ 通知チャンネルが見つかりません（ID: {1352859030715891782})")
                return None
        except Exception as e:
            print(f"寄付通知送信エラー: {e}")
            return None

    async def _handle_quest_completion(
        self,
        interaction: discord.Interaction,
        quest_name: str,
        user: discord.Member
    ) -> None:
        try:
            quest_ref = db.collection("quests").document(str(user.id))
            quest_data = quest_ref.get().to_dict()
            if quest_data:
                quest_data["completed_quests"] = quest_data.get("completed_quests", 0) + 1
                quest_ref.set(quest_data)
        except Exception as e:
            print(f"クエストデータ更新エラー: {e}")

    async def _handle_level_up(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        new_level: int
    ) -> None:
        try:
            user_ref = db.collection("users").document(str(user.id))
            user_data = user_ref.get().to_dict()
            if user_data:
                user_data["level"] = new_level
                user_ref.set(user_data)
        except Exception as e:
            print(f"レベルアップデータ更新エラー: {e}")

TITLE_ANNOUNCEMENT_CHANNEL_ID = 1352859030715891782  # 通知チャンネルID（#称号ログなど）

async def assign_discord_role(interaction: discord.Interaction, role_name: str) -> None:
    """
    指定したロール名のDiscordロールをユーザーに付与し、通知チャンネルにメッセージを送信します。
    """
    guild: Optional[discord.Guild] = interaction.guild
    if not guild:
        return

    role: Optional[discord.Role] = discord.utils.get(guild.roles, name=role_name)
    user = interaction.user
    if role and isinstance(user, discord.Member) and role not in user.roles:
        try:
            await user.add_roles(role)
            print(f"{user.name} に称号「{role_name}」を付与しました")

            # 🎉 通知を指定チャンネルに送信
            channel: Optional[discord.abc.GuildChannel] = guild.get_channel(TITLE_ANNOUNCEMENT_CHANNEL_ID)
            if isinstance(channel, discord.TextChannel):
                await channel.send(f"🏅 {user.mention} が称号「{role_name}」を獲得しました！")

        except Exception as e:
            print(f"ロール付与エラー: {e}")

# 称号とロールの対応表（ギルド関連削除済み）
TITLE_ROLE_MAP = {
    "冒険の始まり": "冒険の始まり",
    "成長の兆し": "成長の兆し",
    "継続は力なり": "継続は力なり",
    "成長の上昇気流": "成長の上昇気流",
    "どんまい": "どんまい",
    "逆にすごい": "逆にすごい",
    "クエストマスター": "クエストマスター",
    "村の救世主": "村の救世主",
    "寄付マスター": "寄付マスター",
    "聖人": "聖人",
    "投資マスター": "投資マスター",
    "ノーリターン": "ノーリターン",
    "ギフトマスター": "ギフトマスター",
    "大盤振る舞い": "大盤振る舞い",
    "ギャンブルマスター": "ギャンブルマスター",
    "ギャンブル狂い": "ギャンブル狂い",
    "地獄の入り口": "地獄の入り口",
    "秘密の共有者": "秘密の共有者",
    "どこにでもいる人": "どこにでもいる人",
    "よく喋る人": "よく喋る人",
    "エミネム": "エミネム"
}

bot = KraftBot()
tree = bot.tree

# --------------------------------------
# ✅ 寄付関連コマンド
# --------------------------------------

class DonationView(discord.ui.View):
    def __init__(self, user_id: str, amount: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.amount = amount
        self.donation_options: List[discord.SelectOption] = []
        self.init_select_menu()
    
    def init_select_menu(self) -> None:
        """Firestoreから寄付先を取得してSelect Menuを初期化（安定版）"""
        try:
            print(f"寄付先取得開始 - ユーザー: {self.user_id}, 金額: {self.amount}")
            
            # Firestoreから寄付先を取得
            donation_targets_ref = db.collection("donation_targets")
            targets = list(donation_targets_ref.stream())
            
            print(f"Firestore query結果: {len(targets)}件の寄付先を取得")
            
            options = []
            for target_doc in targets:
                target_name = target_doc.id
                target_data = target_doc.to_dict()
                description = target_data.get("description", "寄付先")
                
                print(f"  寄付先: {target_name} - {description}")
                
                # 説明が長すぎる場合は短縮
                if len(description) > 80:
                    description = description[:77] + "..."
                
                # Discord SelectOptionの文字数制限を考慮
                if len(target_name) > 100:
                    target_name = target_name[:97] + "..."
                
                options.append(discord.SelectOption(
                    label=target_name,
                    description=description,
                    value=target_name
                ))
            
            # 寄付先が1つもない場合
            if not options:
                print("寄付先が見つかりません")
                options.append(discord.SelectOption(
                    label="寄付先がありません",
                    description="運営に寄付先の追加をリクエストしてください",
                    value="no_targets"
                ))
            
            # Discord Selectの制限：最大25個まで
            if len(options) > 25:
                options = options[:25]
                print(f"寄付先を25件に制限しました")
            
            # Select Menu作成
            select: discord.ui.Select = discord.ui.Select(
                placeholder="寄付先を選択してください...",
                options=options,
                min_values=1,
                max_values=1
            )
            select.callback = self.select_callback
            self.add_item(select)
            
            self.donation_options: List[discord.SelectOption] = options
            print(f"Select Menu作成完了: {len(options)}個のオプション")
            
        except Exception as e:
            print(f"寄付先取得エラー: {e}")
            print(f"エラー詳細: {type(e).__name__}: {str(e)}")
            
            # エラー時のフォールバック
            try:
                error_options = [discord.SelectOption(
                    label="エラー：寄付先を取得できません",
                    description="しばらく時間をおいて再度お試しください",
                    value="error"
                )]
                
                select = discord.ui.Select(
                    placeholder="エラーが発生しました...",
                    options=error_options
                )
                select.callback = self.select_callback
                self.add_item(select)
                
                print("エラー用Select Menu作成完了")
                
            except Exception as fallback_error:
                print(f"フォールバック処理もエラー: {fallback_error}")
    
    async def select_callback(self, interaction: discord.Interaction) -> None:
        """寄付先選択時のコールバック処理"""
        try:
            print(f"寄付先選択コールバック開始 - ユーザー: {interaction.user.id}")
            
            selected_value = interaction.data['values'][0]
            print(f"選択された寄付先: {selected_value}")
            
            if selected_value == "no_targets":
                await interaction.response.send_message(
                    "❌ 現在利用可能な寄付先がありません。\n"
                    "運営に寄付先の追加をリクエストしてください。",
                    ephemeral=True
                )
                return
            elif selected_value == "error":
                await interaction.response.send_message(
                    "❌ システムエラーが発生しました。\n"
                    "しばらく時間をおいて再度お試しください。",
                    ephemeral=True
                )
                return
            
            # 選択された寄付先に寄付実行
            await self.process_donation(interaction, selected_value)
            
        except Exception as e:
            print(f"選択コールバックエラー: {e}")
            try:
                await interaction.response.send_message(
                    f"❌ 処理中にエラーが発生しました: {str(e)}",
                    ephemeral=True
                )
            except:
                await interaction.followup.send(
                    f"❌ 処理中にエラーが発生しました: {str(e)}",
                    ephemeral=True
                )
    
    async def process_donation(self, interaction: discord.Interaction, target: str) -> None:
        """寄付処理を実行（安定版）"""
        try:
            print(f"寄付処理開始: {target} に {self.amount}KR")
            await interaction.response.defer()
            
            user_ref = db.collection("users").document(self.user_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                await interaction.followup.send("❌ ユーザー情報が見つかりませんでした。")
                return
            
            user_data = user_doc.to_dict()
            balance = user_data.get("balance", 0)
            
            # 残高確認（二重チェック）
            if balance < self.amount:
                await interaction.followup.send(f"💸 残高不足です。現在の残高は {balance:,}KR です。")
                return
            
            # 残高から差し引き
            new_balance = balance - self.amount
            user_data["balance"] = new_balance
            user_data["donation_total"] = user_data.get("donation_total", 0) + self.amount
            
            # XP獲得処理
            xp_amount = 0
            level_up_message = ""
            
            try:
                from level_system import add_xp_and_check_level_up
                
                xp_amount = (self.amount // 100) * 10  # 100KRごとに10XP
                level_up, new_level, old_level, kr_level_reward, new_titles = await add_xp_and_check_level_up(
                    self.user_id, xp_amount, is_exempt=False
                )
                
                if level_up:
                    level_up_message = f"\n🎉 レベルアップ！ レベル {old_level} → {new_level}\n💰 レベルアップ報酬: {kr_level_reward:,} KR"
                    user_data["balance"] += kr_level_reward
                    
            except ImportError:
                xp_amount = 0
                level_up_message = ""
            except Exception as e:
                print(f"XP処理エラー: {e}")
                xp_amount = 0
                level_up_message = ""
            
            # ユーザーデータ更新
            user_ref.set(user_data, merge=True)
            print(f"ユーザーデータ更新完了: 残高 {balance} → {user_data['balance']}")
            
            # 寄付ログを記録
            try:
                donation_log = {
                    "user_id": self.user_id,
                    "username": interaction.user.name,
                    "display_name": interaction.user.display_name,
                    "amount": self.amount,
                    "target": target,
                    "timestamp": datetime.datetime.utcnow().isoformat()
                }
                db.collection("donations").add(donation_log)
                print("寄付ログ記録完了")
            except Exception as log_error:
                print(f"寄付ログ記録エラー: {log_error}")
            
            # 称号チェック（聖人）
            new_titles_message = ""
            try:
                titles = set(user_data.get("titles", []))
                
                if user_data.get("balance", 0) == 0 and "聖人" not in titles:
                    titles.add("聖人")
                    user_data["titles"] = list(titles)
                    user_ref.set(user_data, merge=True)
                    new_titles_message = "\n🎉 新しい称号を獲得: 聖人"
                    
                    # ロール付与
                    try:
                        role = discord.utils.get(interaction.guild.roles, name="聖人")
                        if role and role not in interaction.user.roles:
                            await interaction.user.add_roles(role)
                            print("聖人ロール付与完了")
                    except Exception as role_error:
                        print(f"ロール付与エラー: {role_error}")
                        
            except Exception as title_error:
                print(f"称号処理エラー: {title_error}")
            
            # 寄付通知
            try:
                donation_channel = bot.get_channel(1352859030715891782)
                if donation_channel:
                    await donation_channel.send(
                        f"🎁 **{interaction.user.display_name}** さんが「{target}」に **{self.amount:,}KR** を寄付しました！"
                    )
                    print("寄付通知送信完了")
            except Exception as notify_error:
                print(f"寄付通知送信エラー: {notify_error}")
            
            # 成功メッセージ
            message = (
                f"✅ 寄付が完了しました！ありがとうございました。\n"
                f"📌 寄付先: **{target}**\n"
                f"💰 金額: **{self.amount:,}KR**\n"
                f"✨ 経験値: **+{xp_amount} XP**\n"
                f"💵 残高: **{user_data['balance']:,} KR**"
                f"{level_up_message}{new_titles_message}"
            )
            
            await interaction.followup.send(message)
            print("寄付処理完了")
            
            # 寄付処理成功後
            await bot.notification_system.send_donation_notification(
                interaction.user,
                target,
                self.amount
            )
            
        except Exception as e:
            print(f"寄付処理エラー: {e}")
            import traceback
            print(f"トレースバック: {traceback.format_exc()}")
            
            try:
                await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")
            except:
                print("エラーメッセージ送信も失敗")

@tree.command(name="寄付", description="任意のプロジェクトにKRを寄付します")
@app_commands.describe(金額="寄付する金額（KR）")
async def donate(interaction: discord.Interaction, 金額: int) -> None:
    try:
        print(f"寄付コマンド実行開始 - ユーザー: {interaction.user.id}, 金額: {金額}")
        
        if 金額 <= 0:
            await interaction.response.send_message("❌ 寄付額は1KR以上にしてください。", ephemeral=True)
            return
        
        user_id = str(interaction.user.id)
        
        # 残高確認
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            await interaction.response.send_message("❌ ユーザー情報が見つかりませんでした。", ephemeral=True)
            return
        
        user_data = user_doc.to_dict()
        balance = user_data.get("balance", 0)
        
        if balance < 金額:
            await interaction.response.send_message(f"💸 残高不足です。現在の残高は {balance:,}KR です。", ephemeral=True)
            return
        
        # 寄付先が存在するかチェック
        try:
            donation_targets_ref = db.collection("donation_targets")
            targets = list(donation_targets_ref.stream())
            print(f"寄付先確認: {len(targets)}件の寄付先が存在")
            
            if not targets:
                await interaction.response.send_message(
                    "❌ 現在利用可能な寄付先がありません。\n"
                    "運営に寄付先の追加をリクエストしてください。",
                    ephemeral=True
                )
                return
                
        except Exception as targets_error:
            print(f"寄付先確認エラー: {targets_error}")
            await interaction.response.send_message(
                "❌ 寄付先情報の取得に失敗しました。\n"
                "しばらく時間をおいて再度お試しください。",
                ephemeral=True
            )
            return
        
        # 寄付先選択UI表示
        embed = discord.Embed(
            title="🎁 寄付先選択",
            description=f"**寄付金額: {金額:,} KR**\n**現在残高: {balance:,} KR**\n\n利用可能な寄付先から選択してください：",
            color=discord.Color.green()
        )
        
        # DonationView作成
        try:
            view = DonationView(user_id, 金額)
            print(f"DonationView作成完了: オプション数 {len(view.donation_options)}")
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            print("寄付UI送信完了")
            
        except Exception as view_error:
            print(f"DonationView作成エラー: {view_error}")
            await interaction.response.send_message(
                f"❌ 寄付画面の作成に失敗しました: {str(view_error)}",
                ephemeral=True
            )
        
    except Exception as e:
        print(f"寄付コマンドエラー: {e}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        
        try:
            await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
        except:
            print("エラーレスポンス送信も失敗")

@tree.command(name="寄付先追加", description="新しい寄付先を追加します（運営専用）")
@app_commands.describe(名前="寄付先の名前", 説明="寄付先の説明")
async def add_donation_target(interaction: discord.Interaction, 名前: str, 説明: str) -> None:
    # 運営ユーザーID
    管理者ID一覧 = ["1249582099825164312","867343308426444801"]

    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは運営のみ使用できます。", ephemeral=True)
        return

    try:
        donation_ref = db.collection("donation_targets").document(名前)
        donation_ref.set({
            "description": 説明,
            "created_by": interaction.user.display_name,
            "created_at": datetime.datetime.utcnow().isoformat()
        })
        await interaction.response.send_message(f"✅ 寄付先「{名前}」を追加しました！\n📝 説明: {説明}")

    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)

# デバッグ用管理者コマンド
@tree.command(name="寄付先確認", description="現在の寄付先一覧を確認します（管理者専用）")
async def check_donation_targets(interaction: discord.Interaction) -> None:
    # 管理者チェック
    管理者ID一覧 = ["1249582099825164312","867343308426444801"]
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return

    try:
        await interaction.response.defer(ephemeral=True)
        
        donation_targets_ref = db.collection("donation_targets")
        targets = list(donation_targets_ref.stream())
        
        if not targets:
            await interaction.followup.send("❌ 寄付先が1件も登録されていません。")
            return
        
        target_list = []
        for target_doc in targets:
            target_name = target_doc.id
            target_data = target_doc.to_dict()
            description = target_data.get("description", "説明なし")
            created_by = target_data.get("created_by", "不明")
            
            target_list.append(f"**{target_name}**\n説明: {description}\n作成者: {created_by}\n")
        
        embed = discord.Embed(
            title="🎁 寄付先一覧",
            description="\n".join(target_list),
            color=discord.Color.blue()
        )
        embed.set_footer(text=f"合計 {len(targets)} 件の寄付先")
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラー: {str(e)}")

# --------------------------------------
# ✅ クエスト関連コマンド（改善版）
# --------------------------------------

async def assign_role_if_available(interaction, title_name) -> None:
    guild = interaction.guild
    if guild is None:
        return
    role = discord.utils.get(guild.roles, name=title_name)
    if role:
        await interaction.user.add_roles(role)

@tree.command(name="クエスト登録", description="達成期日と内容を自由に設定したクエストを登録します")
@app_commands.describe(期日="クエスト達成の期限日 (YYYY-MM-DD)", 内容="クエストの具体的な内容")
async def register_quest(interaction: discord.Interaction, 期日: str, 内容: str) -> None:
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    quest_ref = db.collection("quests").document(user_id)
    
    # 日付形式の検証
    try:
        deadline = datetime.datetime.strptime(期日, "%Y-%m-%d")
        deadline = deadline.replace(hour=23, minute=59, second=59)
    except ValueError:
        await interaction.followup.send("❌ 日付形式が正しくありません。YYYY-MM-DD形式で入力してください。")
        return
    
    # 過去の日付はエラー
    if deadline < datetime.datetime.utcnow():
        await interaction.followup.send("❌ 過去の日付は指定できません。")
        return
    
    # クエストデータの取得
    quest_doc = quest_ref.get()
    quest_data = quest_doc.to_dict() if quest_doc.exists else {}
    
    # クエストIDの生成（現在時刻のタイムスタンプ）
    quest_id = f"quest_{int(datetime.datetime.utcnow().timestamp())}"
    
    # クエストデータの保存
    quest_data[quest_id] = {
        "内容": 内容,
        "期日": deadline.isoformat(),
        "作成日": datetime.datetime.utcnow().isoformat(),
        "状態": "進行中"
    }
    
    quest_ref.set(quest_data)
    
    # ✅ 改善：クエストIDを非表示にしてスッキリした表示
    await interaction.followup.send(
        f"✅ クエスト「**{内容}**」を登録しました！\n"
        f"📅 期限: **{期日}**\n"
        f"💡 達成時は `/クエスト達成` コマンドで報告してください。"
    )

@tree.command(name="クエスト達成", description="進行中のクエストから選択して達成報告をします")
async def complete_quest(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    
    user_id = str(interaction.user.id)
    quest_ref = db.collection("quests").document(user_id)
    user_ref = db.collection("users").document(user_id)
    
    # クエストデータの取得
    quest_doc = quest_ref.get()
    
    if not quest_doc.exists:
        await interaction.followup.send("❌ 進行中のクエストが見つかりません。")
        return
    
    quest_data = quest_doc.to_dict()
    
    # 進行中のクエストを取得
    active_quests = {}
    now = datetime.datetime.utcnow()
    
    for quest_id, quest in quest_data.items():
        if isinstance(quest, dict) and "状態" in quest and quest["状態"] == "進行中":
            # ✅ 修正：期限切れチェックを改善
            deadline_str = quest.get("期日")
            if deadline_str and deadline_str != "なし":
                try:
                    deadline = datetime.datetime.fromisoformat(deadline_str)
                    if now <= deadline:  # 期限内のもののみ
                        active_quests[quest_id] = quest
                except Exception:
                    continue
            else:
                # 期日なしのクエストも含める
                active_quests[quest_id] = quest
    
    if not active_quests:
        await interaction.followup.send("📝 現在進行中のクエストがありません。\n💡 `/クエスト登録` でクエストを作成してください。")
        return
    
    # ✅ 改善：選択肢として表示するViewクラスを作成
    class QuestSelectView(discord.ui.View):
        def __init__(self, active_quests_data, quest_ref, user_ref):
            super().__init__(timeout=300)  # 5分でタイムアウト
            self.active_quests = active_quests_data
            self.quest_ref = quest_ref
            self.user_ref = user_ref
            
            # 選択肢を動的に作成（最大25個まで）
            options = []
            for quest_id, quest in list(active_quests_data.items())[:25]:
                content = quest.get("内容", "内容なし")
                deadline_str = quest.get("期日", "")
                
                # 期日を読みやすい形式に変換
                if deadline_str and deadline_str != "なし":
                    try:
                        deadline = datetime.datetime.fromisoformat(deadline_str)
                        deadline_display = f"{deadline.month}/{deadline.day}"
                    except:
                        deadline_display = "期限不明"
                else:
                    deadline_display = "期限なし"
                
                # 内容が長い場合は短縮
                if len(content) > 80:
                    content = content[:77] + "..."
                
                options.append(
                    discord.SelectOption(
                        label=content,
                        description=f"期限: {deadline_display}",
                        value=quest_id
                    )
                )
            
            # セレクトメニューを追加
            select = discord.ui.Select(
                placeholder="達成したクエストを選択してください...",
                options=options
            )
            select.callback = self.quest_selected
            self.add_item(select)
        
        async def quest_selected(self, interaction: discord.Interaction):
            selected_quest_id = interaction.data['values'][0]
            selected_quest = self.active_quests[selected_quest_id]
            
            # クエスト達成処理を実行
            await self.process_quest_completion(interaction, selected_quest_id, selected_quest)
        
        async def process_quest_completion(self, interaction, quest_id, quest_entry) -> None:
            # 既存のクエスト達成処理ロジック
            await interaction.response.defer()
            
            # クエストデータを更新
            quest_data = self.quest_ref.get().to_dict()
            user_doc = self.user_ref.get()
            user_data = user_doc.to_dict() if user_doc.exists else {}
            
            # クエスト達成処理
            quest_entry["状態"] = "達成"
            quest_entry["達成日"] = datetime.datetime.utcnow().isoformat()
            quest_data[quest_id] = quest_entry
            self.quest_ref.set(quest_data)
            
            # 達成回数の更新
            completed_quests = user_data.get("completed_quests", 0) + 1
            user_data["completed_quests"] = completed_quests
            
            # ストリークの更新
            streak_count = user_data.get("quest_streak", 0) + 1
            user_data["quest_streak"] = streak_count
            
            # 期日と作成日の取得
            deadline_str = quest_entry.get("期日")
            creation_date_str = quest_entry.get("作成日")
            
            # 期日なしの場合のデフォルト処理
            if deadline_str and deadline_str != "なし":
                try:
                    deadline = datetime.datetime.fromisoformat(deadline_str)
                except:
                    deadline = datetime.datetime.utcnow() + datetime.timedelta(days=30)
            else:
                deadline = datetime.datetime.utcnow() + datetime.timedelta(days=30)
            
            if creation_date_str:
                try:
                    creation_date = datetime.datetime.fromisoformat(creation_date_str)
                except:
                    creation_date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            else:
                creation_date = datetime.datetime.utcnow() - datetime.timedelta(days=1)
            
            # 経過時間比率の計算
            now = datetime.datetime.utcnow()
            total_time = (deadline - creation_date).total_seconds()
            elapsed_time = (now - creation_date).total_seconds()
            elapsed_time_ratio = elapsed_time / total_time if total_time > 0 else 0.5
            
            # クエストタイプの決定
            if quest_id in ["weekly", "monthly", "yearly"]:
                quest_type = quest_id
            else:
                # 期限までの長さで判定
                days_to_deadline = (deadline - creation_date).days
                if days_to_deadline <= 7:
                    quest_type = "weekly"
                elif days_to_deadline <= 31:
                    quest_type = "monthly"
                else:
                    quest_type = "yearly"
            
            # XP獲得処理
            from xp_calculator import get_quest_xp
            xp_amount = get_quest_xp(quest_type, elapsed_time_ratio, streak_count, user_data)
            
            # XP加算とレベルアップ確認
            from level_system import add_xp_and_check_level_up
            level_up, new_level, old_level, kr_reward, new_titles = await add_xp_and_check_level_up(
                str(interaction.user.id), xp_amount, is_exempt=True
            )
            
            # KR報酬
            kr_amount = 500 if quest_type == "weekly" else 2000 if quest_type == "monthly" else 10000
            user_data["balance"] = user_data.get("balance", 0) + kr_amount
            
            # クエスト達成関連の称号
            titles = set(user_data.get("titles", []))
            achievement_titles = []
            
            if completed_quests == 1 and "冒険の始まり" not in titles:
                titles.add("冒険の始まり")
                achievement_titles.append("冒険の始まり")
            elif completed_quests == 10 and "成長の兆し" not in titles:
                titles.add("成長の兆し")
                achievement_titles.append("成長の兆し")
            elif completed_quests == 30 and "継続は力なり" not in titles:
                titles.add("継続は力なり")
                achievement_titles.append("継続は力なり")
            elif completed_quests == 50 and "成長の上昇気流" not in titles:
                titles.add("成長の上昇気流")
                achievement_titles.append("成長の上昇気流")
            
            if streak_count >= 10 and "コンシステント" not in titles:
                titles.add("コンシステント")
                achievement_titles.append("コンシステント")
            
            user_data["titles"] = list(titles)
            self.user_ref.set(user_data)
            
            # レスポンスメッセージの作成
            message = f"✅ クエスト「**{quest_entry['内容']}**」を達成しました！\n"
            message += f"💰 報酬: **{kr_amount:,} KR**\n"
            message += f"✨ 経験値: **+{xp_amount} XP**\n"
            
            if streak_count >= 3:
                message += f"🔄 **{streak_count}連続達成!**\n"
            
            if achievement_titles:
                message += "\n🎉 **新しい称号を獲得しました！**\n"
                for title in achievement_titles:
                    message += f"🏅 **{title}**\n"
            
            if new_titles:
                for title in new_titles:
                    message += f"🏅 レベルアップで称号「**{title}**」を獲得しました！\n"
            
            if level_up:
                message += f"\n🎉 **レベルアップ！** 🎉\n"
                message += f"レベル **{old_level}** から **{new_level}** に上がりました！\n"
                message += f"💰 報酬として **{kr_reward:,} KR** が付与されました！\n"
            
            await interaction.followup.send(message)
            
            # クエスト達成後
            await bot.notification_system.send_quest_notification(
                interaction.user,
                quest_entry['内容'],
                kr_amount
            )
    
    # Viewを表示
    view = QuestSelectView(active_quests, quest_ref, user_ref)
    
    # 進行中のクエスト一覧を表示
    quest_list = []
    for quest_id, quest in active_quests.items():
        content = quest.get("内容", "")
        deadline_str = quest.get("期日", "")
        
        if deadline_str and deadline_str != "なし":
            try:
                deadline = datetime.datetime.fromisoformat(deadline_str)
                deadline_display = f"{deadline.month}月{deadline.day}日"
            except:
                deadline_display = "期限不明"
        else:
            deadline_display = "期限なし"
        
        # 内容を短縮表示
        if len(content) > 50:
            content = content[:47] + "..."
        
        quest_list.append(f"📌 **{content}** (期限: {deadline_display})")
    
    embed = discord.Embed(
        title="🎯 クエスト達成報告",
        description="以下の進行中のクエストから、達成したものを選択してください：",
        color=discord.Color.green()
    )
    
    embed.add_field(
        name="📝 進行中のクエスト",
        value="\n".join(quest_list[:10]) + ("\n...他" if len(quest_list) > 10 else ""),
        inline=False
    )
    
    embed.set_footer(text="選択肢から達成したクエストを選んでください")
    
    await interaction.followup.send(embed=embed, view=view)

@tree.command(name="クエスト状況", description="現在進行中のクエストを表示します")
async def quest_status(interaction: discord.Interaction) -> None:
    try:
        await interaction.response.defer()
        user_id = str(interaction.user.id)
        user_ref = db.collection("quests").document(user_id)
        user_data = user_ref.get()

        if not user_data.exists:
            embed = discord.Embed(
                title="📝 クエスト状況",
                description="🔍 **現在進行中のクエストはありません！**\n💡 `/クエスト登録` でクエストを作成してください。",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed)
            return

        user_quests = user_data.to_dict()
        active_quests = []
        now = datetime.datetime.utcnow()

        # 新しいクエスト形式に対応
        for quest_id, quest in user_quests.items():
            if isinstance(quest, dict) and "状態" in quest and quest["状態"] == "進行中":
                content = quest.get("内容", "内容なし")
                deadline_iso = quest.get("期日")

                # ✅ 修正：期日なしクエストにも対応
                if deadline_iso and deadline_iso != "なし":
                    try:
                        deadline = datetime.datetime.fromisoformat(deadline_iso)
                        if now > deadline:
                            continue  # 期限切れのものは表示しない
                        
                        # 残り時間を計算
                        time_left = deadline - now
                        if time_left.days > 0:
                            time_display = f"あと{time_left.days}日"
                        elif time_left.seconds > 3600:
                            hours = time_left.seconds // 3600
                            time_display = f"あと{hours}時間"
                        else:
                            time_display = "期限間近"
                        
                        deadline_str = f"{deadline.year}/{deadline.month:02d}/{deadline.day:02d}"
                    except Exception:
                        deadline_str = "不明"
                        time_display = ""
                else:
                    deadline_str = "期限なし"
                    time_display = ""

                active_quests.append({
                    "content": content,
                    "deadline": deadline_str,
                    "time_left": time_display
                })

        embed = discord.Embed(
            title="📝 クエスト状況",
            color=discord.Color.blue()
        )

        if active_quests:
            quest_text = []
            for i, quest in enumerate(active_quests[:15], 1):  # 最大15件表示
                if quest['time_left']:
                    quest_text.append(
                        f"**{i}.** {quest['content']}\n"
                        f"📅 期限: {quest['deadline']} ({quest['time_left']})\n"
                    )
                else:
                    quest_text.append(
                        f"**{i}.** {quest['content']}\n"
                        f"📅 期限: {quest['deadline']}\n"
                    )
            
            embed.description = "\n".join(quest_text)
            embed.add_field(
                name="💡 ヒント",
                value="達成したクエストは `/クエスト達成` で報告しましょう！",
                inline=False
            )
            
            if len(active_quests) > 15:
                embed.set_footer(text=f"他に {len(active_quests) - 15} 件のクエストがあります")
        else:
            embed.description = "🔍 **現在進行中のクエストはありません！**\n💡 `/クエスト登録` でクエストを作成してください。"

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ エラー: {str(e)}")
  

# --------------------------------------
# ✅ プロフィール関連コマンド
# --------------------------------------

@tree.command(name="プロフィール", description="ユーザーの総合的な状況を表示します")
async def profile(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    user_id = str(interaction.user.id)
    
    # レベル情報を取得
    from level_system import get_level_info
    level_info = await get_level_info(user_id)
    
    # ユーザーデータを取得
    user_ref = db.collection("users").document(user_id)
    user_doc = user_ref.get()
    user_data = user_doc.to_dict() if user_doc.exists else {}
    
    # クエスト情報を取得（新しい形式に対応）
    quest_ref = db.collection("quests").document(user_id)
    quest_doc = quest_ref.get()
    quest_data = quest_doc.to_dict() if quest_doc.exists else {}
    active_quests = [q for q in quest_data.values() if isinstance(q, dict) and "状態" in q and q["状態"] == "進行中"]
    
    # 投資ポートフォリオを取得
    investment_ref = db.collection("investments").document(user_id)
    investment_doc = investment_ref.get()
    investment_data = investment_doc.to_dict() if investment_doc.exists else {}
    
    # 送金・寄付情報
    donation_total = user_data.get("donation_total", 0)
    transfers_total = user_data.get("transfers_total", 0)
    
    # プロフィール埋め込みを作成
    embed = discord.Embed(
        title=f"🔰 {interaction.user.display_name} さんのプロフィール",
        color=discord.Color.blue()
    )
    
    # 基本情報（レベル、XP、進捗バー）
    progress_bar = "■" * (level_info['progress_percent'] // 5) + "□" * ((100 - level_info['progress_percent']) // 5)
    embed.add_field(
        name="📊 レベル情報",
        value=(
            f"🏆 レベル: **{level_info['level']}**\n"
            f"✨ 経験値: **{level_info['xp']:,}** / **{level_info['next_level_xp']:,}** XP\n"
            f"📈 進捗: {progress_bar} ({level_info['progress_percent']}%)\n"
            f"📅 本日の獲得XP: **{level_info['today_xp_earned']:,}** / **{level_info['daily_xp_cap']:,}** XP"
        ),
        inline=False
    )
    
    # 経済状況（所持KR、送金総額、寄付総額）
    embed.add_field(
        name="💰 経済状況",
        value=(
            f"💵 所持KR: **{user_data.get('balance', 0):,}** KR\n"
            f"🎁 送金総額: **{transfers_total:,}** KR\n"
            f"🏆 寄付総額: **{donation_total:,}** KR"
        ),
        inline=False
    )
    
    # クエスト実績（達成率、連続達成数、現在進行中のクエスト）
    completed_quests = user_data.get("completed_quests", 0)
    total_quests = completed_quests + len(active_quests)
    achievement_rate = (completed_quests / total_quests * 100) if total_quests > 0 else 0
    
    embed.add_field(
        name="🎯 クエスト実績",
        value=(
            f"✅ 達成回数: **{completed_quests}** 回\n"
            f"📊 達成率: **{achievement_rate:.1f}**%\n"
            f"🔢 現在進行中: **{len(active_quests)}** 件\n"
            f"🔄 連続達成数: **{user_data.get('quest_streak', 0)}** 回"
        ),
        inline=False
    )
    
    # 称号コレクション（獲得称号一覧）
    titles = level_info.get("titles", [])
    if titles:
        embed.add_field(
            name="🏅 称号コレクション",
            value=", ".join([f"`{title}`" for title in titles]),
            inline=False
        )
    
    # アクティビティ統計（投稿数、通算ログイン日数）
    embed.add_field(
        name="📝 アクティビティ統計",
        value=(
            f"💬 投稿数: **{user_data.get('total_messages', 0):,}** 件\n"
            f"📱 通算ログイン日数: **{user_data.get('login_days', 0)}** 日"
        ),
        inline=False
    )
    
    # 投資ポートフォリオ概要（総資産、損益率）
    total_assets = 0
    profit_rate = 0
    if investment_data:
        portfolio = investment_data.get("portfolio", {})
        for stock_data in portfolio.values():
            if isinstance(stock_data, dict):
                total_assets += stock_data.get("current_value", 0)
        
        initial_investment = investment_data.get("total_invested", 1)
        if initial_investment > 0:
            profit_rate = ((total_assets / initial_investment) - 1) * 100
    
    embed.add_field(
        name="📈 投資ポートフォリオ",
        value=(
            f"💹 総資産: **{total_assets:,}** KR\n"
            f"📊 損益率: **{profit_rate:.1f}**%"
        ),
        inline=False
    )
    
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.set_footer(text=f"{datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M')} • KRAFT")
    
    await interaction.followup.send(embed=embed)

# bot.pyの他のコマンドと同じ場所に追加

@tree.command(name="ニックネーム設定", description="ウェブサイト用のニックネームを設定・変更します")
@app_commands.describe(ニックネーム="表示したいニックネーム（20文字以内）")
async def set_website_nickname(interaction: discord.Interaction, ニックネーム: str) -> None:
    try:
        # 文字数制限チェック
        if len(ニックネーム) > 20:
            await interaction.response.send_message("❌ ニックネームは20文字以内で設定してください。", ephemeral=True)
            return
        
        # 不適切な文字列チェック（基本的なフィルター）
        prohibited_words = ["admin", "管理者", "運営", "bot", "system"]
        if any(word in ニックネーム.lower() for word in prohibited_words):
            await interaction.response.send_message("❌ そのニックネームは使用できません。", ephemeral=True)
            return
        
        # 空文字・スペースのみチェック
        if not ニックネーム.strip():
            await interaction.response.send_message("❌ 有効なニックネームを入力してください。", ephemeral=True)
            return
        
        user_id = str(interaction.user.id)
        user_ref = db.collection("users").document(user_id)
        
        # 既存データを取得または初期化
        user_doc = user_ref.get()
        if user_doc.exists:
            user_data = user_doc.to_dict()
            old_nickname = user_data.get("website_nickname")
        else:
            user_data = {
                "level": 1,
                "xp": 0,
                "balance": 0,
                "titles": [],
                "completed_quests": 0,
                "total_messages": 0
            }
            old_nickname = None
        
        # ニックネーム設定（自動上書き）
        user_data["website_nickname"] = ニックネーム.strip()
        user_ref.set(user_data, merge=True)
        
        if old_nickname:
            await interaction.response.send_message(
                f"✅ ニックネームを「**{old_nickname}**」から「**{ニックネーム}**」に変更しました！\n"
                f"💡 KRAFTウェブサイトのプロフィール一覧で確認できます。",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"✅ ウェブサイト用ニックネームを「**{ニックネーム}**」に設定しました！\n"
                f"💡 KRAFTウェブサイトのプロフィール一覧で確認できます。",
                ephemeral=True
            )
        
    except Exception as e:
        await interaction.response.send_message(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)
        print(f"ニックネーム設定エラー: {e}")

    
# --------------------------------------
# ✅ 通貨システム関連コマンド
# --------------------------------------

@tree.command(name="残高", description="自分のKR残高を確認します")
async def check_balance(interaction: discord.Interaction) -> None:
    try:
        user_id = str(interaction.user.id)
        user_ref = db.collection("users").document(user_id)
        user_data = user_ref.get()

        balance = user_data.to_dict().get("balance", 0) if user_data.exists else 0
        await interaction.response.send_message(f"💰 **{interaction.user.name} さんの残高:** {balance:,} KR", ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(f"❌ エラー: {str(e)}", ephemeral=True)

@tree.command(name="送金", description="他のユーザーにKRを送金します")
async def transfer_kr(interaction: discord.Interaction, recipient: discord.Member, 金額: int) -> None:
    try:
        if 金額 <= 0:
            await interaction.response.send_message("❌ 送金額は1KR以上にしてください。")
            return

        sender_id = str(interaction.user.id)
        recipient_id = str(recipient.id)

        sender_ref = db.collection("users").document(sender_id)
        recipient_ref = db.collection("users").document(recipient_id)

        sender_data = sender_ref.get()
        recipient_data = recipient_ref.get()

        sender_balance = sender_data.to_dict().get("balance", 0) if sender_data.exists else 0
        recipient_balance = recipient_data.to_dict().get("balance", 0) if recipient_data.exists else 0

        if sender_balance < 金額:
            await interaction.response.send_message("❌ 残高不足です。")
            return

        # 送金処理
        sender_ref.update({"balance": sender_balance - 金額})
        sender_data_dict = sender_data.to_dict() if sender_data.exists else {}
        sender_data_dict["transfers_total"] = sender_data_dict.get("transfers_total", 0) + 金額
        sender_ref.set(sender_data_dict, merge=True)
        
        recipient_ref.set({"balance": recipient_balance + 金額}, merge=True)

        # XP獲得処理 (送金: 100KRごとに5XP)
        from level_system import add_xp_and_check_level_up
        xp_amount = (金額 // 100) * 5  # 100KRごとに5XP
        level_up, new_level, old_level, kr_level_reward, new_titles = await add_xp_and_check_level_up(
            sender_id, xp_amount, is_exempt=False
        )

        message = f"✅ {recipient.mention} に {金額:,} KR を送金しました！\n✨ 経験値: +{xp_amount} XP"
        
        if level_up:
            message += f"\n🎉 レベルアップ！ レベル {old_level} → {new_level}"
            message += f"\n💰 レベルアップ報酬: {kr_level_reward} KR"

        await interaction.response.send_message(message)

    except Exception as e:
        await interaction.response.send_message(f"❌ エラー: {str(e)}")

# --------------------------------------
# ✅ イベントハンドラ
# --------------------------------------

# メッセージ送信時のXP獲得処理
@bot.event
async def on_message(message) -> None:
    # Bot自身のメッセージは無視
    if message.author.bot:
        return
    
    # コマンド処理
    await bot.process_commands(message)
    
    # メッセージXPの計算
    xp_amount = get_message_xp(message.content)
    
    # XP加算とレベルアップ確認
    level_up, new_level, old_level, kr_reward, new_titles = await add_xp_and_check_level_up(
        str(message.author.id),
        xp_amount
    )
    
    # レベルアップ通知
    if level_up:
        await bot.notification_system.send_level_up_notification(
            message.author,
            old_level,
            new_level,
            kr_reward,
            new_titles
        )

# --------------------------------------
# ✅ バックグラウンドタスク
# --------------------------------------

# 期限切れクエスト確認の定期実行タスク
# check_expired_quests 関数を以下のコードで完全に置き換えてください

@tasks.loop(hours=1)
async def check_expired_quests() -> None:
    """期限切れクエストを確認するバックグラウンドタスク（称号システム統合版）"""
    try:
        print("=== 期限切れクエストチェック開始 ===") 
        now = datetime.datetime.utcnow()
        print(f"現在時刻: {now}") 
        quests_ref = db.collection("quests")
        print("Firestoreクエリ実行中...")
        quests = quests_ref.stream()
        
        expired_quest_users = []  # 期限切れクエストを持つユーザーのリスト
        
        for quest_doc in quests:
            user_id = quest_doc.id
            if user_id == "1249582099825164312":  # 特定ユーザーのみ
                print(f"=== ターゲットユーザー {user_id} のデバッグ開始 ===")
                quest_data = quest_doc.to_dict()
                print(f"クエストデータの全体: {quest_data}")
                print(f"クエスト数: {len(quest_data)}")
                
                # 期限切れクエストをフィルタリング
                expired_quests = []
                for quest_id, quest in quest_data.items():
                    print(f"チェック中: {quest_id} = {quest}")
                    if isinstance(quest, dict) and "状態" in quest and quest["状態"] == "進行中":
                        print(f"  → 進行中クエスト発見")
                        deadline_str = quest.get("期日") or quest.get("期限")
                        print(f"  → 期日: {deadline_str}")
                        if deadline_str and deadline_str != "なし":
                            try:
                                deadline = datetime.datetime.fromisoformat(deadline_str)
                                if now > deadline:
                                    expired_quests.append(quest_id)
                                    print(f"  → 期限切れ！")
                            except (ValueError, TypeError):
                                pass
                
                # 期限切れクエストを削除
                if expired_quests:
                    print(f"ユーザー {user_id} に期限切れクエスト {len(expired_quests)}件発見") 
                    for quest_id in expired_quests:
                        quest_data.pop(quest_id)
                    
                    quests_ref.document(user_id).set(quest_data)
                    expired_quest_users.append(user_id)  # 失敗称号チェック用に記録
                    print(f"ユーザー {user_id} の期限切れクエスト {len(expired_quests)}件を削除しました")
                
                break  # このユーザーのみ処理して終了
        
        # 称号システム統合：クエスト失敗称号チェック
        if TITLE_SYSTEM_ENABLED and expired_quest_users:
            title_results = await integrate_title_system_to_quest_expiry(expired_quest_users)
            
            # 新称号獲得者をコンソールに表示
            for user_id, new_titles in title_results.items():
                if new_titles:
                    print(f"ユーザー {user_id} がクエスト失敗で称号 {new_titles} を獲得")
    
    except Exception as e:
        print(f"❌ 期限切れクエスト確認で詳細エラー: {e}")
        print(f"エラータイプ: {type(e)}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")
        
# 称号システム統合：クエスト失敗称号チェック
        if TITLE_SYSTEM_ENABLED and expired_quest_users:
            title_results = await integrate_title_system_to_quest_expiry(expired_quest_users)
            
            # 新称号獲得者をコンソールに表示
            for user_id, new_titles in title_results.items():
                if new_titles:
                    print(f"ユーザー {user_id} がクエスト失敗で称号 {new_titles} を獲得")
    
    except Exception as e:
        print(f"❌ 期限切れクエスト確認で詳細エラー: {e}")
        print(f"エラータイプ: {type(e)}")
        import traceback
        print(f"トレースバック: {traceback.format_exc()}")

    """期限切れクエストを確認するバックグラウンドタスク"""
    try:
        now = datetime.utcnow()
        quests_ref = db.collection("quests")
        quests = quests_ref.stream()
        
        for quest_doc in quests:
            user_id = quest_doc.id
            quest_data = quest_doc.to_dict()
            
            # 期限切れクエストをフィルタリング
            expired_quests = []
            for quest_id, quest in quest_data.items():
                if isinstance(quest, dict) and "状態" in quest and quest["状態"] == "進行中":
                    deadline_str = quest.get("期日")
                    # 期日がない場合は削除対象外
                    if deadline_str and deadline_str != "なし":
                        try:
                            deadline = datetime.datetime.fromisoformat(deadline_str)
                            if now > deadline:
                                expired_quests.append(quest_id)
                        except (ValueError, TypeError):
                            pass
            
            # 期限切れクエストを削除
            if expired_quests:
                for quest_id in expired_quests:
                    quest_data.pop(quest_id)
                
                quests_ref.document(user_id).set(quest_data)
                print(f"ユーザー {user_id} の期限切れクエスト {len(expired_quests)}件を削除しました")
    
    except Exception as e:
        print(f"期限切れクエスト確認エラー: {e}")

@check_expired_quests.before_loop
async def before_check_expired_quests() -> None:
    await bot.wait_until_ready()

# --------------------------------------
# ✅ 自動ニュース生成システム
# --------------------------------------

@tasks.loop(hours=1)
async def auto_generate_news() -> None:
    """平日に自動でニュースを生成・投稿するバックグラウンドタスク"""
    try:
        # NEWS_SYSTEM_ENABLEDチェック
        if not NEWS_SYSTEM_ENABLED or news_generator is None:
            return
            
        now = datetime.datetime.utcnow()
        # 日本時間に変換（UTC+9）
        jst_now = now + datetime.timedelta(hours=9)
        
        # 平日チェック（0=月曜, 6=日曜）
        if jst_now.weekday() >= 5:  # 土日はスキップ
            return
        
        current_hour = jst_now.hour
        
        # ニュース生成タイミング（日本時間）
        news_times = [
            (9, 10),    # 朝: 9:00-10:00
            (12, 14),   # 昼: 12:00-14:00  
            (16, 17)    # 夕方: 16:00-17:00
        ]
        
        # 現在時刻がニュース生成時間帯かチェック
        should_generate = False
        for start_hour, end_hour in news_times:
            if start_hour <= current_hour < end_hour:
                # 30%の確率で生成（1時間に1回チェックなので適度な頻度）
                if random.random() < 0.3:
                    should_generate = True
                    break
        
        if not should_generate:
            return
        
        print(f"📰 自動ニュース生成開始 - {jst_now.strftime('%Y-%m-%d %H:%M')} JST")
        
        # ランダムに1-2社のニュースを生成
        num_news = random.randint(1, 2)
        tickers = random.sample(list(news_generator.company_contexts.keys()), num_news)
        
        # ニュース生成・投稿
        for ticker in tickers:
            try:
                # Claude APIでニュース生成
                news_data = news_generator.generate_news(ticker)
                
                if not news_data:
                    continue
                
                # Firestoreに保存
                news_id = news_generator.save_news_to_firestore(news_data)
                
                if not news_id:
                    continue
                
                # 株価に影響適用
                if news_data["impact_score"] != 0:
                    news_generator.apply_price_impact(ticker, news_data["impact_score"])
                
                # Discord投稿
                await post_news_to_discord(news_data)
                
                print(f"✅ 自動ニュース生成完了: {ticker} - {news_data['headline']}")
                
                # 連続投稿を避けるため少し待機
                await asyncio.sleep(random.randint(30, 120))  # 30-120秒
                
            except Exception as e:
                print(f"自動ニュース生成エラー ({ticker}): {e}")
                continue
    
    except Exception as e:
        print(f"自動ニュース生成システムエラー: {e}")

async def post_news_to_discord(news_data) -> None:
    """ニュースをDiscordに投稿"""
    try:
        channel = bot.get_channel(INVESTMENT_NEWS_CHANNEL_ID)
        if not channel:
            print(f"ニュースチャンネルが見つかりません (ID: {INVESTMENT_NEWS_CHANNEL_ID})")
            return
        
        # 影響度に応じた色設定
        impact = news_data["impact_score"]
        if impact >= 2:
            color = 0x00ff00    # 緑 - 大幅プラス
        elif impact >= 1:
            color = 0x90EE90    # 薄緑 - プラス
        elif impact >= -1:
            color = 0xffff00   # 黄 - 中立
        elif impact >= -2:
            color = 0xffa500   # オレンジ - マイナス
        else:
            color = 0xff0000    # 赤 - 大幅マイナス
        
        # 影響度の表示
        if impact >= 2:
            impact_text = "📈 大幅上昇期待"
        elif impact >= 1:
            impact_text = "📈 上昇期待"
        elif impact >= -1:
            impact_text = "📊 中立"
        elif impact >= -2:
            impact_text = "📉 下落懸念"
        else:
            impact_text = "📉 大幅下落懸念"
        
        # 企業情報取得
        company_ref = db.collection("companies").document(news_data["ticker"])
        company_doc = company_ref.get()
        company_data = company_doc.to_dict() if company_doc.exists else {}
        current_price = company_data.get("current_price", "不明")
        
        # Embed作成
        embed = discord.Embed(
            title=f"📰 {news_data['headline']}",
            description=news_data['content'],
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        
        embed.add_field(
            name="🏢 企業情報",
            value=f"**{company_data.get('name', 'Unknown')} ({news_data['ticker']})**\n現在株価: {current_price:,} KR",
            inline=True
        )
        
        embed.add_field(
            name="📊 市場への影響",
            value=impact_text,
            inline=True
        )
        
        
        embed.set_footer(text=f"ニュースタイプ: {news_data['news_type']} | KRAFT投資システム")
        
        # 投稿
        await channel.send(embed=embed)
        print(f"✅ ニュース投稿完了: {news_data['ticker']} - {news_data['headline']}")
        
    except Exception as e:
        print(f"Discord投稿エラー: {e}")

# --------------------------------------
# ✅ 管理者用手動ニュース生成コマンド（テスト用）
# --------------------------------------

@tree.command(name="ニュース生成", description="投資ニュースを手動生成します（管理者専用）")
@app_commands.describe(銘柄="ニュースを生成する銘柄（省略時はランダム）")
@app_commands.choices(銘柄=[
    app_commands.Choice(name="🤖 Wicrosoft (WICR)", value="WICR"),
    app_commands.Choice(name="⚛️ Qoogle (QOOG)", value="QOOG"),
    app_commands.Choice(name="🎮 Roblux (RBLX)", value="RBLX"),
    app_commands.Choice(name="📺 Netfox (NFOX)", value="NFOX"),
    app_commands.Choice(name="🌱 Mosla (MOSL)", value="MOSL"),
    app_commands.Choice(name="🚚 Nikuda (NKDA)", value="NKDA"),
    app_commands.Choice(name="🧬 Firma Schnitzel (FSCH)", value="FSCH"),
    app_commands.Choice(name="🏥 Iroha (IRHA)", value="IRHA"),
    app_commands.Choice(name="💳 Strike (STRK)", value="STRK"),
    app_commands.Choice(name="🏦 Assist (ASST)", value="ASST"),
    app_commands.Choice(name="🎲 ランダム", value="random")
])
async def manual_news_generation(interaction: discord.Interaction, 銘柄: app_commands.Choice[str] = None) -> None:
    # 管理者チェック
    管理者ID一覧 = ["1249582099825164312", "867343308426444801"]
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # NEWS_SYSTEM_ENABLEDチェック
        if not NEWS_SYSTEM_ENABLED or news_generator is None:
            await interaction.followup.send("❌ ニュース生成システムが無効です。Claude APIキーまたはnews_generator.pyを確認してください。", ephemeral=True)
            return
        
        # 銘柄選択
        if 銘柄 is None or 銘柄.value == "random":
            ticker = random.choice(list(news_generator.company_contexts.keys()))
        else:
            ticker = 銘柄.value
        
        # Claude APIを使用してニュース生成
        news_data = news_generator.generate_news(ticker)
        
        if not news_data:
            await interaction.followup.send("❌ ニュース生成に失敗しました。", ephemeral=True)
            return
        
        # Firestoreに保存
        news_id = news_generator.save_news_to_firestore(news_data)
        
        if not news_id:
            await interaction.followup.send("❌ ニュースの保存に失敗しました。", ephemeral=True)
            return
        
        # 株価に影響適用
        if news_data["impact_score"] != 0:
            news_generator.apply_price_impact(ticker, news_data["impact_score"])
        
        # Discord投稿
        await post_news_to_discord(news_data)
        
        await interaction.followup.send(f"✅ {ticker} のニュースを生成・投稿しました！", ephemeral=True)
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラー: {str(e)}", ephemeral=True)
        print(f"ニュース生成エラー: {e}")

# bot.py の on_ready 関数内に追加
# if not auto_generate_news.is_running():
#     auto_generate_news.start()
#     print("✅ 自動ニュース生成システム開始")

# ===== 管理者専用コマンド =====

@tree.command(name="期限切れテスト", description="期限切れクエスト処理を強制実行（管理者専用）")
async def force_expired_check(interaction: discord.Interaction) -> None:
    管理者ID一覧 = ["1249582099825164312", "867343308426444801"]
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ 管理者専用", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        await check_expired_quests()
        await interaction.followup.send("✅ 期限切れチェック実行完了\nコンソールログを確認してください")
    except Exception as e:
        await interaction.followup.send(f"❌ エラー: {str(e)}")

@tree.command(name="称号整理", description="削除予定の称号を全ユーザーから除去します（管理者専用）")
async def cleanup_titles(interaction: discord.Interaction) -> None:
    # 管理者チェック
    管理者ID一覧 = ["1249582099825164312", "867343308426444801"]
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは管理者のみ使用できます。", ephemeral=True)
        return
    
    if not TITLE_SYSTEM_ENABLED:
        await interaction.response.send_message("❌ 称号システムが無効です。", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        results = await cleanup_all_deprecated_titles()
        
        embed = discord.Embed(
            title="🧹 称号整理完了",
            description="削除予定の称号を除去しました",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="📊 処理結果",
            value=f"処理したユーザー: {results['total_users']}人\n削除した称号: {results['total_removed']}個",
            inline=False
        )
        embed.add_field(
            name="🗑️ 削除された称号",
            value="冒険の始まり、成長の兆し、継続は力なり、成長の上昇気流、コンシステント、村の救世主、ノーリターン、秘密の共有者",
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}", ephemeral=True)

# ==============================================
# ✅ KRAFT週刊Podcast機能
# bot.pyの最後（bot.run(TOKEN)の直前）に追加
# ==============================================

# Podcast機能用の設定値とインポート
PODCAST_CHANNEL_ID = 1352859030715891782  # 📻｜クラフトラジオチャンネルID
管理者ID一覧 = ["1249582099825164312", "867343308426444801"]

# プライベート・除外対象のキーワード
NEGATIVE_KEYWORDS = [
    "悲しい", "つらい", "困った", "問題", "心配", "不安", "失敗", "だめ", "最悪",
    "疲れた", "しんどい", "きつい", "苦しい", "痛い", "病気", "体調", "具合"
]

PRIVATE_KEYWORDS = [
    "個人的", "秘密", "内緒", "プライベート", "家族", "親", "恋人", "彼女", "彼氏",
    "住所", "電話", "メール", "パスワード", "個人情報", "年収", "給料"
]

class WeeklyPodcastGenerator:
    def __init__(self, bot):
        self.bot = bot
        
    async def collect_weekly_messages(self) -> None:
        """1週間分のメッセージを全チャンネルから収集"""
        week_start = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        all_messages = []
        channel_stats = {}
        
        try:
            for guild in self.bot.guilds:
                for channel in guild.text_channels:
                    # プライベートチャンネルをスキップ
                    if any(word in channel.name.lower() for word in ['private', 'プライベート', '運営', 'admin']):
                        continue
                    
                    try:
                        messages = []
                        async for message in channel.history(after=week_start, limit=1000):
                            if not message.author.bot:  # Bot以外のメッセージ
                                messages.append({
                                    'content': message.content,
                                    'author': message.author.display_name,
                                    'channel': channel.name,
                                    'timestamp': message.created_at,
                                    'reactions': len(message.reactions)
                                })
                        
                        if messages:
                            all_messages.extend(messages)
                            channel_stats[channel.name] = len(messages)
                            
                    except discord.Forbidden:
                        # アクセス権限がないチャンネルはスキップ
                        continue
                        
        except Exception as e:
            print(f"メッセージ収集エラー: {e}")
            
        return all_messages, channel_stats
    
    async def get_user_display_name(self, user_id) -> None:
        """ユーザーIDから実際の表示名を取得（Discord API強化版）"""
        try:
            print(f"ユーザー名取得開始: {user_id}")
            
            # 1. Discord上での表示名を取得（優先度最高）
            try:
                user = self.bot.get_user(int(user_id))
                if user:
                    print(f"  Discord user found: {user.name}")
                    
                    # サーバー内でのニックネームを優先
                    for guild in self.bot.guilds:
                        member = guild.get_member(int(user_id))
                        if member:
                            display_name = member.display_name or member.name
                            print(f"  Guild member display name: {display_name}")
                            return display_name
                    
                    # ニックネームがない場合はユーザー名
                    return user.display_name or user.name
                else:
                    print(f"  get_user failed, trying fetch_user...")
                    # get_userで取得できない場合はfetch_userを試行
                    user = await self.bot.fetch_user(int(user_id))
                    if user:
                        print(f"  fetch_user success: {user.name}")
                        return user.display_name or user.name
            except Exception as discord_error:
                print(f"  Discord API error: {discord_error}")
            
            # 2. 最近のメッセージ履歴から表示名を取得
            try:
                print(f"  Discord API failed, searching message history...")
                for guild in self.bot.guilds:
                    for channel in guild.text_channels:
                        try:
                            # 最近の100件のメッセージから該当ユーザーを探す
                            async for message in channel.history(limit=100):
                                if str(message.author.id) == user_id:
                                    display_name = message.author.display_name or message.author.name
                                    print(f"  Found in message history: {display_name}")
                                    return display_name
                        except discord.Forbidden:
                            continue
                        except Exception:
                            continue
            except Exception as history_error:
                print(f"  Message history search error: {history_error}")
            
            # 3. Firestoreから表示名を取得（通常は空）
            try:
                print(f"  Trying Firestore for user: {user_id}")
                user_ref = db.collection("users").document(user_id)
                user_doc = user_ref.get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    # 複数のフィールドを確認
                    possible_names = [
                        user_data.get('display_name'),
                        user_data.get('username'), 
                        user_data.get('name'),
                        user_data.get('discord_name')
                    ]
                    
                    for name in possible_names:
                        if name and isinstance(name, str) and len(name.strip()) > 0:
                            print(f"  Firestore display name found: {name}")
                            return name.strip()
                    
                    print(f"  Firestore data exists but no valid display name: {list(user_data.keys())}")
                else:
                    print(f"  No Firestore data for user: {user_id}")
            except Exception as firestore_error:
                print(f"  Firestore error: {firestore_error}")
            
            # 4. 最後の手段：より分かりやすいフォールバック
            try:
                # IDの最後4桁で識別しやすく
                fallback_name = f"メンバー{user_id[-4:]}"
                print(f"  Using fallback name: {fallback_name}")
                return fallback_name
            except:
                return "匿名メンバー"
                
        except Exception as e:
            print(f"ユーザー名取得エラー {user_id}: {e}")
            return f"メンバー{str(user_id)[-4:] if user_id else '????'}"
    
    async def collect_real_level_ups(self):
        """実際のレベルアップデータを正確に収集（修正版）"""
        week_start = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        level_ups = []
        
        try:
            # レベルアップ通知チャンネルから実際の通知を取得
            level_channel_id = 1352859030715891782  # レベルアップ通知チャンネル
            level_channel = self.bot.get_channel(level_channel_id)
            
            print(f"レベルアップチャンネル取得: {level_channel}")
            
            if level_channel:
                message_count = 0
                async for message in level_channel.history(after=week_start, limit=200):
                    message_count += 1
                    print(f"メッセージ {message_count}: {message.content[:100]}...")
                    
                    if message.author.bot and ("レベルアップ" in message.content or "レベル" in message.content):
                        print(f"レベルアップメッセージ発見: {message.content}")
                        
                        # Embedからレベルアップ情報を抽出
                        if message.embeds:
                            embed = message.embeds[0]
                            print(f"Embed情報: title={embed.title}, description={embed.description}")
                            
                            description = embed.description or ""
                            title = embed.title or ""
                            
                            # 複数のパターンでユーザーIDとレベル情報を抽出
                            user_mention_match = re.search(r'<@(\d+)>', description + title + message.content)
                            level_match = re.search(r'レベル\s*(\d+)\s*から.*レベル\s*(\d+)', description + title + message.content)
                            
                            # 代替パターン
                            if not level_match:
                                level_match = re.search(r'レベル\s*(\d+).*→.*(\d+)', description + title + message.content)
                            if not level_match:
                                level_match = re.search(r'Lv\s*(\d+).*Lv\s*(\d+)', description + title + message.content)
                            
                            print(f"ユーザーマッチ: {user_mention_match}")
                            print(f"レベルマッチ: {level_match}")
                            
                            if user_mention_match and level_match:
                                user_id = user_mention_match.group(1)
                                old_level = int(level_match.group(1))
                                new_level = int(level_match.group(2))
                                
                                display_name = await self.get_user_display_name(user_id)
                                print(f"レベルアップ検出: {display_name} Lv{old_level}→{new_level}")
                                
                                level_ups.append({
                                    'user_name': display_name,
                                    'old_level': old_level,
                                    'new_level': new_level,
                                    'timestamp': message.created_at,
                                    'is_milestone': new_level % 10 == 0
                                })
                            else:
                                # パターンマッチに失敗した場合の詳細ログ
                                print(f"パターンマッチ失敗 - content: {message.content}")
                                if message.embeds:
                                    print(f"  - embed title: {message.embeds[0].title}")
                                    print(f"  - embed description: {message.embeds[0].description}")
                
                print(f"レベルアップチャンネル検索完了: {message_count}件のメッセージを確認, {len(level_ups)}件のレベルアップを発見")
            
            # Firestoreから補完データを取得（既存のレベルアップが取得できない場合の補完）
            if len(level_ups) == 0:
                print("レベルアップ通知が見つからないため、Firestoreから推定データを取得")
                users_ref = db.collection('users')
                for user_doc in users_ref.stream():
                    user_data = user_doc.to_dict()
                    user_id = user_doc.id
                    
                    # 今週の大幅なXP獲得があったユーザーをチェック
                    current_level = user_data.get('level', 1)
                    total_xp = user_data.get('xp', 0)
                    
                    # レベル1以上で活動のあるユーザーを推定レベルアップとして記録
                    if current_level > 1:
                        display_name = await self.get_user_display_name(user_id)
                        
                        level_ups.append({
                            'user_name': display_name,
                            'estimated_growth': True,
                            'current_level': current_level,
                            'is_active': True
                        })
                    
                    # 最大5件まで
                    if len(level_ups) >= 5:
                        break
                            
        except Exception as e:
            print(f"レベルアップデータ収集エラー: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")
        
        print(f"最終的なレベルアップデータ: {len(level_ups)}件")
        return level_ups

    async def collect_real_quest_completions(self):
        """実際のクエスト達成データを正確に収集（修正版）"""
        week_start = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        quest_completions = []
        
        try:
            print("クエスト達成データ収集開始")
            
            # 全ユーザーのクエストデータをチェック
            quests_ref = db.collection('quests')
            user_count = 0
            
            for quest_doc in quests_ref.stream():
                user_id = quest_doc.id
                user_count += 1
                quest_data = quest_doc.to_dict()
                
                print(f"ユーザー {user_count}: {user_id} のクエストデータをチェック")
                
                for quest_id, quest in quest_data.items():
                    if isinstance(quest, dict) and "状態" in quest and quest["状態"] == "達成":
                        completion_date_str = quest.get("達成日")
                        print(f"  達成クエスト発見: {quest_id} - {quest.get('内容', '不明')} (達成日: {completion_date_str})")
                        
                        if completion_date_str:
                            try:
                                completion_date = datetime.datetime.fromisoformat(completion_date_str)
                                if completion_date > week_start:
                                    # ユーザー名を正確に取得
                                    display_name = await self.get_user_display_name(user_id)
                                    print(f"    今週の達成クエスト: {display_name} - {quest.get('内容', 'クエスト')}")
                                    
                                    quest_completions.append({
                                        'user_name': display_name,
                                        'quest_title': quest.get('内容', 'クエスト'),
                                        'completion_date': completion_date,
                                        'quest_type': self.determine_quest_type(quest)
                                    })
                            except Exception as date_error:
                                print(f"    日付解析エラー: {date_error}")
                                continue
            
            print(f"クエスト達成データ収集完了: {len(quest_completions)}件の達成を発見")
            
        except Exception as e:
            print(f"クエスト達成データ収集エラー: {e}")
            import traceback
            print(f"詳細エラー: {traceback.format_exc()}")
        
        return quest_completions

    def determine_quest_type(self, quest) -> None:
        """クエストタイプを判定"""
        try:
            deadline_str = quest.get("期日")
            creation_date_str = quest.get("作成日")
            
            if deadline_str and creation_date_str:
                deadline = datetime.datetime.fromisoformat(deadline_str)
                creation_date = datetime.datetime.fromisoformat(creation_date_str)
                duration = (deadline - creation_date).days
                
                if duration <= 7:
                    return "短期"
                elif duration <= 31:
                    return "中期"
                else:
                    return "長期"
        except:
            pass
        
        return "個人"
    
    async def collect_weekly_kraft_data(self):
        """KRAFTシステムから週次データ収集（修正版）"""
        week_start = datetime.datetime.utcnow() - datetime.timedelta(days=7)
        
        # レベルアップ情報収集（修正版）
        level_ups = await self.collect_real_level_ups()
        
        # クエスト達成情報収集（修正版）
        quest_completions = await self.collect_real_quest_completions()
        
        kr_activities: List[Any] = []  # KR活動は後で拡張
        
        return {
            'level_ups': level_ups,
            'quest_completions': quest_completions,
            'kr_activities': kr_activities
        }
    
    def analyze_messages(self, messages):
        """メッセージを分析してトレンドや話題を抽出"""
        if not messages:
            return {}
        
        # フィルタリング：ネガティブ・プライベート内容を除外
        filtered_messages = []
        for msg in messages:
            content_lower = msg['content'].lower()
            if not any(keyword in content_lower for keyword in NEGATIVE_KEYWORDS + PRIVATE_KEYWORDS):
                if len(msg['content']) > 10:  # 短すぎるメッセージは除外
                    filtered_messages.append(msg)
        
        # トレンド分析
        all_text = ' '.join([msg['content'] for msg in filtered_messages])
        
        # キーワード抽出（簡易版）
        words = re.findall(r'[ぁ-んア-ンa-zA-Z0-9]{3,}', all_text)
        word_freq = Counter(words)
        
        # 人気の話題（リアクション数が多い）
        popular_messages = sorted(filtered_messages, key=lambda x: x['reactions'], reverse=True)[:5]
        
        # チャンネル別活動
        channel_activity = Counter([msg['channel'] for msg in filtered_messages])
        
        # アクティブユーザー
        user_activity = Counter([msg['author'] for msg in filtered_messages])
        
        return {
            'total_messages': len(filtered_messages),
            'trending_keywords': [word for word, count in word_freq.most_common(10) if count > 2],
            'popular_messages': popular_messages,
            'active_channels': dict(channel_activity.most_common(5)),
            'active_users': dict(user_activity.most_common(10)),
            'daily_average': len(filtered_messages) // 7
        }
    
    def generate_weekly_report(self, messages_data, kraft_data, analysis):
        """お馴染みの週刊番組としてのレポート生成"""
        
        # 期間設定
        end_date = datetime.datetime.utcnow()
        start_date = end_date - datetime.timedelta(days=7)
        
        # 週番号計算
        week_number = end_date.isocalendar()[1]
        
        report = f"""# KRAFT Weekly News - 第{week_number}回
## {start_date.strftime('%Y年%m月%d日')} ～ {end_date.strftime('%Y年%m月%d日')}

皆さん、こんにちは！KRAFT Weekly Newsの時間です。今週も一週間お疲れ様でした。
いつものように、この一週間のKRAFTコミュニティの動きを振り返っていきましょう。

## 📊 今週の活動概況

今週のKRAFTは{analysis['total_messages']}件のメッセージが投稿され、{len(analysis['active_users'])}人のメンバーが活動してくださいました。
1日平均{analysis['daily_average']}件の投稿があり、活発な一週間となりました。

### チャンネル別の盛り上がり
{self.format_channel_activity(analysis['active_channels'])}

## 🎉 今週の成長ハイライト

{self.format_level_achievements(kraft_data['level_ups'])}

## 🏆 クエスト達成報告

{self.format_quest_achievements(kraft_data['quest_completions'])}

## 💬 今週の話題とトレンド

{self.format_topics(analysis)}

## 👥 今週のアクティブメンバー

{self.format_active_members(analysis['active_users'])}

## 🌟 編集後記

今週のKRAFTも、{len(analysis['active_users'])}人の皆さんのおかげで温かいコミュニティとなりました。
一人ひとりの参加が、このコミュニティの魅力を作り上げています。
来週もそれぞれのペースで、楽しく活動していきましょう。

来週のKRAFT Weekly Newsでまたお会いしましょう。それでは皆さん、来週も素敵な一週間をお過ごしください！

---
*KRAFT Weekly News 第{week_number}回 - 毎週日曜配信*  
*番組への感想やリクエストは📻｜クラフトラジオチャンネルでお待ちしています*
"""
        
        return report
    
    def format_channel_activity(self, channel_activity):
        """チャンネル活動のフォーマット"""
        if not channel_activity:
            return "今週は全体的に穏やかな活動でした。"
        
        formatted = ["今週特に活発だったチャンネルは："]
        for channel, count in list(channel_activity.items())[:3]:
            formatted.append(f"📺 #{channel}チャンネル: {count}件の投稿")
        
        return '\n'.join(formatted)
    
    def format_level_achievements(self, level_ups):
        """レベルアップ情報のフォーマット（修正版）"""
        if not level_ups:
            return "今週は大きなレベルアップの報告はありませんでしたが、多くのメンバーが経験値を着実に積み重ねています。継続は力なり、ですね。"
        
        formatted = []
        milestone_count = 0
        regular_count = 0
        
        for achievement in level_ups[:8]:  # 最大8件表示
            if achievement.get('is_milestone'):
                formatted.append(f"🏆 **{achievement['user_name']}さん**がレベル{achievement['new_level']}到達！素晴らしいマイルストーンです。")
                milestone_count += 1
            elif 'new_level' in achievement:
                formatted.append(f"🎉 **{achievement['user_name']}さん**がレベル{achievement['old_level']}からレベル{achievement['new_level']}にアップ")
                regular_count += 1
            elif achievement.get('estimated_growth'):
                formatted.append(f"📈 **{achievement['user_name']}さん**が現在レベル{achievement['current_level']}で活発に活動中")
                regular_count += 1
        
        # サマリー追加
        if milestone_count > 0:
            formatted.append(f"\n今週は特に{milestone_count}人のメンバーが大きなマイルストーンを達成されました！")
        
        return '\n'.join(formatted)
    
    def format_quest_achievements(self, quest_completions):
        """クエスト達成情報のフォーマット（修正版）"""
        if not quest_completions:
            return "今週はクエスト達成の報告はありませんでしたが、多くのメンバーが目標に向かって取り組んでいることと思います。皆さんの継続的な努力を応援しています。"
        
        formatted = []
        by_type: Dict[str, Any] = {}
        
        # タイプ別に分類
        for quest in quest_completions:
            quest_type = quest.get('quest_type', '個人')
            if quest_type not in by_type:
                by_type[quest_type] = []
            by_type[quest_type].append(quest)
        
        # タイプ別に表示
        for quest_type, quests in by_type.items():
            if quest_type != '個人':
                formatted.append(f"**{quest_type}クエスト達成**")
            
            for quest in quests[:4]:  # 各タイプ最大4件
                quest_title = quest['quest_title']
                # 長すぎるタイトルは短縮
                if len(quest_title) > 30:
                    quest_title = quest_title[:27] + "..."
                
                formatted.append(f"✅ **{quest['user_name']}さん**「{quest_title}」達成")
        
        total_count = len(quest_completions)
        if total_count > 1:
            formatted.append(f"\n今週は合計{total_count}件のクエストが達成されました。目標に向かう皆さんの姿勢、本当に素晴らしいです！")
        
        return '\n'.join(formatted)
    
    def format_topics(self, analysis):
        """話題のフォーマット"""
        if not analysis['trending_keywords']:
            return "今週は特定の大きな話題はありませんでしたが、日常的な温かい会話が交わされていました。"
        
        keywords = ', '.join(analysis['trending_keywords'][:4])
        return f"""今週よく話題に上がったキーワードは「{keywords}」でした。
コミュニティの関心事が垣間見える興味深い一週間でしたね。"""
    
    def format_active_members(self, active_users):
        """アクティブメンバーのフォーマット"""
        if not active_users:
            return "今週も多くのメンバーにご参加いただき、ありがとうございました。"
        
        top_contributors = list(active_users.items())[:5]
        formatted = ["今週特に活発にご参加いただいたメンバーの皆さん："]
        
        for user, count in top_contributors:
            formatted.append(f"👏 {user}さん（{count}件の投稿）")
        
        return '\n'.join(formatted)

# --------------------------------------
# ✅ Podcast関連コマンド
# --------------------------------------

@tree.command(name="週刊レポート生成", description="NotebookLM用の週刊レポートを生成します（管理者専用）")
async def generate_weekly_report(interaction: discord.Interaction) -> None:
    """週刊レポート生成コマンド"""
    
    # 管理者チェック
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは管理者のみ実行できます。", ephemeral=True)
        return
    
    await interaction.response.defer()
    
    try:
        # 進捗メッセージ
        await interaction.followup.send("📊 週刊データを収集中...")
        
        # データ収集
        podcast_generator = WeeklyPodcastGenerator(bot)
        
        # メッセージデータ収集
        messages, channel_stats = await podcast_generator.collect_weekly_messages()
        await interaction.edit_original_response(content="📊 週刊データを収集中... (Discord メッセージ完了)")
        
        # KRAFTシステムデータ収集
        kraft_data = await podcast_generator.collect_weekly_kraft_data()
        await interaction.edit_original_response(content="📊 週刊データを収集中... (KRAFT データ完了)")
        
        # データ分析
        analysis = podcast_generator.analyze_messages(messages)
        await interaction.edit_original_response(content="📊 週刊データを収集中... (分析完了)")
        
        # レポート生成
        report = podcast_generator.generate_weekly_report(messages, kraft_data, analysis)
        await interaction.edit_original_response(content="📊 週刊データを収集中... (レポート生成完了)")
        
        # ファイル保存
        filename = f"kraft_weekly_report_{datetime.datetime.now().strftime('%Y%m%d')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        # 統計情報の表示
        stats_embed = discord.Embed(
            title="📊 今週のKRAFT統計",
            color=discord.Color.blue()
        )
        
        stats_embed.add_field(
            name="💬 メッセージ統計",
            value=f"総メッセージ数: {analysis['total_messages']}\n"
                  f"アクティブユーザー: {len(analysis['active_users'])}人\n"
                  f"1日平均: {analysis['daily_average']}件",
            inline=True
        )
        
        stats_embed.add_field(
            name="🏆 KRAFT活動",
            value=f"レベルアップ: {len(kraft_data['level_ups'])}件\n"
                  f"クエスト達成: {len(kraft_data['quest_completions'])}件\n"
                  f"KR活動: {len(kraft_data['kr_activities'])}件",
            inline=True
        )
        
        # ファイル送信
        with open(filename, 'rb') as f:
            file = discord.File(f, filename)
            await interaction.edit_original_response(
                content="✅ 週刊レポートが完成しました！\n"
                       "このファイルをNotebookLMにアップロードしてPodcast生成してください。",
                attachments=[file]
            )
        
        # 統計も送信
        await interaction.followup.send(embed=stats_embed)
        
        # ファイルクリーンアップ
        import os
        os.remove(filename)
        
    except Exception as e:
        await interaction.edit_original_response(content=f"❌ エラーが発生しました: {str(e)}")
        print(f"週刊レポート生成エラー: {e}")

@tree.command(name="ポッドキャスト投稿", description="完成したPodcastを📻｜クラフトラジオチャンネルに投稿します（管理者専用）")
async def post_podcast(interaction: discord.Interaction) -> None:
    """Podcast投稿コマンド"""
    
    # 管理者チェック
    if str(interaction.user.id) not in 管理者ID一覧:
        await interaction.response.send_message("❌ このコマンドは管理者のみ実行できます。", ephemeral=True)
        return
    
    # 添付ファイルの確認
    if not interaction.message.attachments:
        await interaction.response.send_message(
            "🎙️ 音声ファイルを添付してこのコマンドを実行してください。\n"
            "対応形式: .mp3, .wav, .m4a, .ogg",
            ephemeral=True
        )
        return
    
    attachment = interaction.message.attachments[0]
    
    # ファイル形式の確認
    audio_extensions = ['.mp3', '.wav', '.m4a', '.ogg', '.flac']
    if not any(attachment.filename.lower().endswith(ext) for ext in audio_extensions):
        await interaction.response.send_message(
            f"❌ 音声ファイルを添付してください。\n対応形式: {', '.join(audio_extensions)}",
            ephemeral=True
        )
        return
    
    await interaction.response.defer()
    
    try:
        # 📻｜クラフトラジオチャンネル取得
        podcast_channel = bot.get_channel(PODCAST_CHANNEL_ID)
        
        if not podcast_channel:
            await interaction.followup.send(f"❌ 📻｜クラフトラジオチャンネルが見つかりません（ID: {PODCAST_CHANNEL_ID}）")
            return
        
        # 豪華な投稿用Embed作成
        embed = discord.Embed(
            title="🎙️ KRAFT Weekly Podcast",
            description=f"**{datetime.datetime.now().strftime('%Y年%m月%d日')}週のコミュニティニュース**",
            color=0x00ff00
        )
        
        embed.add_field(
            name="📻 今週のKRAFT振り返り",
            value="今週のコミュニティ活動をPodcast形式でお届けします！\n"
                  "レベルアップ、クエスト達成、みんなの話題など、\n"
                  "この一週間を音声で振り返ってみてください。",
            inline=False
        )
        
        embed.add_field(
            name="🎧 聞き方",
            value="• ファイルをダウンロードして再生\n"
                  "• Discordで直接再生\n"
                  "• 倍速再生で時短視聴もおすすめ",
            inline=True
        )
        
        embed.add_field(
            name="💭 感想・リクエスト募集",
            value="番組の感想や「こんな話題も取り上げて欲しい」\n"
                  "というリクエストがあれば、\n"
                  "このチャンネルで教えてください！",
            inline=True
        )
        
        embed.set_footer(text="🎵 NotebookLM + KRAFT Bot で自動生成")
        
        # 通知付きで投稿
        await podcast_channel.send(
            content="@everyone 📻 **KRAFT Weekly Podcast** 最新回をお届けします！\n"
                   "今週もお疲れ様でした。ぜひお聞きください！",
            embed=embed,
            file=await attachment.to_file()
        )
        
        await interaction.followup.send("✅ Podcastを📻｜クラフトラジオチャンネルに投稿しました！")
        
    except Exception as e:
        await interaction.followup.send(f"❌ 投稿エラー: {str(e)}")
        print(f"Podcast投稿エラー: {e}")

@tree.command(name="今週の統計", description="今週のコミュニティ統計を表示します")
async def weekly_stats(interaction: discord.Interaction) -> None:
    """今週の統計表示"""
    
    await interaction.response.defer()
    
    try:
        podcast_generator = WeeklyPodcastGenerator(bot)
        
        # データ収集
        messages, channel_stats = await podcast_generator.collect_weekly_messages()
        kraft_data = await podcast_generator.collect_weekly_kraft_data()
        analysis = podcast_generator.analyze_messages(messages)
        
        # 統計Embed作成
        embed = discord.Embed(
            title="📊 今週のKRAFT統計",
            description=f"期間: {(datetime.datetime.utcnow() - datetime.timedelta(days=7)).strftime('%m/%d')} ～ {datetime.datetime.utcnow().strftime('%m/%d')}",
            color=discord.Color.blue()
        )
        
        embed.add_field(
            name="💬 メッセージ活動",
            value=f"総投稿数: **{analysis['total_messages']}件**\n"
                  f"1日平均: **{analysis['daily_average']}件**\n"
                  f"参加者数: **{len(analysis['active_users'])}人**",
            inline=True
        )
        
        embed.add_field(
            name="🏆 KRAFT成長記録",
            value=f"レベルアップ: **{len(kraft_data['level_ups'])}件**\n"
                  f"クエスト達成: **{len(kraft_data['quest_completions'])}件**\n"
                  f"KR活動: **{len(kraft_data['kr_activities'])}件**",
            inline=True
        )
        
        if analysis['trending_keywords']:
            embed.add_field(
                name="🔥 今週のキーワード",
                value=', '.join(analysis['trending_keywords'][:5]),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ 統計取得エラー: {str(e)}")

# 投資システムコマンド - bot.pyに追加

# --------------------------------------
# ✅ 投資システム関連コマンド
# --------------------------------------

# 改善版投資システムコマンド - bot.pyの既存投資コマンドと置き換え

# --------------------------------------
# ✅ 改善版投資システム関連コマンド
# --------------------------------------

# 銘柄選択肢の定義
class StockChoices:
    WICR = "WICR"
    QOOG = "QOOG" 
    RBLX = "RBLX"
    ASST = "ASST"

@tree.command(name="株式購入", description="株式を購入します")
@app_commands.describe(
    銘柄="購入する銘柄を選択してください", 
    株数="購入する株数を入力してください"
)
# bot.pyの選択肢部分を以下と置き換え（株式購入・株式売却の両方）

@app_commands.choices(銘柄=[
    # テック系
    app_commands.Choice(name="🤖 Wicrosoft (WICR) - AI・Bot開発", value="WICR"),
    app_commands.Choice(name="⚛️ Qoogle (QOOG) - 量子コンピュータ", value="QOOG"),
    
    # エンターテイメント系  
    app_commands.Choice(name="🎮 Roblux (RBLX) - ゲーム開発", value="RBLX"),
    app_commands.Choice(name="📺 Netfox (NFOX) - 動画配信", value="NFOX"),
    
    # 伝統産業系
    app_commands.Choice(name="🌱 Mosla (MOSL) - 再生エネルギー", value="MOSL"),
    app_commands.Choice(name="🚚 Nikuda (NKDA) - 物流・配送", value="NKDA"),
    
    # ヘルスケア系
    app_commands.Choice(name="🧬 Firma Schnitzel (FSCH) - バイオテック", value="FSCH"),
    app_commands.Choice(name="🏥 Iroha (IRHA) - 医療IT", value="IRHA"),
    
    # 金融系
    app_commands.Choice(name="💳 Strike (STRK) - デジタル決済", value="STRK"),
    app_commands.Choice(name="🏦 Assist (ASST) - 銀行・金融", value="ASST")
])
async def buy_stock_improved(interaction: discord.Interaction, 銘柄: app_commands.Choice[str], 株数: int) -> None:
    await interaction.response.defer()
    
    try:
        user_id = str(interaction.user.id)
        ticker = 銘柄.value
        
        # 入力検証
        if 株数 <= 0:
            await interaction.followup.send("❌ 株数は1以上を指定してください。")
            return
        
        # 企業情報取得
        company_ref = db.collection("companies").document(ticker)
        company_doc = company_ref.get()
        
        if not company_doc.exists:
            await interaction.followup.send("❌ 企業データが見つかりません。")
            return
        
        company_data = company_doc.to_dict()
        current_price = company_data["current_price"]
        total_cost = current_price * 株数
        transaction_fee = int(total_cost * 0.02)  # 2%手数料
        total_payment = total_cost + transaction_fee
        
        # ユーザーの残高確認
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        
        if not user_doc.exists:
            await interaction.followup.send("❌ ユーザーデータが見つかりません。")
            return
        
        user_data = user_doc.to_dict()
        current_balance = user_data.get("balance", 0)
        
        if current_balance < total_payment:
            await interaction.followup.send(
                f"💸 残高不足です。\n"
                f"必要額: {total_payment:,} KR (株式代金: {total_cost:,} + 手数料: {transaction_fee:,})\n"
                f"現在残高: {current_balance:,} KR"
            )
            return
        
        # 投資データ取得/初期化
        investment_ref = db.collection("user_investments").document(user_id)
        investment_doc = investment_ref.get()
        
        if investment_doc.exists:
            investment_data = investment_doc.to_dict()
        else:
            investment_data = {
                "portfolio": {},
                "total_invested": 0,
                "total_fees_paid": 0
            }
        
        # ポートフォリオ更新
        portfolio = investment_data.get("portfolio", {})
        
        if ticker in portfolio:
            # 既存銘柄の追加購入
            existing_shares = portfolio[ticker]["shares"]
            existing_cost = portfolio[ticker]["total_cost"]
            new_shares = existing_shares + 株数
            new_total_cost = existing_cost + total_cost
            avg_cost = new_total_cost / new_shares
            
            portfolio[ticker] = {
                "shares": new_shares,
                "avg_cost": round(avg_cost, 2),
                "total_cost": new_total_cost,
                "current_price": current_price
            }
        else:
            # 新規銘柄購入
            portfolio[ticker] = {
                "shares": 株数,
                "avg_cost": current_price,
                "total_cost": total_cost,
                "current_price": current_price
            }
        
        # データ更新
        investment_data["portfolio"] = portfolio
        investment_data["total_invested"] = investment_data.get("total_invested", 0) + total_cost
        investment_data["total_fees_paid"] = investment_data.get("total_fees_paid", 0) + transaction_fee
        
        # 残高更新
        user_data["balance"] = current_balance - total_payment
        
        # データベース更新
        investment_ref.set(investment_data)
        user_ref.set(user_data, merge=True)
        
        # 取引履歴記録
        transaction_data = {
            "user_id": user_id,
            "type": "buy",
            "ticker": ticker,
            "shares": 株数,
            "price": current_price,
            "total_cost": total_cost,
            "fee": transaction_fee,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        db.collection("transactions").add(transaction_data)
        
        # 成功メッセージ
        await interaction.followup.send(
            f"✅ **{company_data['name']} ({ticker})** を購入しました！\n\n"
            f"📊 **取引詳細**\n"
            f"株数: **{株数:,}株**\n"
            f"単価: **{current_price:,} KR/株**\n"
            f"株式代金: **{total_cost:,} KR**\n"
            f"手数料: **{transaction_fee:,} KR** (2.0%)\n"
            f"総支払額: **{total_payment:,} KR**\n\n"
            f"💰 残高: **{user_data['balance']:,} KR**"
        )
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")

@tree.command(name="株式売却", description="保有株式を売却します")
@app_commands.describe(
    銘柄="売却する銘柄を選択してください", 
    株数="売却する株数を入力してください"
)
# bot.pyの選択肢部分を以下と置き換え（株式購入・株式売却の両方）

@app_commands.choices(銘柄=[
    # テック系
    app_commands.Choice(name="🤖 Wicrosoft (WICR) - AI・Bot開発", value="WICR"),
    app_commands.Choice(name="⚛️ Qoogle (QOOG) - 量子コンピュータ", value="QOOG"),
    
    # エンターテイメント系  
    app_commands.Choice(name="🎮 Roblux (RBLX) - ゲーム開発", value="RBLX"),
    app_commands.Choice(name="📺 Netfox (NFOX) - 動画配信", value="NFOX"),
    
    # 伝統産業系
    app_commands.Choice(name="🌱 Mosla (MOSL) - 再生エネルギー", value="MOSL"),
    app_commands.Choice(name="🚚 Nikuda (NKDA) - 物流・配送", value="NKDA"),
    
    # ヘルスケア系
    app_commands.Choice(name="🧬 Firma Schnitzel (FSCH) - バイオテック", value="FSCH"),
    app_commands.Choice(name="🏥 Iroha (IRHA) - 医療IT", value="IRHA"),
    
    # 金融系
    app_commands.Choice(name="💳 Strike (STRK) - デジタル決済", value="STRK"),
    app_commands.Choice(name="🏦 Assist (ASST) - 銀行・金融", value="ASST")
])
async def sell_stock_improved(interaction: discord.Interaction, 銘柄: app_commands.Choice[str], 株数: int) -> None:
    await interaction.response.defer()
    
    try:
        user_id = str(interaction.user.id)
        ticker = 銘柄.value
        
        # 投資データ確認
        investment_ref = db.collection("user_investments").document(user_id)
        investment_doc = investment_ref.get()
        
        if not investment_doc.exists:
            await interaction.followup.send("❌ 投資データが見つかりません。まず株式を購入してください。")
            return
        
        investment_data = investment_doc.to_dict()
        portfolio = investment_data.get("portfolio", {})
        
        if ticker not in portfolio:
            await interaction.followup.send(f"❌ {ticker} を保有していません。")
            return
        
        holding = portfolio[ticker]
        if holding["shares"] < 株数:
            await interaction.followup.send(
                f"❌ 保有株数が不足しています。\n"
                f"保有数: {holding['shares']}株、売却希望: {株数}株"
            )
            return
        
        # 企業情報取得
        company_ref = db.collection("companies").document(ticker)
        company_doc = company_ref.get()
        company_data = company_doc.to_dict()
        current_price = company_data["current_price"]
        
        # 売却計算
        total_revenue = current_price * 株数
        transaction_fee = int(total_revenue * 0.02)  # 2%手数料
        net_revenue = total_revenue - transaction_fee
        
        # 損益計算
        cost_basis = holding["avg_cost"] * 株数
        profit_loss = total_revenue - cost_basis
        
        # ポートフォリオ更新
        if holding["shares"] == 株数:
            # 全株売却
            del portfolio[ticker]
        else:
            # 一部売却
            remaining_shares = holding["shares"] - 株数
            remaining_cost = holding["total_cost"] - cost_basis
            portfolio[ticker] = {
                "shares": remaining_shares,
                "avg_cost": holding["avg_cost"],
                "total_cost": remaining_cost,
                "current_price": current_price
            }
        
        # ユーザー残高更新
        user_ref = db.collection("users").document(user_id)
        user_doc = user_ref.get()
        user_data = user_doc.to_dict()
        user_data["balance"] = user_data.get("balance", 0) + net_revenue
        
        # データベース更新
        investment_data["portfolio"] = portfolio
        investment_ref.set(investment_data)
        user_ref.set(user_data, merge=True)
        
        # 取引履歴記録
        transaction_data = {
            "user_id": user_id,
            "type": "sell",
            "ticker": ticker,
            "shares": 株数,
            "price": current_price,
            "total_revenue": total_revenue,
            "fee": transaction_fee,
            "profit_loss": profit_loss,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        db.collection("transactions").add(transaction_data)
        
        # 損益表示
        profit_emoji = "📈" if profit_loss >= 0 else "📉"
        profit_text = f"+{profit_loss:,}" if profit_loss >= 0 else f"{profit_loss:,}"
        
        await interaction.followup.send(
            f"✅ **{company_data['name']} ({ticker})** を売却しました！\n\n"
            f"📊 **取引詳細**\n"
            f"株数: **{株数:,}株**\n"
            f"単価: **{current_price:,} KR/株**\n"
            f"売却代金: **{total_revenue:,} KR**\n"
            f"手数料: **{transaction_fee:,} KR** (2.0%)\n"
            f"受取金額: **{net_revenue:,} KR**\n\n"
            f"{profit_emoji} **損益: {profit_text} KR**\n"
            f"💰 残高: **{user_data['balance']:,} KR**"
        )
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")


@tree.command(name="ポートフォリオ", description="投資ポートフォリオを表示します")
async def portfolio(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    
    try:
        user_id = str(interaction.user.id)
        
        # 投資データ取得
        investment_ref = db.collection("user_investments").document(user_id)
        investment_doc = investment_ref.get()
        
        if not investment_doc.exists:
            await interaction.followup.send(
                "📊 **投資ポートフォリオ**\n\n"
                "投資データがありません。\n"
                "`/投資購入` コマンドで投資を始めましょう！"
            )
            return
        
        investment_data = investment_doc.to_dict()
        portfolio = investment_data.get("portfolio", {})
        
        if not portfolio:
            await interaction.followup.send(
                "📊 **投資ポートフォリオ**\n\n"
                "現在保有銘柄はありません。\n"
                "`/投資購入` コマンドで投資を始めましょう！"
            )
            return
        
        # 現在価格を取得して評価額計算
        total_value = 0
        total_cost = 0
        holdings_text = []
        
        for ticker, holding in portfolio.items():
            company_ref = db.collection("companies").document(ticker)
            company_doc = company_ref.get()
            company_data = company_doc.to_dict()
            
            current_price = company_data["current_price"]
            shares = holding["shares"]
            avg_cost = holding["avg_cost"]
            cost_basis = holding["total_cost"]
            current_value = current_price * shares
            profit_loss = current_value - cost_basis
            profit_rate = (profit_loss / cost_basis) * 100
            
            total_value += current_value
            total_cost += cost_basis
            
            profit_emoji = "📈" if profit_loss >= 0 else "📉"
            profit_text = f"+{profit_loss:,}" if profit_loss >= 0 else f"{profit_loss:,}"
            rate_text = f"+{profit_rate:.1f}%" if profit_rate >= 0 else f"{profit_rate:.1f}%"
            
            holdings_text.append(
                f"**{company_data['name']} ({ticker})**\n"
                f"保有: {shares:,}株 | 平均: {avg_cost:,}KR → 現在: {current_price:,}KR\n"
                f"評価額: {current_value:,}KR | {profit_emoji} {profit_text}KR ({rate_text})\n"
            )
        
        # 全体損益
        total_profit = total_value - total_cost
        total_rate = (total_profit / total_cost) * 100 if total_cost > 0 else 0
        
        portfolio_emoji = "📈" if total_profit >= 0 else "📉"
        total_profit_text = f"+{total_profit:,}" if total_profit >= 0 else f"{total_profit:,}"
        total_rate_text = f"+{total_rate:.1f}%" if total_rate >= 0 else f"{total_rate:.1f}%"
        
        embed = discord.Embed(
            title="📊 投資ポートフォリオ",
            color=discord.Color.green() if total_profit >= 0 else discord.Color.red()
        )
        
        embed.add_field(
            name="💼 総合評価",
            value=(
                f"評価額: **{total_value:,} KR**\n"
                f"投資元本: **{total_cost:,} KR**\n"
                f"{portfolio_emoji} 損益: **{total_profit_text} KR ({total_rate_text})**"
            ),
            inline=False
        )
        
        embed.add_field(
            name="📈 保有銘柄",
            value="\n".join(holdings_text),
            inline=False
        )
        
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        await interaction.followup.send(f"❌ エラーが発生しました: {str(e)}")

# --------------------------------------
# ✅ Bot起動
# --------------------------------------

# ✅ Botを起動
bot.run(TOKEN)