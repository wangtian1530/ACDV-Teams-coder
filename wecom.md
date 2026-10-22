# 🚀 Chào mừng đến với ACDV-Teams Coder!

> **Vì sao ACDV-Teams Coder ra đời?** 
> Giữa thời đại các dịch vụ đám mây đắt đỏ, phụ thuộc vào hạ tầng bên ngoài và những gói thuê bao dễ tạo ra "cú sốc chi phí", ACDV-Teams Coder được tạo ra để giải quyết triệt để bài toán: **Làm sao để có một môi trường lập trình độc lập, tối ưu tuyệt đối, linh hoạt và hoàn toàn nằm trong tầm kiểm soát ngay trên thiết bị cá nhân (Android/Termux và Linux local)?**

Chào mừng bạn đã đến với **ACDV-Teams Coder** — hệ thống Web IDE mô-đun tối ưu, hiệu năng cao được thiết kế chuyên biệt để chạy mượt mà trên môi trường Android/Termux và Linux cục bộ (localhost). 

Dự án mang đến tinh thần **mã nguồn mở minh bạch, tự lực cánh sinh**, định hình theo triết lý **"Vỏ siêu nhẹ"**: Python đóng vai trò là trạm trung chuyển điều phối linh hoạt, kết hợp cùng các module độc lập hiệu năng cao, mang lại trải nghiệm lập trình tự chủ và hoàn toàn kiểm soát trên thiết bị của chính bạn.

---

## 📖 Hướng dẫn sử dụng cơ bản (Dành cho User)

### 1. Khởi động hệ thống
* Hệ thống chạy hoàn toàn ở chế độ **Non-root (Không sudo)** nhằm đảm bảo an toàn tuyệt đối cho thiết bị của bạn.
* Khởi động trạm trung chuyển Python qua dòng lệnh local trên Termux/Linux. Giao diện Web IDE sẽ sẵn sàng để bạn quản lý project và thao tác trực tiếp.

### 2. Quản lý và Cắm rút Module
* **Cơ chế Module độc lập:** Mỗi tính năng mở rộng được đóng gói trong một thư mục tài nguyên riêng biệt. 
* **Quy tắc bảo mật SHA256 & Thương hiệu:** 
  * Hệ thống tự động quét và kiểm tra mã băm SHA256 đối với các module mang nhãn hiệu **`acdv-teams`** để chống mã độc và giả mạo.
  * Nếu phát hiện mã nguồn bị can thiệp trái phép, hệ thống sẽ tự động vô hiệu hóa module đó để bảo vệ an toàn cho toàn bộ hệ thống.
  * **Luật chơi mở (Mã nguồn công khai):** Bạn hoàn toàn có quyền sao chép (copy) và tự do tùy biến mã nguồn theo ý thích, nhưng **bắt buộc phải đổi tên khác** để không xung đột với bản chính hãng của ACDV-Teams.

---

## 🛠️ Định hướng tương lai & Phát triển

* **Tăng tốc độ bàn thờ với C++:** Trong tương lai, các tác vụ tính toán nặng hoặc xử lý logic cốt lõi sẽ được biên dịch sẵn thành các file binary (native binary) độc quyền, cắm trực tiếp vào module để đạt hiệu năng tối đa mà không làm phồng to app core.
* **Cơ chế tự hủy an toàn (Heartbeat):** Các module sẽ liên tục đồng bộ trạng thái kết nối với core. Mất kết nối là tự động giải phóng tài nguyên, không để lại tiến trình mồ côi (orphan process) ngốn ngầm RAM hay CPU.

---

## ⚠️ Trạng thái hiện tại (Đang phát triển)
* Dự án hiện đang trong **quá trình phát triển và hoàn thiện**. 
* Hệ thống có thể vẫn còn tồn tại **một số bug ẩn** trong quá trình tương tác giữa core Python và các module độc lập. 
* Mọi đóng góp, báo lỗi hoặc tự do vọc vạch tùy biến đều được hoan nghênh theo đúng tinh thần mã nguồn mở và tự chủ công nghệ!

*Chúc bạn có những trải nghiệm code thật mượt mà cùng ACDV-Teams Coder!*
