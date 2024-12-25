import json
import logging

import requests


class Notifier:
    """
    Slack通知

    Attributes:
        api_url (str): 接続するAPIのURL
        slack_url (str): 通知するSlackのIncoming Webhook URL
        project_uuid (str): プロジェクトUUID
    """

    def __init__(self, api_url: str, slack_url: str, project_uuid: str) -> None:
        self.api_url = api_url
        self.slack_url = slack_url
        self.project_uuid = project_uuid

    def notify(self, meas_uuid: str) -> None:
        """
        通知

        Args:
            meas_uuid (str): 計測UUID
        """
        message = {
            "attachments": [
                {
                    "color": "#00bfff",
                    "author_name": "Distance Service",
                    "author_icon": "https://slack-imgs.com/?c=1&o1=wi32.he32.si&url=https%3A%2F%2Fintdash-fmm-map.s3.ap-northeast-1.amazonaws.com%2Fasset%2Fvm2m.png",
                    "title": "距離を算出しました",
                    "fields": [
                        {
                            "title": "計測",
                            "value": f"<{self.api_url}/console/measurements/{meas_uuid}/?projectUuid={self.project_uuid}|Meas Hub>",
                        },
                        {
                            "title": "プレイバック再生",
                            "value": f"<{self.api_url}/vm2m/?projectUuid={self.project_uuid}&screenName=Distance&playMode=storedData&measUuid={meas_uuid}|Data Visualizer>",
                        },
                    ],
                    "footer": "SDK入門⑥〜最速最高度で計測する日〜",
                    "footer_icon": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTkbv74KdmChO7FenKcskkqIZTIYEMjJSisLjZVk5_O7pe-QKEBb1Kntdx-grb7dvdsNDs&usqp=CAU",
                    "mrkdwn_in": ["text", "fields"],
                }
            ]
        }

        response = requests.post(
            self.slack_url,
            data=json.dumps(message),
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            logging.error(
                f"Failed to notify Code: {response.status_code}, Response: {response.text}"
            )
