import pytest
from notification_system import NotificationSystem
import discord
from datetime import datetime
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

@pytest.fixture
def mock_bot() -> AsyncMock:
    return AsyncMock(spec=discord.Client)

@pytest.fixture
def mock_channel() -> AsyncMock:
    return AsyncMock(spec=discord.TextChannel)

@pytest.fixture
def mock_user() -> AsyncMock:
    user = AsyncMock(spec=discord.User)
    user.name = "TestUser"
    user.display_avatar.url = "https://example.com/avatar.png"
    return user

@pytest.fixture
def notification_system(mock_bot: AsyncMock) -> NotificationSystem:
    return NotificationSystem(mock_bot)

@pytest.mark.asyncio
async def test_send_level_up_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """レベルアップ通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # テストデータ
    old_level = 1
    new_level = 2
    kr_reward = 100
    new_titles = ["冒険者"]
    
    # 通知送信
    result = await notification_system.send_level_up_notification(
        mock_user,
        old_level,
        new_level,
        kr_reward,
        new_titles
    )
    await asyncio.sleep(0.1)
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    embed = mock_channel.send.call_args[1]["embed"]
    assert "レベルアップ" in embed.description
    assert str(old_level) in embed.description
    assert str(new_level) in embed.description
    assert str(kr_reward) in embed.description
    assert "冒険者" in embed.description

@pytest.mark.asyncio
async def test_send_title_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """称号獲得通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # テストデータ
    title = "冒険者"
    
    # 通知送信
    result = await notification_system.send_title_notification(
        mock_user,
        title
    )
    await asyncio.sleep(0.1)
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    embed = mock_channel.send.call_args[1]["embed"]
    assert "称号" in embed.description
    assert title in embed.description

@pytest.mark.asyncio
async def test_notification_channel_not_found(
    mock_bot: AsyncMock,
    mock_user: AsyncMock
) -> None:
    """通知チャンネルが見つからない場合のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = None
    
    # 通知送信
    result = await notification_system.send_level_up_notification(
        mock_user,
        1,
        2,
        100,
        []
    )
    await asyncio.sleep(0.1)
    # アサーション
    assert result is False
    mock_bot.get_channel.assert_called_once()

@pytest.mark.asyncio
async def test_notification_error_handling(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """通知エラー処理のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    mock_channel.send.side_effect = Exception("Test error")
    
    # 通知送信
    result = await notification_system.send_level_up_notification(
        mock_user,
        1,
        2,
        100,
        []
    )
    await asyncio.sleep(0.1)
    # アサーション
    assert result is False
    mock_channel.send.assert_called_once()

@pytest.mark.asyncio
async def test_multiple_notification_types(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """複数の通知タイプを同時に送信するテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # レベルアップと称号獲得の通知を同時に送信
    results = await asyncio.gather(
        notification_system.send_level_up_notification(mock_user, 1, 2, 100, []),
        notification_system.send_title_notification(mock_user, "冒険者")
    )
    await asyncio.sleep(0.1)
    
    # 両方の通知が成功するはず
    assert all(results)
    assert mock_channel.send.call_count == 2
    
    # 各通知の内容を確認
    calls = mock_channel.send.call_args_list
    level_up_embed = calls[0][1]["embed"]
    title_embed = calls[1][1]["embed"]
    
    assert "レベルアップ" in level_up_embed.description
    assert "称号" in title_embed.description

@pytest.mark.asyncio
async def test_notification_with_custom_color(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """カスタムカラーを使用した通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    custom_color = 0xff0000  # 赤色
    
    # カスタムカラーで通知を送信
    result = await notification_system.send_notification(
        "level_up",
        mock_user,
        "テスト通知",
        color=custom_color
    )
    await asyncio.sleep(0.1)
    
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    
    # Embedの色を確認
    embed = mock_channel.send.call_args[1]["embed"]
    assert embed.color.value == custom_color

@pytest.mark.asyncio
async def test_notification_with_multiple_fields(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """複数のフィールドを持つ通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # 複数のフィールドを持つ通知を送信
    fields = [
        {"name": "フィールド1", "value": "値1", "inline": True},
        {"name": "フィールド2", "value": "値2", "inline": False},
        {"name": "フィールド3", "value": "値3", "inline": True}
    ]
    
    result = await notification_system.send_notification(
        "level_up",
        mock_user,
        "テスト通知",
        fields=fields
    )
    await asyncio.sleep(0.1)
    
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    
    # Embedのフィールドを確認
    embed = mock_channel.send.call_args[1]["embed"]
    assert len(embed.fields) == 3
    assert embed.fields[0].name == "フィールド1"
    assert embed.fields[0].value == "値1"
    assert embed.fields[0].inline is True
    assert embed.fields[1].name == "フィールド2"
    assert embed.fields[1].value == "値2"
    assert embed.fields[1].inline is False
    assert embed.fields[2].name == "フィールド3"
    assert embed.fields[2].value == "値3"
    assert embed.fields[2].inline is True

@pytest.mark.asyncio
async def test_batch_processing(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """バッチ処理のテスト"""
    notification_system = NotificationSystem(mock_bot)
    mock_bot.get_channel.return_value = mock_channel
    
    # バッチ処理を開始
    await notification_system.start_batch_processing()
    
    # 複数の通知を送信
    for i in range(3):
        await notification_system.send_notification(
            "level_up",
            mock_user,
            f"テスト通知 {i}"
        )
    
    # バッチ処理が完了するまで待機
    await asyncio.sleep(notification_system.batch_delay * 2)
    
    # アサーション
    assert mock_channel.send.call_count == 3
    
    # バッチ処理を停止
    await notification_system.stop_batch_processing()

@pytest.mark.asyncio
async def test_force_immediate_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """即時送信を強制するテスト"""
    notification_system = NotificationSystem(mock_bot)  # バッチモード
    mock_bot.get_channel.return_value = mock_channel
    
    # force_immediate=Trueで通知を送信
    result = await notification_system.send_notification(
        "level_up",
        mock_user,
        "テスト通知",
        force_immediate=True
    )
    
    # 即時送信されるはず
    assert result is True
    mock_channel.send.assert_called_once()

@pytest.mark.asyncio
async def test_immediate_mode_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """即時送信モードのテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # 通知を送信
    result = await notification_system.send_notification(
        "level_up",
        mock_user,
        "テスト通知"
    )
    
    # 即時送信されるはず
    assert result is True
    mock_channel.send.assert_called_once()

@pytest.mark.asyncio
async def test_batch_size_limit(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """バッチサイズ制限のテスト"""
    notification_system = NotificationSystem(mock_bot)
    notification_system.batch_size = 2
    mock_bot.get_channel.return_value = mock_channel
    
    # バッチ処理を開始
    await notification_system.start_batch_processing()
    
    # バッチサイズより多い通知を送信
    for i in range(5):
        await notification_system.send_notification(
            "level_up",
            mock_user,
            f"テスト通知 {i}"
        )
    
    # バッチ処理が完了するまで待機
    await asyncio.sleep(notification_system.batch_delay * 2)
    
    # アサーション
    assert mock_channel.send.call_count == 5
    
    # バッチ処理を停止
    await notification_system.stop_batch_processing()

@pytest.mark.asyncio
async def test_send_quest_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """クエスト完了通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # 通知送信
    result = await notification_system.send_quest_notification(
        mock_user,
        "テストクエスト"
    )
    
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    embed = mock_channel.send.call_args[1]["embed"]
    assert "クエスト完了" in embed.description
    assert "テストクエスト" in embed.description

@pytest.mark.asyncio
async def test_send_donation_notification(
    mock_bot: AsyncMock,
    mock_user: AsyncMock,
    mock_channel: AsyncMock
) -> None:
    """寄付通知のテスト"""
    notification_system = NotificationSystem(mock_bot, immediate_mode=True)
    mock_bot.get_channel.return_value = mock_channel
    
    # 通知送信
    result = await notification_system.send_donation_notification(
        mock_user,
        1000
    )
    
    # アサーション
    assert result is True
    mock_channel.send.assert_called_once()
    embed = mock_channel.send.call_args[1]["embed"]
    assert "寄付" in embed.description
    assert "1000" in embed.description 