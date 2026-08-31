const uploadForm = document.getElementById('uploadForm');
const pdfInput = document.getElementById('pdfInput');
const urlInput = document.getElementById('urlInput');
const uploadStatus = document.getElementById('uploadStatus');
const procedureList = document.getElementById('procedureList');

// Mật khẩu quản trị: hỏi 1 lần khi mở trang, giữ trong sessionStorage (mất khi
// đóng tab, khác accessToken người dùng thường lưu lâu dài trong localStorage).
function adminPassword() {
  let pw = sessionStorage.getItem('adminPassword');
  if (!pw) {
    pw = prompt('Nhập mật khẩu quản trị để quản lý dữ liệu thủ tục:') || '';
    sessionStorage.setItem('adminPassword', pw);
  }
  return pw;
}

function authHeaders() {
  return { 'X-Admin-Password': adminPassword() };
}

function handleAuthFailure(response) {
  if (response.status === 401) {
    sessionStorage.removeItem('adminPassword');
    return true;
  }
  return false;
}

async function loadProcedures() {
  procedureList.textContent = 'Đang tải...';
  try {
    const response = await fetch('/procedures');
    const procedures = await response.json();

    if (procedures.length === 0) {
      procedureList.innerHTML = '<div class="empty-hint">Chưa có thủ tục nào được tải lên.</div>';
      return;
    }

    procedureList.innerHTML = procedures
      .map((p) => {
        const codeLine = p.procedure_code ? `<span class="code">Mã: ${p.procedure_code}</span>` : '';
        const linkLine = p.source_url
          ? `<br /><a href="${p.source_url}" target="_blank" rel="noopener">Xem trên dichvucong.gov.vn</a>`
          : '';
        return `
          <div class="procedure-item">
            <div class="procedure-info">
              <span class="name">${p.procedure_name}</span> ${codeLine}
              ${linkLine}
            </div>
            <button type="button" class="delete-btn" data-slug="${p.slug}">Xóa</button>
          </div>
        `;
      })
      .join('');
  } catch {
    procedureList.innerHTML = '<div class="empty-hint">Không tải được danh sách thủ tục.</div>';
  }
}

procedureList.addEventListener('click', async (event) => {
  const button = event.target.closest('.delete-btn');
  if (!button) return;

  const slug = button.dataset.slug;
  if (!confirm('Xóa thủ tục này khỏi dữ liệu tra cứu? Không thể hoàn tác.')) return;

  button.disabled = true;
  button.textContent = 'Đang xóa...';
  try {
    const response = await fetch(`/procedures/${slug}`, { method: 'DELETE', headers: authHeaders() });
    if (handleAuthFailure(response)) {
      alert('Sai mật khẩu quản trị, vui lòng thử lại.');
      button.disabled = false;
      button.textContent = 'Xóa';
      return;
    }
    const result = await response.json();
    if (result.ok) {
      loadProcedures();
    } else {
      alert(result.error || 'Xóa thất bại.');
      button.disabled = false;
      button.textContent = 'Xóa';
    }
  } catch {
    alert('Không thể kết nối máy chủ, vui lòng thử lại.');
    button.disabled = false;
    button.textContent = 'Xóa';
  }
});

uploadForm.onsubmit = async (event) => {
  event.preventDefault();
  const file = pdfInput.files[0];
  if (!file) return;

  uploadStatus.textContent = 'Đang tải lên và xử lý...';
  uploadStatus.className = '';

  const formData = new FormData();
  formData.append('file', file);
  formData.append('source_url', urlInput.value.trim());

  try {
    const response = await fetch('/upload-pdf', { method: 'POST', body: formData, headers: authHeaders() });
    if (handleAuthFailure(response)) {
      uploadStatus.textContent = 'Sai mật khẩu quản trị, vui lòng thử lại.';
      uploadStatus.className = 'error';
      return;
    }
    const result = await response.json();
    if (result.ok) {
      uploadStatus.textContent = `Đã lưu và cập nhật dữ liệu: ${result.saved_as}`;
      uploadStatus.className = 'ok';
      uploadForm.reset();
      loadProcedures();
    } else {
      uploadStatus.textContent = result.error || 'Tải lên thất bại.';
      uploadStatus.className = 'error';
    }
  } catch {
    uploadStatus.textContent = 'Không thể kết nối máy chủ, vui lòng thử lại.';
    uploadStatus.className = 'error';
  }
};

loadProcedures();
