# slot-data-collectors

パチスロ台データを複数のWebデータソースから取得・解析・標準化するPython基盤です。

現在は **PScube の取得経路を実サイトで検証する段階まで進んでいます**。機種一覧XHR、個別台XHR、確率からの回転数推定、グラフ画像からの差枚推定プロトタイプを実装済みです。

2026-09-22 の実サイト検証では、1店舗について機種一覧 **41機種・110台** を全3ページから取得し、サーバーの `count=41` と一致することを確認しました。個別台では BIG / REG / 3種類の確率 / 最大出玉 / グラフ参照先を取得できています。

PScube の `SlotResult` への最終標準化、複数台・複数店舗の本番収集、Supabase書き込み、REITO収集処理は未実装です。確認できていないHTML構造やセレクタは推測で実装しません。

## 役割分担

| リポジトリ・サービス | 責務 |
| --- | --- |
| slot-data-collectors | Webからの取得・解析・標準化 |
| Supabase | データ保存・統合（将来の接続先） |
| Slot-Data-Analysis | データ分析 |
| Slot-Data-Analysis-web | Web画面・可視化 |
| Slot-Data-Analysis-DB | DB schema / migration / view / RPC管理 |

このリポジトリには分析・ランキング計算やDB書き込みを含めません。

## 構成

```text
collectors/
  __init__.py
  pscube/                  # client.py / parser.py / collector.py / inspect.py / models.py / __init__.py
  reitoweb/                # 同じ構成の未実装の骨格
common/
  __init__.py
  models.py                # dataclass SlotResultと値の検証
  normalize.py             # source固有データ → SlotResult（現時点では未実装）
  exceptions.py            # 取得・解析・標準化の例外
  logging_config.py        # JSON形式ログとURLのマスキング
jobs/
  __init__.py
  collect_pscube.py         # 通信しない設定・実装状態の確認用エントリーポイント
  inspect_pscube.py         # URLを1つ受け取る取得検証CLI
  inspect_pscube_machines.py # 機種一覧JSONの取得・検証CLI
  inspect_pscube_unit.py     # 個別台1台・4日分のJSONと回転数推定
  inspect_pscube_graph.py    # グラフ1枚の差枚推定・注釈画像
tests/
  __init__.py
  conftest.py              # テスト中の実HTTP通信を禁止
  test_models.py
  test_collectors.py
  test_inspection.py
  test_machines.py
  test_unit.py
  test_graph.py
  fixtures/               # 機密情報を除いたHTML fixtureの保存先
.env.example
.gitignore
requirements.txt
README.md
AGENTS.md               # Codex/AI開発エージェント向け作業規約
```

## Collectorの設計

```text
Web → client.fetch(url) → HTML → parser.parse(html)
    → source固有データ → normalize → SlotResult
```

- clientはHTTPのみを担当します。`requests.Session`による通常のCookie維持とセッション注入に対応します。所有するセッションはコンテキストマネージャーで閉じ、注入したセッションは呼び出し元が管理します。
- parserはレスポンス本文だけを解析し、通信しません。PScubeではHTML診断に加え、機種一覧JSON・個別台JSONを専用parserで解析します。
- normalizeはsource固有データを共通`SlotResult`へ変換する場所です。HTML/JSON解析はここに入れません。PScubeの最終マッピングはまだ未実装です。
- collectorはclientとparserを組み合わせます。PScubeでは機種一覧のページング収集まで実装済みです。今後、個別台を複数台へ展開して標準化層へ接続します。
- jobは設定読み込みと検証実行を担当します。`inspect_pscube*` 系CLIで、HTML・機種一覧・個別台・グラフを段階的に検証できます。`collect_pscube` の本番収集接続はまだ行いません。

`SlotResult`は台番号・営業日・sourceを必須とし、店舗ID・機種ID・名称・各集計値・URLは`None`を許容します。台番号は正の整数、game/bb/rbは0以上、medalは負数も許容します。boolや数値文字列は自動変換せず拒否します。営業日は`date`、取得時刻はタイムゾーン付き`datetime`で、既定はUTCです。sourceは固定列挙にせず、追加したソース名も保持します。

## 開発環境

Python 3.10以上を使用します。以下はリポジトリ直下で実行してください。
既存の`.venv`が動作する場合は作り直す必要はありません。

Windows PowerShell:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m jobs.collect_pscube --help
.\.venv\Scripts\python.exe -m jobs.collect_pscube
```

`.env`が既にある場合、コピーは省略してください。仮想環境を有効化する場合は
`.\.venv\Scripts\Activate.ps1`を実行し、以降は`python -m pytest`などを利用できます。
有効化しなくても上記の実行ファイル指定で動作します。

macOS / Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp -n .env.example .env
.venv/bin/python -m pytest
.venv/bin/python -m jobs.collect_pscube --help
```

既存の仮想環境が`No Python at ...`で起動しない場合は、作成元のPythonが利用できていません。
使用する仮想環境は`.venv`に統一します。起動できない`.venv`を削除してから、利用可能なPythonで上記の作成・インストール・テスト手順を実行してください。

## 環境変数と通信設定

jobはリポジトリ直下の`.env`を読み込みます。OSの環境変数を優先し、未設定・空欄は既定値を使います。

| 変数 | 既定値 | 内容 |
| --- | --- | --- |
| REQUEST_TIMEOUT | 15 | requestsのタイムアウト秒数（正の有限値） |
| REQUEST_INTERVAL | 1 | 前回リクエスト終了から次回開始までの最低間隔秒数（0以上の有限値） |

Python APIを直接使う場合は`PscubeClient(timeout=..., request_interval=...)`に渡してください。
User-Agentを設定し、逐次取得します。並列利用を想定していません。
リトライは既定で0回、`max_retries`で最大3回まで指定でき、接続エラー・タイムアウトだけを指数的な待機を挟んで再試行します。
HTTPエラー（401/403/429などを含む）は再試行しません。タイムアウトはジョブ全体の期限ではありません。

## テスト・ログ・機密情報

`python -m pytest`でモデル・HTTPモック・未実装境界・ログを検証します。実サイトへのアクセスはありません。
fixtureのHTMLは`tests/fixtures/`配下に置いてGit管理できます。一時HTML・debug・logs・`.env`・仮想環境は除外し、`.env.example`だけを共有します。

ログはloggingを使用し、source / URL / 成功・失敗 / 件数をJSON形式で記録します。
URLはoriginだけを残し、ユーザー情報・パス・クエリ・fragmentを削除します。
失敗時の件数は不明として`null`を記録します。例外本文・HTML・Cookie・ヘッダー・APIキー・DB接続文字列は記録しません。
`SlotResult.source_url`には元URLが入る想定のため、将来の保存・出力時には認証情報が含まれていないか確認が必要です。
fixtureにもCookie・トークン・個人情報や非公開データを含めないでください。

対象サイトの利用条件とアクセス可能な範囲を確認し、適切な間隔で取得します。
ログイン回避・認証突破・CAPTCHA回避・アクセス制御回避は実装しません。

## PScube取得検証

仮想環境を有効化し、リポジトリ直下で実行します。

```sh
python -m jobs.inspect_pscube "URL"
python -m jobs.inspect_pscube "URL" --save-html
python -m jobs.inspect_pscube --help
```

有効化しない場合はWindowsで`.\.venv\Scripts\python.exe`を`python`の代わりに使用できます。

このコマンドはPScubeのアクセス挙動を調査する検証ツールであり、アクセス制御回避や認証突破を目的としません。
`requests.Session`で指定URLへ通常のGETを行い、HTTPリダイレクトだけを追従します。
承認ボタン操作、form送信、meta refreshの追従、JavaScript実行、ブラウザ自動化は行いません。
環境変数のtimeout・通信間隔を使用し、検証CLIのリトライは0回です。
HTTPリダイレクト中の各通信はrequestsの通常動作に従い、`REQUEST_INTERVAL`は`fetch`呼び出し間の間隔です。

標準出力のJSONにrequested/final URL、HTTP status、Content-Type、本文サイズ（受信・展開後のバイト数）、
リダイレクトの有無、セッションおよびリダイレクト応答で確認したCookie名一覧、HTML診断を表示します。
安全のためURLはoriginのみを残し、パス・query・fragment・ユーザー情報を`[redacted]`に置き換えます。
同一host内の遷移先パスはこの出力からは特定できませんが、リダイレクトの有無は履歴から判定します。
ヘッダーはSet-Cookieを除外し、Content-Typeのメディア型以外の値は伏せて名前のみ確認できます。
Cookie値は通常のセッション内だけで扱い、FetchResult・ログ・レポートへコピーしません。
HTML本文は`FetchResult.html`で利用でき、オブジェクトのreprには含めません。

診断はtitle、meta refresh、form数、リンク数（href付きaタグ）、script数、iframe数、submit数、
password input、checkbox、承認/同意/確認/利用規約/agreement/consentの有無を抽出します。
submit数にはinputのsubmit/imageとtype省略またはsubmitのbuttonを含みます。
キーワードはscript/styleを除くテキストの部分一致で、承認画面を確定するものではありません。
通常ページにも「確認」などがあれば検出されます。

INFOログは標準エラーへ出力し、requested/final host・status・サイズを記録します。
HTTP 4xx/5xxでも診断・任意保存を行い終了コード1、400未満は0、設定・通信・保存失敗は1です。
既存の`PscubeClient.fetch()`は従来通りHTTPエラーを例外にし、検証用の`fetch_result()`だけがエラー応答も返します。

`--save-html`指定時だけ、リポジトリ直下の`debug/pscube/`へUTC timestampとhost名のファイル名で保存します。
例：`20260922_001500_123456_pscube_jp.html`。同時刻のファイルが既にある場合は連番を付け、上書きしません。保存はデコード後のHTMLをUTF-8で行います。
`debug/`はGit管理対象外です。HTML自体にはhidden inputやtoken等が含まれる可能性があり、
自動で完全に機密情報を除去するものではありません。ローカル調査用として扱い、共有やfixture化する前に内容を確認・除去してください。
titleも本文由来なので、JSONレポートを共有する前に確認してください。

実URLで次に確認する項目：HTTP statusと最終host、リダイレクト有無、Cookie名、
title・承認語句・meta refresh・formの有無、保存HTMLの文字化けやデータ表示の有無。
承認画面が出た場合はそこで観察に留め、このツールで操作しません。

## PScube機種一覧XHR取得

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

## PScube個別台JSONと回転数推定

```powershell
python -m jobs.inspect_pscube_unit "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v06-001.php?cd_dai=0272" --save-json
python -m jobs.inspect_pscube_unit --from-json "debug/pscube/保存した_unit.json"
python -m jobs.inspect_pscube_unit --help
```

仮想環境を有効化していない場合は`python`を`.\.venv\Scripts\python.exe`に置き換えます。
1回に1台だけ、個別台HTML→同じSessionでGET `nc-m06-001.php` の順に取得します。
通常HTMLのインラインscriptから`api.apikey`、`api.token = JSON.parse(...)`、`.show(台番号, 営業日, ...)`を読み取り、
`cd_dai / YMD_biz / apikey / _i / _t / page=1`を渡します。
この限定した文字列形式だけを解析し、JavaScriptを実行しません。構造が未対応・欠損なら`UnitRequestUnsupported`で停止します。
Cookieコピー・手動キー注入・CAPTCHA対応・アクセス制御回避はありません。
通常SessionのCookie維持、REQUEST_TIMEOUT / REQUEST_INTERVALを利用します。
履歴用page/pageMaxの巡回、他台の取得、Graph画像のダウンロードは行いません。

確認済みの区分：m03は機種一覧・ページング・台番号一覧、m06は個別台のBIG/REG/各確率/最大出玉とGraph画像URLです。
2026-09-22にa744207の0272について通常HTML→XHRの実取得を確認しました。
実m06の`Data`には`null`の空行があり、これをスキップします。
`Dai.cd_dai`は文字列のまま、`Ki.name / Ki.cd_kisyu`は機種名・コードとして保持します。
`Data.title`で対応する行を選び、itemの先頭4個を営業日・1日前・2日前・3日前へ対応させます。
false/null/空文字・短い配列の不足分はNone、ゼロ回は0として保持します。未知titleは無視し、重複titleや不正値はエラーです。
確率は数値・数値文字列・`1/193.5`等を分母のfloatに変換します。0の確率は利用不能としてNoneとします。
Graphは日付・title・src・legendを保持し、日付でdaily.graph_srcに対応させます。
legendは現時点で元JSONの形のまま保持します。CLIにはURL本体を出さず、存在有無だけを表示します。

回転数は直接値ではなく**推定値**です。BB×分母、RB×分母、(BB+RB)×合成分母のうち有効な組だけを使います。
0回の項目は除外し、BB/RBどちらか欠損の場合は合成も除外します。すべて無効ならestimated_gameはNoneです。
逆算平均をROUND_HALF_UPで整数化した中心の±20Gを探索し、各比率をDecimalのROUND_HALF_UPで小数1桁にした値が
表示分母と一致する整数を候補として保存します。候補が複数なら平均に最も近い値（同距離は大きい値）、
候補ゼロなら平均をROUND_HALF_UPで整数化します。spreadは有効な逆算値の最大−最小です。
サイトの丸め方式がROUND_HALF_UPであること自体は未確認で、候補は探索範囲内の整合性を示します。実測gameと同一視しません。
最大出玉は差枚ではなく、SlotResult.medalやgameへの自動転記はしません。

実取得した0272の保存JSONの再解析結果（当日は途中経過）：

| 営業日 | BIG | REG | 最大出玉 | estimated_game | 候補 | spread |
| --- | ---: | ---: | ---: | ---: | --- | ---: |
| 2026-09-22 | 0 | 1 | 105 | 309 | 309 | 0.0 |
| 2026-09-21 | 38 | 25 | 3715 | 7353 | 7352, 7353 | 0.9 |
| 2026-09-20 | 30 | 20 | 1488 | 6510 | 6509, 6510 | 0.0 |
| 2026-09-19 | 31 | 25 | 1324 | 7656 | 7656 | 2.0 |

`--save-json`は解析前のraw JSONだけをGit対象外のdebug/pscubeへ保存します。
ファイル名はUTC時刻・ランダム識別子・host・unitという固定語から作り、キーやqueryは含めません。
raw JSONのGraph src等に秘密値が含まれる可能性があるため、共有・fixture化前の確認が必要です。
HTMLやリクエストのキー・Cookieは保存・ログ出力しません。エラー時はstage・例外型・HTTP statusのみを記録します。
`--from-json`は外部通信せず再解析できます。

追加ファイル：`unit_parser.py`（純粋なJSON解析）、`unit_request.py`（通常HTMLの設定抽出）、
`estimation.py`（Decimal推定）、`jobs/inspect_pscube_unit.py`（CLI）、`tests/test_unit.py`と架空fixture。
ユーザー所有の`tests/test_pscube.py`はimport時に実通信する手動検証用のため、pytest収集から除外します。
同ファイルは変更・コミットしていません。pytestでは収集段階からHTTPを禁止しています。

個別台JSON用CLIは画像取得を行いません。画像による差枚推定は下記の検証用CLIを使用します。

## グラフ画像による差枚推定（検証用）

確認したm06 JSONには最終差枚の直接値がなく、Graph画像から推定します。
gameは3確率の整合性から小さい候補範囲へ復元できる一方、medalは画素・軸設定・終点検出による誤差を持ちます。
どちらも推定値で、本番運用・DB保存には使用していません。

Pillowだけを追加しました。`python -m pip install -r requirements.txt`で更新してください。

```powershell
# 1台・1日だけ通常HTML→JSON→画像を同じSessionで取得
python -m jobs.inspect_pscube_graph --unit 0272 --date 20260921 --unit-url "https://yasudaya.pscube.jp/h/a744207/cgi-bin/nc-v06-001.php?cd_dai=0272" --annotate
# 保存済み画像を通信せず解析
python -m jobs.inspect_pscube_graph --unit 0272 --date 20260921 --image "debug/pscube/graphs/20260921_0272.png" --annotate
```

通常ページのテンプレートで確認した`/h/<hall>/graph/{{>src}}`を使います。
画像GETには通常ページのRefererを付けます。今回、Refererなしでは403、通常のReferer付きでは取得できました。
Graph srcをCLIやログに表示しません。Cookieのコピー・認証回避・403再試行は行いません。
古いJSONの期限等が不明なため、ネットワークモードでは同一Sessionで最新の個別台JSONを取得してから1枚だけ取得します。
画像はPNGへ再保存し、`debug/pscube/graphs/YYYYMMDD_台番号.png`に保存します。同じ日・台の再取得は上書きします。
店舗をファイル名に含めないため、別店舗の同じ台番号・日付では衝突します。今回は1店舗の検証用です。

`collectors/pscube/graph.py`の`GraphProfile / GraphEstimate / fetch_graph / estimate_graph / annotate_graph`を追加しました。
中央領域で長く続く灰色の水平線を検出し、隣接行を集約します。長い縦軸から左端、水平線の端から右端を検出します。
plotの外側を上側・左側・下側のタイトル／軸ラベル領域として解析対象外にします（文字は認識しません）。
水平線間隔のばらつき6%以内を確認し、上下グリッド全体の高さを間隔数で割ってstep_pxを求めます。
ピンク系RGBの許容範囲で8近傍連結成分を抽出し、plot幅の15%以上にわたる成分だけを候補にします。
単一成分の最右端列のY中央値を終点として、`(zero_y-end_y)/step_px*step_medal`をROUND_HALF_UPで整数化します。

**軸の数値は幾何だけでは確定できません。** 初期プロファイルは上5000・下-1000・1000枚刻みの7本です。
0ラインはこの前提で下から2本目とします。`--top-medal / --bottom-medal / --step-medal`で変更できます。
軸ラベルや目視の+3200枚に合わせた自動補正は行いません。明るい主要線が想定ゼロ線と矛盾する場合は棄却します。
全7本・安定間隔・単一連結線・終点が右側85%以上ならhigh、途中終了ならmedium。
欠損グリッド・複数の大きい線成分・縦方向のクリップ等ではlowかつestimated_medal=Noneです。
今回はグリッド補間を行いません。highは指定スケールが正しい前提での幾何検出の確からしさで、枚数精度の保証ではありません。

`--annotate`はplot矩形（水色）、グリッド（橙）、0ライン（緑）、終点（赤）を
`debug/pscube/graphs/annotated/YYYYMMDD_台番号.png`へ保存します。通常解析には不要です。
終了コードは推定成功0、検出不能2、取得・設定・読み込み失敗1です。

実画像検証：0272 / 2026-09-21、800×730、plot=(79,20,780,676)。
grid Y=[20,129,238,348,457,567,676]、zero_y=567、step_px=109.3333、終点=(779,211)。
estimated_medal=**+3256枚**、confidence=high（既定スケールの前提あり）。1pxは約9.15枚に相当します。

同一台・同一日の外部値との初期比較では、**みんレポ +3250枚 / アナスロ +3245枚 / PScube画像推定 +3256枚** でした。差はみんレポ比+6枚、アナスロ比+11枚で、この1件では良好です。ただし1サンプルのため、置換判断には複数台・複数差枚レンジでの誤差分布検証が必要です。

外部画像をGitに入れず、テストではPillowで架空の正差枚・負差枚・ノイズ・欠損・異なる画像サイズを生成します。
残課題は軸レンジ変更の識別、線切れ・別配色・複数線・途中経過・端でのクリップへの対応、複数実例と既知差枚による精度評価です。次の検証では、みんレポ・アナスロ等と同一台同一日で比較し、MAE・中央値・最大誤差・±25/50/100/200枚以内率などを算出します。
OCR・機械学習・一括取得・並列取得・Supabase保存は追加していません。

## データソース追加と今後

同じシステムを使う店舗は同じcollectorを共有し、店舗ごとのURLやIDは呼び出し側の設定として扱います。
PScube、REITO、その他のソースは`collectors/<source>/`でHTTP・解析・収集を分離し、共通の`SlotResult`へ変換します。
現時点では汎用基底クラスやプラグイン基盤を導入していません。

1. 許可された実際のPScube HTMLを機密情報除去済みfixtureとして用意する。
2. 店舗・機種・台番号・営業日・game/bb/rb/medalの意味、欠損表記、文字コード、必要な通常セッション操作を確認する。
3. parserとnormalizeをfixtureと期待値で実装・検証し、jobを収集用に接続する。
4. REITOの実HTMLを確認し、同じ責務分離で追加する。

今回の対象外：SupabaseへのINSERT/UPDATE、DB変更、Materialized View更新、GitHub Actions、Playwright/Selenium、並列大量アクセス、みんレポ既存コードの移植、分析ロジック。
