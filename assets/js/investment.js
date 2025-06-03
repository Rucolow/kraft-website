/**
 * KRAFT投資ページ - 株価変動率固定化版
 * Math.random()を削除し、日付ベース固定値に変更
 */

// モジュール重複防止: 既に宣言されている場合はスキップ
if (typeof window.InvestmentPage === 'undefined') {
  
  window.InvestmentPage = class InvestmentPage {
    constructor() {
      this.dataManager = null;
      this.companies = [];
      this.marketNews = [];
      this.selectedPeriod = '1d';
      this.selectedIndustry = 'all';
      
      this.initializeInvestmentPage();
    }

    /**
     * 投資ページの初期化
     */
    async initializeInvestmentPage() {
      try {
        console.log('投資ページ初期化開始...');
        
        // KRAFTDataManagerの初期化を待つ
        await this.waitForDataManager();
        
        // 各セクションの初期化
        await Promise.all([
          this.loadCompaniesData(),
          this.loadMarketNews(),
          this.updateMarketStats()
        ]);
        
        // イベントリスナーの設定
        this.setupEventListeners();
        
        console.log('投資ページの初期化が完了しました');
      } catch (error) {
        console.error('投資ページの初期化に失敗:', error);
        this.showErrorMessage('データの読み込みに失敗しました');
      }
    }

    /**
     * KRAFTDataManagerの準備完了を待つ
     */
    async waitForDataManager() {
      return new Promise((resolve) => {
        const checkDataManager = () => {
          if (window.kraftDataManager) {
            this.dataManager = window.kraftDataManager;
            console.log('KRAFTDataManager接続完了');
            resolve();
          } else {
            setTimeout(checkDataManager, 100);
          }
        };
        checkDataManager();
      });
    }

    /**
     * 企業データの読み込み
     */
    async loadCompaniesData() {
      try {
        // Firebaseから企業データを取得
        if (this.dataManager && typeof this.dataManager.getCompaniesData === 'function') {
          this.companies = await this.dataManager.getCompaniesData();
          console.log('Firebase企業データ取得成功:', this.companies.length + '社');
        } else {
          throw new Error('DataManager利用不可');
        }
      } catch (error) {
        console.warn('Firebase接続失敗、モックデータを使用:', error.message);
        // フォールバック: モックデータを使用
        this.companies = this.getMockCompaniesData();
      }
      
      // 企業カードの描画
      this.renderCompaniesGrid(this.companies);
      
      // Chart.js削除のため、チャート初期化をスキップ
      this.initializeChartPlaceholder();
      
      // ランキングの更新
      this.updateRankings();
    }

    /**
     * 投資ニュースの読み込み
     */
    async loadMarketNews() {
      try {
        if (this.dataManager && typeof this.dataManager.getMarketNews === 'function') {
          this.marketNews = await this.dataManager.getMarketNews(10);
          console.log('Firebaseニュース取得成功:', this.marketNews.length + '件');
        } else {
          throw new Error('ニュースDataManager利用不可');
        }
      } catch (error) {
        console.warn('ニュース取得失敗、モックデータを使用:', error.message);
        this.marketNews = this.getMockNewsData();
      }
      
      this.renderMarketNews(this.marketNews);
    }

    /**
     * Chart.js削除により、プレースホルダー表示のみ
     */
    initializeChartPlaceholder() {
      const chartContainer = document.getElementById('stockChart');
      if (!chartContainer) {
        console.warn('stockChart要素が見つかりません');
        return;
      }
      
      console.log('チャートプレースホルダー確認完了');
      // HTMLで既にプレースホルダーが設定されているため、何もしない
    }

    /**
     * 企業カードグリッドの描画
     */
    renderCompaniesGrid(companies) {
      const grid = document.getElementById('companies-grid');
      if (!grid) {
        console.error('companies-grid要素が見つかりません');
        return;
      }

      // フィルタリング
      const filteredCompanies = this.selectedIndustry === 'all' 
        ? companies 
        : companies.filter(company => company.industry === this.selectedIndustry);

      if (filteredCompanies.length === 0) {
        grid.innerHTML = `
          <div class="col-12">
            <div class="alert alert-info text-center">
              選択した業界に該当する企業がありません
            </div>
          </div>
        `;
        return;
      }

      grid.innerHTML = filteredCompanies.map(company => this.createCompanyCard(company)).join('');
      
      // カードクリックイベントの設定
      this.setupCompanyCardEvents();
      
      console.log(`企業カード ${filteredCompanies.length}社表示完了`);
    }

    /**
     * 企業カードHTMLの生成
     */
    createCompanyCard(company) {
      const priceChange = this.calculatePriceChange(company);
      const changeClass = priceChange >= 0 ? 'positive' : 'negative';
      const changeSymbol = priceChange >= 0 ? '+' : '';
      
      return `
        <div class="company-card ${company.industry}" data-ticker="${company.ticker}">
          <div class="company-header">
            <div class="company-info">
              <h3>${this.getIndustryIcon(company.industry)} ${company.name}</h3>
              <div class="company-ticker">${company.ticker}</div>
            </div>
            <div class="price-display">
              <div class="current-price">${this.safeFormatNumber(company.current_price)} KR</div>
              <div class="price-change ${changeClass}">
                ${changeSymbol}${priceChange.toFixed(2)}%
              </div>
            </div>
          </div>
          
          <div class="company-description">
            ${this.getCompanyDescription(company.ticker)}
          </div>
          
          <div class="company-metrics">
            <div class="metric">
              <span class="metric-value">${(company.dividend_yield * 100).toFixed(1)}%</span>
              <span class="metric-label">配当利回り</span>
            </div>
            <div class="metric">
              <span class="metric-value">${this.getIndustryName(company.industry)}</span>
              <span class="metric-label">業界</span>
            </div>
          </div>
        </div>
      `;
    }

    /**
     * 安全な数値フォーマット（toLocaleStringエラー対策）
     */
    safeFormatNumber(num) {
      try {
        // 数値チェック
        if (typeof num !== 'number' || isNaN(num)) {
          return '0';
        }
        
        // 大きな数値は手動フォーマット
        if (num >= 1000000) {
          return (num / 1000000).toFixed(1) + 'M';
        }
        if (num >= 1000) {
          return (num / 1000).toFixed(1) + 'K';
        }
        
        // 小さな数値は直接表示
        if (num < 1000) {
          return Math.round(num).toString();
        }
        
        // フォールバック：toLocaleStringを安全に使用
        try {
          return num.toLocaleString('ja-JP');
        } catch {
          // toLocaleStringが失敗した場合の最終フォールバック
          return Math.round(num).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
        }
      } catch (error) {
        console.warn('数値フォーマットエラー:', error);
        return '0';
      }
    }

    /**
     * 株価変動率の計算（ニュース連動版）
     * 基本変動率 + ニュース影響度を組み合わせ
     */
    calculatePriceChange(company) {
      // 1. 基本変動率を計算（日付ベース）
      const today = new Date();
      const dateString = today.getFullYear() + '-' + (today.getMonth() + 1) + '-' + today.getDate();
      
      let hash = 0;
      const combined = company.ticker + dateString;
      
      for (let i = 0; i < combined.length; i++) {
        const char = combined.charCodeAt(i);
        hash = ((hash << 5) - hash) + char;
        hash = hash & hash; // 32bit整数に変換
      }
      
      // 基本変動率: -3.0%から+3.0%の範囲
      const normalized = Math.abs(hash) / 2147483647;
      const baseChangeRate = (normalized * 6) - 3; // -3.0 から +3.0 の範囲
      
      // 2. ニュース影響度を計算
      const newsImpact = this.calculateNewsImpact(company);
      
      // 3. 合計変動率を計算（最大±8%に制限）
      const totalChange = baseChangeRate + newsImpact;
      const limitedChange = Math.max(-8, Math.min(8, totalChange));
      
      return Math.round(limitedChange * 100) / 100; // 小数点2桁に丸める
    }

    /**
     * ニュース影響度の計算
     * 企業固有ニュース + 市場全体ニュースの影響を算出
     */
    calculateNewsImpact(company) {
      if (!this.marketNews || this.marketNews.length === 0) {
        return 0; // ニュースがない場合は影響なし
      }

      let totalImpact = 0;
      const today = new Date();
      const oneDayAgo = new Date(today.getTime() - 24 * 60 * 60 * 1000);

      this.marketNews.forEach(news => {
        const newsDate = new Date(news.timestamp);
        
        // 24時間以内のニュースのみ影響を考慮
        if (newsDate >= oneDayAgo) {
          // 企業固有ニュースかチェック
          if (news.ticker && news.ticker === company.ticker) {
            // 企業固有ニュース: impact_scoreをそのまま適用
            totalImpact += news.impact_score * 0.8; // 80%の影響度
          } else if (!news.ticker) {
            // 市場全体ニュース: 業界による影響度調整
            const industryMultiplier = this.getIndustryNewsMultiplier(company.industry, news);
            totalImpact += news.impact_score * 0.3 * industryMultiplier; // 30%の影響度
          }
        }
      });

      // 影響度を-5%から+5%の範囲に制限
      return Math.max(-5, Math.min(5, totalImpact));
    }

    /**
     * 業界別ニュース影響度の調整
     * ニュース内容に応じて業界ごとの感受性を調整
     */
    getIndustryNewsMultiplier(industry, news) {
      const headline = news.headline.toLowerCase();
      const content = news.content.toLowerCase();
      
      // キーワードベースの業界影響度判定
      const techKeywords = ['ai', 'tech', '技術', 'quantum', '量子'];
      const financeKeywords = ['規制', '金融', 'finance', '決済', 'crypto'];
      const healthKeywords = ['medical', '医療', 'bio', 'health', '臨床'];
      const entertainmentKeywords = ['game', 'meta', 'ゲーム', 'エンタメ'];
      const industrialKeywords = ['energy', 'エネルギー', '産業', 'industrial'];

      const checkKeywords = (keywords) => {
        return keywords.some(keyword => 
          headline.includes(keyword) || content.includes(keyword)
        );
      };

      switch (industry) {
        case 'tech':
          if (checkKeywords(techKeywords)) return 1.5; // 高影響
          if (checkKeywords(financeKeywords)) return 0.8; // 中影響
          break;
        case 'finance':
          if (checkKeywords(financeKeywords)) return 1.5; // 高影響
          if (checkKeywords(techKeywords)) return 0.9; // 中影響
          break;
        case 'healthcare':
          if (checkKeywords(healthKeywords)) return 1.5; // 高影響
          break;
        case 'entertainment':
          if (checkKeywords(entertainmentKeywords)) return 1.5; // 高影響
          if (checkKeywords(techKeywords)) return 1.0; // 中影響
          break;
        case 'industrial':
          if (checkKeywords(industrialKeywords)) return 1.5; // 高影響
          break;
      }
      
      return 1.0; // デフォルト影響度
    }

    /**
     * 業界アイコンの取得
     */
    getIndustryIcon(industry) {
      const icons = {
        'tech': '🤖',
        'entertainment': '🎮',
        'industrial': '🏭',
        'healthcare': '🏥',
        'finance': '🏦'
      };
      return icons[industry] || '🏢';
    }

    /**
     * 業界名の取得
     */
    getIndustryName(industry) {
      const names = {
        'tech': 'テクノロジー',
        'entertainment': 'エンターテイメント',
        'industrial': '産業・エネルギー',
        'healthcare': 'ヘルスケア',
        'finance': '金融'
      };
      return names[industry] || '不明';
    }

    /**
     * 企業説明の取得
     */
    getCompanyDescription(ticker) {
      const descriptions = {
        'WICR': 'AI・Bot開発のリーディングカンパニー。次世代の対話型AIプラットフォームを提供',
        'QOOG': '量子コンピュータ技術のパイオニア。革新的な量子アルゴリズムを研究開発',
        'RBLX': 'メタバース・ゲーム開発プラットフォーム。クリエイター経済をサポート',
        'NFOX': '動画配信・エンターテイメント大手。オリジナルコンテンツに強み',
        'MOSL': '再生可能エネルギーの総合企業。太陽光・風力発電システムを展開',
        'NKDA': '物流・配送サービスの革新企業。AI配送最適化システムを運用',
        'FSCH': 'バイオテクノロジーの研究開発企業。画期的な医療技術を開発',
        'IRHA': '医療IT・ヘルスケアプラットフォーム。診療支援システムを提供',
        'STRK': 'デジタル決済・フィンテック企業。暗号資産決済ソリューション',
        'ASST': '伝統的銀行・金融サービス。安定した配当と堅実な成長を継続'
      };
      return descriptions[ticker] || 'さまざまな事業を展開する総合企業';
    }

    /**
     * ニュース表示の描画
     */
    renderMarketNews(newsItems) {
      const container = document.getElementById('news-container');
      if (!container) return;

      if (newsItems.length === 0) {
        container.innerHTML = `
          <div class="alert alert-info">
            現在表示できるニュースがありません
          </div>
        `;
        return;
      }

      container.innerHTML = newsItems.map(news => this.createNewsItem(news)).join('');
    }

    /**
     * ニュースアイテムHTMLの生成
     */
    createNewsItem(news) {
      const impactClass = this.getImpactClass(news.impact_score);
      const impactText = this.getImpactText(news.impact_score);
      const timestamp = this.formatTimestamp(news.timestamp);
      
      return `
        <div class="news-item ${impactClass}">
          <div class="news-headline">${news.headline}</div>
          <div class="news-content">${news.content}</div>
          <div class="news-meta">
            <span class="news-impact ${impactClass}">${impactText}</span>
            <span class="news-time">${timestamp}</span>
          </div>
        </div>
      `;
    }

    /**
     * 影響度クラスの取得
     */
    getImpactClass(score) {
      if (score >= 2) return 'positive';
      if (score <= -2) return 'negative';
      return 'neutral';
    }

    /**
     * 影響度テキストの取得
     */
    getImpactText(score) {
      if (score >= 3) return '大幅上昇期待';
      if (score >= 1) return '上昇期待';
      if (score <= -3) return '大幅下落リスク';
      if (score <= -1) return '下落リスク';
      return '中立';
    }

    /**
     * タイムスタンプのフォーマット
     */
    formatTimestamp(timestamp) {
      const date = new Date(timestamp);
      const now = new Date();
      const diffHours = Math.floor((now - date) / (1000 * 60 * 60));
      
      if (diffHours < 1) return '数分前';
      if (diffHours < 24) return `${diffHours}時間前`;
      return `${Math.floor(diffHours / 24)}日前`;
    }

    /**
     * ランキングの更新
     */
    updateRankings() {
      const companiesWithChange = this.companies.map(company => ({
        ...company,
        change: this.calculatePriceChange(company)
      }));

      // 上昇率ランキング
      const topGainers = companiesWithChange
        .sort((a, b) => b.change - a.change)
        .slice(0, 5);
      
      // 下落率ランキング
      const topLosers = companiesWithChange
        .sort((a, b) => a.change - b.change)
        .slice(0, 5);

      this.renderRanking('top-gainers', topGainers);
      this.renderRanking('top-losers', topLosers);
    }

    /**
     * ランキング表示の描画
     */
    renderRanking(elementId, companies) {
      const container = document.getElementById(elementId);
      if (!container) return;

      container.innerHTML = companies.map(company => {
        const changeClass = company.change >= 0 ? 'positive' : 'negative';
        const changeSymbol = company.change >= 0 ? '+' : '';
        
        return `
          <div class="ranking-item">
            <span class="ranking-company">${company.name}</span>
            <span class="ranking-change ${changeClass}">
              ${changeSymbol}${company.change.toFixed(2)}%
            </span>
          </div>
        `;
      }).join('');
    }

    /**
     * 市場統計の更新
     */
    async updateMarketStats() {
      try {
        // Firebase接続時は実際のデータを取得を試行
        if (this.dataManager && typeof this.dataManager.getMarketStats === 'function') {
          const stats = await this.dataManager.getMarketStats();
          this.displayMarketStats(stats);
          console.log('Firebase市場統計取得成功');
        } else {
          // フォールバック: 実データベース計算を使用
          console.log('Firebase市場統計利用不可、実データから計算');
          this.displayMarketStats(this.calculateRealMarketStats());
        }
      } catch (error) {
        console.error('Firebase市場統計取得失敗、実データから計算:', error);
        this.displayMarketStats(this.calculateRealMarketStats());
      }
    }

    /**
     * 実データベース市場統計の計算
     * 実際の企業データと変動率を使用
     */
    calculateRealMarketStats() {
      // 実際の企業データから時価総額を計算
      const totalMarketCap = this.companies.reduce((sum, company) => {
        // 各企業の仮想発行済み株式数（企業規模に応じて調整）
        const shares = this.getCompanyShares(company);
        return sum + (company.current_price * shares);
      }, 0);

      // 上昇企業数の計算（実際の変動率を使用）
      const risingStocks = this.companies.filter(company => 
        this.calculatePriceChange(company) > 0
      ).length;

      // アクティブ投資家数（実データベース計算）
      const activeInvestors = this.calculateActiveInvestors();

      // 日次取引高（実データベース計算）  
      const dailyVolume = this.calculateDailyVolume();

      return {
        totalMarketCap: totalMarketCap,
        risingStocks: risingStocks,
        totalStocks: this.companies.length,
        activeInvestors: activeInvestors,
        dailyVolume: dailyVolume
      };
    }

    /**
     * 企業別発行済み株式数の取得
     * 企業規模と業界に応じて現実的な値を設定
     */
    getCompanyShares(company) {
      // 株価帯による企業規模推定
      if (company.current_price >= 100) {
        return 800000; // 大型株: 80万株
      } else if (company.current_price >= 60) {
        return 1200000; // 中型株: 120万株  
      } else {
        return 2000000; // 小型株: 200万株
      }
    }

    /**
     * アクティブ投資家数の計算
     * 市場の活発度と企業数から推定
     */
    calculateActiveInvestors() {
      const baseInvestors = 120; // ベース投資家数
      const marketActivity = this.calculateMarketActivity();
      const activityBonus = Math.floor(marketActivity * 50);
      
      return baseInvestors + activityBonus;
    }

    /**
     * 市場活発度の計算
     * 変動率の絶対値から市場の動きを測定
     */
    calculateMarketActivity() {
      if (this.companies.length === 0) return 0;
      
      const totalVolatility = this.companies.reduce((sum, company) => {
        return sum + Math.abs(this.calculatePriceChange(company));
      }, 0);
      
      const averageVolatility = totalVolatility / this.companies.length;
      return Math.min(averageVolatility / 5, 1); // 0-1の範囲で正規化
    }

    /**
     * 日次取引高の計算  
     * 時価総額と市場活発度から推定
     */
    calculateDailyVolume() {
      const totalMarketCap = this.companies.reduce((sum, company) => {
        const shares = this.getCompanyShares(company);
        return sum + (company.current_price * shares);
      }, 0);
      
      const marketActivity = this.calculateMarketActivity();
      const turnoverRate = 0.015 + (marketActivity * 0.01); // 1.5%-2.5%の回転率
      
      return Math.floor(totalMarketCap * turnoverRate);
    }

    /**
     * 市場統計の表示（実データ専用フォーマット）
     */
    displayMarketStats(stats) {
      console.log('=== 市場統計更新開始 ===');
      console.log('受信データ:', stats);
      
      // 総時価総額の表示（M単位で表示）
      const marketCapFormatted = this.formatLargeNumber(stats.totalMarketCap) + ' KR';
      this.updateStatElement('total-market-cap', marketCapFormatted);
      console.log('総時価総額更新:', marketCapFormatted);
      
      // 上昇銘柄数の表示
      const risingStocksFormatted = `${stats.risingStocks} / ${stats.totalStocks}`;
      this.updateStatElement('rising-stocks', risingStocksFormatted);
      console.log('上昇銘柄更新:', risingStocksFormatted);
      
      // アクティブ投資家数の表示
      const investorsFormatted = stats.activeInvestors.toString();
      this.updateStatElement('active-investors', investorsFormatted);
      console.log('投資家数更新:', investorsFormatted);
      
      // 日次取引高の表示（M単位で表示）
      const volumeFormatted = this.formatLargeNumber(stats.dailyVolume) + ' KR';
      this.updateStatElement('daily-volume', volumeFormatted);
      console.log('取引高更新:', volumeFormatted);
      
      console.log('=== 市場統計更新完了 ===');
    }

    /**
     * 大きな数値の専用フォーマット
     * 市場統計表示用の正確なフォーマット
     */
    formatLargeNumber(num) {
      if (typeof num !== 'number' || isNaN(num)) {
        return '0';
      }
      
      if (num >= 1000000000) {
        return (num / 1000000000).toFixed(1) + 'B';
      }
      if (num >= 1000000) {
        return (num / 1000000).toFixed(1) + 'M';
      }
      if (num >= 1000) {
        return (num / 1000).toFixed(1) + 'K';
      }
      
      return Math.round(num).toString();
    }

    /**
     * 統計要素の更新（詳細ログ付き）
     */
    updateStatElement(id, value) {
      const element = document.getElementById(id);
      if (element) {
        const oldValue = element.textContent;
        element.textContent = value;
        console.log(`要素更新成功: ${id} "${oldValue}" → "${value}"`);
      } else {
        console.error(`要素が見つかりません: ${id}`);
      }
    }

    /**
     * イベントリスナーの設定
     */
    setupEventListeners() {
      // 業界タブクリック
      document.querySelectorAll('[data-industry]').forEach(tab => {
        tab.addEventListener('click', (e) => {
          e.preventDefault();
          this.handleIndustryFilter(e.target.dataset.industry);
        });
      });

      // チャート期間切り替え（Chart.js削除のため、現在は無効）
      document.querySelectorAll('[data-period]').forEach(btn => {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          this.handlePeriodChange(e.target.dataset.period);
        });
      });

      // 企業カードクリックイベントは別途設定
      this.setupCompanyCardEvents();
    }

    /**
     * 企業カードクリックイベント
     */
    setupCompanyCardEvents() {
      document.querySelectorAll('.company-card').forEach(card => {
        card.addEventListener('click', () => {
          const ticker = card.dataset.ticker;
          this.showCompanyModal(ticker);
        });
      });
    }

    /**
     * 業界フィルターの処理
     */
    handleIndustryFilter(industry) {
      this.selectedIndustry = industry;
      
      // アクティブタブの更新
      document.querySelectorAll('[data-industry]').forEach(tab => {
        tab.classList.remove('active');
      });
      
      const activeTab = document.querySelector(`[data-industry="${industry}"]`);
      if (activeTab) {
        activeTab.classList.add('active');
      }
      
      // 企業グリッドの再描画
      this.renderCompaniesGrid(this.companies);
    }

    /**
     * チャート期間変更の処理（Chart.js削除のため、現在は何もしない）
     */
    handlePeriodChange(period) {
      this.selectedPeriod = period;
      
      // アクティブボタンの更新
      document.querySelectorAll('[data-period]').forEach(btn => {
        btn.classList.remove('active');
      });
      
      const activeBtn = document.querySelector(`[data-period="${period}"]`);
      if (activeBtn) {
        activeBtn.classList.add('active');
      }
      
      console.log(`期間変更: ${period} (チャート表示は後日実装予定)`);
    }

    /**
     * 企業詳細モーダルの表示
     */
    showCompanyModal(ticker) {
      const company = this.companies.find(c => c.ticker === ticker);
      if (!company) return;

      const modal = document.getElementById('companyModal');
      const modalBody = document.getElementById('companyModalBody');
      const modalLabel = document.getElementById('companyModalLabel');
      
      if (!modal || !modalBody || !modalLabel) return;

      modalLabel.textContent = `${company.name} (${ticker})`;
      modalBody.innerHTML = this.createCompanyModalContent(company);
      
      // Bootstrap モーダルを表示
      if (typeof bootstrap !== 'undefined' && bootstrap.Modal) {
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
      } else {
        // フォールバック: モーダルを直接表示
        modal.style.display = 'block';
        modal.classList.add('show');
        console.warn('Bootstrap Modal が利用できません');
      }
    }

    /**
     * 企業詳細モーダルコンテンツの生成
     */
    createCompanyModalContent(company) {
      const change = this.calculatePriceChange(company);
      const changeClass = change >= 0 ? 'text-success' : 'text-danger';
      const changeSymbol = change >= 0 ? '+' : '';
      
      return `
        <div class="row">
          <div class="col-md-6">
            <h5>基本情報</h5>
            <table class="table table-sm">
              <tr>
                <td>現在価格</td>
                <td><strong>${this.safeFormatNumber(company.current_price)} KR</strong></td>
              </tr>
              <tr>
                <td>変動率</td>
                <td class="${changeClass}"><strong>${changeSymbol}${change.toFixed(2)}%</strong></td>
              </tr>
              <tr>
                <td>配当利回り</td>
                <td>${(company.dividend_yield * 100).toFixed(1)}%</td>
              </tr>
              <tr>
                <td>業界</td>
                <td>${this.getIndustryName(company.industry)}</td>
              </tr>
            </table>
          </div>
          <div class="col-md-6">
            <h5>企業概要</h5>
            <p>${this.getCompanyDescription(company.ticker)}</p>
            
            <h6>リスク要因</h6>
            <ul class="small text-muted">
              <li>市場ボラティリティの影響</li>
              <li>業界固有の競争リスク</li>
              <li>規制環境の変化</li>
            </ul>
            
            <div class="mt-3 p-3 bg-light rounded">
              <h6>📈 個別チャート</h6>
              <p class="small text-muted mb-0">※ 株価推移チャートは開発完了後に表示されます</p>
            </div>
          </div>
        </div>
      `;
    }

    /**
     * エラーメッセージの表示
     */
    showErrorMessage(message) {
      const grid = document.getElementById('companies-grid');
      if (grid) {
        grid.innerHTML = `
          <div class="col-12">
            <div class="alert alert-warning text-center">
              <i class="fas fa-exclamation-triangle me-2"></i>
              ${message}
            </div>
          </div>
        `;
      }
    }

    /**
     * モック企業データ（Firebase接続失敗時用）
     */
    getMockCompaniesData() {
      return [
        {
          ticker: "WICR",
          name: "Wicrosoft",
          industry: "tech",
          current_price: 85,
          dividend_yield: 0.015,
          volatility: 0.02
        },
        {
          ticker: "QOOG",
          name: "Qoogle",
          industry: "tech",
          current_price: 158,
          dividend_yield: 0.00,
          volatility: 0.03
        },
        {
          ticker: "RBLX",
          name: "Roblux",
          industry: "entertainment",
          current_price: 72,
          dividend_yield: 0.02,
          volatility: 0.025
        },
        {
          ticker: "NFOX",
          name: "Netfox",
          industry: "entertainment",
          current_price: 64,
          dividend_yield: 0.015,
          volatility: 0.02
        },
        {
          ticker: "MOSL",
          name: "Mosla",
          industry: "industrial",
          current_price: 48,
          dividend_yield: 0.03,
          volatility: 0.018
        },
        {
          ticker: "NKDA",
          name: "Nikuda",
          industry: "industrial",
          current_price: 32,
          dividend_yield: 0.04,
          volatility: 0.015
        },
        {
          ticker: "FSCH",
          name: "Firma Schnitzel",
          industry: "healthcare",
          current_price: 142,
          dividend_yield: 0.00,
          volatility: 0.04
        },
        {
          ticker: "IRHA",
          name: "Iroha",
          industry: "healthcare",
          current_price: 76,
          dividend_yield: 0.01,
          volatility: 0.022
        },
        {
          ticker: "STRK",
          name: "Strike",
          industry: "finance",
          current_price: 98,
          dividend_yield: 0.00,
          volatility: 0.035
        },
        {
          ticker: "ASST",
          name: "Assist",
          industry: "finance",
          current_price: 45,
          dividend_yield: 0.05,
          volatility: 0.012
        }
      ];
    }

    /**
     * モックニュースデータ（Firebase接続失敗時用）
     */
    getMockNewsData() {
      return [
        {
          headline: "🤖 Wicrosoft、革新的AI技術を発表",
          content: "次世代対話AIの新機能により、ユーザー体験が大幅に向上",
          impact_score: 3,
          ticker: "WICR",
          timestamp: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString()
        },
        {
          headline: "📈 量子コンピュータ市場が急成長",
          content: "Qoogleの技術開発により、量子コンピュータの実用化が加速",
          impact_score: 2,
          ticker: "QOOG",
          timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString()
        },
        {
          headline: "🎮 メタバース市場の拡大継続",
          content: "Robluxの新プラットフォームにより、クリエイター収益が増加",
          impact_score: 1,
          ticker: "RBLX",
          timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString()
        },
        {
          headline: "⚠️ 規制強化によるフィンテック企業への影響",
          content: "新しい金融規制により、デジタル決済企業の成長に懸念",
          impact_score: -2,
          ticker: "STRK",
          timestamp: new Date(Date.now() - 8 * 60 * 60 * 1000).toISOString()
        },
        {
          headline: "🏥 バイオテック企業の臨床試験結果に注目",
          content: "Firma Schnitzelの新薬臨床試験の結果発表が来週予定",
          impact_score: 0,
          ticker: "FSCH",
          timestamp: new Date(Date.now() - 12 * 60 * 60 * 1000).toISOString()
        }
      ];
    }
  };

  // ページ読み込み時に投資ページを初期化（重複防止）
  document.addEventListener('DOMContentLoaded', () => {
    if (!window.investmentPageInstance) {
      console.log('InvestmentPage 初期化中...');
      window.investmentPageInstance = new window.InvestmentPage();
    }
  });
}