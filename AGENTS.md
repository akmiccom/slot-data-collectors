# AGENTS.md

このファイルは `slot-data-collectors` で作業する Codex / AI コーディングエージェント向けの実装規約です。
README.md は人向けの仕様・使い方、AGENTS.md はエージェント向けの作業ルールとして扱ってください。

## 1. リポジトリの目的

このリポジトリの責務は、複数のWebデータソースからパチスロ台データを **取得・解析・標準化** することです。

- `slot-data-collectors`: Web取得・source固有解析・標準化
- Supabase: 保存・統合（将来接続）
- `Slot-Data-Analysis`: 分析
- `Slot-Data-Analysis-web`: 表示・可視化
- `Slot-Data-Analysis-DB`: schema / migration / view / RPC

このリポジトリにランキング、設定推測、店舗分析、Materialized View更新などの分析ロジックを追加しないでください。

## 2. 現在の実装状態

PScubeについて以下は実装・実サイト確認済みです。

- 通常ページを `requests.Session` で取得
- 機種一覧XHR `nc-m03-001.php` のJSON取得
- `page / pageMax` による逐次ページング
- `Ki` から機種名、機種コード、台数、先頭ゼロ付き台番号一覧を解析
- 2026-09-22の検証で全3ページ、41機種・110台を取得し `count=41` と一致
- 個別台XHR `nc-m06-001.php` のJSON取得
- BIG / REG / BIG確率 / REG確率 / 合成確率 / 最大出玉 / Graph参照先を解析
- 3種類の確率から `estimated_game` を復元
- Graph PNGからグリッド、0ライン、折れ線終点を検出し `estimated_medal` を推定するプロトタイプ
- 0272 / 2026-09-21で `estimated_medal=+3256`、比較値はみんレポ+3250、アナスロ+3245

未実装・未確定：

- PScube全台の本番一括収集
- `SlotResult` への最終normalize
- Supabase INSERT/UPDATE
- REITO本実装
- GitHub Actions本番収集
- 差枚推定の大量精度検証と軸レンジ自動判別

## 3. 最重要の設計原則

sourceごとに取得実装を分離し、共通化は取得後に行います。

```text
Web
  ↓
client       HTTPのみ
  ↓
parser       HTML/JSON → source固有モデル。通信禁止
  ↓
collector    client + parser のオーケストレーション
  ↓
normalize    source固有モデル → SlotResult
```

PScube固有処理を `common/` に漏らさないでください。
店舗ごとのスクレイパーも作らず、同じサイトシステムは同じcollectorを共有します。

## 4. Codex利用量を抑える作業ルール

ユーザーはCodexのレート制限を避けたいので、不要な探索・再調査をしないでください。

1. **README.md と AGENTS.md を最初に読む。** 既に確認済みの仕様を再発見するための広範囲な調査をしない。
2. **タスクに関係するファイルだけ先に読む。** 原則としてリポジトリ全体を総当たりで読まない。
3. 既存実装がある場合は新規フレームワークや大規模リファクタを提案せず、最小差分で進める。
4. 1タスクは原則1コミット相当の大きさにする。
5. テストはまず変更箇所に近いものを実行し、コミット前に `python -m pytest` を1回実行する。
6. 同じ失敗コマンドを理由なく何度も繰り返さない。
7. 確認済み仕様と矛盾する場合だけ、追加調査を行う。
8. 作業完了後の説明は短くし、変更ファイル・テスト・残課題・commit hashを中心に報告する。

## 5. PScubeで確認済みの通信仕様

### m03: 機種一覧

- GET `nc-m03-001.php`
- JSON
- 主なquery: `cd_ps`, `bai`, `YMD_biz`, `page`, `loaded`
- トップレベル: `YMD_biz / PS / Ki / count / page / pageMax`
- `Ki[].list.cd_dai` は台番号文字列。先頭ゼロを保持すること

2026-09-22実測：

- page 1: 20機種 / 86台
- page 2: 20機種 / 23台
- page 3: 1機種 / 1台
- 合計: 41機種 / 110台
- `count=41`

### m06: 個別台

通常の個別台HTMLを取得し、そこから通常ページ動作に必要な値を読み取った後、同一Sessionで `nc-m06-001.php` をGETします。

確認済みquery項目には `cd_dai`, `YMD_biz`, `apikey`, `_i`, `_t`, `page` があります。
秘密値はコード、fixture、ログ、README、AGENTS.mdへ保存しないでください。

確認済みData title:

- BIG
- REG
- BIG確率
- REG確率
- 合成確率
- 最大出玉

item先頭4要素は営業日、1日前、2日前、3日前に対応します。

## 6. 回転数推定

直接のgameがないため、以下から復元します。

```text
g_bb       = BB * BB確率分母
g_rb       = RB * REG確率分母
g_combined = (BB + RB) * 合成確率分母
```

有効な値の平均近傍で整数Gを探索し、Decimal `ROUND_HALF_UP` で小数1桁に丸めた際に表示確率を再現する候補を保持します。

- 候補1件 → その値
- 候補複数 → 逆算平均に最も近い値
- 候補0件 → 平均をROUND_HALF_UP
- 0回の項目はその確率式を使わない
- `estimated_game` は推定値。実測値扱いしない

実例：0272

| 日付 | BIG | REG | estimated_game | candidates |
| --- | ---: | ---: | ---: | --- |
| 2026-09-22 | 0 | 1 | 309 | 309 |
| 2026-09-21 | 38 | 25 | 7353 | 7352, 7353 |
| 2026-09-20 | 30 | 20 | 6510 | 6509, 6510 |
| 2026-09-19 | 31 | 25 | 7656 | 7656 |

## 7. 差枚推定

JSONの「最大出玉」は差枚ではありません。`SlotResult.medal`へ直接転記しないでください。

現在はGraph PNGから推定します。

```text
zero_y, step_px, end_y
→ (zero_y - end_y) / step_px * step_medal
```

初期プロファイルは上5000、下-1000、1000枚刻みです。軸レンジは常に同一とは限らないため、固定前提を本番仕様に昇格させないでください。

初期検証：0272 / 2026-09-21

- PScube画像推定: +3256
- みんレポ: +3250
- アナスロ: +3245

この1件だけでは精度保証しません。今後は同一台・同一日で多数比較し、少なくともMAE、中央値、最大誤差、±25/50/100/200枚以内率を評価してください。

## 8. セキュリティ・アクセス

禁止：

- Cookie値のハードコード・ログ出力・fixture保存
- APIキー、token、`cf_clearance` 等の秘密値の保存・共有
- CAPTCHA回避
- ログイン・認証・アクセス制御の回避
- 403/429に対する回避実装
- 並列大量アクセス
- 不要な高頻度アクセス

許可される通常動作の `requests.Session`、通常ページから取得できる設定値、Referer等だけを使用します。

HTTPエラー時は秘密情報やレスポンス本文をログへ出さず、stage / exception type / status程度に留めてください。

## 9. テスト規約

- pytestから実サイトへアクセスしない
- `tests/conftest.py` の通信禁止を維持する
- fixtureは架空または機密情報除去済みにする
- 外部サイトの画像を原則Gitへ入れない
- 画像処理テストはPillowで生成したfixtureを優先
- 既存テストを壊した場合、仕様変更なのか回帰なのかを先に判定する

変更後の基本確認：

```powershell
python -m pytest
```

CLIを変更した場合：

```powershell
python -m jobs.<target> --help
```

## 10. コーディング方針

- Python 3.10+
- 型ヒントを付ける
- source固有モデルはdataclassを優先
- `print`ではなく`logging`。ただしCLIの結果JSON等、既存方針に合わせた標準出力は可
- parser内でHTTPしない
- client内で業務解析しない
- boolをintとして誤受理しない
- 台番号は文字列で保持し先頭ゼロを失わない
- 不明な値を推測で補完しない
- 未対応構造は黙って誤変換せず明示的な例外またはNoneにする
- 過度な抽象化、不要な基底クラス、不要な依存追加を避ける

## 11. Git / コミット

ユーザーから別指示がない限り、実装・テスト成功後はコミットまで行って構いません。

コミット前：

- `git status`
- `.env`, `debug/`, `.venv/`, secretsが追跡されていないこと
- `python -m pytest` 成功
- 必要なCLI `--help` 成功

原則として今回変更したファイルだけをstageしてください。
push、merge、branch削除は明示指示がない限り行わないでください。

コミットメッセージは変更内容に対応する短いConventional Commit形式を優先します。

例：

```text
feat: add PScube unit batch validation
fix: handle missing PScube graph rows
refactor: isolate PScube normalization
```

## 12. 仕様記録とコードの同期

- READMEは概要・使い方、docsは詳細仕様、AGENTSはAI作業規約として扱う。
- 実サイトで新しい通信仕様・JSONフィールド・軸レンジ・配色を確認した場合、実装変更と同じコミットで[docs/pscube](docs/pscube/overview.md)の該当仕様を更新する。
- XHR URL/query、parser/field mapping、estimated_game、GraphProfile/線検出、normalize、source優先順位を変更した場合は関連docsを確認する。影響がなければ編集は不要。
- 確認済み事実と推測を区別し、1例の仕様を常に成立するものと一般化しない。
- グラフ解析では誤推定よりNoneを優先し、既存の確認済み実例を回帰ケースとして維持する。
- 軸と配色の確認例・制約は[グラフ解析](docs/pscube/graph-estimation.md)、実例は[検証記録](docs/pscube/validation.md)へ記録する。
- 複数台検証CLIは台選択を必須とし逐次取得する。403/429では以後の取得を停止し、成功済みCSV行・手入力比較値を保持する。本番collectorへの統合とは区別する。

## 13. 次に優先する作業

現時点の優先順位は以下です。

1. PScube差枚推定を複数台で検証する
2. みんレポ・アナスロ等との同一台同一日比較をCSV等で集計する
3. 軸レンジ違い・負差枚・0付近・大幅プラス・途中経過を検証する
4. 精度が十分なら複数台の逐次収集へ拡張する
5. PScube source固有モデル → `SlotResult` normalizeを設計する
6. その後にSupabase統合方針を検討する
7. REITOはPScubeと分離した `collectors/reitoweb/` で実装する

依頼されていない先の工程まで一度に実装しないでください。
