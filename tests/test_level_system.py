import unittest
import asyncio
from unittest.mock import Mock, patch
import sys
import os

# プロジェクトのルートディレクトリをPythonパスに追加
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from level_system import add_xp_and_check_level_up, get_level_info

class TestLevelSystem(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.get_event_loop()
    
    def tearDown(self):
        self.loop.close()
    
    @patch('level_system.get_db')
    async def test_level_up_notification(self, mock_get_db):
        # モックの設定
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # テスト用のユーザーデータ
        test_user_id = "test_user_123"
        test_user_data = {
            "level": 1,
            "xp": 0,
            "balance": 0,
            "titles": ["偉大なる一歩"]
        }
        
        # Firestoreのモック設定
        mock_user_ref = Mock()
        mock_user_doc = Mock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = test_user_data
        mock_user_ref.get.return_value = mock_user_doc
        mock_db.collection.return_value.document.return_value = mock_user_ref
        
        # テスト実行
        level_up, new_level, old_level, kr_reward, new_titles = await add_xp_and_check_level_up(
            test_user_id,
            xp_amount=1000  # レベルアップするのに十分なXP
        )
        
        # アサーション
        self.assertTrue(level_up)
        self.assertEqual(new_level, 2)
        self.assertEqual(old_level, 1)
        self.assertTrue(kr_reward > 0)
        self.assertTrue(len(new_titles) > 0)
    
    @patch('level_system.get_db')
    async def test_no_level_up(self, mock_get_db):
        # モックの設定
        mock_db = Mock()
        mock_get_db.return_value = mock_db
        
        # テスト用のユーザーデータ
        test_user_id = "test_user_123"
        test_user_data = {
            "level": 1,
            "xp": 0,
            "balance": 0,
            "titles": ["偉大なる一歩"]
        }
        
        # Firestoreのモック設定
        mock_user_ref = Mock()
        mock_user_doc = Mock()
        mock_user_doc.exists = True
        mock_user_doc.to_dict.return_value = test_user_data
        mock_user_ref.get.return_value = mock_user_doc
        mock_db.collection.return_value.document.return_value = mock_user_ref
        
        # テスト実行
        level_up, new_level, old_level, kr_reward, new_titles = await add_xp_and_check_level_up(
            test_user_id,
            xp_amount=10  # レベルアップしないXP量
        )
        
        # アサーション
        self.assertFalse(level_up)
        self.assertEqual(new_level, 1)
        self.assertEqual(old_level, 1)
        self.assertEqual(kr_reward, 0)
        self.assertEqual(len(new_titles), 0)

if __name__ == '__main__':
    unittest.main() 