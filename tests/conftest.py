import pytest
import discord
from unittest.mock import Mock, AsyncMock
import sys
import os
from discord.ext import commands

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

@pytest.fixture
def mock_bot(mock_channel):
    """Discord Botのモックを作成"""
    bot = Mock(spec=commands.Bot)
    bot.get_channel = AsyncMock(return_value=mock_channel)
    return bot

@pytest.fixture
def mock_user():
    """Discord Userのモックを作成"""
    user = Mock(spec=discord.User)
    user.id = 123456789
    user.name = "TestUser"
    user.display_name = "Test User"
    user.avatar = Mock()
    user.avatar.url = "https://example.com/avatar.png"
    return user

@pytest.fixture
def mock_channel():
    """Discord TextChannelのモックを作成"""
    channel = Mock(spec=discord.TextChannel)
    channel.id = 1352859030715891782
    channel.send = AsyncMock(return_value=None)
    return channel

@pytest.fixture
def mock_interaction(mock_user):
    """Discord Interactionのモックを作成"""
    interaction = Mock(spec=discord.Interaction)
    interaction.user = mock_user
    interaction.response = Mock()
    interaction.response.send_message = AsyncMock(return_value=None)
    return interaction 