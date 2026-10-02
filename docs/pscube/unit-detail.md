# PScube個別台JSONと回転数推定

## 2026-10-01に確認したtitle alias

| 内部キー | 表示名 |
| --- | --- |
| toku1-count-s | BIG |
| toku5-count-s | REG |
| toku1-ratio-s | BIG確率 |
| toku5-ratio-s | REG確率 |
| toku0-ratio-s | 合成確率 |
| sadama_s-s | 最大出玉 |

表示名と内部キーを同じ意味へ正規化します。両方の併記も重複としてエラーにします。未知titleは推測で分類しません。

0272 / 2026-10-01のBIG=25、REG=26、分母252.4/242.7/123.8、最大出玉1769から、既存推定は6311G（候補なし・spread=3.8）です。逆算値6310.0/6310.2/6313.8の平均6311.333…を丸めたフォールバックで、実測Gではありません。最大出玉は差枚に転記しません。

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
