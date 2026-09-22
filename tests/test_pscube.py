import requests
import re
import json

base = "https://yasudaya.pscube.jp/h/a744203/cgi-bin/"
unit_no = "0092"

s = requests.Session()
s.headers.update({
    "User-Agent": "Mozilla/5.0"
})

# 1. 個別台HTML取得
url = base + f"nc-v06-001.php?cd_dai={unit_no}"
p = s.get(url, timeout=20)
p.raise_for_status()

text = p.text

print("HTML status:", p.status_code)
print("HTML length:", len(text))

# 2. APIキー
m = re.search(r"api\.apikey\s*=\s*'([^']+)'", text)
if not m:
    raise RuntimeError("apikey が見つかりません")

apikey = m.group(1)

# 3. token
m = re.search(
    r"api\.token\s*=\s*JSON\.parse\('(.+?)'\)",
    text
)
if not m:
    raise RuntimeError("token が見つかりません")

token_raw = m.group(1)
token = json.loads(token_raw)

# 4. 営業日
m = re.search(
    rf"\.show\('{unit_no}',\s*'(\d{{8}})'",
    text
)
if not m:
    raise RuntimeError("YMD_biz が見つかりません")

ymd = m.group(1)

print("apikey:", apikey)
print("YMD_biz:", ymd)
print("token keys:", token.keys())

# 5. JSON API取得
params = {
    "cd_dai": unit_no,
    "YMD_biz": ymd,
    "apikey": apikey,
    "_i": token["_i"],
    "_t": token["_t"],
    "page": 1,
}

api_url = base + "nc-m06-001.php"

headers = {
    "User-Agent": "Mozilla/5.0",
    "X-Requested-With": "XMLHttpRequest",
    "Referer": url,
    "Accept": "application/json, text/javascript, */*; q=0.01",
}

r = s.get(
    api_url,
    params=params,
    headers=headers,
    timeout=20
)

print("API URL:")
print(r.url)
print()
print("API status:", r.status_code)
print("Content-Type:", r.headers.get("Content-Type"))
print("Content-Length:", r.headers.get("Content-Length"))
print("response bytes:", len(r.content))
print()
print(repr(r.text[:5000]))