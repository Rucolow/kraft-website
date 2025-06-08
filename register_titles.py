import firebase_admin
from firebase_admin import credentials, firestore

# Firebase認証
cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)
db = firestore.client()

# 称号データ
titles = [
    {"id": "quest_1", "category": "クエスト", "name": "冒険の始まり", "condition": "クエスト達成数1回", "effect": "特になし"},
    {"id": "quest_10", "category": "クエスト", "name": "成長の兆し", "condition": "クエスト達成数10回", "effect": "特になし"},
    {"id": "quest_30", "category": "クエスト", "name": "継続は力なり", "condition": "クエスト達成数30回", "effect": "特になし"},
    {"id": "quest_50", "category": "クエスト", "name": "成長の上昇気流", "condition": "クエスト達成数50回", "effect": "特になし"},
    {"id": "quest_2fail", "category": "クエスト", "name": "どんまい", "condition": "クエスト2連続未達成", "effect": "特になし"},
    {"id": "quest_10fail", "category": "クエスト", "name": "逆にすごい", "condition": "クエスト10回連続未達成", "effect": "特になし"},
    {"id": "quest_top", "category": "クエスト", "name": "クエストマスター", "condition": "年間クエスト達成数1位", "effect": "特になし"},
    {"id": "emergency_top", "category": "クエスト", "name": "村の救世主", "condition": "年間緊急クエスト参加最多", "effect": "特になし"},
    {"id": "donation_top", "category": "寄付", "name": "寄付マスター", "condition": "年間寄付額トップ", "effect": "特になし"},
    {"id": "donation_0", "category": "寄付", "name": "聖人", "condition": "寄付で残高が0になった", "effect": "特になし"},
    {"id": "invest_top", "category": "投資", "name": "投資マスター", "condition": "年間最多投資報酬獲得者", "effect": "特になし"},
    {"id": "invest_0", "category": "投資", "name": "ノーリターン", "condition": "投資で残高が0になった", "effect": "特になし"},
    {"id": "gift_top", "category": "送金", "name": "ギフトマスター", "condition": "年間ユーザー間送信額トップ", "effect": "特になし"},
    {"id": "gift_0", "category": "送金", "name": "大盤振る舞い", "condition": "他のユーザーに送金して残高が0になった", "effect": "特になし"},
    {"id": "gamble_top", "category": "ギャンブル", "name": "ギャンブルマスター", "condition": "年間最多ギャンブル報酬獲得者", "effect": "特になし"},
    {"id": "gamble_0", "category": "ギャンブル", "name": "ギャンブル狂い", "condition": "ギャンブルで残高が0になった", "effect": "特になし"},
    {"id": "gamble_lose3", "category": "ギャンブル", "name": "地獄の入り口", "condition": "ギャンブルで3連敗", "effect": "特になし"},
    {"id": "guild_create", "category": "その他", "name": "ギルドマスター", "condition": "ギルドを創設", "effect": "5000KRを支払い、自分のギルドを創設できる"},
    {"id": "login_100", "category": "その他", "name": "秘密の共有者", "condition": "初回ログインから100日経過 または 寄付額5000KR超え", "effect": "シークレットスレッドにアクセス可能"},
    {"id": "login_most", "category": "その他", "name": "どこにでもいる人", "condition": "月間最多ログイン", "effect": "特になし"},
    {"id": "message_most", "category": "その他", "name": "よく喋る人", "condition": "月間で最も多く発言した", "effect": "特になし"},
    {"id": "eminem", "category": "その他", "name": "エミネム", "condition": "投稿内容が平均80文字以上、直近5件中3件が長文", "effect": "特になし"}
]

# Firestoreにアップロード
for title in titles:
    doc_ref = db.collection("titles").document(title["id"])
    doc_ref.set(title)

print("✅ 全ての称号データをFirestoreに登録しました！")