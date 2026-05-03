# English Expression Extractors PRD

## 1. Product Summary

English Expression Extractors は、YouTube / podcast / news / interview などの英語 transcript を、ユーザー専用の「使える英語表現データベース」に変換する学習ツールである。

ジェネラルな単語帳ではなく、特にビジネスシーン、さらに言えばスタートアップ経営やベンチャーキャピタル業界などの文脈でそのまま再利用できる英語表現の塊を抽出し、日本語訳・ニュアンス・型・自分用例文・タグまで含むカードとして保存するツールである。

初期実装は CLI を前提とし、旧 `lab/english-expressions-extractor` の学びを取り込み、`tools/phrasify` 配下で継続利用できる tool として運用する。

## 2. Problem

一定レベルを超えた英語学習者にとって、高みを目指す勉強方法にシルバーブレットはない。
最近ではYoutubeやPodcastなどで、実際にシリコンバレーで活躍するビジネスパーソンのリアルな英語コンテンツから知的刺刺激を得ることは実務上重要になりつつある。そのため、よくある学習教材の長文コンテンツを読んだり聞いたりするのではなく、実際のユースケースに近い学習資産として、特に VC / startup / business 文脈で実務で自然に使える表現・言い回し・発話フレームを蓄積することが重要である。

現状の課題:

- transcript は素材として残るが、復習可能な表現カードになっていない
- 単語抽出に寄ると、実務で口から出せる表現になりにくい
- 上級者向けの仕事に最適化された学習教材がない
- 元文・日本語訳・ニュアンス・応用例文が分断される
- 複数コンテンツをまたいだ重複排除・頻度集約が手作業になる

## 3. Target User

Primary user:

- 私自身
- 日本語ネイティブで、英語を VC / startup / finance / MBA / interview / business discussion で使いたいユーザー
- CEFR B2 以上を想定し、基礎単語ではなく、自然な英語運用力を上げたい
- 長文 podcast / YouTube / news / interview transcript を継続的に学習素材化したい

Secondary users:

- 英語 transcript を社内・個人の学習 DB に変換したい knowledge worker
- Notion / Anki / Obsidian などで復習システムを作りたいユーザー

## 4. Goals

MVP goals:

- 主要フロー
  - `txt` / `md` / `srt` / `vtt` transcript を入力できる
  - transcript を cleaning / chunking し、LLM に渡せる単位へ分割する
  - 単語ではなく、実務で再利用できる expression を抽出する
  - 各 expression に日本語訳・ニュアンス・用法・自分用例文・タグを付与する
  - 重複 expression を正規化・dedup する
  - JSONL のいずれかで出力できる
- その他機能
  - Notion 連携または Notion handoff JSON を生成できる
  - CLI で 1 ファイルを処理できる
  - 頻度・有用性・自分の業務文脈に基づく priority scoring

Longer-term goals:

- Notion DB / Anki / Obsidian への安定した export
- Review queue と学習ステータス管理
- Phrase Pattern Generator による「表現の型」化

## 5. Non-Goals

MVP では以下を扱わない:

- 音声・動画からの transcription 本体
- 完全な学習 UI
- SRS アルゴリズムの実装
- 翻訳品質の人手レビュー workflow
- 全 Vault / 全 Clips の自動巡回

## 6. Input

Supported input:

- Markdown transcript
- Plain text transcript
- SRT subtitle file
- VTT subtitle file

Expected source types:

- YouTube transcript
- Podcast transcript
- News / article transcript
- Interview transcript
- VC / startup / business discussion content

MVP assumption:

- 基本入力は `md` ファイル
- 既存 Knowledge clip と相性がよい形式を優先する

## 7. Output Schema

1 expression あたり最低限以下を持つ:

```json
{
  "expression": "double down on",
  "original_sentence": "We decided to double down on the enterprise segment.",
  "jp_translation": "エンタープライズ領域にさらに注力することにした。",
  "nuance": "単に続けるのではなく、確信を持って追加投資・注力するニュアンス。",
  "usage": "投資判断、事業戦略、リソース配分の文脈で使う。",
  "pattern": "double down on + noun / initiative / segment",
  "reusable_examples": [
    "We should double down on founder-led sales before scaling paid acquisition.",
    "The fund doubled down on AI infrastructure after seeing early customer pull."
  ],
  "tags": ["business_collocation", "strategy", "vc_startup"],
  "source": {
    "file": "example.md",
    "timestamp": "00:12:34",
    "chunk_id": "example-003"
  },
  "scores": {
    "usefulness": 0.9,
    "source_confidence": 0.95
  }
}
```

MVP required fields:

- `expression`
- `original_sentence`
- `jp_translation`
- `usage`
- `reusable_examples`
- `tags`
- `source`


Recommended fields:

- `pattern`
- `source`
- `extracted_at`
- `review_status`

## 8. Extraction Criteria

抽出対象は、単語ではなく「発話でそのまま使える塊」を優先する。

Core Criteria

- 会議で使える表現
- 意見を述べる表現
- 反論・留保表現
- 要約・整理表現
- 交渉・提案表現
- ニュース理解に使える表現
- VC / startup / business context の表現
- カジュアルなネイティブ表現
- 高頻度の句動詞
- コロケーション
- 決まり文句
- 便利な接続表現

## 9. Core Workflow

MVP workflow:

```text
Transcript Input
  -> Cleaning
  -> Chunking
  -> Expression Candidate Extraction
  -> Expression Classification
  -> Deduplication
  -> Validation
  -> Card Generation
  -> JSONL / CSV / Notion handoff Export
```
