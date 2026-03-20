#!/bin/bash

# --- 配置区 ---
REPO_DIR="~/Downloads/trump-dashboard-auto"
DATA_SOURCE="~/Downloads/paper_results/real_backtest.json"
HTML_SOURCE="~/Downloads/trump_dashboard.html"

echo "🚀 开始同步 Trump Dashboard..."

# 1. 确保在仓库目录
cd $REPO_DIR

# 2. 预清理：删除烦人的乱码和临时文件
echo "🧹 正在清理冗余文件..."
rm -f "#" "docs/index.html.bak" "修改修改时间" "deploy.sh"

# 3. 数据对齐：从 Downloads 抓取最新的回测 JSON 和生成的 HTML
echo "📊 同步本地回测数据..."
mkdir -p paper_results
if [ -f $DATA_SOURCE ]; then
    cp $DATA_SOURCE paper_results/
    echo "✅ JSON 数据已更新"
else
    echo "⚠️ 警告: 未找到 real_backtest.json"
fi

if [ -f $HTML_SOURCE ]; then
    cp $HTML_SOURCE docs/index.html
    echo "✅ HTML 模板已更新"
fi

# 4. 解决冲突：强制拉取远程更改 (防止 Action 运行后本地无法推送)
echo "🔄 正在与 GitHub 云端同步逻辑..."
git pull origin main --rebase

# 5. 提交并推送
echo "📤 正在推送到生产环境 (GitHub Pages)..."
git add .
git commit -m "sync: 💡 本地一键同步 $(date +'%Y-%m-%d %H:%M:%S')"
git push origin main

echo "✨ 所有任务已完成！请等待 1 分钟后刷新网页。"
