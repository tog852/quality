# Phân tích chất lượng không khí - Flask Application

Ứng dụng web phân tích chất lượng không khí tại Phường Tân Bình, TP Đồng Xoài, Bình Phước sử dụng dữ liệu từ Google Earth Engine.

## Tính năng

- Hiển thị bản đồ phân bố nồng độ khí CO, NO2, HCHO
- Phân tích nồng độ khí tại một điểm cụ thể
- Phân tích nồng độ trung bình trong một khu vực
- Biểu đồ nồng độ khí theo tháng (năm 2023)

## Yêu cầu hệ thống

- Python 3.7+
- Pip (trình quản lý gói Python)
- Tài khoản Google Earth Engine đã được kích hoạt

## Cài đặt

1. Clone repository:
```
git clone <repository-url>
cd <repository-folder>
```

2. Cài đặt các gói phụ thuộc:
```
pip install -r requirements.txt
```

3. Xác thực với Google Earth Engine:
```
earthengine authenticate
```

## Cách chạy ứng dụng

1. Chạy ứng dụng Flask:
```
python app.py
```

2. Mở trình duyệt web và truy cập:
```
http://localhost:5000
```

## Triển khai

Để triển khai trên môi trường production, bạn có thể sử dụng Gunicorn:

```
gunicorn app:app
```

## Cấu trúc dự án

- `app.py`: Ứng dụng Flask chính
- `templates/index.html`: Giao diện người dùng
- `requirements.txt`: Danh sách các gói phụ thuộc
- `README.md`: Tài liệu hướng dẫn

## Đóng góp

Vui lòng gửi Pull Request hoặc mở Issue để đóng góp cho dự án.

## Giấy phép

[MIT License](LICENSE) 