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
    page_title="Quản Lý Câu Lạc Bộ Cầu Lông", layout="wide", page_icon="🏸"
)
st.title("🏸 Hệ Thống Quản Lý Câu Lạc Bộ Cầu Lông")

# Thanh điều hướng góc trái (Sidebar)
with st.sidebar:
    st.header("⚙️ Cấu Hình & Tài Khoản")
    api_key_input = st.text_input(
        "Nhập OpenAI API Key (Tuỳ chọn):",
        type="password",
        help="Nếu đã cấu hình Secrets trên Streamlit Cloud, bạn có thể bỏ qua ô này.",
    )
    user_role = st.selectbox(
        "Vai trò người dùng", ["Thủ Quỹ / Quản Trị Viên", "Thành Viên"]
    )

# Tự động kết nối OpenAI Client
client = get_openai_client(api_key_input)

if not client:
    st.info(
        "💡 Vui lòng nhập OpenAI API Key ở thanh bên hoặc cấu hình Secrets để sử dụng tính năng AI."
    )

tabs = st.tabs(
    ["📝 Nhập Buổi Tập", "🧾 Quét Hóa Đơn / Giọng Nói", "📊 Báo Cáo Tài Chính & Công Nợ"]
)

# ------------------------------------------
# TAB 1: NHẬP BUỔI TẬP & ĐIỂM DANH
# ------------------------------------------
with tabs[0]:
    st.subheader("Tạo Buổi Tập Mới & Tự Động Chia Phí")

    col1, col2 = st.columns(2)
    with col1:
        session_date = st.date_input("Ngày tập luyện", datetime.now())
        court_fee = st.number_input("Tiền thuê sân (VNĐ)", value=0, step=10000)
        shuttle_fee = st.number_input("Tiền mua cầu (VNĐ)", value=0, step=10000)
        party_fee = st.number_input(
            "Tiền nước uống / Ăn uống (VNĐ)", value=0, step=10000
        )

    with col2:
        fixed_input = st.text_area(
            "Danh sách Thành viên Cố định (Mỗi người 1 dòng)", "Nam\nBắc\nHải"
        )
        casual_input = st.text_area(
            "Danh sách Khách Vãng lai (Mỗi người 1 dòng)", "Dũng\nTuấn"
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
                f"Đã lưu thành công! Phí mỗi người: {fee_per_person:,.0f} VNĐ (Tổng: {total_people} người)"
            )

# ------------------------------------------
# TAB 2: QUÉT HÓA ĐƠN & GIỌNG NÓI (AI)
# ------------------------------------------
with tabs[1]:
    st.subheader("🤖 Phân Tích Dữ Liệu Tự Động Bằng AI")

    col_bill, col_voice = st.columns(2)

    with col_bill:
        st.write("### 📸 Quét Hóa Đơn (Hình Ảnh)")
        uploaded_file = st.file_uploader(
            "Tải ảnh hóa đơn tiền sân, nước, cầu...", type=["jpg", "png", "jpeg"]
        )

        if uploaded_file:
            st.image(uploaded_file, caption="Ảnh hóa đơn", width=250)
            if st.button("Phân Tích Hóa Đơn Bằng AI"):
                if not client:
                    st.error(
                        "Vui lòng nhập API Key hoặc cấu hình Secrets để sử dụng AI!"
                    )
                else:
                    try:
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
            "Tải tệp âm thanh ghi âm buổi tập...", type=["mp3", "wav", "m4a"]
        )

        if audio_file:
            if st.button("Phân Tích Giọng Nói"):
                if not client:
                    st.error(
                        "Vui lòng nhập API Key hoặc cấu hình Secrets để sử dụng AI!"
                    )
                else:
                    try:
                        with st.spinner("Đang chuyển đổi giọng nói..."):
                            voice_data = process_voice_input(
                                client, audio_file
                            )

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

    try:
        df_sessions = pd.read_sql_query("SELECT * FROM sessions", conn)
        df_payments = pd.read_sql_query("SELECT * FROM member_payments", conn)
    except Exception:
        df_sessions = pd.DataFrame()
        df_payments = pd.DataFrame()

    if not df_sessions.empty:
        df_sessions["total_expense"] = (
            df_sessions["court_fee"]
            + df_sessions["shuttle_fee"]
            + df_sessions["party_fee"]
        )

        total_income_real = 0.0
        if not df_payments.empty and "status" in df_payments.columns:
            paid_records = df_payments[df_payments["status"] == "Đã trả"]
            if not paid_records.empty:
                total_income_real = float(paid_records["amount_due"].sum())

        total_expense_all = float(df_sessions["total_expense"].sum())
        profit = total_income_real - total_expense_all

        # Chỉ số KPI
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Tổng Chi Phí", f"{total_expense_all:,.0f} VNĐ")
        kpi2.metric("Tổng Thu Thực Tế", f"{total_income_real:,.0f} VNĐ")
        kpi3.metric("Lời / Lỗ Ròng", f"{profit:,.0f} VNĐ")

        # Cảnh báo thâm hụt
        if profit < 0:
            st.error(
                f"🚨 **CẢNH BÁO LỖ:** Câu lạc bộ đang thâm hụt `{abs(profit):,.0f} VNĐ`!"
            )
        else:
            st.success("✅ CLB đang có doanh thu dương.")

        st.divider()

        # Quản lý Công Nợ Thành Viên
        st.write("### 💳 Bảng Danh Sách Công Nợ Thành Viên")
        if not df_payments.empty and "status" in df_payments.columns:
            unpaid_df = df_payments[df_payments["status"] == "Còn nợ"].copy()
            if not unpaid_df.empty:
                st.warning(
                    f"Có **{len(unpaid_df)}** lượt chưa thanh toán. Tổng nợ: **{unpaid_df['amount_due'].sum():,.0f} VNĐ**"
                )

                # Đổi tên cột trong Bảng hiển thị sang tiếng Việt có dấu
                display_df = unpaid_df.rename(
                    columns={
                        "id": "Mã Giao Dịch",
                        "session_id": "Mã Buổi Tập",
                        "member_name": "Tên Thành Viên",
                        "member_type": "Loại Thành Viên",
                        "amount_due": "Số Tiền Cần Đóng (VNĐ)",
                        "amount_paid": "Số Tiền Đã Đóng (VNĐ)",
                        "status": "Trạng Thái",
                    }
                )

                # Hiển thị bảng danh sách công nợ
                st.dataframe(display_df, use_container_width=True)

                st.write("#### 📝 Cập Nhật Trạng Thái Thanh Toán")
                selected_payment_id = st.selectbox(
                    "Chọn thành viên vừa hoàn tất đóng tiền:",
                    options=unpaid_df["id"].tolist(),
                    format_func=lambda x: f"Mã GD: {x} - {unpaid_df[unpaid_df['id']==x]['member_name'].values[0]} ({unpaid_df[unpaid_df['id']==x]['amount_due'].values[0]:,.0f} VNĐ)",
                )

                if st.button("Xác Nhận Đã Thu Tiền", type="primary"):
                    c = conn.cursor()
                    c.execute(
                        "UPDATE member_payments SET status = 'Đã trả' WHERE id = ?",
                        (selected_payment_id,),
                    )
                    conn.commit()
                    st.success("Đã cập nhật trạng thái thanh toán thành công!")
                    st.rerun()
            else:
                st.info("🎉 Tất cả thành viên đã đóng phí đầy đủ!")
        else:
            st.info("Chưa có ghi nhận công nợ nào.")
    else:
        st.info("Chưa có dữ liệu buổi tập nào. Hãy sang **Tab 1** để tạo buổi tập đầu tiên!")

    conn.close()