const loginForm = document.getElementById('loginForm');
const passwordInput = document.getElementById('passwordInput');
const loginStatus = document.getElementById('loginStatus');
const afterLoginSection = document.getElementById('afterLoginSection');

loginForm.onsubmit = async (event) => {
  event.preventDefault();
  loginStatus.textContent = 'Đang kiểm tra...';
  loginStatus.className = '';

  try {
    const response = await fetch('/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password: passwordInput.value }),
    });
    const result = await response.json();
    if (!response.ok) {
      loginStatus.textContent = result.detail || 'Sai mật khẩu.';
      loginStatus.className = 'error';
      return;
    }
    loginStatus.textContent = '';
    passwordInput.value = '';
    afterLoginSection.hidden = false;
  } catch {
    loginStatus.textContent = 'Không thể kết nối máy chủ, vui lòng thử lại.';
    loginStatus.className = 'error';
  }
};
