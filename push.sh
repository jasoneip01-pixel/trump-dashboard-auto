#!/bin/bash

# 1. 确保在正确的目录下（脚本所在目录）
cd "$(dirname "$0")"

echo "🚀 开始推送更新到 GitHub..."

# 2. 执行 Git 三部曲
git add .

# 获取当前时间作为 Commit 信息
current_time=$(date "+%Y-%m-%d %H:%M:%S")
git commit -m "Auto-update Dashboard: $current_time"

# 3. 推送到远程
git push

echo "✅ 推送完成！请等待约 1 分钟让 GitHub Actions 自动更新网页数据。"
