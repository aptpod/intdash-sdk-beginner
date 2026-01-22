import base64
import json
import logging
from typing import Dict

from const.const import MODEL
from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam


class Chatter:
    """
    生成AI問い合わせ

    Attributes:
        client (OpenAI): OpenAIクライアント
        system_prompt (string): システムプロンプト
    """

    def __init__(self, api_key: str, system_prompt: str) -> None:
        self.client = OpenAI(api_key=api_key)
        self.system_prompt = system_prompt

    def chat(self, image: bytes) -> Dict:
        """
        OpenAI API呼び出し

        プロンプトを構成して、chat.completionを呼び出す。
        - JPEGデータ

        Params:
            image (bytes): JPEGデータ

        Returns:
            Dict: 要約結果
        """
        image_b64 = base64.b64encode(image).decode("utf-8")
        messages: list[ChatCompletionMessageParam] = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"},
                    },
                ],
            },
        ]
        resp = self.client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=400,
            temperature=0.3,
            response_format={"type": "json_object"},
        )

        answer = resp.choices[0].message.content
        logging.info(f"Summary response： {answer}")
        if not answer:
            raise Exception("chat.completions responses None!")
        try:
            answer_json = json.loads(answer)
        except json.JSONDecodeError:
            raise Exception(f"json load error: {json}")

        return answer_json
