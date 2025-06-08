import firebase_admin
from firebase_admin import credentials, firestore
import datetime
import random
import hashlib

# Firebase初期化（既存のbot.pyと同じ設定使用）
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

def calculate_price_change(company):
    """株価変動率の計算（ニュース連動版）- Webサイトと同じロジック"""
    try:
        # 1. 基本変動率を計算（日付ベース）
        today = datetime.datetime.utcnow()
        date_string = f"{today.year}-{today.month}-{today.day}"
        
        # ティッカーシンボルと日付から決定論的なシードを生成
        combined = company['ticker'] + date_string
        hash_value = int(hashlib.sha256(combined.encode()).hexdigest()[:8], 16)
        
        # 基本変動率: -3.0%から+3.0%の範囲
        normalized = abs(hash_value) / (2**32)
        base_change_rate = (normalized * 6) - 3  # -3.0 から +3.0 の範囲
        
        # 2. ニュース影響度を計算
        news_impact = calculate_news_impact(company)
        
        # 3. 合計変動率を計算（最大±8%に制限）
        total_change = base_change_rate + news_impact
        limited_change = max(-8, min(8, total_change))
        
        return round(limited_change, 2)
    
    except Exception as e:
        print(f"株価変動計算エラー ({company.get('ticker', 'UNKNOWN')}): {e}")
        return 0.0

def calculate_news_impact(company):
    """ニュース影響度の計算"""
    try:
        # 24時間以内のニュースを取得
        one_day_ago = datetime.datetime.utcnow() - datetime.timedelta(days=1)
        
        news_ref = db.collection("market_news")
        news_docs = news_ref.where("timestamp", ">=", one_day_ago.isoformat()).get()
        
        total_impact = 0
        
        for news_doc in news_docs:
            news_data = news_doc.to_dict()
            
            # 企業固有ニュースかチェック
            if news_data.get("ticker") == company['ticker']:
                # 企業固有ニュース: impact_scoreをそのまま適用
                total_impact += news_data.get("impact_score", 0) * 0.8  # 80%の影響度
            elif not news_data.get("ticker"):
                # 市場全体ニュース: 業界による影響度調整
                industry_multiplier = get_industry_news_multiplier(company['industry'], news_data)
                total_impact += news_data.get("impact_score", 0) * 0.3 * industry_multiplier  # 30%の影響度
        
        # 影響度を-5%から+5%の範囲に制限
        return max(-5, min(5, total_impact))
    
    except Exception as e:
        print(f"ニュース影響計算エラー: {e}")
        return 0

def get_industry_news_multiplier(industry, news_data):
    """業界別ニュース影響度の調整"""
    try:
        headline = news_data.get('headline', '').lower()
        content = news_data.get('content', '').lower()
        
        # キーワードベースの業界影響度判定
        tech_keywords = ['ai', 'tech', '技術', 'quantum', '量子']
        finance_keywords = ['規制', '金融', 'finance', '決済', 'crypto']
        health_keywords = ['medical', '医療', 'bio', 'health', '臨床']
        entertainment_keywords = ['game', 'meta', 'ゲーム', 'エンタメ']
        industrial_keywords = ['energy', 'エネルギー', '産業', 'industrial']

        def check_keywords(keywords):
            return any(keyword in headline or keyword in content for keyword in keywords)

        if industry == 'tech':
            if check_keywords(tech_keywords):
                return 1.5  # 高影響
            if check_keywords(finance_keywords):
                return 0.8  # 中影響
        elif industry == 'finance':
            if check_keywords(finance_keywords):
                return 1.5  # 高影響
            if check_keywords(tech_keywords):
                return 0.9  # 中影響
        elif industry == 'healthcare':
            if check_keywords(health_keywords):
                return 1.5  # 高影響
        elif industry == 'entertainment':
            if check_keywords(entertainment_keywords):
                return 1.5  # 高影響
            if check_keywords(tech_keywords):
                return 1.0  # 中影響
        elif industry == 'industrial':
            if check_keywords(industrial_keywords):
                return 1.5  # 高影響
        
        return 1.0  # デフォルト影響度
    
    except Exception as e:
        print(f"業界影響度計算エラー: {e}")
        return 1.0

def get_company_shares(company):
    """企業別発行済み株式数の取得（株価帯による規模推定）"""
    try:
        current_price = company.get('current_price', 50)
        
        if current_price >= 100:
            return 800000  # 大型株: 80万株
        elif current_price >= 60:
            return 1200000  # 中型株: 120万株
        else:
            return 2000000  # 小型株: 200万株
    
    except Exception as e:
        print(f"発行株式数計算エラー: {e}")
        return 1000000  # デフォルト値

def calculate_market_activity(companies):
    """市場活発度の計算"""
    try:
        if not companies:
            return 0
        
        total_volatility = sum(abs(calculate_price_change(company)) for company in companies)
        average_volatility = total_volatility / len(companies)
        return min(average_volatility / 5, 1)  # 0-1の範囲で正規化
    
    except Exception as e:
        print(f"市場活発度計算エラー: {e}")
        return 0.5

def calculate_real_market_stats():
    """実データベース市場統計の計算（投資家数修正版）"""
    try:
        print("📊 実データベース市場統計計算開始...")
        
        # 企業データを取得
        companies_ref = db.collection("companies")
        companies_docs = companies_ref.get()
        companies = [doc.to_dict() for doc in companies_docs]
        
        if not companies:
            print("⚠️ 企業データが見つかりません")
            return None
        
        print(f"企業データ取得: {len(companies)}社")
        
        # 実際の企業データから時価総額を計算
        total_market_cap = 0
        rising_stocks = 0
        
        for company in companies:
            # 各企業の発行済み株式数（企業規模に応じて調整）
            shares = get_company_shares(company)
            current_price = company.get('current_price', 0)
            total_market_cap += current_price * shares
            
            # 上昇企業数の計算（実際の変動率を使用）
            price_change = calculate_price_change(company)
            if price_change > 0:
                rising_stocks += 1
        
        # 実際のアクティブ投資家数を取得
        try:
            investors_ref = db.collection("user_investments")
            investors_docs = list(investors_ref.get())
            active_investors = len(investors_docs)
            print(f"実際の投資家数: {active_investors}人")
        except Exception as e:
            print(f"投資家数取得エラー: {e}")
            active_investors = 0
        
        # 日次取引高（実データベース計算）
        market_activity = calculate_market_activity(companies)
        turnover_rate = 0.015 + (market_activity * 0.01)  # 1.5%-2.5%の回転率
        daily_volume = int(total_market_cap * turnover_rate)
        
        # 市場トレンドの判定
        rising_ratio = rising_stocks / len(companies) if companies else 0
        if rising_ratio > 0.6:
            market_trend = "bullish"
        elif rising_ratio < 0.4:
            market_trend = "bearish"
        else:
            market_trend = "neutral"
        
        # ボラティリティ指数の計算
        total_volatility = sum(abs(calculate_price_change(company)) for company in companies)
        volatility_index = round(total_volatility / len(companies) * 2, 1) if companies else 15.0
        
        # 上昇率・下落率ランキング
        companies_with_change = []
        for company in companies:
            change = calculate_price_change(company)
            companies_with_change.append({
                'ticker': company['ticker'],
                'change': change
            })
        
        # 上昇率トップ3
        top_gainers = sorted(companies_with_change, key=lambda x: x['change'], reverse=True)[:3]
        top_gainers_tickers = [c['ticker'] for c in top_gainers]
        
        # 下落率トップ3
        top_losers = sorted(companies_with_change, key=lambda x: x['change'])[:3]
        top_losers_tickers = [c['ticker'] for c in top_losers]
        
        market_stats = {
            "date": datetime.datetime.utcnow().strftime("%Y-%m-%d"),
            "total_market_cap": int(total_market_cap),
            "active_investors": active_investors,  # 実際の投資家数
            "daily_volume": daily_volume,
            "rising_stocks": rising_stocks,
            "total_stocks": len(companies),
            "market_trend": market_trend,
            "volatility_index": volatility_index,
            "top_gainers": top_gainers_tickers,
            "top_losers": top_losers_tickers,
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        print(f"✅ 市場統計計算完了:")
        print(f"  総時価総額: {total_market_cap:,} KR")
        print(f"  上昇銘柄: {rising_stocks}/{len(companies)}")
        print(f"  投資家数: {active_investors}")
        print(f"  取引高: {daily_volume:,} KR")
        print(f"  市場トレンド: {market_trend}")
        
        return market_stats
    
    except Exception as e:
        print(f"❌ 市場統計計算エラー: {e}")
        import traceback
        print(f"詳細エラー: {traceback.format_exc()}")
        return None

def create_missing_collections():
    """不足しているCollectionを作成・修復（実データ版）"""
    
    print("🔧 Firebase投資データ修復開始...")
    
    # 1. market_news Collection作成（investment_newsから移行）
    print("\n📰 market_news Collection作成中...")
    
    sample_news = [
        {
            "headline": "🤖 Wicrosoft、革新的AI技術を発表",
            "content": "次世代対話AIの新機能により、ユーザー体験が大幅に向上",
            "impact_score": 3,
            "ticker": "WICR",
            "news_type": "product_launch",
            "timestamp": datetime.datetime.utcnow().isoformat()
        },
        {
            "headline": "📈 量子コンピュータ市場が急成長",
            "content": "Qoogleの技術開発により、量子コンピュータの実用化が加速",
            "impact_score": 2,
            "ticker": "QOOG", 
            "news_type": "market_trend",
            "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(hours=2)).isoformat()
        },
        {
            "headline": "🎮 メタバース市場の拡大継続",
            "content": "Robluxの新プラットフォームにより、クリエイター収益が増加",
            "impact_score": 1,
            "ticker": "RBLX",
            "news_type": "earnings",
            "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(hours=4)).isoformat()
        },
        {
            "headline": "⚠️ 規制強化によるフィンテック企業への影響",
            "content": "新しい金融規制により、デジタル決済企業の成長に懸念",
            "impact_score": -2,
            "ticker": "STRK",
            "news_type": "regulatory",
            "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(hours=6)).isoformat()
        },
        {
            "headline": "🏥 バイオテック企業の臨床試験結果に注目",
            "content": "Firma Schnitzelの新薬臨床試験の結果発表が来週予定",
            "impact_score": 0,
            "ticker": "FSCH",
            "news_type": "clinical_trial",
            "timestamp": (datetime.datetime.utcnow() - datetime.timedelta(hours=8)).isoformat()
        }
    ]
    
    for i, news in enumerate(sample_news):
        doc_id = f"news_{datetime.datetime.utcnow().strftime('%Y%m%d')}_{i+1:03d}"
        db.collection("market_news").document(doc_id).set(news)
        print(f"  ✅ {news['ticker']}: {news['headline']}")
    
    # 2. 実データベース市場統計を計算・作成
    print("\n📊 実データベース市場統計計算中...")
    
    market_stats = calculate_real_market_stats()
    
    if market_stats:
        today = datetime.datetime.utcnow()
        db.collection("market_stats").document(today.strftime("%Y-%m-%d")).set(market_stats)
        print(f"  ✅ 実データ市場統計作成: {today.strftime('%Y-%m-%d')}")
    else:
        print("  ❌ 市場統計計算に失敗しました")
    
    # 3. 企業データの存在確認・修復
    print("\n🏢 企業データ存在確認...")
    
    companies_ref = db.collection("companies")
    companies = companies_ref.get()
    
    if len(list(companies)) < 10:
        print("  ⚠️ 企業データが不足しています。追加中...")
        
        # 企業マスターデータ
        COMPANIES_DATA = {
            "WICR": {
                "ticker": "WICR",
                "name": "Wicrosoft",
                "industry": "tech",
                "current_price": 85,
                "shares_outstanding": 1000000,
                "dividend_yield": 0.015,
                "volatility": 0.02
            },
            "QOOG": {
                "ticker": "QOOG", 
                "name": "Qoogle",
                "industry": "tech",
                "current_price": 158,
                "shares_outstanding": 500000,
                "dividend_yield": 0.0,
                "volatility": 0.035
            },
            "RBLX": {
                "ticker": "RBLX",
                "name": "Roblux", 
                "industry": "entertainment",
                "current_price": 72,
                "shares_outstanding": 800000,
                "dividend_yield": 0.02,
                "volatility": 0.025
            },
            "NFOX": {
                "ticker": "NFOX",
                "name": "Netfox",
                "industry": "entertainment", 
                "current_price": 64,
                "shares_outstanding": 900000,
                "dividend_yield": 0.015,
                "volatility": 0.02
            },
            "MOSL": {
                "ticker": "MOSL",
                "name": "Mosla",
                "industry": "industrial",
                "current_price": 48,
                "shares_outstanding": 1500000,
                "dividend_yield": 0.03,
                "volatility": 0.015
            },
            "NKDA": {
                "ticker": "NKDA",
                "name": "Nikuda",
                "industry": "industrial",
                "current_price": 32,
                "shares_outstanding": 2500000,
                "dividend_yield": 0.04,
                "volatility": 0.01
            },
            "FSCH": {
                "ticker": "FSCH",
                "name": "Firma Schnitzel",
                "industry": "healthcare",
                "current_price": 142,
                "shares_outstanding": 400000,
                "dividend_yield": 0.0,
                "volatility": 0.03
            },
            "IRHA": {
                "ticker": "IRHA",
                "name": "Iroha",
                "industry": "healthcare",
                "current_price": 76,
                "shares_outstanding": 700000,
                "dividend_yield": 0.01,
                "volatility": 0.02
            },
            "STRK": {
                "ticker": "STRK",
                "name": "Strike",
                "industry": "finance",
                "current_price": 98,
                "shares_outstanding": 600000,
                "dividend_yield": 0.0,
                "volatility": 0.025
            },
            "ASST": {
                "ticker": "ASST",
                "name": "Assist",
                "industry": "finance", 
                "current_price": 45,
                "shares_outstanding": 2000000,
                "dividend_yield": 0.05,
                "volatility": 0.01
            }
        }
        
        for ticker, data in COMPANIES_DATA.items():
            db.collection("companies").document(ticker).set(data)
            print(f"  ✅ {ticker}: {data['name']}")
    else:
        print("  ✅ 企業データ確認完了")
    
    print("\n🎉 Firebase投資データ修復完了！")
    print("\n📋 作成されたCollection:")
    print("  - market_news: 5件のサンプルニュース（investment_newsから移行）")
    print("  - market_stats: 実データベース計算による市場統計")
    print("  - companies: 10社のマスターデータ確認")
    
    return True

def verify_collections():
    """Collection作成結果を検証"""
    print("\n🔍 Collection検証開始...")
    
    # market_news検証
    news_ref = db.collection("market_news")
    news_count = len(list(news_ref.get()))
    print(f"📰 market_news: {news_count}件")
    
    # market_stats検証
    stats_ref = db.collection("market_stats")
    stats_count = len(list(stats_ref.get()))
    print(f"📊 market_stats: {stats_count}件")
    
    # companies検証  
    companies_ref = db.collection("companies")
    companies_count = len(list(companies_ref.get()))
    print(f"🏢 companies: {companies_count}件")
    
    if news_count >= 3 and stats_count >= 1 and companies_count >= 10:
        print("✅ すべてのCollectionが正常に作成されました！")
        return True
    else:
        print("❌ Collection作成に問題があります")
        return False

def update_daily_market_stats():
    """日次市場統計の更新（定期実行用）"""
    try:
        print("📊 日次市場統計更新開始...")
        
        market_stats = calculate_real_market_stats()
        
        if market_stats:
            today = datetime.datetime.utcnow()
            db.collection("market_stats").document(today.strftime("%Y-%m-%d")).set(market_stats)
            print(f"✅ 市場統計更新完了: {today.strftime('%Y-%m-%d')}")
            print(f"  総時価総額: {market_stats['total_market_cap']:,} KR")
            print(f"  上昇銘柄: {market_stats['rising_stocks']}/{market_stats['total_stocks']}")
            print(f"  投資家数: {market_stats['active_investors']}")
            print(f"  取引高: {market_stats['daily_volume']:,} KR")
            return True
        else:
            print("❌ 市場統計計算に失敗しました")
            return False
    
    except Exception as e:
        print(f"❌ 日次市場統計更新エラー: {e}")
        return False

if __name__ == "__main__":
    try:
        success = create_missing_collections()
        if success:
            verify_collections()
            print("\n🚀 修復完了！ウェブサイトをリロードして確認してください。")
            print("\n💡 日次更新には update_daily_market_stats() を定期実行してください")
        else:
            print("\n❌ 修復に失敗しました")
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        print(f"詳細: {traceback.format_exc()}")