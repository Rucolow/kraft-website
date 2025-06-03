// assets/js/theme-manager.js - テーマ切り替え機能

class ThemeManager {
    constructor() {
        this.currentTheme = 'light';
        this.initialize();
    }

    /**
     * テーママネージャーの初期化
     */
    initialize() {
        // 保存されたテーマを読み込み
        this.loadSavedTheme();
        
        // テーマ切り替えボタンのイベントリスナー設定
        this.setupEventListeners();
        
        // 初期テーマを適用
        this.applyTheme(this.currentTheme);
        
        console.log('🎨 テーママネージャー初期化完了');
    }

    /**
     * 保存されたテーマの読み込み
     */
    loadSavedTheme() {
        try {
            const savedTheme = localStorage.getItem('kraft-theme');
            if (savedTheme && (savedTheme === 'light' || savedTheme === 'dark')) {
                this.currentTheme = savedTheme;
            }
        } catch (error) {
            console.log('テーマ設定の読み込みに失敗:', error);
            this.currentTheme = 'light';
        }
    }

    /**
     * イベントリスナーの設定
     */
    setupEventListeners() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', () => {
                this.toggleTheme();
            });
        }
    }

    /**
     * テーマの切り替え
     */
    toggleTheme() {
        const newTheme = this.currentTheme === 'light' ? 'dark' : 'light';
        this.setTheme(newTheme);
    }

    /**
     * テーマの設定
     */
    setTheme(theme) {
        this.currentTheme = theme;
        this.applyTheme(theme);
        this.saveTheme(theme);
        this.updateThemeIcon(theme);
    }

    /**
     * テーマの適用
     */
    applyTheme(theme) {
        const body = document.body;
        
        if (theme === 'dark') {
            body.setAttribute('data-theme', 'dark');
            body.classList.add('dark-theme');
        } else {
            body.removeAttribute('data-theme');
            body.classList.remove('dark-theme');
        }
    }

    /**
     * テーマアイコンの更新
     */
    updateThemeIcon(theme) {
        const themeIcon = document.getElementById('themeIcon');
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'fas fa-sun';
            } else {
                themeIcon.className = 'fas fa-moon';
            }
        }
    }

    /**
     * テーマの保存
     */
    saveTheme(theme) {
        try {
            localStorage.setItem('kraft-theme', theme);
        } catch (error) {
            console.log('テーマ設定の保存に失敗:', error);
        }
    }

    /**
     * 現在のテーマを取得
     */
    getCurrentTheme() {
        return this.currentTheme;
    }
}

// ダークテーマ用CSS（動的に追加）
const darkThemeCSS = `
body.dark-theme {
    background-color: #1a1a1a !important;
    color: #e9ecef !important;
}

body.dark-theme .card {
    background-color: #2d2d2d !important;
    color: #e9ecef !important;
}

body.dark-theme .navbar-dark {
    background-color: #0d1117 !important;
}

body.dark-theme .bg-light {
    background-color: #2d2d2d !important;
}

body.dark-theme .text-dark {
    color: #e9ecef !important;
}

body.dark-theme .investment-page {
    background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%) !important;
}

body.dark-theme .company-card {
    background-color: #2d2d2d !important;
    color: #e9ecef !important;
    border-color: #404040 !important;
}

body.dark-theme .stat-card {
    background-color: #2d2d2d !important;
    color: #e9ecef !important;
}

body.dark-theme .news-item {
    background-color: #2d2d2d !important;
    color: #e9ecef !important;
}

body.dark-theme .ranking-item {
    background-color: #2d2d2d !important;
    color: #e9ecef !important;
}
`;

// ダークテーマCSSを動的に追加
function addDarkThemeCSS() {
    const styleElement = document.createElement('style');
    styleElement.id = 'dark-theme-css';
    styleElement.textContent = darkThemeCSS;
    document.head.appendChild(styleElement);
}

// ページ読み込み時にダークテーマCSSを追加
document.addEventListener('DOMContentLoaded', () => {
    addDarkThemeCSS();
});

// グローバルエクスポート
window.ThemeManager = ThemeManager;