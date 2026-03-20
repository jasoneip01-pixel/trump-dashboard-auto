#!/bin/bash
# 1. 进入仓库并确保本地代码是最新的
git pull origin main --rebase

# 2. 从上一级目录复制最新的 HTML
cp ../trump_dashboard.html docs/index.html

# 3. 清理可能存在的临时文件
rm -f "#" "docs/index.html.bak" "修改修改时间"

# 4. 提交并推送
git add docs/index.html
git commit -m "site update: $(date)"
git push origin main

echo "✅ Dashboard 已更新并推送到 GitHub!"
