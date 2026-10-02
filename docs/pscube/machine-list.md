# PScube機種一覧XHR取得

ユーザーが実通信で確認した仕様：GET `nc-m03-001.php`、Content-Typeは
`application/json`。パラメータは`cd_ps=2`、`bai=0`、`YMD_biz=`、`page=1`、`loaded=`。
トップレベルに`YMD_biz / PS / Ki / count / page / pageMax`があり、
`Ki`が機種一覧、各機種の`list.cd_dai`が先頭ゼロ付き台番号一覧です。

```powershell
python -m jobs.inspect_pscube_machines "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v03-001.php?cd_ps=2"
python -m jobs.inspect_pscube_machines "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v03-001.php?cd_ps=2" --save-json
python -m jobs.inspect_pscube_machines --help
```

有効化していない場合は`python`を`.\.venv\Scripts\python.exe`等に置き換えてください。
通常ページをGETしてから、同じSessionでXHRをpage=1からpageMaxまで逐次取得します。
各呼び出し間は`REQUEST_INTERVAL`、timeoutは`REQUEST_TIMEOUT`を使用します。
手動Cookie注入や認証回避は行いません。HTTPエラー、JSONでない応答、必須フィールド不正で停止します。
出力はhost、営業日、サーバーのcount/pageMax、取得機種件数、各機種名・台数・台番号件数です。
2026-09-22 の実取得では、page 1=20機種/86台、page 2=20機種/23台、page 3=1機種/1台で、合計41機種/110台でした。トップレベルの`count=41`と取得機種件数が一致することを確認済みです。

`client.fetch_json()`はJSON decodeまで行い`JsonFetchResult`を返します。
`parser.parse_machine_page()`は通信せず`PscubeMachinePage`へ変換し、
`collector.collect_machines()`は`list[PscubeMachine]`を返します。
CLIは同じ`iter_machine_pages()`を使いページ情報も表示します。
`collectors/pscube/models.py`の対応：

| 元JSON | Python |
| --- | --- |
| YMD_biz | business_date |
| nmk_kisyu | machine_name |
| cd_ps | cd_ps |
| bai | rate |
| ct_dai | unit_count |
| list.cd_kisyu | machine_code |
| list.cd_dai | unit_numbers（文字列のまま保持） |
| mph | machine_path（取得しません） |

実装上の受け入れ規則（実レスポンス全パターンの確認済み仕様ではありません）：
保存済み実JSONで`YMD_biz`が8桁の整数（例：20260922）になることを確認し、対応しています。
文字列のYYYYMMDD / YYYY-MM-DD / YYYY/MM/DDも許容し、空はNone。
機種名とlist.cd_dai、トップレベルのKi/count/page/pageMaxは必須です。
その他のモデル項目は欠損をNoneとし、未知フィールド（PS/fg_new/mcd_kisyu/nm_ka/DIVA等）は変換しません。
数値項目は数値文字列も許容しますが、台番号を数値から補完することはしません。
空一覧はcount=0、page=1、pageMax=0または1を許容します。
要求と異なるpageや、途中で変わる営業日/count/pageMaxはエラーとします。

`--save-json`は各取得ページを`debug/pscube/`へUTC時刻・ランダム識別子・host・ページ番号で保存します。
ヘッダーやCookieは保存しません。JSON本文は未加工のため、共有前に内容を確認してください。
JSONは機種情報の解析前に保存するため、解析に失敗したページも調査できます。
JSON decode自体に失敗した応答は保存されません。失敗ログの`stage`と`error_type`で
設定・URL検証・初期ページ取得・XHR取得・保存・解析を区別し、HTTPエラー時はstatusも表示します。
例外本文やレスポンス本文はログに出しません。途中失敗でも保存済みファイルは残ります。
テスト用JSONは確認された構造を模した架空データです。実サイトにはテストからアクセスしません。
mph先・DBマッピングは未実装です。個別台取得は次のm06用CLIを使用します。
