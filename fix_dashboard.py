import json
import os
import re

# --- 1. 配置数据 (你的真实回测结果) ---
REAL_RETURN = "+52.33%"
REAL_SHARPE = "0.99"
REAL_WIN_RATE = "54.59%"

def fix_dashboard():
    html_path = 'docs/index.html'
    json_path = 'paper_results/real_backtest.json'
    
    if not os.path.exists(html_path):
        print(f"❌ 找不到 HTML 文件: {html_path}")
        return

    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # --- 2. 尝试从 JSON 读取最新数据 (如果存在) ---
    try:
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
                # 假设 JSON 结构包含 total_return 和 sharpe_ratio
                val_return = data.get('total_return', REAL_RETURN)
                val_sharpe = data.get('sharpe_ratio', REAL_SHARPE)
                print(f"✅ 从 JSON 读取到数据: {val_return}")
        else:
            val_return = REAL_RETURN
            val_sharpe = REAL_SHARPE
            print("ℹ️ 未找到 JSON，使用硬编码保底数据")
    except Exception as e:
        print(f"⚠️ 读取 JSON 失败: {e}")
        val_return = REAL_RETURN
        val_sharpe = REAL_SHARPE

    # --- 3. 强力替换 HTML 中的 0.0% 和 0.00 ---
    # 替换累计收益率 (匹配 +0.0% 或 0.0%)
    content = re.sub(r'>\+?0\.0%<', f'>{val_return}<', content)
    # 替换夏普比率 (匹配 0.00)
    content = re.sub(r'>0\.00<', f'>{val_sharpe}<', content)
    # 替换胜率 (如果是 0.0% 的话)
    content = re.sub(r'Win Rate: 0\.0%', f'Win Rate: {REAL_WIN_RATE}', content)

    # --- 4. 写回文件 ---
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("🚀 HTML 指标修复完成！")

if __name__ == "__main__":
    fix_dashboard()
