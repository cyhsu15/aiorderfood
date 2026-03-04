"""
Chat API 路由：提供聊天推薦與語音辨識功能
"""
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.modules.menu.menu import fetch_menu
from .service import process_chat_request, transcribe_audio
from .exceptions import DatabaseConnectionError, AIServiceError, WhisperServiceError
import opencc
from loguru import logger
logger.add('ChatAPI.log')
logger.info('Start...')

router = APIRouter()

converter = opencc.OpenCC('s2twp.json')

# 環境變數：是否為 debug 模式
DEBUG = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")

# ----------------------
# Pydantic Schemas
# ----------------------

class RecommendationItem(BaseModel):
    """推薦項目"""
    name: str = Field(..., description="菜品名稱")
    reason: str = Field(..., description="推薦理由")
    image_url: Optional[str] = Field(None, description="菜品圖片 URL，可能為 None")
    id: Optional[int] = Field(None, description="菜品 ID（用於購物車）")
    dish_id: Optional[int] = Field(None, description="菜品 ID（向後兼容）")
    price: Optional[float] = Field(None, description="價格，可能為 None 或 0.0")
    size: Optional[str] = Field(None, description="份量標籤，可能為 None")
    price_id: Optional[int] = Field(None, description="價格 ID（dish_price 主鍵，用於下單與 forecast 查詢）")
    forecast_6d: Optional[list] = Field(None, description="未來6天預測（若有）")
    forecast_status: Optional[str] = Field(None, description="forecast 是否可用：ok / missing / stale")


class ChatResponse(BaseModel):
    """聊天回應"""
    message: str = Field(..., description="助理回覆訊息")
    recommendations: List[RecommendationItem] = Field(default_factory=list, description="推薦菜品清單")


class ChatMessage(BaseModel):
    """對話訊息"""
    role: str = Field(..., description="角色：user 或 assistant")
    content: str = Field(..., description="訊息內容")


class ChatRequest(BaseModel):
    """聊天請求"""
    message: str = Field(..., description="使用者訊息")
    context: List[ChatMessage] = Field(default_factory=list, description="對話歷史")


class TranscriptionResponse(BaseModel):
    """語音轉文字回應"""
    text: str = Field(..., description="轉換後的文字")
    language: str = Field(..., description="偵測到的語言")


# ----------------------
# API Endpoints
# ----------------------

@router.post("/chat", response_model=ChatResponse)
def api_chat(payload: ChatRequest, db: Session = Depends(get_db)):
    """
    聊天推薦 API

    根據使用者的訊息與對話歷史，提供個性化的菜品推薦。
    """
    try:
        # 獲取最新菜單
        menu = fetch_menu(db)

        # 轉換 context 為 dict 格式
        context_dicts = [{"role": msg.role, "content": msg.content} for msg in payload.context]

        # 處理聊天請求
        result = process_chat_request(
            message=payload.message,
            context=context_dicts,
            menu=menu,
            db=db
        )

        # 驗證並返回結果
        try:
            logger.info(f"返回結果: {result}")
            return ChatResponse.parse_obj(result)
        except ValidationError as e:
            # Pydantic 驗證失敗
            if DEBUG:
                logger.error(f"Pydantic 驗證失敗: {e}")
                logger.error(f"原始數據: {result}")
            else:
                logger.error(
                    f"Pydantic 驗證失敗: {type(e).__name__}",
                    extra={
                        "error_count": len(e.errors()),
                        "fields": [err["loc"] for err in e.errors()]
                    }
                )

            # 如果驗證失敗，返回簡化版本
            return ChatResponse(
                message=result.get('message', '抱歉，我無法正確處理您的請求'),
                recommendations=[]
            )

    except DatabaseConnectionError as e:
        logger.error(f"資料庫連接錯誤: {e}")
        raise HTTPException(
            status_code=503,
            detail="資料庫服務暫時無法使用，請稍後再試"
        )

    except AIServiceError as e:
        logger.error(f"AI 服務錯誤: {e}")
        raise HTTPException(
            status_code=503,
            detail="AI 服務暫時無法使用，請稍後再試"
        )

    except Exception as e:
        logger.error(f"Exception: {e}", exc_info=True)

        # 生產環境中隱藏詳細錯誤訊息
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"聊天請求失敗: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="系統處理請求時發生錯誤，請稍後再試")


@router.post("/chat/transcribe", response_model=TranscriptionResponse)
async def api_transcribe(file: UploadFile = File(...)):
    """
    語音轉文字 API

    使用 Whisper 模型將音訊檔案轉換為文字。
    支援格式：webm, mp3, wav, m4a 等。
    """
    logger.debug('進入語音轉文字 API')
    try:
        # 讀取上傳的檔案
        audio_bytes = await file.read()
        logger.info(f'音訊檔案大小: {len(audio_bytes)} bytes')
        if not audio_bytes or len(audio_bytes) < 2000:
            raise HTTPException(status_code=400, detail="音訊檔案太小或為空")
        
        # 調用 Whisper 轉換
        result = transcribe_audio(audio_bytes, file.filename or "audio.webm")
        logger.info(f'transcription zh: {result}')
        result['text'] = converter.convert(result['text'])
        logger.info(f'transcription zh-tw: {result}')
        return TranscriptionResponse(**result)

    except WhisperServiceError as e:
        logger.error(f"Whisper 服務錯誤: {e}")
        raise HTTPException(
            status_code=503,
            detail="語音辨識服務暫時無法使用"
        )

    except Exception as e:
        logger.error(f"Exception: {e}", exc_info=True)

        # 生產環境中隱藏詳細錯誤訊息
        if DEBUG:
            raise HTTPException(status_code=500, detail=f"語音轉文字失敗: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="語音轉文字處理失敗，請稍後再試")