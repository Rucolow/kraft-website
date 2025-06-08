import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Firebase 初期化
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

# 寄付先の登録
donation_targets = [
    {"name": "学校建設プロジェクト", "description": "村の子どもたちのための学校を建てます"},
    {"name": "森林再生活動", "description": "伐採された森を復活させるための植林活動"},
    {"name": "農業支援プログラム", "description": "若者のための農業スタートアップ支援"}
]

for target in donation_targets:
    doc_ref = db.collection("donation_targets").document(target["name"])
    doc_ref.set({
        "name": target["name"],
        "description": target["description"],
        "created_at": datetime.datetime.utcnow().isoformat()
    })
    print(f"✅ 寄付先「{target['name']}」を登録しました")