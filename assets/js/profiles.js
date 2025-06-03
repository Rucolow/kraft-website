/**
 * プロフィールページ投資機能拡張
 * 既存のprofiles.jsに追加する投資データ表示機能
 */

// 既存のUserProfilesクラスに以下のメソッドを追加

/**
 * ユーザープロフィール表示に投資情報を追加
 */
async enhanceProfileWithInvestmentData(profileElement, userData) {
  try {
    const userId = userData.user_id || userData.id;
    if (!userId) return;
    
    // 投資データの取得
    const investmentData = await this.dataManager.getUserInvestments(userId);
    if (!investmentData) return;
    
    // 投資セクションHTML生成
    const investmentSection = this.createInvestmentSection(investmentData);
    
    // プロフィールカードに投資情報を挿入
    const cardBody = profileElement.querySelector('.card-body');
    if (cardBody) {
      cardBody.insertAdjacentHTML('beforeend', investmentSection);
    }
    
  } catch (error) {
    console.error('投資データ表示エラー:', error);
  }
}

/**
 * 投資セクションHTMLの生成
 */
createInvestmentSection(investmentData) {
  const portfolioValue = this.calculatePortfolioValue(investmentData.portfolio);
  const totalInvested = investmentData.total_invested || 0;
  const profit = portfolioValue - totalInvested;
  const profitPercent = totalInvested > 0 ? (profit / totalInvested) * 100 : 0;
  
  const profitClass = profit >= 0 ? 'text-success' : 'text-danger';
  const profitSymbol = profit >= 0 ? '+' : '';
  
  return `
    <div class="investment-summary mt-4 pt-4 border-top">
      <h6 class="mb-3">
        <i class="fas fa-chart-line me-2 text-primary"></i>投資ポートフォリオ
      </h6>
      
      <!-- 投資サマリー -->
      <div class="row g-2 mb-3">
        <div class="col-4">
          <div class="investment-stat">
            <div class="stat-value">${this.formatCurrency(portfolioValue)}</div>
            <div class="stat-label">総資産</div>
          </div>
        </div>
        <div class="col-4">
          <div class="investment-stat">
            <div class="stat-value ${profitClass}">${profitSymbol}${this.formatCurrency(profit)}</div>
            <div class="stat-label">損益</div>
          </div>
        </div>
        <div class="col-4">
          <div class="investment-stat">
            <div class="stat-value ${profitClass}">${profitSymbol}${profitPercent.toFixed(1)}%</div>
            <div class="stat-label">利回り</div>
          </div>
        </div>
      </div>
      
      <!-- 保有銘柄 -->
      <div class="holdings-summary">
        <div class="small text-muted mb-2">保有銘柄:</div>
        <div class="holdings-tags">
          ${this.createHoldingsTags(investmentData.portfolio)}
        </div>
      </div>
      
      <!-- 投資統計 -->
      <div class="investment-metrics mt-3">
        <div class="row g-2 small">
          <div class="col-6">
            <span class="text-muted">取引手数料:</span>
            <span class="float-end">${this.formatCurrency(investmentData.total_fees_paid || 0)}</span>
          </div>
          <div class="col-6">
            <span class="text-muted">配当収入:</span>
            <span class="float-end text-success">${this.formatCurrency(investmentData.total_dividends || 0)}</span>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * ポートフォリオ価値の計算
 */
calculatePortfolioValue(portfolio) {
  if (!portfolio || typeof portfolio !== 'object') return 0;
  
  let totalValue = 0;
  
  for (const [ticker, holding] of Object.entries(portfolio)) {
    if (holding && holding.shares && holding.avg_cost) {
      // 簡易計算: 平均取得価格 × 株数
      // 実際の実装では現在価格を使用
      const currentPrice = this.getCurrentPrice(ticker);
      totalValue += holding.shares * currentPrice;
    }
  }
  
  return totalValue;
}

/**
 * 現在株価の取得（簡易版）
 */
getCurrentPrice(ticker) {
  // モック価格データ
  const mockPrices = {
    'WICR': 85,
    'QOOG': 158,
    'RBLX': 72,
    'NFOX': 64,
    'MOSL': 48,
    'NKDA': 32,
    'FSCH': 142,
    'IRHA': 76,
    'STRK': 98,
    'ASST': 45
  };
  
  return mockPrices[ticker] || 100;
}

/**
 * 保有銘柄タグの生成
 */
createHoldingsTags(portfolio) {
  if (!portfolio || typeof portfolio !== 'object') {
    return '<span class="badge bg-light text-muted">保有銘柄なし</span>';
  }
  
  const holdings = Object.entries(portfolio)
    .filter(([ticker, holding]) => holding && holding.shares > 0)
    .slice(0, 5); // 最大5銘柄まで表示
  
  if (holdings.length === 0) {
    return '<span class="badge bg-light text-muted">保有銘柄なし</span>';
  }
  
  const tags = holdings.map(([ticker, holding]) => {
    const shares = holding.shares || 0;
    return `<span class="stock-tag">${ticker} (${shares}株)</span>`;
  }).join(' ');
  
  const remainingCount = Object.keys(portfolio).length - holdings.length;
  const moreTag = remainingCount > 0 ? ` <span class="stock-tag more">+${remainingCount}銘柄</span>` : '';
  
  return tags + moreTag;
}

/**
 * 通貨フォーマット
 */
formatCurrency(amount) {
  if (amount >= 1000000) {
    return (amount / 1000000).toFixed(1) + 'M KR';
  }
  if (amount >= 1000) {
    return (amount / 1000).toFixed(1) + 'K KR';
  }
  return Math.round(amount).toLocaleString() + ' KR';
}

/**
 * プロフィールモーダルに投資詳細を追加
 */
async enhanceModalWithInvestmentDetails(modalBody, userData) {
  try {
    const userId = userData.user_id || userData.id;
    if (!userId) return;
    
    // 投資データと取引履歴の取得
    const [investmentData, transactions] = await Promise.all([
      this.dataManager.getUserInvestments(userId),
      this.dataManager.getUserTransactions(userId, 10)
    ]);
    
    if (!investmentData && (!transactions || transactions.length === 0)) {
      return; // 投資データがない場合は何も追加しない
    }
    
    // 投資詳細セクションの追加
    const investmentDetailsSection = this.createInvestmentDetailsSection(investmentData, transactions);
    modalBody.insertAdjacentHTML('beforeend', investmentDetailsSection);
    
  } catch (error) {
    console.error('モーダル投資詳細表示エラー:', error);
  }
}

/**
 * 投資詳細セクションHTMLの生成
 */
createInvestmentDetailsSection(investmentData, transactions) {
  return `
    <div class="investment-details mt-4 pt-4 border-top">
      <h5 class="mb-3">
        <i class="fas fa-chart-pie me-2 text-primary"></i>投資詳細
      </h5>
      
      <!-- ポートフォリオ詳細 -->
      ${this.createPortfolioDetails(investmentData)}
      
      <!-- 取引履歴 -->
      ${this.createTransactionHistory(transactions)}
      
      <!-- 投資パフォーマンス -->
      ${this.createPerformanceMetrics(investmentData, transactions)}
    </div>
  `;
}

/**
 * ポートフォリオ詳細の生成
 */
createPortfolioDetails(investmentData) {
  if (!investmentData || !investmentData.portfolio) {
    return `
      <div class="alert alert-info small">
        <i class="fas fa-info-circle me-2"></i>
        まだ投資を開始していません
      </div>
    `;
  }
  
  const holdings = Object.entries(investmentData.portfolio)
    .filter(([ticker, holding]) => holding && holding.shares > 0)
    .map(([ticker, holding]) => {
      const currentPrice = this.getCurrentPrice(ticker);
      const marketValue = holding.shares * currentPrice;
      const cost = holding.total_cost || (holding.shares * holding.avg_cost);
      const profit = marketValue - cost;
      const profitPercent = cost > 0 ? (profit / cost) * 100 : 0;
      
      return { ticker, holding, currentPrice, marketValue, cost, profit, profitPercent };
    })
    .sort((a, b) => b.marketValue - a.marketValue);
  
  if (holdings.length === 0) {
    return `
      <div class="alert alert-info small">
        <i class="fas fa-info-circle me-2"></i>
        現在保有している銘柄はありません
      </div>
    `;
  }
  
  return `
    <div class="portfolio-details mb-4">
      <h6 class="mb-3">ポートフォリオ構成</h6>
      <div class="table-responsive">
        <table class="table table-sm">
          <thead>
            <tr>
              <th>銘柄</th>
              <th class="text-end">株数</th>
              <th class="text-end">時価</th>
              <th class="text-end">損益</th>
            </tr>
          </thead>
          <tbody>
            ${holdings.map(holding => `
              <tr>
                <td>
                  <strong>${holding.ticker}</strong>
                  <br>
                  <small class="text-muted">${holding.currentPrice} KR</small>
                </td>
                <td class="text-end">${holding.holding.shares}</td>
                <td class="text-end">${this.formatCurrency(holding.marketValue)}</td>
                <td class="text-end ${holding.profit >= 0 ? 'text-success' : 'text-danger'}">
                  ${holding.profit >= 0 ? '+' : ''}${this.formatCurrency(holding.profit)}
                  <br>
                  <small>(${holding.profit >= 0 ? '+' : ''}${holding.profitPercent.toFixed(1)}%)</small>
                </td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    </div>
  `;
}

/**
 * 取引履歴の生成
 */
createTransactionHistory(transactions) {
  if (!transactions || transactions.length === 0) {
    return `
      <div class="transaction-history mb-4">
        <h6 class="mb-3">最近の取引</h6>
        <div class="alert alert-info small">
          <i class="fas fa-info-circle me-2"></i>
          取引履歴がありません
        </div>
      </div>
    `;
  }
  
  return `
    <div class="transaction-history mb-4">
      <h6 class="mb-3">最近の取引</h6>
      <div class="transaction-list">
        ${transactions.slice(0, 5).map(transaction => `
          <div class="transaction-item">
            <div class="d-flex justify-content-between align-items-center">
              <div>
                <span class="badge ${transaction.type === 'buy' ? 'bg-success' : 'bg-danger'} me-2">
                  ${transaction.type === 'buy' ? '購入' : '売却'}
                </span>
                <strong>${transaction.ticker}</strong>
                <span class="text-muted">${transaction.shares}株</span>
              </div>
              <div class="text-end">
                <div>${this.formatCurrency(transaction.total_amount)}</div>
                <small class="text-muted">${this.formatTimestamp(transaction.timestamp)}</small>
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

/**
 * パフォーマンス指標の生成
 */
createPerformanceMetrics(investmentData, transactions) {
  if (!investmentData || !transactions) {
    return '';
  }
  
  const totalInvested = investmentData.total_invested || 0;
  const portfolioValue = this.calculatePortfolioValue(investmentData.portfolio);
  const totalFees = investmentData.total_fees_paid || 0;
  const totalDividends = investmentData.total_dividends || 0;
  
  // 投資期間の計算
  const firstTransaction = transactions[transactions.length - 1];
  const investmentDuration = firstTransaction 
    ? Math.floor((Date.now() - new Date(firstTransaction.timestamp)) / (1000 * 60 * 60 * 24))
    : 0;
  
  // 取引回数の計算
  const totalTrades = transactions.length;
  const buyTrades = transactions.filter(t => t.type === 'buy').length;
  const sellTrades = transactions.filter(t => t.type === 'sell').length;
  
  return `
    <div class="performance-metrics">
      <h6 class="mb-3">投資パフォーマンス</h6>
      <div class="row g-3">
        <div class="col-md-6">
          <div class="metric-card">
            <div class="metric-label">投資期間</div>
            <div class="metric-value">${investmentDuration}日</div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="metric-card">
            <div class="metric-label">取引回数</div>
            <div class="metric-value">${totalTrades}回</div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="metric-card">
            <div class="metric-label">購入/売却</div>
            <div class="metric-value">${buyTrades}/${sellTrades}</div>
          </div>
        </div>
        <div class="col-md-6">
          <div class="metric-card">
            <div class="metric-label">手数料合計</div>
            <div class="metric-value">${this.formatCurrency(totalFees)}</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

/**
 * タイムスタンプのフォーマット
 */
formatTimestamp(timestamp) {
  const date = new Date(timestamp);
  const now = new Date();
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return '今日';
  if (diffDays === 1) return '昨日';
  if (diffDays < 7) return `${diffDays}日前`;
  return date.toLocaleDateString('ja-JP');
}

/**
 * 投資ランキングの生成
 */
async generateInvestmentRankings() {
  try {
    // 全ユーザーの投資データを取得してランキング生成
    // 実装は複雑になるため、ここではモックランキングを表示
    return this.getMockInvestmentRankings();
  } catch (error) {
    console.error('投資ランキング生成エラー:', error);
    return [];
  }
}

/**
 * モック投資ランキングの生成
 */
getMockInvestmentRankings() {
  return [
    { userId: 'user1', username: 'InvestorKing', totalReturn: 25.8, portfolioValue: 150000 },
    { userId: 'user2', username: 'StockMaster', totalReturn: 18.3, portfolioValue: 89000 },
    { userId: 'user3', username: 'CryptoWhale', totalReturn: 15.2, portfolioValue: 234000 },
    { userId: 'user4', username: 'DividendHunter', totalReturn: 12.7, portfolioValue: 76000 },
    { userId: 'user5', username: 'GrowthInvestor', totalReturn: 9.4, portfolioValue: 45000 }
  ];
}

// 既存のprofiles.jsファイルに追加するCSS
const additionalInvestmentCSS = `
<style>
/* 投資関連スタイル */
.investment-summary {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 1rem;
}

.investment-stat {
  text-align: center;
  padding: 0.5rem;
}

.investment-stat .stat-value {
  font-weight: bold;
  font-size: 0.9rem;
  margin-bottom: 0.25rem;
}

.investment-stat .stat-label {
  font-size: 0.75rem;
  color: #6c757d;
}

.holdings-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 0.25rem;
}

.stock-tag {
  background: #e9ecef;
  color: #495057;
  padding: 0.25rem 0.5rem;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 500;
}

.stock-tag.more {
  background: #007bff;
  color: white;
}

.transaction-item {
  padding: 0.75rem;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  margin-bottom: 0.5rem;
}

.metric-card {
  text-align: center;
  padding: 1rem;
  background: #f8f9fa;
  border-radius: 6px;
}

.metric-card .metric-label {
  font-size: 0.8rem;
  color: #6c757d;
  margin-bottom: 0.5rem;
}

.metric-card .metric-value {
  font-weight: bold;
  color: #212529;
}

.portfolio-details .table th {
  border-top: none;
  font-weight: 600;
  color: #495057;
  font-size: 0.85rem;
}

.portfolio-details .table td {
  font-size: 0.85rem;
  vertical-align: middle;
}
</style>
`;