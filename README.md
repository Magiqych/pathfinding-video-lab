# pathfinding-video-lab

経路探索アルゴリズムの可視化動画を、オフラインで安定して生成するための Python プロジェクトです。

このリポジトリでは、処理の流れを次のように分離しています。

**algorithm → event sequence → timeline → render plan → audio timeline → export**

アルゴリズム本体はイベント列のみを出力し、描画はレンダラー、音声はオーディオ生成、最終的な動画化と一時ファイル整理はエクスポーターが担当します。

---

## プロジェクト概要

主な特徴:

- BFS の探索過程を動画として可視化可能
- 共有タイムラインから映像と音声を同期生成
- Shorts 向け縦動画と横長動画の両方に対応しやすい設計
- 将来的な 4K 長尺書き出しを見据えた profile ベース構成
- レンダリング、音声、エクスポート責務の明確な分離

想定する今後の対応アルゴリズム:

- BFS
- DFS
- Dijkstra
- A*
- Greedy Best-First Search
- そのほか比較用アルゴリズム

---

## セットアップ手順

### 1. Windows PowerShell で仮想環境を作成

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

PowerShell のポリシーで有効化できない場合は、必要に応じて次を実行してください。

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

### 2. 依存関係インストール手順

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

## FFmpeg の準備

最終的な MP4 出力には FFmpeg が必要です。リポジトリ内には同梱していないため、各自でインストールし、PATH が通っている状態にしてください。

確認コマンド:

```powershell
ffmpeg -version
```

---

## 実行例

### テストを実行

```powershell
pytest
```

### BFS の Shorts 向け縦動画を出力

```powershell
python -m src.app --algorithm bfs --scenario open_demo --export --export-profile shorts_vertical
```

### HD 横長動画を出力

```powershell
python -m src.app --algorithm bfs --scenario maze_demo --export --export-profile hd_landscape
```

### 4K 向けプロファイルで実行

```powershell
python -m src.app --algorithm bfs --scenario maze_demo --export --export-profile uhd_4k_landscape --layout-profile 4k_landscape
```

### グリッドサイズを上書き

```powershell
python -m src.app --algorithm bfs --scenario open_demo --export-profile shorts_vertical --grid-cols 16 --grid-rows 24
```

---

## export profile の説明

組み込み済みの export profile:

- **shorts_vertical**: 1080 × 1920
- **hd_landscape**: 1920 × 1080
- **uhd_4k_landscape**: 3840 × 2160

各 profile では、以下をまとめて定義します。

- 出力解像度
- FPS
- 映像コーデック設定
- 音声コーデック設定
- 既定のレイアウト
- 一時フレームの保持方針
- エクスポートモード

同じアルゴリズムのイベント列を、Shorts 用・通常動画用・将来の 4K 用へ再利用できる点が利点です。

---

## grid size の説明

グリッド密度は出力解像度とは独立して指定できます。

主な設定:

- **grid_cols**: 列数
- **grid_rows**: 行数
- **layout viewport**: 実際にグリッドを描く領域
- **cell size**: viewport と grid size から自動計算されるセルサイズ

つまり、同じ 1080×1920 出力でも、12×20 と 16×24 では見た目の密度だけを変えられます。

---

## Shorts向けと将来の4K長尺向け設計方針

### Shorts 向け方針

- 9:16 の縦長レイアウトを優先
- 上下のテキストバーはデフォルトで無効
- グリッドをほぼ全画面に配置
- テンポよく視認しやすいアニメーション

### 将来の 4K 長尺向け方針

- profile を切り替えるだけで高解像度対応可能
- frame_sequence モードでデバッグしやすい
- stream_to_ffmpeg モードを将来最適化しやすい構造
- 長時間出力時の I/O やメモリ効率改善を見据えた責務分離

---

## 出力ファイルの保存先

通常、生成物は以下に保存されます。

- **output/frames/**: 番号付き PNG フレーム列
- **output/videos/**: 最終 MP4 と、必要時に残される一時 WAV

ファイル名には実行条件が含まれるため、複数条件での書き出しを比較しやすくなっています。

---

## 一時ファイルの扱い

- 音声が有効な場合、WAV はこれまで通り生成されます
- **MP4 の mux が成功した場合は、一時 WAV を自動削除**します
- **成功時は、output/frames 配下の当該フレームディレクトリも自動削除**します
- **mux が失敗した場合は、デバッグ用に WAV とフレームを保持**します
- フレームを残したい場合は、既存の frame 保持設定や CLI オプションを利用できます

---

## レイアウトと出力モード

### layout profile

- **shorts_vertical**
- **standard_landscape**
- **4k_landscape**

### export mode

- **frame_sequence**: PNG フレーム列を書き出すデバッグしやすい方式
- **stream_to_ffmpeg**: 将来の長尺・高解像度最適化のための拡張ポイント

---

## 今後の実装予定

1. BFS 以外のアルゴリズム実装拡充
2. イベントモデルの強化
3. シナリオ生成の多様化
4. 4K 長尺書き出し時のパフォーマンス最適化
5. 複数アルゴリズムの比較表示
6. より高度な音響・演出の追加

---

## 開発メモ

- Python 3.11+
- src レイアウト
- 型ヒントを利用
- pytest による基本検証あり
- FFmpeg ベースのオフライン MP4 生成
- レンダラーとアルゴリズムを疎結合に維持
