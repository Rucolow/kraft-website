import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Firebase 初期化
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)
db = firestore.client()

now = datetime.datetime.utcnow()
users_ref = db.collection("quests")
users = users_ref.stream()

for user in users:
    data = user.to_dict()
    updated = False
    streak = data.get("quest_streak", 0)
    titles = set(data.get("titles", []))

    for quest_type in ["weekly", "monthly", "yearly"]:
        quest = data.get(quest_type)
        if isinstance(quest, dict) and quest.get("状態") == "進行中":
            deadline_str = quest.get("期限")
            if deadline_str:
                deadline = datetime.datetime.fromisoformat(deadline_str)
                if now > deadline:
                    # 未達成扱い
                    quest["状態"] = "未達成"
                    data[quest_type] = quest
                    streak += 1
                    updated = True
                    print(f"{user.id} の {quest_type} クエストが未達成に")

                    # 🔁 過去クエストに追加
                    past_list = data.get("past_quests", [])
                    past_list.append({
                        "種類": quest_type,
                        "内容": quest.get("内容", ""),
                        "状態": "未達成",
                        "期限": quest.get("期限"),
                        "判定時刻": now.isoformat()
                    })
                    data["past_quests"] = past_list

    # ストリーク称号
    if streak >= 10 and "逆にすごい" not in titles:
        titles.add("逆にすごい")
        print(f"{user.id} が称号「逆にすごい」を獲得！")
    elif streak == 2 and "どんまい" not in titles:
        titles.add("どんまい")
        print(f"{user.id} が称号「どんまい」を獲得！")

    if updated:
        data["quest_streak"] = streak
        data["titles"] = list(titles)
        users_ref.document(user.id).set(data)