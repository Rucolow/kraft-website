cat > assets/js/main.js << 'EOF'
// KRAFT Website Main JavaScript
console.log('KRAFT Website loaded');

// Chart.js のグローバル設定
if (typeof Chart !== 'undefined') {
  Chart.defaults.responsive = true;
  Chart.defaults.maintainAspectRatio = false;
  console.log('Chart.js loaded successfully');
}

// Chart.js テストチャート作成
function createTestChart(canvasId) {
  if (typeof Chart !== 'undefined') {
    const ctx = document.getElementById(canvasId);
    if (ctx) {
      new Chart(ctx, {
        type: 'bar',
        data: {
          labels: ['Level 1-10', 'Level 11-20', 'Level 21-30', 'Level 31-40', 'Level 41-50', '50+'],
          datasets: [{
            label: 'Users',
            data: [12, 19, 8, 5, 2, 1],
            backgroundColor: [
              'rgba(255, 99, 132, 0.2)',
              'rgba(54, 162, 235, 0.2)',
              'rgba(255, 205, 86, 0.2)',
              'rgba(75, 192, 192, 0.2)',
              'rgba(153, 102, 255, 0.2)',
              'rgba(255, 159, 64, 0.2)'
            ],
            borderWidth: 1
          }]
        },
        options: {
          scales: {
            y: {
              beginAtZero: true
            }
          },
          plugins: {
            title: {
              display: true,
              text: 'Level Distribution (Test Data)'
            }
          }
        }
      });
    }
  }
}

// DOM読み込み完了時の処理
document.addEventListener('DOMContentLoaded', function() {
  // テストチャートの作成
  if (document.getElementById('testChart')) {
    createTestChart('testChart');
  }
});
EOF