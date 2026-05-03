# English Expression Extractors PRD

## 1. Product Summary

English Expression Extractors は、YouTube / podcast / news / interview などの英語 transcript を、ユーザー専用の「使える英語表現データベース」に変換する学習ツールである。

ジェネラルな単語帳ではなく、特にビジネスシーン、さらに言えばスタートアップ経営やベンチャーキャピタル業界などの文脈でそのまま再利用できる英語表現の塊を抽出し、日本語訳・ニュアンス・型・自分用例文・タグまで含むカードとして保存するツールである。

初期実装は CLI を前提とし、現在は standalone OSS repo として運用する。

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
- 外部ナレッジベース全体の自動巡回

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
- Markdown note と相性がよい形式を優先する

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

## 99. Open Source Readiness

Phrasify は単体 OSS repo として公開・運用する。公開 repo では、ユーザーが任意の transcript をローカルCLIで処理し、JSONL / CSV / Notion handoff へ変換できる状態を canonical とする。

公開 repo には汎用 CLI / tests / examples / skills / docs のみを置き、実データ・API key・個人環境の運用情報は含めない。生成物は ignored `outputs/` に置けるが、公開 repo の tracked files には入れない。

推奨 positioning:

> Phrasify is a Japanese-first CLI that turns English transcripts into reusable business expression cards.

OSS としては、汎用の英語学習アプリではなく、以下の narrow wedge で出す。

- 日本語ネイティブ向け
- transcript-to-expression-card CLI
- business / startup / VC English に強い
- JSONL / CSV / Notion / Anki などへつなげやすい local-first tool
- LLM provider はユーザーが自分の API key で選ぶ

### 99.1 Repository Separation Checklist

- [x] standalone repo として切り出す
- [x] repo 名を `phrasify` に決める
- [x] standalone remote を作成し、`main` を push する
- [x] 親プロジェクト固有の path を README / code / tests から削除する
- [x] 親プロジェクトの `.env` fallback を削除し、公開 repo では `.env` / environment variables のみにする
- [x] 親プロジェクト固有の registry / metadata 前提を公開 repo に持ち込まない
- [x] `phrasify.design-spec.md` は v0.1.0 では root に残す。公開後に docs が増えたら `docs/design-spec.md` への移動を再判断する
- [x] `outputs/` の実データを公開 repo に含めない
- [x] `outputs/.gitkeep` のみ残すか、出力例は `examples/` に匿名化して置く

### 99.2 Privacy / Data Handling Checklist

- [x] transcript が LLM provider API に送信されることを README に明記する
- [x] どのデータがローカル保存されるかを README に明記する
- [x] API key は environment variable でのみ読む設計にする
- [x] `.env.example` を追加し、実キーを含む `.env` は `.gitignore` に入れる
- [x] sample transcript / sample output は個人情報・著作権上の懸念がない素材に差し替える
- [x] Notion handoff payload に個人の DB ID や data source ID を直書きしない
- [x] Notion / Anki export では外部書き込みが明示 opt-in であることを保証する

### 99.3 Product / Documentation Checklist

- [x] 日本語 README を first-class にする
- [x] 英語 README を追加するか、README の下部に short English section を置く
- [x] 30 秒で価値が分かる usage example を README 冒頭に置く
- [x] 入力形式（`.md`, `.txt`, `.srt`, `.vtt`）を明記する
- [x] 出力 schema の例を README に載せる
- [x] `extract`, `export`, `aggregate` のコマンド例を整える
- [x] `--provider`, `--model`, `--max-expressions`, `--notion-handoff` の説明を足す
- [x] quality metrics（`expression_in_source`, `original_sentence_in_source`）の意味を説明する
- [x] FAQ を追加する（例: "Anki に入れられる?", "transcript はどこに送られる?", "日本語以外でも使える?"）

### 99.4 Packaging / Distribution Checklist

- [x] `pyproject.toml` の metadata を OSS 向けに整える
- [x] license を決める（候補: MIT or Apache-2.0）
- [x] `LICENSE` を追加する
- [x] `CHANGELOG.md` を追加する
- [x] `CONTRIBUTING.md` を追加するか、README に最小限の contribution guide を置く
- [x] `CODE_OF_CONDUCT.md` が必要か判断する（v0.1.0 では未追加。外部 contributor を積極募集する段階で再判断）
- [x] `pip install -e .` で動くことを確認する
- [x] `phrasify` console script が動くことを確認する
- [x] GitHub Actions で unit tests を回す
- [x] Python version support を明記する（現状は `>=3.11`）
- [x] Claude Code / Codex 向けに `skills/phrasify/SKILL.md` を同梱する
- [x] README に skill install 手順を追加する
- [x] `MANIFEST.in` で skill / examples / prompt を sdist に含める

### 99.5 Code Quality Checklist

- [x] `src/phrasify` layout を維持する
- [x] core logic は LLM provider 非依存に保つ
- [x] LLM adapter は OpenAI / Anthropic で分離し、provider 追加を容易にする
- [x] prompt は `src/phrasify/prompts/` に置き、将来的に user override 可能にする
- [x] file loader / cleaning / chunking / schema / export の unit tests を維持する
- [x] LLM API を叩かない fixture-based test を追加する
- [x] malformed JSON / empty transcript / unsupported extension の error path をテストする
- [ ] CSV export の multiline field が spreadsheet で崩れないか確認する
- [x] aggregate の dedup rule を README に明記し、test coverage を維持する

### 99.6 Roadmap Before Public Announcement

- [ ] `v0.1.0` として CLI extraction を安定化する
- [x] CSV export を README の primary flow に入れる
- [ ] `--format anki-csv` を追加するか、Anki import 用 CSV recipe を README に書く
- [x] Notion handoff から個人 DB 依存を外す
- [x] example transcript + expected output を追加する
- [x] 最小 GitHub Actions workflow を追加する
- [x] issue template を追加する
- [ ] 最初の 3 つの "good first issue" を切る

### 99.7 Do Not Open Source Until

- [x] 実 API key / 個人 Notion ID / 個人 transcript が repo に含まれていない
- [x] 個人の絶対パスへの依存が public code path から消えている
- [x] README だけで third party user が dry-run / sample extraction まで到達できる
- [x] tests が fresh clone で通る
- [x] license が明示されている
- [x] transcript の外部送信に関する privacy note がある
- [x] private / generated files は `.gitignore` で tracked files から除外されている
- [x] `scripts/oss_check.py` で公開前に個人パス・実キー・既知の private Notion ID を検出できる
- [x] GitHub Actions で `oss_check.py` と unit tests を両方実行する
