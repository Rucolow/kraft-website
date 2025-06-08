import discord
from typing import Optional, List, Dict, Any, Tuple, DefaultDict, Union, cast, Set, Protocol
import asyncio
from datetime import datetime
import os
from collections import defaultdict

class NotificationChannel(Protocol):
    """通知チャンネルのプロトコル"""
    async def send(self, content: Optional[str] = None, *, embed: Optional[discord.Embed] = None) -> discord.Message:
        ...

class NotificationSystem:
    """
    Discord通知システム。バッチ処理・即時送信・チャンネルキャッシュ・重複防止などを提供。
    """
    bot: discord.Client
    notification_channels: Dict[str, int]
    notification_locks: Dict[str, asyncio.Lock]
    channel_cache: Dict[int, discord.TextChannel]
    notification_queue: Dict[str, List[Tuple[discord.TextChannel, discord.User, str, int, Optional[str], Optional[List[Dict[str, Any]]]]]]
    batch_size: int
    batch_delay: float
    _batch_tasks: Dict[str, Optional[asyncio.Task]]
    is_test: bool
    immediate_mode: bool

    def __init__(self, bot: discord.Client, immediate_mode: bool = False) -> None:
        """
        NotificationSystemの初期化。
        Args:
            bot: Discord Botインスタンス
            immediate_mode: 即時送信モードを有効にするかどうか
        """
        self.bot = bot
        self.notification_channels: Dict[str, int] = {
            'level_up': 1234567890,  # レベルアップ通知用チャンネルID
            'title': 1234567890,     # 称号獲得通知用チャンネルID
            'quest': 1234567890,     # クエスト完了通知用チャンネルID
            'donation': 1234567890   # 寄付通知用チャンネルID
        }
        self.notification_locks: Dict[str, asyncio.Lock] = {}
        self.channel_cache: Dict[int, discord.TextChannel] = {}
        self.notification_queue: Dict[str, List[Tuple[discord.TextChannel, discord.User, str, int, Optional[str], Optional[List[Dict[str, Any]]]]]] = defaultdict(list)
        self.batch_size: int = 5
        self.batch_delay: float = 1.0
        self._batch_tasks: Dict[str, Optional[asyncio.Task]] = {
            'level_up': None,
            'title': None,
            'quest': None,
            'donation': None
        }
        self.is_test: bool = bool(os.getenv('PYTEST_CURRENT_TEST'))
        self.immediate_mode: bool = immediate_mode
    
    async def _get_channel(self, notification_type: str) -> Optional[discord.TextChannel]:
        """
        チャンネルを取得（キャッシュを使用）
        Args:
            notification_type: 通知タイプ
        Returns:
            Optional[discord.TextChannel]: 取得したチャンネル
        """
        channel_id = self.notification_channels.get(notification_type)
        if not channel_id:
            return None

        channel = self.channel_cache.get(channel_id)
        if not channel:
            raw_channel = self.bot.get_channel(channel_id)
            if isinstance(raw_channel, discord.TextChannel):
                self.channel_cache[channel_id] = raw_channel
                channel = raw_channel
            else:
                return None

        return channel

    async def _send_notification_immediate(
        self,
        channel: discord.TextChannel,
        user: discord.User,
        content: str,
        color: int,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None
    ) -> bool:
        """
        通知を即時送信する。
        Args:
            channel: 送信先チャンネル
            user: 通知対象ユーザー
            content: 通知内容
            color: 埋め込み色
            title: 通知タイトル
            fields: 追加フィールド
        Returns:
            bool: 成功時True
        """
        try:
            embed = discord.Embed(
                title=title or f"🎉 {user.name} の通知",
                description=content,
                color=color,
                timestamp=datetime.now()
            )
            embed.set_author(name=str(user), icon_url=user.display_avatar.url)

            if fields:
                for field in fields:
                    embed.add_field(
                        name=field.get("name", ""),
                        value=field.get("value", ""),
                        inline=field.get("inline", True)
                    )

            await channel.send(embed=embed)
            return True
        except Exception as e:
            print(f"Error sending notification: {e}")
            return False

    async def send_notification(
        self,
        notification_type: str,
        user: discord.User,
        content: str,
        color: int = 0x00ff00,
        title: Optional[str] = None,
        fields: Optional[List[Dict[str, Any]]] = None,
        force_immediate: bool = False
    ) -> bool:
        """
        通知を送信する。
        Args:
            notification_type: 通知タイプ
            user: 通知対象ユーザー
            content: 通知内容
            color: 埋め込み色
            title: 通知タイトル
            fields: 追加フィールド
            force_immediate: 即時送信を強制するかどうか
        Returns:
            bool: 成功時True
        """
        try:
            # チャンネルを取得
            channel = await self._get_channel(notification_type)
            if not channel:
                print(f"⚠️ 通知チャンネルが見つかりません（タイプ: {notification_type}）")
                return False

            # 即時送信モードまたはテスト環境の場合は即時送信
            if self.immediate_mode or self.is_test or force_immediate:
                return await self._send_notification_immediate(channel, user, content, color, title, fields)

            # バッチ処理を使用
            self.notification_queue[notification_type].append((channel, user, content, color, title, fields))
            return True

        except Exception as e:
            print(f"Error in send_notification: {e}")
            return False

    async def _process_batch(self, notification_type: str) -> None:
        """
        バッチで通知を送信する内部ループ。
        Args:
            notification_type: 通知タイプ
        """
        while True:
            try:
                notifications = self.notification_queue[notification_type]
                if not notifications:
                    await asyncio.sleep(self.batch_delay)
                    continue

                # バッチサイズ分の通知を取得
                batch = notifications[:self.batch_size]
                self.notification_queue[notification_type] = notifications[self.batch_size:]

                # バッチ内の通知を処理
                for channel, user, content, color, title, fields in batch:
                    await self._send_notification_immediate(channel, user, content, color, title, fields)
                    await asyncio.sleep(0.1)  # レート制限を考慮した待機

            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in batch processing: {e}")
                await asyncio.sleep(self.batch_delay)

    async def start_batch_processing(self) -> None:
        """
        バッチ処理を開始する。
        """
        for notification_type in self.notification_channels.keys():
            if self._batch_tasks[notification_type] is None:
                self._batch_tasks[notification_type] = asyncio.create_task(
                    self._process_batch(notification_type)
                )

    async def stop_batch_processing(self) -> None:
        """
        バッチ処理を停止する。
        """
        for notification_type, task in self._batch_tasks.items():
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                self._batch_tasks[notification_type] = None

    async def send_level_up_notification(
        self,
        user: discord.User,
        old_level: int,
        new_level: int,
        kr_reward: int,
        new_titles: List[str]
    ) -> bool:
        """
        レベルアップ通知を送信。
        Args:
            user: 通知対象ユーザー
            old_level: 旧レベル
            new_level: 新レベル
            kr_reward: 報酬KR
            new_titles: 新称号リスト
        Returns:
            bool: 成功時True
        """
        content = f"🎉 レベルアップ！\nレベル {old_level} → {new_level}\n💰 報酬: {kr_reward}KR"
        if new_titles:
            content += f"\n🏆 新しい称号: {', '.join(new_titles)}"
        return await self.send_notification('level_up', user, content, 0x00ff00)

    async def send_title_notification(self, user: discord.User, title: str) -> bool:
        """
        称号獲得通知を送信。
        Args:
            user: 通知対象ユーザー
            title: 称号名
        Returns:
            bool: 成功時True
        """
        content = f"🏆 新しい称号を獲得しました！\n{title}"
        return await self.send_notification('title', user, content, 0xffd700)

    async def send_quest_notification(self, user: discord.User, quest_name: str) -> bool:
        """
        クエスト完了通知を送信。
        Args:
            user: 通知対象ユーザー
            quest_name: クエスト名
        Returns:
            bool: 成功時True
        """
        content = f"✅ クエスト完了！\n{quest_name}"
        return await self.send_notification('quest', user, content, 0x4169e1)

    async def send_donation_notification(self, user: discord.User, amount: int) -> bool:
        """
        寄付通知を送信。
        Args:
            user: 通知対象ユーザー
            amount: 寄付額
        Returns:
            bool: 成功時True
        """
        content = f"💖 寄付ありがとうございます！\n💰 寄付額: {amount}KR"
        return await self.send_notification('donation', user, content, 0xff69b4) 