import base64
import json
import os
import sqlite3
from typing import Any, Dict, Optional
from openai import OpenAI
import streamlit as st

DB_FILE = "badminton_club.db"


def init_db() -> None:
    """Khởi tạo các bảng dữ liệu cho hệ thống."""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS members (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT CHECK(type IN ('Cố định', 'Vãng lai')),
            phone TEXT
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            court_fee REAL DEFAULT 0,
            shuttle_fee REAL DEFAULT 0,
            party_fee REAL DEFAULT 0,
            total_income REAL DEFAULT 0,
            note TEXT
        )
    """
    )

    c.execute(
        """
        CREATE TABLE IF NOT EXISTS member_payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER,
            member_name TEXT,
            member_type TEXT,
            amount_due REAL,
            amount_paid REAL DEFAULT 0,
            status TEXT CHECK(status IN ('Đã trả', 'Còn nợ')),
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """
    )

    conn.commit()
    conn.close()


def get_openai_client(api_key_input: Optional[str] = None) -> Optional[OpenAI]:
    """Tự động ưu tiên lấy API Key từ Streamlit Secrets hoặc biến môi trường,

    nếu không có sẽ dùng API Key người dùng nhập ở giao diện.
    """
    # 1. Kiểm tra Secrets trên Streamlit Cloud
    if hasattr(st, "secrets") and "OPENAI_API_KEY" in st.secrets:
        return OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

    # 2. Kiểm tra biến môi trường
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return OpenAI(api_key=env_key)

    # 3. Dùng API Key nhập tay từ giao diện
    if api_key_input:
        return OpenAI(api_key=api_key_input)

    return None


def process_bill_image(client: OpenAI, image_bytes: bytes) -> Dict[str, Any]:
    """Phân tích ảnh hóa đơn bằng GPT-4o Vision."""
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    prompt = """
    Hãy phân tích hình ảnh hóa đơn này và trả về kết quả dưới dạng JSON duy nhất với cấu trúc:
    {
        "category": "Tên khoản chi (Tiền sân / Tiền cầu / Tiền ăn uống)",
        "amount": số_tiền_chính_xác_dạng_số,
        "note": "Mô tả ngắn gọn nội dung hóa đơn"
    }
    Chỉ trả về JSON, không thêm văn bản khác.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        },
                    },
                ],
            }
        ],
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def process_voice_input(client: OpenAI, audio_file: Any) -> Dict[str, Any]:
    """Chuyển giọng nói thành dữ liệu thu chi bằng Whisper."""
    transcription = client.audio.transcriptions.create(
        model="whisper-1", file=audio_file, language="vi"
    )
    text = transcription.text

    prompt = f"""
    Trích xuất dữ liệu từ câu nói sau về buổi tập cầu lông: "{text}"
    Trả về định dạng JSON duy nhất với cấu trúc:
    {{
        "court_fee": số tiền sân (hoặc 0),
        "shuttle_fee": số tiền cầu (hoặc 0),
        "party_fee": số tiền ăn uống/nước (hoặc 0),
        "fixed_members": ["Tên hội viên cố định 1", "Tên hội viên cố định 2"],
        "casual_members": ["Tên khách vãng lai 1"],
        "note": "Tóm tắt ngắn gọn"
    }}
    Chỉ trả về JSON.
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    result = json.loads(response.choices[0].message.content)
    result["raw_text"] = text
    return result