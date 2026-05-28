import os
import json
import urllib.request
import urllib.parse
import sys

# 設定値
SHOP_ID = "2759"
SITE_CODE = "ado-officialshop"
API_URL = f"https://shop.api.groobee.com/products/search?per_page=100&shop_id={SHOP_ID}"
SHOP_URL = "https://ado-officialshop-friedpotato.com/shops/Ao"
BASE_PRODUCT_URL = "https://ado-officialshop-friedpotato.com/products"
STATE_FILE = "stock_state.json"

# Discord Webhook URL (環境変数から取得)
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def fetch_products():
    """Groobee APIから製品データを取得する"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'Origin': 'https://ado-officialshop-friedpotato.com',
        'Referer': 'https://ado-officialshop-friedpotato.com/',
        'X-Bet-Site-Code': SITE_CODE
    }
    req = urllib.request.Request(API_URL, headers=headers)
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        return data.get('_embedded', {}).get('products', [])

def send_discord_message(content):
    """Discord Webhookに通知を送信する"""
    if not WEBHOOK_URL:
        print("Warning: DISCORD_WEBHOOK_URL が設定されていないため、Discordへの通知はスキップします。")
        print("通知内容:\n", content)
        return
    
    payload = {"content": content}
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=data,
        headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            print("Discordへの通知に成功しました。")
    except Exception as e:
        print(f"Discord通知送信エラー: {e}", file=sys.stderr)

def main():
    print("再販検知スクリプトを実行中...")
    
    try:
        products = fetch_products()
        print(f"APIから {len(products)} 個の商品を取得しました。")
    except Exception as e:
        print(f"APIからのデータ取得エラー: {e}", file=sys.stderr)
        sys.exit(1)
        
    # 現在の在庫ステータスを構築
    # 在庫あり条件: isSoldOutがFalse、かつisAvailableがTrue、かつ販売開始前でなく、かつ販売終了でない
    current_state = {}
    for p in products:
        pid = str(p.get('id'))
        name = p.get('name')
        slug = p.get('slug')
        price = p.get('price')
        is_sold_out = p.get('isSoldOut', False)
        is_available = p.get('isAvailable', True)
        is_before_launch = p.get('isBeforeLaunch', False)
        is_sales_end = p.get('isSalesEnd', False)
        
        is_in_stock = (not is_sold_out) and is_available and (not is_before_launch) and (not is_sales_end)
        
        current_state[pid] = {
            'name': name,
            'slug': slug,
            'price': price,
            'is_in_stock': is_in_stock
        }
        
    # 前回の状態を読み込む
    prev_state = {}
    is_first_run = not os.path.exists(STATE_FILE)
    if not is_first_run:
        try:
            with open(STATE_FILE, 'r', encoding='utf-8') as f:
                prev_state = json.load(f)
            print("前回の在庫ステータスを読み込みました。")
        except Exception as e:
            print(f"ステータスファイルの読み込みエラー（初回実行として扱います）: {e}", file=sys.stderr)
            is_first_run = True
            
    restocked_items = []
    
    if is_first_run:
        print("初回実行のため、現在のステータスを保存し、監視を開始します（再販通知は行いません）。")
        # 監視開始のお知らせをDiscordに送信
        startup_msg = (
            "【Ado Official Shop 再販検知システム】\n"
            f"監視システムが正常に起動しました！\n"
            f"現在 {len(current_state)} 個の商品を監視しています。\n"
            f"対象ショップ: {SHOP_URL}"
        )
        send_discord_message(startup_msg)
    else:
        # 再販（out_of_stock -> in_stock）された商品をチェック
        for pid, info in current_state.items():
            if info['is_in_stock']:
                prev_info = prev_state.get(pid)
                # 前回在庫がなかった、または新規追加商品の場合に検知
                if not prev_info or not prev_info.get('is_in_stock', False):
                    restocked_items.append(info)
                    
        if restocked_items:
            print(f"再販を検知しました！ 商品数: {len(restocked_items)}")
            
            # メッセージの作成
            msg_lines = [
                "【Ado Official Shop 再販検知】",
                "以下のグッズの再販（在庫復活）が検知されました！",
                ""
            ]
            for item in restocked_items:
                product_url = f"{BASE_PRODUCT_URL}/{item['slug']}" if item['slug'] else SHOP_URL
                msg_lines.append("----------------------------------------")
                msg_lines.append(f"■ 商品名: {item['name']}")
                msg_lines.append(f"■ 価格: {item['price']:,}円")
                msg_lines.append(f"■ 商品ページ: {product_url}")
            msg_lines.append("----------------------------------------")
            msg_lines.append("")
            msg_lines.append(f"ショップURL: {SHOP_URL}")
            
            discord_msg = "\n".join(msg_lines)
            send_discord_message(discord_msg)
        else:
            print("再販された商品は検知されませんでした。")
            
    # 今回の状態をファイルに書き出す
    try:
        with open(STATE_FILE, 'w', encoding='utf-8') as f:
            json.dump(current_state, f, ensure_ascii=False, indent=2)
        print("最新の在庫ステータスを保存しました。")
    except Exception as e:
        print(f"ステータスファイルの書き込みエラー: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
