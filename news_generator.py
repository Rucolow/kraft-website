# news_generator.py - Claude API使用のニュース生成システム

import os
import anthropic
import firebase_admin
from firebase_admin import firestore
import datetime
import random
import json
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

# Claude API初期化
claude_client = anthropic.Anthropic(api_key=CLAUDE_API_KEY)

# Firebase初期化（既存の設定使用）
if not firebase_admin._apps:
    from firebase_admin import credentials
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

class NewsGenerator:
    def __init__(self):
        self.company_contexts = {
            "WICR": {
                "name": "Wicrosoft",
                "industry": "AI・Bot開発",
                "business": "Discord Bot開発・運営、AI チャットボット技術、自然言語処理エンジン",
                "news_types": ["技術革新", "新機能リリース", "パートナーシップ", "AI業界動向"]
            },
            "QOOG": {
                "name": "Qoogle", 
                "industry": "量子コンピュータ",
                "business": "量子コンピュータ研究開発、次世代暗号化技術、金融機関向けセキュリティ",
                "news_types": ["技術ブレークスルー", "研究成果発表", "政府契約", "特許関連"]
            },
            "RBLX": {
                "name": "Roblux",
                "industry": "ゲーム開発", 
                "business": "PCゲーム開発、モバイルゲーム運営、eスポーツイベント主催",
                "news_types": ["新作発表", "ユーザー数増加", "大会開催", "コラボ企画"]
            },
            "NFOX": {
                "name": "Netfox",
                "industry": "動画配信",
                "business": "動画配信プラットフォーム運営、ライブストリーミング、コンテンツ制作",
                "news_types": ["人気コンテンツ", "クリエイター契約", "新機能追加", "利用者数"]
            },
            "MOSL": {
                "name": "Mosla",
                "industry": "再生エネルギー",
                "business": "太陽光発電システム製造、風力発電設備、環境コンサルティング",
                "news_types": ["大型プロジェクト受注", "技術革新", "政府支援", "環境規制"]
            },
            "NKDA": {
                "name": "Nikuda", 
                "industry": "物流・配送",
                "business": "国際物流サービス、倉庫管理・配送、サプライチェーン最適化",
                "news_types": ["大手企業契約", "物流効率化", "新拠点開設", "燃料価格影響"]
            },
            "FSCH": {
                "name": "Firma Schnitzel",
                "industry": "バイオテクノロジー", 
                "business": "新薬研究開発、遺伝子治療技術、臨床試験サービス",
                "news_types": ["臨床試験結果", "新薬承認", "研究提携", "規制対応"]
            },
            "IRHA": {
                "name": "Iroha",
                "industry": "医療IT",
                "business": "電子カルテシステム、遠隔診療プラットフォーム、AI診断支援",
                "news_types": ["医療機関導入", "AI精度向上", "遠隔医療拡大", "データセキュリティ"]
            },
            "STRK": {
                "name": "Strike", 
                "industry": "デジタル決済",
                "business": "デジタル決済サービス、暗号通貨取引所、ブロックチェーン技術",
                "news_types": ["決済提携", "規制対応", "セキュリティ強化", "暗号通貨動向"]
            },
            "ASST": {
                "name": "Assist",
                "industry": "銀行・金融",
                "business": "個人・法人向け銀行業務、住宅ローン・事業融資、資産運用サービス", 
                "news_types": ["業績発表", "新サービス", "金利政策影響", "デジタル化推進"]
            }
        }
    
    def generate_news(self, ticker):
        """指定企業のニュースを生成"""
        company = self.company_contexts[ticker]
        news_type = random.choice(company["news_types"])
        
        prompt = f"""
あなたは金融ニュース記者です。以下の企業について、リアルな投資ニュースを1つ生成してください。

企業情報:
- 企業名: {company['name']} ({ticker})
- 業界: {company['industry']}
- 事業内容: {company['business']}
- ニュースタイプ: {news_type}

要件:
1. 150-250文字程度の日本語ニュース
2. 投資判断に影響する具体的な内容
3. 株価への影響度を-3から+3で評価
4. リアリティがあり説得力のある内容

出力形式（JSON）:
{{
  "headline": "ニュースの見出し",
  "content": "ニュース本文",
  "impact_score": 影響度数値,
  "news_type": "{news_type}",
  "ticker": "{ticker}"
}}
"""
        
        try:
            response = claude_client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            # JSON解析
            news_text = response.content[0].text
            news_data = json.loads(news_text)
            
            # タイムスタンプ追加
            news_data["timestamp"] = datetime.datetime.utcnow().isoformat()
            news_data["generated_by"] = "claude-3-sonnet"
            
            return news_data
            
        except Exception as e:
            print(f"ニュース生成エラー: {e}")
            return self.get_fallback_news(ticker)
    
    def get_fallback_news(self, ticker):
        """APIエラー時のフォールバックニュース"""
        company = self.company_contexts[ticker]
        fallback_news = [
            {
                "headline": f"{company['name']}、堅調な業績を維持",
                "content": f"{company['name']}は{company['industry']}分野での事業展開を継続し、安定した成長を示している。市場からは今後の動向に注目が集まる。",
                "impact_score": 0,
                "news_type": "業績",
                "ticker": ticker
            }
        ]
        
        news = random.choice(fallback_news)
        news["timestamp"] = datetime.datetime.utcnow().isoformat()
        news["generated_by"] = "fallback"
        return news
    
    def save_news_to_firestore(self, news_data):
        """ニュースをFirestoreに保存"""
        try:
            news_ref = db.collection("market_news").add(news_data)
            print(f"ニュース保存完了: {news_ref[1].id}")
            return news_ref[1].id
        except Exception as e:
            print(f"ニュース保存エラー: {e}")
            return None
    
    def apply_price_impact(self, ticker, impact_score):
        """ニュース影響で株価を変動"""
        try:
            company_ref = db.collection("companies").document(ticker)
            company_doc = company_ref.get()
            
            if not company_doc.exists:
                return
            
            company_data = company_doc.to_dict()
            current_price = company_data["current_price"]
            
            # 影響度に基づく価格変動（-3〜+3 → -15%〜+15%）
            price_change_rate = impact_score * 0.05  # 5%ずつ
            new_price = int(current_price * (1 + price_change_rate))
            new_price = max(new_price, 1)  # 最低1KR
            
            # 価格更新
            company_data["current_price"] = new_price
            company_ref.set(company_data)
            
            # 価格履歴記録
            today = datetime.datetime.utcnow()
            price_history = {
                "ticker": ticker,
                "date": today.strftime("%Y-%m-%d"),
                "old_price": current_price,
                "new_price": new_price,
                "change_rate": price_change_rate,
                "reason": "news_impact",
                "timestamp": today.isoformat()
            }
            
            db.collection("price_changes").add(price_history)
            print(f"{ticker} 価格更新: {current_price} → {new_price} ({price_change_rate:+.1%})")
            
        except Exception as e:
            print(f"価格変動エラー: {e}")
    
    def generate_daily_news(self):
        """日次ニュース生成（2-4件）"""
        news_count = random.randint(2, 4)
        tickers = random.sample(list(self.company_contexts.keys()), news_count)
        
        generated_news = []
        for ticker in tickers:
            news = self.generate_news(ticker)
            news_id = self.save_news_to_firestore(news)
            
            if news_id and news["impact_score"] != 0:
                self.apply_price_impact(ticker, news["impact_score"])
            
            generated_news.append(news)
        
        return generated_news

# テスト実行用
if __name__ == "__main__":
    generator = NewsGenerator()
    news = generator.generate_news("WICR")
    print(json.dumps(news, ensure_ascii=False, indent=2))