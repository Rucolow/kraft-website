# investment_db_init.py - KRAFT投資システム初期化

import firebase_admin
from firebase_admin import credentials, firestore
import datetime

# Firebase初期化（既存のbot.pyと同じ設定使用）
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase_credentials.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# 企業マスターデータ
# 10社企業マスターデータ - COMPANIES_DATAを以下と置き換え

COMPANIES_DATA = {
    # テック系
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
    
    # エンターテイメント系
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
    
    # 伝統産業系
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
    
    # ヘルスケア系
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
    
    # 金融系
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


def init_investment_system():
    """投資システムのFirestore初期化"""
    
    # 1. 企業マスターデータ投入
    print("🏢 企業マスターデータを投入中...")
    for ticker, data in COMPANIES_DATA.items():
        db.collection("companies").document(ticker).set(data)
        print(f"  ✅ {ticker} - {data['name']}")
    
    # 2. 初期株価データ
    print("📈 初期株価データを投入中...")
    today = datetime.datetime.utcnow()
    for ticker, data in COMPANIES_DATA.items():
        price_data = {
            "ticker": ticker,
            "date": today.strftime("%Y-%m-%d"),
            "price": data["current_price"],
            "volume": 1000,
            "change": 0.0,
            "timestamp": today.isoformat()
        }
        db.collection("stock_prices").document(f"{ticker}_{today.strftime('%Y%m%d')}").set(price_data)
    
    # 3. 市場データ初期化
    print("📊 市場データを初期化中...")
    market_data = {
        "date": today.strftime("%Y-%m-%d"),
        "total_market_cap": sum(c["current_price"] * c["shares_outstanding"] for c in COMPANIES_DATA.values()),
        "active_traders": 0,
        "total_volume": 0,
        "timestamp": today.isoformat()
    }
    db.collection("market_data").document(today.strftime("%Y-%m-%d")).set(market_data)
    
    print("✅ 投資システム初期化完了！")

if __name__ == "__main__":
    init_investment_system()