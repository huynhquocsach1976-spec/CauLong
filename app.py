import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st
from main import (
    DB_FILE,
    get_openai_client,
    init_db,
    process_bill_image,
    process_voice_input,
)

# Khởi tạo DB khi ứng dụng chạy
init_db()

st.set_page_config(
    page_title="Quản Lý CLB Cầu Lông", layout="wide", page_icon="🏸"
)
st.title("🏸 Hệ Thống Quản Lý CLB Cầu Lông")

# Thanh điều hướng góc trái
with st.sidebar:
    st.header("⚙️ Cấu Hình & Tài Khoản")
    api_key = st.text_input("Nhập OpenAI API Key:", type="password")
    user_role = st.selectbox("Vai trò", ["Thủ Quỹ / Admin", "Thành Viên"])

if not api_key:
    st.info("💡 Vui lòng nhập OpenAI API Key ở thanh bên để kích hoạt tính năng AI.")

tabs = st.tabs(
    ["📝 Nhập Buổi Tập", "🧾 Quét Bill/Giọng Nói", "📊 Báo Cáo Lời/Lỗ & Công Nợ"]
)

# ------------------------------------------
# TAB 1: NHẬP BUỔI TẬP & ĐIỂM DANH
# ------------------------------------------
with tabs[0]:
    st.subheader("Tạo Buổi Tập Mới & Chia Phí Tự Động")

    col1, col2 = st.columns(2)
    with col1:
        session_date = st.date_input("Ngày tập", datetime.now())
        court_fee = st.number_input("Tiền thuê sân (VNĐ)", value=0, step=10000)
        shuttle_fee = st.number_input("Tiền mua cầu (VNĐ)", value=0, step=10000)
        party_fee = st.number_input(
            "Tiền nước / ăn uống (VNĐ)", value=0, step=10000
        )

    with col2:
        fixed_input = st.text_area(
            "Danh sách Cố định (Mỗi người 1 dòng)", "Nam\nBắc\nHải"
        )
        casual_input = st.text_area(
            "Danh sách Vãng lai (Mỗi người 1 dòng)", "Dũng\nTuấn"
        )

    total_expense = court_fee + shuttle_fee + party_fee
    st.markdown(f"**Tổng Chi Phí Buổi Tập:** `{total_expense:,.0f} VNĐ`")

    if st.button("Lưu & Tự Động Chia Phí", type="primary"):
        fixed_list = [x.strip() for x in fixed_input.split("\n") if x.strip()]
        casual_list = [
            x.strip() for x in casual_input.split("\n") if x.strip()
        ]
        total_people = len(fixed_list) + len(casual_list)

        if total_people == 0:
            st.error("Chưa có thành viên nào tham gia!")
        else:
            fee_per_person = total_expense / total_people

            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute(
                """
                INSERT INTO sessions (date, court_fee, shuttle_fee, party_fee, total_income, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    str(session_date),
                    court_fee,
                    shuttle_fee,
                    party_fee,
                    0,
                    "Tạo thủ công",
                ),
            )
            session_id = c.lastrowid

            for name in fixed_list:
                c.execute(
                    """
                    INSERT INTO member_payments (session_id, member_name, member_type, amount_due, status)
                    VALUES (?, ?, 'Cố định', ?, 'Còn nợ')
                """,
                    (session_id, name, fee_per_person),
                )

            for name in casual_list:
                c.execute(
                    """
                    INSERT INTO member_payments (session_id, member_name, member_type, amount_due, status)
                    VALUES (?, ?, 'Vãng lai', ?, 'Còn nợ')
                """,
                    (session_id, name, fee_per_person),
                )

            conn.commit()
            conn.close()
            st.success(
                f"Đã lưu thành công! Phí mỗi người: {fee_per_person:,.0f} VNĐ ({total_people} người)"
            )

# ------------------------------------------
# TAB 2: QUÉT BILL & GIỌNG NÓI (AI)
# ------------------------------------------
with tabs[1]:
    st.subheader("🤖 Phân Tích Dữ Liệu Tự Động Bằng AI")

    col_bill, col_voice = st.columns(2)

    with col_bill:
        st.write("### 📸 Quét Bill (Hình Ảnh)")
        uploaded_file = st.file_uploader(
            "Tải ảnh hóa đơn tiền sân, nước, cầu...", type=["jpg", "png", "jpeg"]
        )

        if uploaded_file and api_key:
            st.image(uploaded_file, caption="Ảnh hóa đơn", width=250)
            if st.button("Phân Tích Bill bằng AI"):
                try:
                    client = get_openai_client(api_key)
                    with st.spinner("Đang trích xuất dữ liệu..."):
                        img_bytes = uploaded_file.getvalue()
                        bill_data = process_bill_image(client, img_bytes)

                    st.json(bill_data)
                    st.success(
                        f"Nhận diện thành công: **{bill_data.get('category')}** - **{bill_data.get('amount'):,.0f} VNĐ**"
                    )
                except Exception as e:
                    st.error(f"Lỗi khi xử lý hình ảnh: {e}")

    with col_voice:
        st.write("### 🎙️ Nhập Bằng Giọng Nói")
        audio_file = st.file_uploader(
            "Tải file âm thanh ghi âm buổi tập...", type=["mp3", "wav", "m4a"]
        )

        if audio_file and api_key:
            if st.button("Phân Tích Giọng Nói"):
                try:
                    client = get_openai_client(api_key)
                    with st.spinner("Đang chuyển đổi giọng nói..."):
                        voice_data = process_voice_input(client, audio_file)

                    st.markdown(
                        f"**Văn bản nhận diện:** *\"{voice_data.get('raw_text')}\"*"
                    )
                    st.json(voice_data)
                except Exception as e:
                    st.error(f"Lỗi khi xử lý giọng nói: {e}")

# ------------------------------------------
# TAB 3: BÁO CÁO LỜI/LỖ & CẢNH BÁO NỢ
# ------------------------------------------
with tabs[2]:
    st.subheader("📊 Báo Cáo Tài Chính & Quản Lý Công Nợ")

    conn = sqlite3.connect(DB_FILE)
    df_sessions = pd.read_sql_query("SELECT * FROM sessions", conn)

    if not df_sessions.empty():
        df_sessions["total_expense"] = (
            df_sessions["court_fee"]
            + df_sessions["shuttle_fee"]
            + df_sessions["party_fee"]
        )
        df_payments = pd.read_sql_query("SELECT * FROM member_payments", conn)

        total_income_real = df_payments[df_payments["status"] == "Đã trả"][
            "amount_due"
        ].sum()
        total_expense_all = df_sessions["total_expense"].sum()
        profit = total_income_real - total_expense_all

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Tổng Chi Phí", f"{total_expense_all:,.0f} VNĐ")
        kpi2.metric("Tổng Thu Thực Tế", f"{total_income_real:,.0f} VNĐ")
        kpi3.metric("Lời / Lỗ Ròng", f"{profit:,.0f} VNĐ")

        if profit < 0:
            st.error(
                f"🚨 **CẢNH BÁO LỖ:** Câu lạc bộ đang thâm hụt `{abs(profit):,.0f} VNĐ`!"
            )
        else:
            st.success("✅ CLB đang có doanh thu dương.")

        st.divider()

        st.write("### 💳 Quản Lý Công Nợ Thành Viên")
        if not df_payments.empty():
            unpaid_df = df_payments[df_payments["status"] == "Còn nợ"]
            if not unpaid_df.empty():
                st.warning(
                    f"Có {len(unpaid_df)} lượt chưa thanh toán. Tổng nợ: {unpaid_df['amount_due'].sum():,.0f} VNĐ"
                )
                st.dataframe(unpaid_df, use_container_width=True)

                selected_payment_id = st.selectbox(
                    "Chọn thành viên vừa đóng tiền:",
                    options=unpaid_df["id"].tolist(),
                    format_func=lambda x: f"ID: {x} - {unpaid_df[unpaid_df['id']==x]['member_name'].values[0]} ({unpaid_df[unpaid_df['id']==x]['amount_due'].values[0]:,.0f} VNĐ)",
                )

                if st.button("Xác Nhận Đã Thu Tiền"):
                    c = conn.cursor()
                    c.execute(
                        "UPDATE member_payments SET status = 'Đã trả' WHERE id = ?",
                        (selected_payment_id,),
                    )
                    conn.commit()
                    st.success("Cập nhật công nợ thành công!")
                    st.rerun()
            else:
                st.info("🎉 Tất cả thành viên đã đóng phí đầy đủ!")
    else:
        st.info("Chưa có dữ liệu buổi tập.")

    conn.close()