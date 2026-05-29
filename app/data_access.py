"""
app/data_access.py — データ取得の抽象レイヤー。

正本: docs/ai-ecosystem-tool-spec.md §17.2

設計方針:
  - DATA_SOURCE=local : DATA_DIR (または data/) から直接ファイルを読む。
  - DATA_SOURCE=gcs   : GCS SDK 経由で読む (MVP では未配線 / interface stub として定義)。
    スケールアップ時に実装する。呼び出すと NotImplementedError を送出する。
  - 秘密情報 (API key / SA key / GCS bucket 名以外の認証情報) は扱わない。
  - パストラバーサル防止は呼び出し元 (urban_viewer_server) が実施済み。

Cloud Run Job との関係 (§17.1):
  同一 image を `tools/urban_simulation_cli.py` をエントリポイントとして差し替えることで
  Cloud Run Service / Job を兼用する。Job はこのモジュールを直接使用しない。

識別子は英語 / コメントは日本語。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator


# ─────────────────────────────────────────────────────────────────────────────
# ローカル実装
# ─────────────────────────────────────────────────────────────────────────────

class LocalDataAccess:
    """data/ ディレクトリからファイルを読み取るローカル実装。

    DATA_SOURCE=local 時にこのクラスを使用する。
    DATA_DIR 環境変数が設定されていればそのパスを優先する。
    """

    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir

    @property
    def data_dir(self) -> Path:
        """データルートディレクトリ。"""
        return self._data_dir

    def run_file_path(self, run_id: str, filename: str) -> Path:
        """run_id / filename のファイルパスを返す。存在確認は行わない。"""
        return self._data_dir / run_id / filename

    def read_bytes(self, run_id: str, filename: str) -> bytes:
        """ファイルを bytes で読み返す。存在しない場合は FileNotFoundError。"""
        path = self.run_file_path(run_id, filename)
        return path.read_bytes()

    def stream_lines(self, run_id: str, filename: str) -> Iterator[str]:
        """JSONL ファイルを 1 行ずつ yield する。"""
        path = self.run_file_path(run_id, filename)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped:
                    yield stripped + "\n"


# ─────────────────────────────────────────────────────────────────────────────
# GCS 実装 (MVP 未配線 / スケール用 interface stub)
# ─────────────────────────────────────────────────────────────────────────────

class GcsDataAccess:
    """GCS バケットからファイルを取得するスタブ実装。

    NOTE (MVP 未配線):
      本クラスは interface stub であり、MVP では未実装です。
      スケールアップ時に google-cloud-storage SDK を使って実装します。
      DATA_SOURCE=gcs を設定しても現在は NotImplementedError が送出されます。
      GCS バケット: gs://nexus-ai-2045-urban-data/runs/<run_id>/ (§17.2)
    """

    def __init__(self, bucket_name: str) -> None:
        # GCS バケット名。実装時に google.cloud.storage.Client を初期化する。
        self._bucket_name = bucket_name

    def read_bytes(self, run_id: str, filename: str) -> bytes:
        """GCS からファイルを bytes で読み取る (未実装)。"""
        raise NotImplementedError(
            "GcsDataAccess.read_bytes は MVP 未配線です。"
            f" bucket={self._bucket_name} run_id={run_id} file={filename}"
        )

    def stream_lines(self, run_id: str, filename: str) -> Iterator[str]:
        """GCS から JSONL を 1 行ずつ yield する (未実装)。"""
        raise NotImplementedError(
            "GcsDataAccess.stream_lines は MVP 未配線です。"
            f" bucket={self._bucket_name} run_id={run_id} file={filename}"
        )
        # yield を持たないと Iterator 型が成立しないため unreachable だが明示する
        yield  # type: ignore[misc]


# ─────────────────────────────────────────────────────────────────────────────
# ファクトリ
# ─────────────────────────────────────────────────────────────────────────────

def make_data_access(data_source: str, data_dir: Path) -> LocalDataAccess | GcsDataAccess:
    """DATA_SOURCE に応じたデータアクセスオブジェクトを返す。

    Args:
        data_source: 'local' または 'gcs'。
        data_dir: ローカルデータルートディレクトリ (local 時のみ使用)。

    Returns:
        LocalDataAccess (data_source='local') または GcsDataAccess (data_source='gcs')。

    Raises:
        ValueError: data_source が 'local' / 'gcs' 以外の場合。
    """
    if data_source == "local":
        return LocalDataAccess(data_dir)
    if data_source == "gcs":
        # GCS バケット名は固定 (§17.2)。認証は Application Default Credentials 経由。
        return GcsDataAccess(bucket_name="nexus-ai-2045-urban-data")
    raise ValueError(f"unknown DATA_SOURCE: {data_source!r}. 'local' か 'gcs' を指定してください。")
