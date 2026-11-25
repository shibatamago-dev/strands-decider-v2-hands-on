# 検証結果: Strands Decider v2 E2B を Gemini Decision 1 と同じ54問で試した

実行日: 2026-11-25（JST）。検証の設計とコードはこのリポジトリの README と `run_strands_54.py` を参照。

## まとめ

| 指標 | Strands v2 E2B（今回） | nexus-decision-4b（ボス） | Gemini Decision 1（前回） |
| --- | --- | --- | --- |
| 正解率 | **43/54（79.6%）** | 47/54（87.0%） | 53/54（98.1%） |
| カバレッジ（誤差5%以下で自動判断できる割合） | **28/54（51.9%）** | 43/54（79.6%） | （前回は未計測） |
| テキストのみ（設計書8問） | 8/8 | 7/8 | 8/8 |
| 画像46問 | 35/46 | 40/46 | 45/46 |

カバレッジの定義は nexus-decision-4b の著者の報告と同じ（全回答を確信度の高い順に並べ、誤差率が5%以下に収まる最大の prefix の割合）。

確信度の閾値ごとの内訳（今回）:

| 閾値 | 自動判断できる割合 | その誤差率 |
| --- | --- | --- |
| ≥0.5 | 46/54（85.2%） | 19.6% |
| ≥0.8 | 25/54（46.3%） | 4.0% |
| ≥0.9 | 19/54（35.2%） | 0.0% |
| ≥0.95 | 13/54（24.1%） | 0.0% |
| ≥0.99 | 1/54（1.9%） | 0.0% |

## 実行条件

| 項目 | 内容 |
| --- | --- |
| モデル | StrandsAgents/strands-decider-E2B-gemma4-v2-2611（HF、Apache-2.0） |
| ベース | google/gemma-4-E2B-it、bf16 10.3GB、マージ済みフルモデル |
| 温度 | 1.5456（`/health` の表示） |
| コンテキスト | 32,768（`/health` の表示、max_length） |
| 実行基盤 | Google Colab 無料 T4（Tesla T4 15,360MiB、Driver 580.82.07、CUDA 13.0、torch 2.14.1+cu130、Python 3.13.16） |
| 動かし方 | `strands-decider serve` で常駐し、`/v1/systemone` に POST。`ask` は使っていない（1問ごとに再ロードするため） |
| 質問と正解 | Gemini Decision 1 ハンズオンの `standalone_run.py` をそのまま import（11ケース・54問、判定ロジックも同一） |
| 実行時間 | 全54問で 26.5 秒。1ケースあたりのサーバーレイテンシは約 1.9〜2.5 秒（waldo だけ 5.7 秒） |
| ノートブック | https://colab.research.google.com/drive/1ICHDWPzMqeEChH0Zkkbxf6IP89gFEZZj |

## 画像は読めた（設計書の記述と異なる挙動）

公式の設計書（designs/images.md）には「Gemma 4 のモデルはベースモデルのテキストデコーダだけを読み込み vision encoder を落としているため、テキストのみ読む」とあります。一方で README には v2 E2B で画像を使う例が載っています。

実測では画像が読めました：

- `/health` は `"images": true` を返しました（`vision` キーは存在しません）。
- 画像1件・4問のプローブ（road-clean）は 4/4 正解でエラーなしでした。
- 全54問も画像46問込みで実行でき、35/46 が正解でした。

`--vision` 付きの再起動やテキストのみへの切り替えは不要でした。

## 誤りの内訳（11問）

| ケース | 質問 | 正解 | モデルの答え | 確信度 |
| --- | --- | --- | --- | --- |
| waldo | waldo_cell（9択の位置） | middle-right | middle-center | 0.0894 |
| waldo | is_in_top-right | False | True | 0.500 |
| waldo | is_in_middle-center | False | True | 0.5784 |
| waldo | is_in_bottom-center | False | True | 0.6033 |
| waldo | is_in_bottom-right | False | True | 0.5434 |
| bear/forest-bear.png | has_large_animal | True | False | 0.7248 |
| bear/forest-dog.png | has_large_animal | True | False | 0.8846 |
| realistic/bear-distant.jpg | has_bear | True | False | 0.5818 |
| realistic/bear-distant.jpg | has_large_animal | True | False | 0.596 |
| realistic/bear-distant.jpg | what_animal | bear | deer | 0.127 |
| realistic/dog.jpg | has_large_animal | True | False | 0.6783 |

読み取れること:

- **ウォーリーの位置当てが弱い**（5問）。9択の位置を middle-center と答えて外したほか、存在しないはずの場所に「いる」と答えた 4 問。ただし位置の 9 択は確信度 0.0894 と低く、閾値で人間に回す運用なら防げるタイプです。
- **遠くのクマ（bear-distant.jpg）に集中**（3問）。小さい被写体が苦手なのは nexus（同じく 3 問）と同じ傾向です。
- **has_large_animal の誤りが 3 件集中**（forest-bear、forest-dog、dog）。「大きな動物」の解釈で、イヌを「大きな動物」としないのは Gemini Decision 1 の唯一の誤りと同じ傾向です。
- score（5段階）は 10/10 で全問正解でした。

## ケース別

| ケース | 結果 |
| --- | --- |
| waldo（群衆から探す、10問） | 5/10 |
| design_doc（設計書、8問） | 8/8 |
| road/road-clean.png | 4/4 |
| road/road-luggage.png | 4/4 |
| bear/forest-none.png | 4/4 |
| bear/forest-bear.png | 3/4 |
| bear/forest-dog.png | 3/4 |
| realistic/bear-close.jpg | 4/4 |
| realistic/bear-distant.jpg | 1/4 |
| realistic/dog.jpg | 3/4 |
| realistic/empty.jpg | 4/4 |

種類別: choice 8/10、noul 25/34、score 10/10。

## v1 との比較（公式ベンチマークのみ）

v1 E2B は同じ Colab 環境で LoRA の読み込みに失敗したため、実測値はありません（torchao 0.10.0 に対して 0.16.0 以上を要求）。公式ベンチマーク（v2 モデルカード）の比較は次のとおりです。

| 指標 | v2 E2B | v1 E2B |
| --- | --- | --- |
| Decision Index | 57.1 | 29.3 |
| JevBench | 87.4 | 77.5 |
| OpenDecisions | 77.7 | 56.8 |
| DecisionPivot | 23.3 | 7.3 |
| BEV | 74.0 | 63.9 |
| H100 レイテンシ | 62ms/問 | 102ms/問 |

ただし Decision Index は v1 が 0.2.1、v2 が 0.3 とバージョンが違うため、単純な並び比べには注意が必要です。

## 生の結果ファイルについて

実行結果の生 JSON（`strands_54_results.json`、38.58K）は、Colab ランタイムのリサイクルで失われました。本ドキュメントの数値は、保存済みノートブックのセル出力（全54問の OK/MISS 行、SUMMARY 行、閾値表、ケース別集計）から転記したものです。生 JSON を復旧するには54問を再実行して Drive など永続的な場所へ保存し直す必要があります。

## 再現方法

```bash
# Colab（T4 GPU）で
pip install -q "strands-decider[cuda]"
git clone --depth 1 https://github.com/shibatamago-dev/gemini-decision-1-hands-on.git
# サーバ起動（バックグラウンド）
nohup strands-decider serve StrandsAgents/strands-decider-E2B-gemma4-v2-2611 --port 8000 > serve.log 2>&1 &
# 実行（54問の定義は gemini-decision-1-hands-on を隣に置く）
python3 run_strands_54.py
```

T4 が取れないときは中止してください。CPU ランタイムではモデルが載らず OOM になります。
