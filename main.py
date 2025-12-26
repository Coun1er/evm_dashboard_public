import asyncio
import json
import random
import time
from collections import defaultdict

from curl_cffi import AsyncSession
from jinja2 import Template


class CryptoBalanceAnalyzer:
    def __init__(self):
        self.session = None
        self.proxies = []
        self.current_proxy_index = 0

    async def __aenter__(self):
        self.session = AsyncSession()
        await self.load_proxies()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def load_proxies(self):
        """Загрузка прокси из файла"""
        try:
            with open("proxy.txt", "r", encoding="utf-8") as f:
                proxy_lines = [line.strip() for line in f if line.strip()]

            for proxy_line in proxy_lines:
                if ":" in proxy_line and "@" in proxy_line:
                    # Формат: login:pass@ip:port
                    auth_part, server_part = proxy_line.split("@")
                    username, password = auth_part.split(":")
                    ip, port = server_part.split(":")

                    proxy_dict = {
                        "http": f"http://{username}:{password}@{ip}:{port}",
                        "https": f"http://{username}:{password}@{ip}:{port}",
                    }
                    self.proxies.append(proxy_dict)

            print(f"✅ Загружено {len(self.proxies)} прокси")

        except FileNotFoundError:
            print("⚠️ Файл proxy.txt не найден, работаем без прокси")
        except Exception as e:
            print(f"❌ Ошибка при загрузке прокси: {e}")

    def get_next_proxy(self):
        """Получение случайного прокси из списка"""
        if not self.proxies:
            return None

        return random.choice(self.proxies)

    async def get_wallet_data(self, address, max_retries=3):
        """Получение данных из кеша для кошелька по адресу с поддержкой прокси и повторных попыток"""
        url = f"https://api.rabby.io/v1/user/cache_token_list?id={address}"

        for attempt in range(max_retries):
            proxy = self.get_next_proxy()

            try:
                if proxy:
                    print(
                        f"🔄 Попытка (cache) {attempt + 1}/{max_retries} для {address[:8]}... (прокси: {proxy['http'].split('@')[1]})"
                    )
                    response = await self.session.get(
                        url, impersonate="chrome", proxies=proxy, timeout=30
                    )
                else:
                    print(
                        f"🔄 Попытка {attempt + 1}/{max_retries} для {address[:8]}... (без прокси)"
                    )
                    response = await self.session.get(
                        url, impersonate="chrome", timeout=30
                    )

                # Проверяем статус ответа
                if response.status_code != 200:
                    print(f"⚠️ HTTP {response.status_code} для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)  # Экспоненциальная задержка
                        continue
                    else:
                        return []

                # Парсим JSON ответ
                try:
                    data = json.loads(response.text)
                except json.JSONDecodeError:
                    print(f"❌ Некорректный JSON для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    else:
                        return []

                # Проверяем на ошибку "Too Many Requests"
                if (
                    isinstance(data, dict)
                    and data.get("message") == "Too Many Requests"
                ):
                    print(
                        f"🚫 Too Many Requests для {address[:8]}... (попытка {attempt + 1})"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(
                            5 + (2**attempt)
                        )  # Увеличенная задержка для rate limit
                        continue
                    else:
                        print(
                            f"❌ Превышен лимит запросов для {address[:8]}... после {max_retries} попыток"
                        )
                        return []

                # Проверяем, что получили список (корректные данные)
                if not isinstance(data, list):
                    print(f"⚠️ Неожиданный формат данных для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    else:
                        return []

                print(
                    f"✅ Успешно получены данные для {address[:8]}... ({len(data)} токенов)"
                )
                return data

            except asyncio.TimeoutError:
                print(f"⏰ Таймаут для {address[:8]}... (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
            except Exception as e:
                print(f"❌ Ошибка для {address[:8]}... (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue

        print(
            f"💀 Не удалось получить данные для {address[:8]}... после {max_retries} попыток"
        )
        return []

    async def get_first_wallet_data(self, address, max_retries=3):
        """Полученние данных, если первый раз"""
        url = f"https://api.rabby.io/v1/user/token_list?id={address}"

        for attempt in range(max_retries):
            proxy = self.get_next_proxy()

            try:
                if proxy:
                    print(
                        f"🔄 Попытка (firs) {attempt + 1}/{max_retries} для {address[:8]}... (прокси: {proxy['http'].split('@')[1]})"
                    )
                    response = await self.session.get(
                        url, impersonate="chrome", proxies=proxy, timeout=30
                    )
                else:
                    print(
                        f"🔄 Попытка {attempt + 1}/{max_retries} для {address[:8]}... (без прокси)"
                    )
                    response = await self.session.get(
                        url, impersonate="chrome", timeout=30
                    )

                # Проверяем статус ответа
                if response.status_code != 200:
                    print(f"⚠️ HTTP {response.status_code} для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)  # Экспоненциальная задержка
                        continue
                    else:
                        return []

                # Парсим JSON ответ
                try:
                    data = json.loads(response.text)
                except json.JSONDecodeError:
                    print(f"❌ Некорректный JSON для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    else:
                        return []

                # Проверяем на ошибку "Too Many Requests"
                if (
                    isinstance(data, dict)
                    and data.get("message") == "Too Many Requests"
                ):
                    print(
                        f"🚫 Too Many Requests для {address[:8]}... (попытка {attempt + 1})"
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(
                            5 + (2**attempt)
                        )  # Увеличенная задержка для rate limit
                        continue
                    else:
                        print(
                            f"❌ Превышен лимит запросов для {address[:8]}... после {max_retries} попыток"
                        )
                        return []

                # Проверяем, что получили список (корректные данные)
                if not isinstance(data, list):
                    print(f"⚠️ Неожиданный формат данных для {address[:8]}...")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(2**attempt)
                        continue
                    else:
                        return []

                print(
                    f"✅ Успешно получены данные для {address[:8]}... ({len(data)} токенов)"
                )
                return data

            except asyncio.TimeoutError:
                print(f"⏰ Таймаут для {address[:8]}... (попытка {attempt + 1})")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue
            except Exception as e:
                print(f"❌ Ошибка для {address[:8]}... (попытка {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2**attempt)
                    continue

        print(
            f"💀 Не удалось получить данные для {address[:8]}... после {max_retries} попыток"
        )
        return []

    def process_wallet_data(self, address, tokens_data):
        """Обработка данных кошелька и группировка по сетям"""
        networks = defaultdict(lambda: {"tokens": [], "total_value": 0})
        total_wallet_value = 0

        for token in tokens_data:
            chain = token.get("chain", "unknown")
            token_value = token.get("amount", 0) * token.get("price", 0)

            networks[chain]["tokens"].append(
                {
                    "name": token.get("name", "Unknown"),
                    "symbol": token.get("symbol", ""),
                    "amount": token.get("amount", 0),
                    "price": token.get("price", 0),
                    "value": token_value,
                    "logo_url": token.get("logo_url", ""),
                }
            )

            networks[chain]["total_value"] += token_value
            total_wallet_value += token_value

        return {
            "address": address,
            "networks": dict(networks),
            "total_value": total_wallet_value,
        }

    def get_chain_logo(self, chain):
        """Получение логотипа сети"""
        chain_logos = {
            "eth": "https://static.debank.com/image/coin/logo_url/eth/6443cdccced33e204d90cb723c632917.png",
            "bsc": "https://static.debank.com/image/coin/logo_url/bnb/9784283a36f23a58982fc964574ea530.png",
            "matic": "https://static.debank.com/image/matic_token/logo_url/matic/6f5a6b6f0732a7a235131bd7804d357c.png",
            "op": "https://static.debank.com/image/op_token/logo_url/0x4200000000000000000000000000000000000042/029a56df18f88f4123120fdcb6bea40b.png",
            "avax": "https://static.debank.com/image/project/logo_url/avax_wavax/e195cdd89f44bf3d0c65d38ce2c6c662.png",
            "ftm": "https://static.debank.com/image/ftm_token/logo_url/ftm/33fdb9c5067e94f3a1b9e78f6fa86984.png",
            "base": "https://static.debank.com/image/chain/logo_url/base/ccc1513e4f390542c4fb2f4b88ce9579.png",
            "arb": "https://static.debank.com/image/chain/logo_url/arb/854f629937ce94bebeb2cd38fb336de7.png",
            "sonic": "https://static.debank.com/image/chain/logo_url/sonic/8ba4d8395618ec1329ea7142b0fde642.png",
            "era": "https://static.debank.com/image/chain/logo_url/era/2cfcd0c8436b05d811b03935f6c1d7da.png",
            "abs": "https://static.debank.com/image/chain/logo_url/abs/c59200aadc06c79d7c061cfedca85c38.png",
        }
        return chain_logos.get(chain, "https://placehold.co/24x24")

    def get_all_networks(self, wallets_data):
        """Получение списка всех сетей"""
        all_networks = set()
        for wallet in wallets_data:
            all_networks.update(wallet["networks"].keys())
        return sorted(list(all_networks))

    def generate_html(self, wallets_data):
        """Генерация HTML страницы"""
        all_networks = self.get_all_networks(wallets_data)

        template = Template("""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Wallets Balance Dashboard</title>
    <script src="https://unpkg.com/htmx.org@1.9.10"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #34495e, #2c3e50);
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
            overflow: hidden;
        }

        .header {
            background: linear-gradient(135deg, #2c3e50, #3498db);
            color: white;
            padding: 30px;
            text-align: center;
            position: relative;
        }

        .header h1 {
            font-size: 2.5rem;
            margin-bottom: 10px;
            font-weight: 700;
        }

        .header p {
            opacity: 0.9;
            font-size: 1.1rem;
            margin-bottom: 20px;
        }

        .filters-section {
            background: rgba(255,255,255,0.1);
            padding: 20px;
            border-radius: 15px;
            margin-top: 20px;
            text-align: left;
        }

        .filters-toggle {
            background: rgba(255,255,255,0.2);
            border: none;
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.3s ease;
            margin-bottom: 15px;
        }

        .filters-toggle:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }

        .filters-content {
            display: none;
            animation: slideDown 0.3s ease;
        }

        .filters-content.show {
            display: block;
        }

        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .filter-group {
            margin-bottom: 20px;
        }

        .filter-group h3 {
            margin-bottom: 10px;
            font-size: 1rem;
            opacity: 0.9;
        }

        .networks-filter {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 10px;
            margin-bottom: 20px;
        }

        .network-checkbox {
            display: flex;
            align-items: center;
            background: rgba(255,255,255,0.1);
            padding: 8px 12px;
            border-radius: 20px;
            cursor: pointer;
            transition: all 0.3s ease;
            border: 2px solid transparent;
        }

        .network-checkbox:hover {
            background: rgba(255,255,255,0.2);
            transform: translateY(-2px);
        }

        .network-checkbox.checked {
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }

        .network-checkbox input[type="checkbox"] {
            margin-right: 8px;
            transform: scale(1.2);
        }

        .network-checkbox img {
            width: 16px;
            height: 16px;
            margin-right: 6px;
            border-radius: 50%;
        }

        .min-balance-filter {
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .min-balance-filter input {
            background: rgba(255,255,255,0.2);
            border: 2px solid rgba(255,255,255,0.3);
            color: white;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.9rem;
            width: 120px;
        }

        .min-balance-filter input::placeholder {
            color: rgba(255,255,255,0.7);
        }

        .min-balance-filter input:focus {
            outline: none;
            border-color: rgba(255,255,255,0.6);
            background: rgba(255,255,255,0.25);
        }

        .apply-filters-btn {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
            border: none;
            color: white;
            padding: 10px 25px;
            border-radius: 25px;
            cursor: pointer;
            font-weight: 600;
            font-size: 0.9rem;
            transition: all 0.3s ease;
            margin-top: 10px;
        }

        .apply-filters-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(231, 76, 60, 0.4);
        }

        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }

        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 15px;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
            border-left: 4px solid #3498db;
            transition: all 0.3s ease;
        }

        .stat-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 15px 30px rgba(0,0,0,0.1);
        }

        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #2c3e50;
            margin-bottom: 5px;
        }

        .stat-label {
            color: #7f8c8d;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .table-container {
            padding: 30px;
        }

        .wallets-table {
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 15px;
            overflow: hidden;
            box-shadow: 0 10px 20px rgba(0,0,0,0.05);
        }

        .wallets-table th {
            background: linear-gradient(135deg, #34495e, #2c3e50);
            color: white;
            padding: 20px 15px;
            text-align: left;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            font-size: 0.85rem;
        }

        .sortable-header {
            cursor: pointer;
            user-select: none;
            position: relative;
            transition: all 0.3s ease;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }

        .sortable-header:hover {
            background: rgba(255,255,255,0.1);
            transform: translateY(-1px);
        }

        .sort-icon {
            margin-left: 8px;
            font-size: 0.8rem;
            opacity: 0.7;
            transition: all 0.3s ease;
        }

        .sort-icon.active {
            opacity: 1;
            transform: scale(1.2);
        }

        .wallet-row {
            border-bottom: 1px solid #eee;
            transition: all 0.3s ease;
            cursor: pointer;
        }

        .wallet-row:hover {
            background: #f8f9fa;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }

        .wallet-row.hidden {
            display: none;
        }

        .wallet-row td {
            padding: 20px 15px;
            vertical-align: middle;
        }

        .address {
            font-family: 'SF Mono', 'Monaco', monospace;
            background: #f1f3f4;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 0.9rem;
            color: #2c3e50;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.3s ease;
            user-select: none;
        }

        .address:hover {
            background: #e8f4fd;
            transform: translateY(-1px);
            box-shadow: 0 3px 10px rgba(52, 152, 219, 0.2);
        }

        .address:active {
            transform: translateY(0);
        }
        .network-item {
            display: inline-flex;
            align-items: center;
            margin: 5px 10px 5px 0;
            background: linear-gradient(135deg, #74b9ff, #0984e3);
            color: white;
            padding: 8px 15px;
            border-radius: 25px;
            font-size: 0.85rem;
            font-weight: 500;
            box-shadow: 0 5px 10px rgba(116, 185, 255, 0.3);
            transition: all 0.3s ease;
        }

        .network-item:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(116, 185, 255, 0.4);
        }

        .network-item.filtered {
            opacity: 0.3;
            background: #bdc3c7;
        }

        .network-logo {
            width: 20px;
            height: 20px;
            border-radius: 50%;
            margin-right: 8px;
            border: 2px solid rgba(255,255,255,0.3);
        }

        .value {
            font-weight: 600;
            font-size: 1.1rem;
        }

        .value.positive {
            color: #27ae60;
        }

        .total-value {
            font-size: 1.3rem;
            font-weight: bold;
            color: #27ae60;
            text-shadow: 0 2px 4px rgba(39, 174, 96, 0.2);
        }

        .details-row {
            background: #f8f9fa;
            border-left: 4px solid #3498db;
        }

        .details-row.hidden {
            display: none;
        }

        .token-details {
            padding: 20px;
        }

        .network-section {
            margin-bottom: 25px;
            border-radius: 12px;
            overflow: hidden;
            box-shadow: 0 5px 15px rgba(0,0,0,0.05);
        }

        .network-section.filtered {
            display: none;
        }

        .network-header {
            background: linear-gradient(135deg, #74b9ff, #0984e3);
            color: white;
            padding: 15px 20px;
            display: flex;
            align-items: center;
            font-weight: 600;
        }

        .network-header img {
            width: 24px;
            height: 24px;
            margin-right: 12px;
            border-radius: 50%;
            border: 2px solid rgba(255,255,255,0.3);
        }

        .tokens-grid {
            background: white;
            padding: 20px;
        }

        .token-item {
            display: flex;
            justify-content: between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid #eee;
            transition: all 0.3s ease;
        }

        .token-item:hover {
            background: #f8f9fa;
            padding-left: 10px;
            border-radius: 8px;
        }

        .token-item:last-child {
            border-bottom: none;
        }

        .token-item.filtered {
            display: none;
        }

        .token-info {
            display: flex;
            align-items: center;
            flex: 1;
        }

        .token-logo {
            width: 32px;
            height: 32px;
            border-radius: 50%;
            margin-right: 12px;
            border: 2px solid #eee;
        }

        .token-name {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 2px;
        }

        .token-symbol {
            color: #7f8c8d;
            font-size: 0.85rem;
        }

        .token-balance {
            text-align: right;
            margin-left: auto;
        }

        .token-amount {
            font-weight: 600;
            color: #2c3e50;
            margin-bottom: 2px;
        }

        .token-value {
            color: #27ae60;
            font-size: 0.9rem;
            font-weight: 500;
        }

        .expand-btn {
            background: none;
            border: none;
            color: #3498db;
            cursor: pointer;
            font-size: 1.2rem;
            transition: transform 0.3s ease;
        }

        .expand-btn:hover {
            transform: scale(1.2);
        }

        .loading {
            text-align: center;
            padding: 40px;
            color: #7f8c8d;
        }

        .error {
            background: #e74c3c;
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin: 10px 0;
        }

        /* Стили для попапа копирования */
        .copy-popup {
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%) scale(0);
            background: linear-gradient(135deg, #27ae60, #2ecc71);
            color: white;
            padding: 15px 25px;
            border-radius: 25px;
            box-shadow: 0 10px 30px rgba(39, 174, 96, 0.3);
            z-index: 1000;
            font-weight: 600;
            font-size: 0.9rem;
            display: flex;
            align-items: center;
            gap: 10px;
            transition: all 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            pointer-events: none;
        }

        .copy-popup.show {
            transform: translate(-50%, -50%) scale(1);
        }

        .copy-popup::before {
            content: '✓';
            background: rgba(255,255,255,0.2);
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 0.8rem;
        }

        @media (max-width: 768px) {
            .header h1 {
                font-size: 2rem;
            }

            .wallets-table th,
            .wallets-table td {
                padding: 10px 8px;
                font-size: 0.85rem;
            }

            .network-item {
                margin: 3px 5px 3px 0;
                padding: 6px 10px;
                font-size: 0.75rem;
            }

            .token-details {
                padding: 15px;
            }

            .networks-filter {
                grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Wallets Dashboard</h1>
            <p>Мульти чекер баланса кошельков</p>

            <div class="filters-section">
                <button class="filters-toggle" onclick="toggleFilters()">
                    ⚙️ Настройки фильтров
                </button>

                <div class="filters-content" id="filtersContent">
                    <div class="filter-group">
                        <h3>🌐 Отображаемые сети:</h3>
                        <div class="networks-filter">
                            {% for network in all_networks %}
                            <label class="network-checkbox" data-network="{{ network }}">
                                <input type="checkbox" checked onchange="updateNetworkFilter('{{ network }}', this.checked)">
                                <img src="{{ get_chain_logo(network) }}" alt="{{ network }}">
                                {{ network.upper() }}
                            </label>
                            {% endfor %}
                        </div>
                    </div>

                    <div class="filter-group">
                        <h3>💰 Минимальный баланс токена:</h3>
                        <div class="min-balance-filter">
                            <span>$</span>
                            <input type="number"
                                   id="minBalanceInput"
                                   placeholder="0.01"
                                   step="0.01"
                                   min="0"
                                   value="0.01"
                                   onchange="updateMinBalance(this.value)">
                            <span>USD</span>
                        </div>
                    </div>

                    <button class="apply-filters-btn" onclick="applyFilters()">
                        🔄 Применить фильтры
                    </button>
                </div>
            </div>
        </div>

        <div class="stats">
            <div class="stat-card">
                <div class="stat-number" id="walletsCount">{{ wallets_data|length }}</div>
                <div class="stat-label">Кошельков</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="totalValue">${{ "%.2f"|format(total_value) }}</div>
                <div class="stat-label">Общая стоимость</div>
            </div>
            <div class="stat-card">
                <div class="stat-number" id="networksCount">{{ total_networks }}</div>
                <div class="stat-label">Сетей</div>
            </div>
        </div>

        <div class="table-container">
            <table class="wallets-table">
                <thead>
                    <tr>
                        <th style="width: 30px;"></th>
                        <th>Адрес</th>
                        <th>Сети</th>
                        <th style="text-align: right;">
                            <div class="sortable-header" onclick="handleSortClick()">
                                <span>Общая стоимость</span>
                                <span class="sort-icon" id="sortIcon">⇅</span>
                            </div>
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {% for wallet in wallets_data %}
                    <tr class="wallet-row" data-wallet-index="{{ loop.index0 }}" onclick="toggleDetails('details-{{ loop.index0 }}')">
                        <td>
                            <button class="expand-btn" id="btn-{{ loop.index0 }}">▶</button>
                        </td>
                        <td>
                            <div class="address" onclick="copyAddress('{{ wallet.address }}', this)" title="Нажмите, чтобы скопировать адрес">
                                {{ wallet.address[:6] }}...{{ wallet.address[-4:] }}
                            </div>
                        </td>
                        <td class="networks-cell" data-wallet-index="{{ loop.index0 }}">
                            {% for network, data in wallet.networks.items() %}
                            <div class="network-item" data-network="{{ network }}" data-value="{{ data.total_value }}">
                                <img src="{{ get_chain_logo(network) }}" alt="{{ network }}" class="network-logo">
                                {{ network.upper() }} ${{ "%.2f"|format(data.total_value) }}
                            </div>
                            {% endfor %}
                        </td>
                        <td style="text-align: right;">
                            <div class="total-value" data-wallet-index="{{ loop.index0 }}">${{ "%.2f"|format(wallet.total_value) }}</div>
                        </td>
                    </tr>
                    <tr id="details-{{ loop.index0 }}" class="details-row" data-wallet-index="{{ loop.index0 }}" style="display: none;">
                        <td colspan="4">
                            <div class="token-details">
                                {% for network, data in wallet.networks.items() %}
                                <div class="network-section" data-network="{{ network }}">
                                    <div class="network-header">
                                        <img src="{{ get_chain_logo(network) }}" alt="{{ network }}">
                                        <span class="network-name">{{ network.upper() }}</span> <span class="network-total"> (${{ "%.2f"|format(data.total_value) }})</span>
                                    </div>
                                    <div class="tokens-grid">
                                        {% for token in data.tokens %}
                                        <div class="token-item" data-value="{{ token.value }}" data-network="{{ network }}">
                                            <div class="token-info">
                                                <img src="{{ token.logo_url or 'https://placehold.co/32x32' }}"
                                                     alt="{{ token.symbol }}" class="token-logo">
                                                <div>
                                                    <div class="token-name">{{ token.name }}</div>
                                                    <div class="token-symbol">{{ token.symbol }}</div>
                                                </div>
                                            </div>
                                            <div class="token-balance">
                                                <div class="token-amount">{{ "%.6f"|format(token.amount) }}</div>
                                                <div class="token-value">${{ "%.2f"|format(token.value) }}</div>
                                            </div>
                                        </div>
                                        {% endfor %}
                                    </div>
                                </div>
                                {% endfor %}
                            </div>
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>

    <!-- Попап для уведомления о копировании -->
    <div id="copyPopup" class="copy-popup">
        Адрес скопирован в буфер обмена!
    </div>

    <script>
        // Глобальные переменные для фильтров и сортировки (объявляем в самом начале)
        let enabledNetworks = new Set({{ all_networks|tojson }});
        let minBalance = 0.01;
        let walletsData = {{ wallets_data|tojson }};
        let currentSort = 'none'; // 'none', 'desc', 'asc'
        let originalOrder = [];

        // Функция получения логотипа сети (дублируем из Python)
        function getChainLogo(chain) {
            const chainLogos = {
                "eth": "https://static.debank.com/image/coin/logo_url/eth/6443cdccced33e204d90cb723c632917.png",
                "bsc": "https://static.debank.com/image/coin/logo_url/bnb/9784283a36f23a58982fc964574ea530.png",
                "matic": "https://static.debank.com/image/matic_token/logo_url/matic/6f5a6b6f0732a7a235131bd7804d357c.png",
                "op": "https://static.debank.com/image/op_token/logo_url/0x4200000000000000000000000000000000000042/029a56df18f88f4123120fdcb6bea40b.png",
                "avax": "https://static.debank.com/image/project/logo_url/avax_wavax/e195cdd89f44bf3d0c65d38ce2c6c662.png",
                "ftm": "https://static.debank.com/image/ftm_token/logo_url/ftm/33fdb9c5067e94f3a1b9e78f6fa86984.png",
                "base": "https://static.debank.com/image/coin/logo_url/eth/6443cdccced33e204d90cb723c632917.png",
                "arb": "https://static.debank.com/image/coin/logo_url/eth/6443cdccced33e204d90cb723c632917.png"
            };
            return chainLogos[chain] || "https://placehold.co/24x24";
        }

        // Функция обработки клика по сортировке
        function handleSortClick() {
            const sortIcon = document.getElementById('sortIcon');
            const tbody = document.querySelector('.wallets-table tbody');

            // Сохраняем оригинальный порядок при первой сортировке
            if (originalOrder.length === 0) {
                originalOrder = Array.from(tbody.children).map((row, index) => ({
                    element: row,
                    originalIndex: index
                }));
            }

            // Переключаем режим сортировки
            if (currentSort === 'none') {
                currentSort = 'desc';
                sortIcon.textContent = '↓';
                sortIcon.classList.add('active');
            } else if (currentSort === 'desc') {
                currentSort = 'asc';
                sortIcon.textContent = '↑';
                sortIcon.classList.add('active');
            } else {
                currentSort = 'none';
                sortIcon.textContent = '⇅';
                sortIcon.classList.remove('active');
            }

            applySorting();
        }

        function applySorting() {
            const tbody = document.querySelector('.wallets-table tbody');
            const rows = Array.from(tbody.children);

            // Разделяем строки на wallet-row и details-row
            const walletRows = rows.filter(row => row.classList.contains('wallet-row'));
            const detailsRows = rows.filter(row => row.classList.contains('details-row'));

            if (currentSort === 'none') {
                // Возвращаем оригинальный порядок
                originalOrder.forEach(item => {
                    tbody.appendChild(item.element);
                    // Находим соответствующую details-row
                    const walletIndex = item.element.dataset.walletIndex;
                    const detailsRow = detailsRows.find(row => row.dataset.walletIndex === walletIndex);
                    if (detailsRow) {
                        tbody.appendChild(detailsRow);
                    }
                });
            } else {
                // Сортируем по текущей стоимости (учитывая фильтры)
                walletRows.sort((a, b) => {
                    const valueA = getCurrentWalletValue(a.dataset.walletIndex);
                    const valueB = getCurrentWalletValue(b.dataset.walletIndex);

                    return currentSort === 'desc' ? valueB - valueA : valueA - valueB;
                });

                // Перестраиваем DOM
                walletRows.forEach(walletRow => {
                    tbody.appendChild(walletRow);
                    // Добавляем соответствующую details-row сразу после wallet-row
                    const walletIndex = walletRow.dataset.walletIndex;
                    const detailsRow = detailsRows.find(row => row.dataset.walletIndex === walletIndex);
                    if (detailsRow) {
                        tbody.appendChild(detailsRow);
                    }
                });
            }
        }

        function getCurrentWalletValue(walletIndex) {
            // Вычисляем текущую стоимость кошелька с учетом активных фильтров
            const wallet = walletsData[walletIndex];
            let totalValue = 0;

            for (const [network, data] of Object.entries(wallet.networks)) {
                if (enabledNetworks.has(network)) {
                    for (const token of data.tokens) {
                        if (token.value >= minBalance) {
                            totalValue += token.value;
                        }
                    }
                }
            }

            return totalValue;
        }

        // Функция копирования адреса в буфер обмена
        async function copyAddress(fullAddress, element) {
            try {
                // Останавливаем всплытие события, чтобы не раскрывались детали
                event.stopPropagation();

                // Копируем в буфер обмена
                await navigator.clipboard.writeText(fullAddress);

                // Показываем попап
                showCopyPopup();

                // Анимация кнопки
                element.style.transform = 'scale(0.95)';
                element.style.background = '#d5e8d4';

                setTimeout(() => {
                    element.style.transform = '';
                    element.style.background = '';
                }, 150);

            } catch (err) {
                // Фоллбек для старых браузеров
                try {
                    const textArea = document.createElement('textarea');
                    textArea.value = fullAddress;
                    textArea.style.position = 'fixed';
                    textArea.style.left = '-999999px';
                    textArea.style.top = '-999999px';
                    document.body.appendChild(textArea);
                    textArea.focus();
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);

                    showCopyPopup();

                } catch (fallbackErr) {
                    console.error('Не удалось скопировать адрес:', fallbackErr);
                    showCopyPopup('Ошибка копирования');
                }
            }
        }

        // Функция показа попапа
        function showCopyPopup(message = 'Адрес скопирован в буфер обмена!') {
            const popup = document.getElementById('copyPopup');
            popup.textContent = message;
            popup.classList.add('show');

            // Автоматически скрываем через 2 секунды
            setTimeout(() => {
                popup.classList.remove('show');
            }, 2000);
        }

        function toggleFilters() {
            const content = document.getElementById('filtersContent');
            content.classList.toggle('show');
        }

        function updateNetworkFilter(network, isEnabled) {
            if (isEnabled) {
                enabledNetworks.add(network);
            } else {
                enabledNetworks.delete(network);
            }

            // Обновляем визуальное состояние чекбокса
            const checkbox = document.querySelector(`[data-network="${network}"]`);
            if (checkbox) {
                checkbox.classList.toggle('checked', isEnabled);
            }
        }

        function updateMinBalance(value) {
            minBalance = parseFloat(value) || 0;
        }

        function applyFilters() {
            let visibleWallets = 0;
            let totalFilteredValue = 0;
            let visibleNetworks = new Set();
            let visibleTokens = 0;

            // Перебираем все кошельки
            walletsData.forEach((wallet, walletIndex) => {
                let walletValue = 0;
                let hasVisibleTokens = false;
                const walletRow = document.querySelector(`[data-wallet-index="${walletIndex}"].wallet-row`);
                const detailsRow = document.querySelector(`[data-wallet-index="${walletIndex}"].details-row`);

                // Обновляем отображение сетей в строке кошелька
                const networksCell = document.querySelector(`[data-wallet-index="${walletIndex}"].networks-cell`);
                const networkItems = networksCell.querySelectorAll('.network-item');

                networkItems.forEach(item => {
                    const network = item.dataset.network;
                    const networkValue = parseFloat(item.dataset.value);

                    if (enabledNetworks.has(network)) {
                        item.classList.remove('filtered');
                        visibleNetworks.add(network);

                        // Пересчитываем значение с учетом минимального баланса токенов
                        let networkFilteredValue = 0;
                        const networkSection = document.querySelector(`[data-wallet-index="${walletIndex}"] .network-section[data-network="${network}"]`);
                        if (networkSection) {
                            const tokens = networkSection.querySelectorAll('.token-item');
                            tokens.forEach(token => {
                                const tokenValue = parseFloat(token.dataset.value);
                                if (tokenValue >= minBalance) {
                                    token.classList.remove('filtered');
                                    networkFilteredValue += tokenValue;
                                    visibleTokens++;
                                    hasVisibleTokens = true;
                                } else {
                                    token.classList.add('filtered');
                                }
                            });

                            // Обновляем отображение стоимости сети
                            const networkTotal = networkSection.querySelector('.network-total');
                            if (networkTotal) {
                                networkTotal.textContent = `($${networkFilteredValue.toFixed(2)})`;
                            }

                            // Обновляем значение в network-item с сохранением структуры
                            const img = item.querySelector('img');
                            const imgSrc = img ? img.src : getChainLogo(network);
                            const imgAlt = img ? img.alt : network;

                            item.innerHTML = `
                                <img src="${imgSrc}" alt="${imgAlt}" class="network-logo">
                                ${network.toUpperCase()} $${networkFilteredValue.toFixed(2)}
                            `;

                            if (networkFilteredValue === 0) {
                                networkSection.classList.add('filtered');
                                item.classList.add('filtered');
                            } else {
                                networkSection.classList.remove('filtered');
                                walletValue += networkFilteredValue;
                            }
                        }
                    } else {
                        item.classList.add('filtered');
                        // Скрываем секцию сети в деталях
                        const networkSection = document.querySelector(`[data-wallet-index="${walletIndex}"] .network-section[data-network="${network}"]`);
                        if (networkSection) {
                            networkSection.classList.add('filtered');
                        }
                    }
                });

                // Обновляем общую стоимость кошелька (обязательно со знаком $)
                const totalValueElement = document.querySelector(`[data-wallet-index="${walletIndex}"].total-value`);
                if (totalValueElement) {
                    const formattedValue = walletValue > 0 ? `$${walletValue.toFixed(2)}` : '$0.00';
                    totalValueElement.textContent = formattedValue;
                }

                // Показываем/скрываем строку кошелька
                if (hasVisibleTokens && walletValue > 0) {
                    walletRow.classList.remove('hidden');
                    visibleWallets++;
                    totalFilteredValue += walletValue;
                } else {
                    walletRow.classList.add('hidden');
                    detailsRow.classList.add('hidden');
                }
            });

            // Обновляем статистику
            document.getElementById('walletsCount').textContent = visibleWallets;
            document.getElementById('totalValue').textContent = `$${totalFilteredValue.toFixed(2)}`;
            document.getElementById('networksCount').textContent = visibleNetworks.size;
            document.getElementById('tokensCount').textContent = visibleTokens;

            // Применяем сортировку после фильтрации
            if (currentSort !== 'none') {
                applySorting();
            }
        }

        function toggleDetails(rowId) {
            const detailsRow = document.getElementById(rowId);
            const btnId = rowId.replace('details-', 'btn-');
            const btn = document.getElementById(btnId);

            if (detailsRow.style.display === 'none') {
                detailsRow.style.display = 'table-row';
                btn.textContent = '▼';
                btn.style.transform = 'rotate(0deg)';
            } else {
                detailsRow.style.display = 'none';
                btn.textContent = '▶';
                btn.style.transform = 'rotate(0deg)';
            }
        }

        // Инициализация при загрузке страницы
        document.addEventListener('DOMContentLoaded', function() {
            // Анимация появления строк
            const rows = document.querySelectorAll('.wallet-row');
            rows.forEach((row, index) => {
                row.style.opacity = '0';
                row.style.transform = 'translateY(20px)';
                setTimeout(() => {
                    row.style.transition = 'all 0.5s ease';
                    row.style.opacity = '1';
                    row.style.transform = 'translateY(0)';
                }, index * 100);
            });

            // Инициализация состояния чекбоксов
            document.querySelectorAll('.network-checkbox').forEach(checkbox => {
                const network = checkbox.dataset.network;
                const input = checkbox.querySelector('input[type="checkbox"]');
                if (input.checked) {
                    checkbox.classList.add('checked');
                    enabledNetworks.add(network);
                }
            });

            // Сохраняем оригинальный порядок строк
            const tbody = document.querySelector('.wallets-table tbody');
            originalOrder = Array.from(tbody.children).map((row, index) => ({
                element: row,
                originalIndex: index
            }));

            // НЕ применяем фильтры при загрузке, чтобы сохранить исходные значения
        });
    </script>
</body>
</html>
        """)

        # Подсчет статистики
        total_value = sum(wallet["total_value"] for wallet in wallets_data)
        total_networks = len(
            set(
                network
                for wallet in wallets_data
                for network in wallet["networks"].keys()
            )
        )
        total_tokens = sum(
            len(data["tokens"])
            for wallet in wallets_data
            for data in wallet["networks"].values()
        )

        return template.render(
            wallets_data=wallets_data,
            total_value=total_value,
            total_networks=total_networks,
            total_tokens=total_tokens,
            all_networks=all_networks,
            get_chain_logo=self.get_chain_logo,
        )

    async def process_addresses_file(self, file_path="addr.txt"):
        """Обработка файла с адресами"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                addresses = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"❌ Файл {file_path} не найден!")
            return []

        if not addresses:
            print("❌ Файл с адресами пуст!")
            return []

        print(f"📋 Найдено {len(addresses)} адресов для обработки")
        print("=" * 50)

        wallets_data = []

        for i, address in enumerate(addresses, 1):
            print(f"\n🔍 [{i}/{len(addresses)}] Обрабатываю адрес: {address}")
            tokens_data = await self.get_wallet_data(address)

            if not tokens_data:
                print(f"\n🔍 [{i}/{len(addresses)}] Первый раз, нужен другой запрос")
                self.get_first_wallet_data(address)
                print(
                    f"\n🔍 [{i}/{len(addresses)}] Спим 5 сек и получаем филтрованные токены"
                )
                time.sleep(5)
                tokens_data = await self.get_wallet_data(address)

            wallet_info = self.process_wallet_data(address, tokens_data)
            wallets_data.append(wallet_info)

            # Показываем промежуточную статистику
            if tokens_data:
                print(
                    f"💰 Найдено токенов: {len(tokens_data)}, общая стоимость: ${wallet_info['total_value']:.2f}"
                )
            else:
                print("💔 Токены не найдены")

            # Небольшая задержка между запросами
            if i < len(addresses):
                await asyncio.sleep(1)

        print("\n" + "=" * 50)
        print(f"✅ Обработка завершена: {len(addresses)} адресов")
        return wallets_data


async def main():
    print("🚀 Запуск Crypto Balance Analyzer")
    print("=" * 50)

    async with CryptoBalanceAnalyzer() as analyzer:
        # Обработка всех адресов
        wallets_data = await analyzer.process_addresses_file()

        if not wallets_data:
            print("❌ Нет данных для обработки")
            return

        print("\n📊 Генерация HTML дашборда...")

        # Генерация HTML
        html_content = analyzer.generate_html(wallets_data)

        # Сохранение в файл
        output_file = "wallets_dashboard.html"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(html_content)

        # Финальная статистика
        total_value = sum(wallet["total_value"] for wallet in wallets_data)
        wallets_with_tokens = sum(
            1 for wallet in wallets_data if wallet["total_value"] > 0
        )

        print("\n" + "=" * 50)
        print("🎉 РЕЗУЛЬТАТЫ:")
        print(f"✅ HTML дашборд сохранен в файл: {output_file}")
        print(f"📊 Обработано кошельков: {len(wallets_data)}")
        print(f"💰 Кошельков с токенами: {wallets_with_tokens}")
        print(f"💵 Общая стоимость: ${total_value:.2f}")
        if analyzer.proxies:
            print(f"🔗 Использовано прокси: {len(analyzer.proxies)}")
        print(f"🌐 Откройте файл {output_file} в браузере для просмотра")
        print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
