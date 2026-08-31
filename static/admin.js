const loginForm = document.getElementById('loginForm');
const passwordInput = document.getElementById('passwordInput');
const loginStatus = document.getElementById('loginStatus');
const usersSection = document.getElementById('usersSection');
const addUserForm = document.getElementById('addUserForm');
const newUsernameInput = document.getElementById('newUsernameInput');
const addUserStatus = document.getElementById('addUserStatus');
const userList = document.getElementById('userList');

let adminPassword = '';

function renderUsers(usernames) {
  if (!usernames || usernames.length === 0) {
    userList.innerHTML = '<div class="empty-hint">Chưa có username nào được cấp quyền.</div>';
    return;
  }
  userList.innerHTML = usernames
    .map(
      (u) => `
        <div class="procedure-item">
          <div class="procedure-info"><span class="name">${u}</span></div>
          <button type="button" class="delete-btn" data-username="${u}">Xóa</button>
        </div>
      `
    )
    .join('');
}

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
    adminPassword = passwordInput.value;
    loginStatus.textContent = '';
    passwordInput.value = '';
    usersSection.hidden = false;
    renderUsers(result.usernames);
  } catch {
    loginStatus.textContent = 'Không thể kết nối máy chủ, vui lòng thử lại.';
    loginStatus.className = 'error';
  }
};

addUserForm.onsubmit = async (event) => {
  event.preventDefault();
  const username = newUsernameInput.value.trim();
  if (!username) return;

  addUserStatus.textContent = 'Đang thêm...';
  addUserStatus.className = '';
  try {
    const response = await fetch('/admin/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Admin-Password': adminPassword },
      body: JSON.stringify({ username }),
    });
    const result = await response.json();
    if (!response.ok) {
      addUserStatus.textContent = result.detail || 'Thêm thất bại.';
      addUserStatus.className = 'error';
      return;
    }
    addUserStatus.textContent = 'Đã thêm.';
    addUserStatus.className = 'ok';
    newUsernameInput.value = '';
    renderUsers(result.usernames);
    setTimeout(() => { addUserStatus.textContent = ''; }, 3000);
  } catch {
    addUserStatus.textContent = 'Không thể kết nối máy chủ, vui lòng thử lại.';
    addUserStatus.className = 'error';
  }
};

userList.addEventListener('click', async (event) => {
  const button = event.target.closest('.delete-btn');
  if (!button) return;
  const username = button.dataset.username;
  if (!confirm(`Xóa quyền truy cập của "${username}"?`)) return;

  button.disabled = true;
  try {
    const response = await fetch(`/admin/users/${encodeURIComponent(username)}`, {
      method: 'DELETE',
      headers: { 'X-Admin-Password': adminPassword },
    });
    const result = await response.json();
    if (result.ok) {
      renderUsers(result.usernames);
    } else {
      alert(result.detail || 'Xóa thất bại.');
      button.disabled = false;
    }
  } catch {
    alert('Không thể kết nối máy chủ, vui lòng thử lại.');
    button.disabled = false;
  }
});
