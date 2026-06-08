const uploadArea = document.getElementById('uploadArea');
const fileInput = document.getElementById('fileInput');
const progressWrap = document.getElementById('progressWrap');
const progressBar = document.getElementById('progressBar');
const progressText = document.getElementById('progressText');
const statusMsg = document.getElementById('statusMsg');
const fileGrid = document.getElementById('fileGrid');
const filesHeader = document.getElementById('filesHeader');
const fileCount = document.getElementById('fileCount');
const emptyState = document.getElementById('emptyState');

function getFileIcon(name) {
  const ext = name.split('.').pop().toLowerCase();
  const icons = {
    pdf: '📄', doc: '📝', docx: '📝', txt: '📝',
    jpg: '🖼️', jpeg: '🖼️', png: '🖼️', gif: '🖼️', webp: '🖼️', svg: '🖼️',
    mp4: '🎬', mov: '🎬', avi: '🎬', mkv: '🎬',
    mp3: '🎵', wav: '🎵', m4a: '🎵',
    zip: '🗜️', rar: '🗜️', '7z': '🗜️',
    xls: '📊', xlsx: '📊', csv: '📊',
    ppt: '📊', pptx: '📊',
  };
  return icons[ext] || '📎';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function timeAgo(ts) {
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return 'just now';
  if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
  return Math.floor(diff / 3600) + 'h ago';
}

function showStatus(msg, type) {
  statusMsg.textContent = msg;
  statusMsg.className = 'status-msg ' + type;
  if (type === 'success') setTimeout(() => statusMsg.textContent = '', 3000);
}

async function loadFiles() {
  const res = await fetch('/api/files');
  const files = await res.json();

  fileGrid.innerHTML = '';

  if (files.length === 0) {
    filesHeader.style.display = 'none';
    emptyState.style.display = 'block';
    return;
  }

  filesHeader.style.display = 'flex';
  emptyState.style.display = 'none';
  fileCount.textContent = files.length;

  files.forEach(f => {
    const card = document.createElement('div');
    card.className = 'file-card';
    card.innerHTML = `
      <div class="file-icon">${getFileIcon(f.originalname)}</div>
      <div class="file-name">${escapeHtml(f.originalname)}</div>
      <div class="file-size">${formatSize(f.size)}</div>
      <div class="file-age">Uploaded ${timeAgo(f.uploadedAt)}</div>
      <div class="file-actions">
        <button class="btn-download" onclick="downloadFile('${f.filename}')">Download</button>
        <button class="btn-delete" onclick="deleteFile('${f.filename}', this)">✕</button>
      </div>
    `;
    fileGrid.appendChild(card);
  });
}

function escapeHtml(str) {
  return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function downloadFile(filename) {
  window.location.href = '/api/download/' + filename;
}

async function deleteFile(filename, btn) {
  btn.disabled = true;
  const res = await fetch('/api/files/' + filename, { method: 'DELETE' });
  if (res.ok) loadFiles();
}

async function deleteAll() {
  if (!confirm('Delete all files?')) return;
  await fetch('/api/files', { method: 'DELETE' });
  loadFiles();
}

function uploadFile(file) {
  if (!file) return;
  if (file.size > 20 * 1024 * 1024) {
    showStatus('File too large. Max size is 20MB.', 'error');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  const xhr = new XMLHttpRequest();
  xhr.open('POST', '/api/upload');

  progressWrap.style.display = 'block';
  progressBar.style.width = '0%';
  progressText.textContent = '0%';
  showStatus('', '');

  xhr.upload.onprogress = (e) => {
    if (e.lengthComputable) {
      const pct = Math.round((e.loaded / e.total) * 100);
      progressBar.style.width = pct + '%';
      progressText.textContent = pct + '%';
    }
  };

  xhr.onload = () => {
    progressWrap.style.display = 'none';
    const data = JSON.parse(xhr.responseText);
    if (data.success) {
      showStatus('File uploaded successfully!', 'success');
      loadFiles();
    } else {
      showStatus(data.error || 'Upload failed.', 'error');
    }
  };

  xhr.onerror = () => {
    progressWrap.style.display = 'none';
    showStatus('Upload failed. Please try again.', 'error');
  };

  xhr.send(formData);
}

// Drag & drop
uploadArea.addEventListener('dragover', (e) => {
  e.preventDefault();
  uploadArea.classList.add('dragover');
});

uploadArea.addEventListener('dragleave', () => uploadArea.classList.remove('dragover'));

uploadArea.addEventListener('drop', (e) => {
  e.preventDefault();
  uploadArea.classList.remove('dragover');
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
});

fileInput.addEventListener('change', () => {
  if (fileInput.files[0]) uploadFile(fileInput.files[0]);
  fileInput.value = '';
});

// Refresh files every 10 seconds
loadFiles();
setInterval(loadFiles, 10000);
