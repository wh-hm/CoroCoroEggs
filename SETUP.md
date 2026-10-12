## 授業が始まったら一番最初に行うこと

## 1. SQLite Viewerをインストール
VSCodeの拡張機能を開き「SQLite Viewer」をインストールする

## 2. 必要なライブラリをインストール
python -m pip install "uvicorn[standard]" fastapi

## 3. インストールできたか確認

python -m pip show uvicorn
Name: uvicorn と表示されればOKです。


## 4. FastAPIを起動

python -m uvicorn main:app --reload

成功すると、次のような表示が出ます。
INFO:     Uvicorn running on http://127.0.0.1:8000


## 5. テスト画面を開く

webサイトが問題なく表示されたらOK！