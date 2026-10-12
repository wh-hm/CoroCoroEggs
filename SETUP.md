#授業が始まったら一番最初に行うこと

① 必要なライブラリをインストール
python -m pip install "uvicorn[standard]" fastapi


インストールが完了するまで待ってください。
② インストールできたか確認
python -m pip show uvicorn


Name: uvicorn と表示されればOKです。
③ FastAPIを起動
python -m uvicorn main:app --reload


成功すると、次のような表示が出ます。
INFO:     Uvicorn running on http://127.0.0.1:8000


④ テスト画面を開く
ブラウザで次のURLを開いてください。