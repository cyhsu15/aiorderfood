"""
聊天模組自定義例外類別

提供明確的例外類型，便於精確的錯誤處理和診斷。
"""


class ChatServiceError(Exception):
    """聊天服務基礎例外類別"""
    pass


class DatabaseConnectionError(ChatServiceError):
    """
    資料庫連接錯誤

    當無法連接到資料庫或資料庫 session 未正確初始化時拋出。

    範例:
        >>> if not db:
        ...     raise DatabaseConnectionError("資料庫 session 未初始化")
    """
    pass


class AIServiceError(ChatServiceError):
    """
    AI 服務錯誤

    當 OpenAI API、Whisper 模型或其他 AI 服務發生錯誤時拋出。

    範例:
        >>> try:
        ...     llm.invoke(prompt)
        ... except Exception as e:
        ...     raise AIServiceError(f"OpenAI API 調用失敗: {e}")
    """
    pass


class WhisperServiceError(AIServiceError):
    """
    Whisper 語音辨識服務錯誤

    當 Whisper 模型未安裝或語音轉文字失敗時拋出。
    繼承自 AIServiceError，因為 Whisper 是 AI 服務的一部分。

    範例:
        >>> if whisper is None:
        ...     raise WhisperServiceError("Whisper 未安裝")
    """
    pass


class ValidationError(ChatServiceError):
    """
    資料驗證錯誤

    當輸入資料格式不正確或不符合預期時拋出。
    注意：此類別與 Pydantic 的 ValidationError 不同。

    範例:
        >>> if not dish_name:
        ...     raise ValidationError("菜品名稱不能為空")
    """
    pass
