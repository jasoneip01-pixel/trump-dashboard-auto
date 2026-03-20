#!/bin/bash

# --- 自动获取绝对路径 (修复 ~ 展开问题) ---
REPO_DIR="$(pwd)"
DOWNLOADS_DIR="$(dirname "$REPO_DIR")"
DATA_SOURCE="$DOWNLOADS_DIR/paper_results/real_backtest.json"
HTML_SOURCE="$DOWNLOADS_DIR/trump_dashboard.html"

echo "🚀 开始同步 Trump Dashboard..."

# 1. 进入仓库目录
cd "$REPO_DIR"

# 2. 预清理
echo "🧹 正在清理冗余文件..."
rm -f "#" "docs/index.html.bak" "修改修改时间"

# 3. 强制对齐数据 (这是修复 Action 报错的关键)
echo "📊 正在从 Downloads 抓取核心回测数据..."
mkdir -p paper_results
if [ -f "$DATA_SOURCE" ]; then
    cp "$DATA_SOURCE" paper_results/
    echo "✅ 成功抓取: real_backtest.json"
else
    echo "❌ 错误: 在 $DATA_SOURCE 找不到数据文件，请检查回测是否已运行"
fi

if [ -f "$HTML_SOURCE" ]; then
    cp "$HTML_SOURCE" docs/index.html
    echo "✅ 成功更新: docs/index.html"
fi

# 4. 同步远程
echo "🔄 正在与 GitHub 同步..."
git add .
git commit -m "sync: 💡 自动数据对齐 $(date +'%Y-%m-%d %H:%M:%S')"
git pull origin main --rebase
git push origin main

echo "✨ 全部完成！GitHub Actions 现在应该能跑通了。"
