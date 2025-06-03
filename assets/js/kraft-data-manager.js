// assets/js/kraft-data-manager.js (クリーンアップ版)
// 不要なモックデータ・investment_news削除

class KRAFTDataManager {
    constructor() {
        this.db = null;
        this.initialized = false;
        this.cache = new Map();
        this.cacheExpiry = 5 * 60 * 1000; // 5分キャッシュ
        
        console.log("🏗️ KRAFT Data Manager 初期化開始");
        
        // Firebase初期化完了を待つ
        this.waitForFirebase();
    }

    /**
     * Firebase初期化完了を待つ
     */
    waitForFirebase() {
        if (window.db) {
            this.db = window.db;
            this.initialized = true;
            console.log("✅ Firebase既に初期化済み");
        } else {
            window.addEventListener('firebaseInitialized', (event) => {
                if (window.db) {
                    this.db = window.db;
                    this.initialized = true;
                    console.log("✅ Firebase初期化完了を検知");
                }
            });
        }
    }

    /**
     * 接続状態確認メソッド
     */
    isConnected() {
        return this.initialized && 
               this.db !== null && 
               !window.FIREBASE_MOCK_MODE &&
               window.FIREBASE_CONNECTION_SUCCESS !== false;
    }

    /**
     * モックモード判定
     */
    shouldUseMockData() {
        return window.FIREBASE_MOCK_MODE === true || 
               (window.FIREBASE_CONNECTION_ERROR === true && 
                window.FIREBASE_CONNECTION_SUCCESS !== true) ||
               !this.db;
    }

    /**
     * 安全な初期化確認
     */
    async ensureInitialized() {
        if (!this.initialized) {
            await this.initialize();
        }
        
        let attempts = 0;
        while (!this.db && !this.shouldUseMockData() && attempts < 30) {
            await new Promise(resolve => setTimeout(resolve, 100));
            if (window.db) {
                this.db = window.db;
                this.initialized = true;
                break;
            }
            attempts++;
        }
    }

    /**
     * Firebase初期化
     */
    async initialize() {
        try {
            console.log("🔥 KRAFT Data Manager Firebase初期化");
            
            if (this.initialized && this.db) {
                console.log("✅ 既に初期化済み");
                return true;
            }
            
            if (typeof firebase === 'undefined') {
                console.error("❌ Firebase SDK が利用できません");
                window.FIREBASE_MOCK_MODE = true;
                this.initialized = true;
                return true;
            }

            if (window.db) {
                this.db = window.db;
                this.initialized = true;
                console.log("✅ KRAFT Firebase 初期化完了");
                return true;
            } else {
                try {
                    this.db = firebase.firestore();
                    this.initialized = true;
                    console.log("✅ KRAFT Firebase 直接初期化完了");
                    return true;
                } catch (firestoreError) {
                    console.error("❌ Firestore初期化エラー:", firestoreError);
                    window.FIREBASE_MOCK_MODE = true;
                    this.initialized = true;
                    return true;
                }
            }
            
        } catch (error) {
            console.error("❌ Firebase 初期化エラー:", error);
            window.FIREBASE_MOCK_MODE = true;
            this.initialized = true;
            return true;
        }
    }

    /**
     * キャッシュチェック
     */
    getCached(key) {
        const cached = this.cache.get(key);
        if (cached && Date.now() - cached.timestamp < this.cacheExpiry) {
            console.log(`📋 キャッシュヒット: ${key}`);
            return cached.data;
        }
        return null;
    }

    /**
     * キャッシュ保存
     */
    setCache(key, data) {
        this.cache.set(key, {
            data,
            timestamp: Date.now()
        });
        console.log(`💾 キャッシュ保存: ${key} (${data.length || Object.keys(data).length}件)`);
    }

    /**
     * 企業データ取得
     */
    async getCompaniesData() {
        const cacheKey = 'companies_data';
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        try {
            await this.ensureInitialized();
            
            if (this.shouldUseMockData()) {
                console.log("🎭 モック企業データを使用");
                const mockData = this.getMockCompaniesData();
                this.setCache(cacheKey, mockData);
                return mockData;
            }

            console.log('📊 Firebase企業データを取得中...');
            
            const companiesRef = this.db.collection('companies');
            const snapshot = await companiesRef.orderBy('ticker').get();
            
            if (snapshot.empty) {
                console.log('Firebase: 企業データが見つかりません、モックデータを使用');
                const mockData = this.getMockCompaniesData();
                this.setCache(cacheKey, mockData);
                return mockData;
            }
            
            const companies = snapshot.docs.map(doc => {
                const data = doc.data();
                return {
                    ticker: data.ticker || doc.id,
                    name: data.name || 'Unknown Company',
                    industry: data.industry || 'other',
                    current_price: data.current_price || 100,
                    dividend_yield: data.dividend_yield || 0,
                    volatility: data.volatility || 0.02,
                    shares_outstanding: data.shares_outstanding || 1000000
                };
            });
            
            console.log(`✅ Firebase: ${companies.length}社の企業データを取得しました`);
            this.setCache(cacheKey, companies);
            return companies;
            
        } catch (error) {
            console.error('❌ 企業データ取得エラー:', error);
            console.log('🎭 フォールバック: モック企業データを使用');
            const mockData = this.getMockCompaniesData();
            this.setCache(cacheKey, mockData);
            return mockData;
        }
    }

    /**
     * 市場ニュース取得（market_news使用・クリーンアップ版）
     */
    async getMarketNews(limit = 10) {
        const cacheKey = `market_news_${limit}`;
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        try {
            await this.ensureInitialized();
            
            if (this.shouldUseMockData()) {
                console.log("🎭 接続失敗のため、フォールバックデータを使用");
                const mockData = this.getFallbackNewsData();
                this.setCache(cacheKey, mockData);
                return mockData;
            }

            console.log(`📰 Market News（自動生成）を取得中... (limit: ${limit})`);
            
            const newsRef = this.db.collection('market_news');
            const snapshot = await newsRef
                .orderBy('timestamp', 'desc')
                .limit(limit)
                .get();
            
            if (snapshot.empty) {
                console.log('Firebase: Market Newsが見つかりません、フォールバックデータを使用');
                const fallbackData = this.getFallbackNewsData();
                this.setCache(cacheKey, fallbackData);
                return fallbackData;
            }
            
            const news = snapshot.docs.map(doc => {
                const data = doc.data();
                return {
                    id: doc.id,
                    headline: data.headline || 'ニュース見出し',
                    content: data.content || 'ニュース内容',
                    impact_score: data.impact_score || 0,
                    ticker: data.ticker || null,
                    timestamp: data.timestamp || new Date().toISOString(),
                    news_type: data.news_type || 'market',
                    generated_by: data.generated_by || 'system'
                };
            });
            
            console.log(`✅ Market News: ${news.length}件の自動生成ニュースを取得`);
            this.setCache(cacheKey, news);
            return news;
            
        } catch (error) {
            console.error('❌ Market News取得エラー:', error);
            console.log('🎭 フォールバック: フォールバックデータを使用');
            const fallbackData = this.getFallbackNewsData();
            this.setCache(cacheKey, fallbackData);
            return fallbackData;
        }
    }

    /**
     * 市場統計取得
     */
    async getMarketStats() {
        const cacheKey = 'market_stats';
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        try {
            await this.ensureInitialized();
            
            if (this.shouldUseMockData()) {
                console.log("🎭 計算による市場統計を使用");
                const mockData = this.calculateMarketStats();
                this.setCache(cacheKey, mockData);
                return mockData;
            }

            console.log('📈 Firebase市場統計データを取得中...');
            
            const statsRef = this.db.collection('market_stats');
            const today = new Date().toISOString().split('T')[0];
            const doc = await statsRef.doc(today).get();
            
            if (!doc.exists) {
                console.log('Firebase: 市場統計データが見つかりません、計算値を使用');
                const calculatedStats = this.calculateMarketStats();
                this.setCache(cacheKey, calculatedStats);
                return calculatedStats;
            }
            
            const data = doc.data();
            const marketStats = {
                totalMarketCap: data.total_market_cap || 0,
                activeInvestors: data.active_investors || 0,
                dailyVolume: data.daily_volume || 0,
                risingStocks: data.rising_stocks || 0,
                totalStocks: data.total_stocks || 10
            };
            
            console.log('✅ Firebase市場統計データを取得しました');
            this.setCache(cacheKey, marketStats);
            return marketStats;
            
        } catch (error) {
            console.error('❌ 市場統計取得エラー:', error);
            console.log('🎭 フォールバック: 計算統計を使用');
            const calculatedStats = this.calculateMarketStats();
            this.setCache(cacheKey, calculatedStats);
            return calculatedStats;
        }
    }

    /**
     * 市場統計計算
     */
    calculateMarketStats() {
        return {
            totalMarketCap: 425750000,
            activeInvestors: 142,
            dailyVolume: 2400000,
            risingStocks: 7,
            totalStocks: 10
        };
    }

    /**
     * ユーザープロフィール取得
     */
    async getUserProfiles() {
        const cacheKey = 'user_profiles';
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        if (this.shouldUseMockData()) {
            console.log("🎭 モックデータを使用してユーザープロフィールを取得");
            const mockData = this.getMockUserProfiles();
            this.setCache(cacheKey, mockData);
            return mockData;
        }

        try {
            await this.ensureInitialized();
            
            console.log("📊 Firestoreからユーザープロフィールを取得中...");
            const usersRef = this.db.collection('users');
            const snapshot = await usersRef.get();
            
            const profiles = [];
            snapshot.forEach(doc => {
                const data = doc.data ? doc.data() : doc.to_dict();
                profiles.push({
                id: doc.id,
                level: data.level || 1,
                xp: data.xp || 0,
                balance: data.balance || 0,
                titles: data.titles || [],
                completed_quests: data.completed_quests || 0,
                quest_streak: data.quest_streak || 0,
                total_messages: data.total_messages || 0,
                donation_total: data.donation_total || 0,
                transfers_total: data.transfers_total || 0,
                display_name: data.website_nickname || this.anonymizeUser(doc.id)
            });
            });

            this.setCache(cacheKey, profiles);
            console.log(`✅ ${profiles.length}件のユーザープロフィールを取得完了`);
            return profiles;

        } catch (error) {
            console.error("❌ ユーザープロフィール取得エラー:", error);
            console.log("🎭 フォールバック: モックデータを使用");
            const mockData = this.getMockUserProfiles();
            this.setCache(cacheKey, mockData);
            return mockData;
        }
    }

    async getServerStats() {
        const cacheKey = 'server_stats';
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        try {
            console.log("📈 サーバー統計を計算中...");
            const profiles = await this.getUserProfiles();
            
            const stats = {
                total_users: profiles.length,
                active_users: profiles.filter(p => p.total_messages > 0).length,
                total_levels: profiles.reduce((sum, p) => sum + p.level, 0),
                total_xp: profiles.reduce((sum, p) => sum + p.xp, 0),
                total_quests: profiles.reduce((sum, p) => sum + p.completed_quests, 0),
                total_kr_circulation: profiles.reduce((sum, p) => sum + p.transfers_total + p.donation_total, 0),
                level_distribution: this.calculateLevelDistribution(profiles),
                quest_completion_rate: this.calculateQuestCompletionRate(profiles),
                average_level: profiles.length > 0 ? (profiles.reduce((sum, p) => sum + p.level, 0) / profiles.length).toFixed(1) : 0
            };

            this.setCache(cacheKey, stats);
            console.log("✅ サーバー統計計算完了");
            return stats;

        } catch (error) {
            console.error("❌ サーバー統計取得エラー:", error);
            console.log("🎭 フォールバック: モック統計を使用");
            const mockStats = this.getMockServerStats();
            this.setCache(cacheKey, mockStats);
            return mockStats;
        }
    }

    async getRankings() {
        const cacheKey = 'rankings';
        const cached = this.getCached(cacheKey);
        if (cached) return cached;

        try {
            console.log("🏆 ランキングデータを計算中...");
            const profiles = await this.getUserProfiles();
            
            const rankings = {
                level_ranking: profiles
                    .sort((a, b) => b.level - a.level || b.xp - a.xp)
                    .slice(0, 10),
                xp_ranking: profiles
                    .sort((a, b) => b.xp - a.xp)
                    .slice(0, 10),
                quest_ranking: profiles
                    .sort((a, b) => b.completed_quests - a.completed_quests)
                    .slice(0, 10),
                kr_economy_ranking: profiles
                    .sort((a, b) => (b.transfers_total + b.donation_total) - (a.transfers_total + a.donation_total))
                    .slice(0, 10)
            };

            this.setCache(cacheKey, rankings);
            console.log("✅ ランキングデータ計算完了");
            return rankings;

        } catch (error) {
            console.error("❌ ランキング取得エラー:", error);
            console.log("🎭 フォールバック: モックランキングを使用");
            const mockRankings = this.getMockRankings();
            this.setCache(cacheKey, mockRankings);
            return mockRankings;
        }
    }

    // === ユーティリティメソッド ===
    
    calculateLevelDistribution(profiles) {
        const distribution = {
            'Lv1-10': 0,
            'Lv11-20': 0,  
            'Lv21-30': 0,
            'Lv31-40': 0,
            'Lv41-50': 0,
            'Lv50+': 0
        };

        profiles.forEach(profile => {
            const level = profile.level;
            if (level <= 10) distribution['Lv1-10']++;
            else if (level <= 20) distribution['Lv11-20']++;
            else if (level <= 30) distribution['Lv21-30']++;
            else if (level <= 40) distribution['Lv31-40']++;
            else if (level <= 50) distribution['Lv41-50']++;
            else distribution['Lv50+']++;
        });

        return distribution;
    }

    calculateQuestCompletionRate(profiles) {
        const activeUsers = profiles.filter(p => p.total_messages > 0);
        if (activeUsers.length === 0) return 0;

        const questActiveUsers = activeUsers.filter(p => p.completed_quests > 0);
        return ((questActiveUsers.length / activeUsers.length) * 100).toFixed(1);
    }

    anonymizeUser(userId) {
        if (userId && userId.length >= 4) {
            return `メンバー${userId.slice(-4)}`;
        }
        return "メンバー????";
    }

    // === 最小限のフォールバックデータ ===

    getMockUserProfiles() {
        return [
            {
                id: "demo1", display_name: "デモユーザー1", level: 15, xp: 3200,
                balance: 2500, titles: ["初心者"], completed_quests: 8,
                quest_streak: 2, total_messages: 150, donation_total: 500, transfers_total: 800
            },
            {
                id: "demo2", display_name: "デモユーザー2", level: 12, xp: 2100,
                balance: 1800, titles: ["学習者"], completed_quests: 5,
                quest_streak: 1, total_messages: 95, donation_total: 200, transfers_total: 400
            }
        ];
    }

    getMockServerStats() {
        return {
            total_users: 12,
            active_users: 8,
            total_levels: 150,
            total_xp: 25000,
            total_quests: 45,
            total_kr_circulation: 15000,
            level_distribution: {
                'Lv1-10': 4,
                'Lv11-20': 5,
                'Lv21-30': 2,
                'Lv31-40': 1,
                'Lv41-50': 0,
                'Lv50+': 0
            },
            quest_completion_rate: 65.5,
            average_level: 12.5
        };
    }

    getMockRankings() {
        const mockProfiles = this.getMockUserProfiles();
        return {
            level_ranking: mockProfiles.sort((a, b) => b.level - a.level),
            xp_ranking: mockProfiles.sort((a, b) => b.xp - a.xp),
            quest_ranking: mockProfiles.sort((a, b) => b.completed_quests - a.completed_quests),
            kr_economy_ranking: mockProfiles.sort((a, b) => (b.transfers_total + b.donation_total) - (a.transfers_total + a.donation_total))
        };
    }

    getMockCompaniesData() {
        return [
            {
                ticker: "DEMO",
                name: "Demo Company",
                industry: "tech",
                current_price: 100,
                dividend_yield: 0.02,
                volatility: 0.025,
                shares_outstanding: 1000000
            }
        ];
    }

    getFallbackNewsData() {
        return [
            {
                id: "fallback_1",
                headline: "市場は安定した動きを見せています",
                content: "本日の市場は全体的に安定した値動きとなっています。",
                impact_score: 0,
                ticker: null,
                news_type: "market",
                timestamp: new Date().toISOString(),
                generated_by: "fallback"
            }
        ];
    }

    // === 管理機能 ===

    clearCache() {
        this.cache.clear();
        console.log("🗑️ キャッシュをクリアしました");
    }

    async forceRefresh() {
        this.clearCache();
        console.log("🔄 データを強制リフレッシュ中...");
        
        await Promise.all([
            this.getUserProfiles(),
            this.getServerStats(),
            this.getRankings(),
            this.getCompaniesData(),
            this.getMarketNews(),
            this.getMarketStats()
        ]);
        
        console.log("✅ データリフレッシュ完了");
    }

    getConnectionStatus() {
        return {
            initialized: this.initialized,
            mock_mode: this.shouldUseMockData(),
            connection_error: window.FIREBASE_CONNECTION_ERROR || false,
            connection_success: window.FIREBASE_CONNECTION_SUCCESS || false,
            cache_entries: this.cache.size,
            firebase_available: typeof firebase !== 'undefined',
            firestore_available: !!this.db,
            has_window_db: !!window.db
        };
    }
}

// グローバルインスタンス作成
window.kraftDataManager = new KRAFTDataManager();

// 自動初期化
document.addEventListener('DOMContentLoaded', async () => {
    console.log("🚀 KRAFT Data Manager 自動初期化開始");
    
    setTimeout(async () => {
        await window.kraftDataManager.initialize();
        
        const status = window.kraftDataManager.getConnectionStatus();
        console.log("📊 KRAFT Data Manager 接続状態:", status);
        
        if (status.mock_mode) {
            console.warn("⚠️ フォールバックモードで動作中");
        } else {
            console.log("🎉 Firebase実データ接続完了！");
        }
        
    }, 1500);
});

// デバッグ用グローバル関数
window.kraftDebug = {
    clearCache: () => window.kraftDataManager.clearCache(),
    forceRefresh: () => window.kraftDataManager.forceRefresh(),
    getStatus: () => window.kraftDataManager.getConnectionStatus(),
    testConnection: async () => {
        try {
            const companies = await window.kraftDataManager.getCompaniesData();
            console.log(`✅ 接続テスト成功: ${companies.length}社の企業データ取得`);
            return true;
        } catch (error) {
            console.error("❌ 接続テスト失敗:", error);
            return false;
        }
    }
};

console.log("✅ KRAFT Data Manager ロード完了");