# Windows 

## 前提
- Windows では Gstreamer の Python バインディング PyGObject のサポートが不完全でインストールやビルドが難しい。
  - PyGObject は gobject-introspection や glib などの C ライブラリに依存しており、Windows での環境構築は煩雑。
  - Meson / Ninja / pkg-config に加え、Visual Studio C++ Build Tools などのセットアップが必要だが、これらがうまく連携せずにビルドが失敗する。
- そのため、WSL2（Windows Subsystem for Linux 2）上に Ubuntu 環境を建てて開発を行う。
- 開発環境として VS Code を使用する場合、**VS Code のリモート開発機能（Remote - WSL 拡張）**を使うことで、Ubuntu 上のファイルをそのまま編集・実行できる。
  - 開発環境VS Codeはリモート開発プロジェクトとしてUbuntu内のサンプルプログラムを参照・実行する
  - ただし、ローカルの Windows 環境より操作・動作が遅い。

## インストール

### Ubuntu 22.04 インストール

### Java インストール

### Node.js インストール
### npm インストール

### WSL 拡張機能インストール
VS Code の Remote - WSL 拡張機能をインストールすると、ローカルとほぼ同じ感覚で Linux 側の開発ができる。
GUI アプリケーション（GTKなど）を表示するには、VcXsrv や GWSL などの X サーバが別途必要。
