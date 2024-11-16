from intdash import ApiClient, Configuration
from intdash.api import authentication_service_edges_api

# APIトークンで認証
client = ApiClient(
    Configuration(
        host="https://example.intdash.jp/api",
        api_key={"IntdashToken": "YOUR_API_TOKEN"},
    )
)

# エッジサービスのAPIオブジェクトを生成
api = authentication_service_edges_api.AuthenticationServiceEdgesApi(client)

# エッジ一覧の取得
edges = api.list_edges()
print(edges)
