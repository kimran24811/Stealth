const express = require('express');
const multer = require('multer');
const cron = require('node-cron');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = process.env.PORT || 3000;
const UPLOADS_DIR = path.join(__dirname, 'uploads');
const MAX_FILE_AGE_HOURS = 2;

if (!fs.existsSync(UPLOADS_DIR)) fs.mkdirSync(UPLOADS_DIR, { recursive: true });

// Track files: { [ip]: [{ filename, originalname, uploadedAt, size }] }
let fileRegistry = {};

function getClientIP(req) {
  const forwarded = req.headers['x-forwarded-for'];
  return forwarded ? forwarded.split(',')[0].trim() : req.socket.remoteAddress;
}

const storage = multer.diskStorage({
  destination: (req, file, cb) => cb(null, UPLOADS_DIR),
  filename: (req, file, cb) => {
    const unique = Date.now() + '-' + Math.round(Math.random() * 1e6);
    cb(null, unique + path.extname(file.originalname));
  }
});

const upload = multer({
  storage,
  limits: { fileSize: 20 * 1024 * 1024 }, // 20MB
  fileFilter: (req, file, cb) => {
    // Block dangerous executables
    const blocked = ['.exe', '.bat', '.sh', '.cmd', '.ps1', '.msi'];
    const ext = path.extname(file.originalname).toLowerCase();
    if (blocked.includes(ext)) return cb(new Error('File type not allowed'));
    cb(null, true);
  }
});

app.use(express.static(path.join(__dirname, 'public')));

// Get files for this IP
app.get('/api/files', (req, res) => {
  const ip = getClientIP(req);
  const files = fileRegistry[ip] || [];
  res.json(files);
});

// Upload file
app.post('/api/upload', (req, res) => {
  const ip = getClientIP(req);
  upload.single('file')(req, res, (err) => {
    if (err) {
      if (err.code === 'LIMIT_FILE_SIZE') {
        return res.status(400).json({ error: 'File too large. Max size is 20MB.' });
      }
      return res.status(400).json({ error: err.message });
    }
    if (!req.file) return res.status(400).json({ error: 'No file uploaded.' });

    if (!fileRegistry[ip]) fileRegistry[ip] = [];
    fileRegistry[ip].push({
      filename: req.file.filename,
      originalname: req.file.originalname,
      uploadedAt: Date.now(),
      size: req.file.size
    });

    res.json({ success: true });
  });
});

// Download file
app.get('/api/download/:filename', (req, res) => {
  const ip = getClientIP(req);
  const files = fileRegistry[ip] || [];
  const file = files.find(f => f.filename === req.params.filename);
  if (!file) return res.status(404).json({ error: 'File not found.' });

  const filepath = path.join(UPLOADS_DIR, file.filename);
  res.download(filepath, file.originalname);
});

// Delete file
app.delete('/api/files/:filename', (req, res) => {
  const ip = getClientIP(req);
  const files = fileRegistry[ip] || [];
  const idx = files.findIndex(f => f.filename === req.params.filename);
  if (idx === -1) return res.status(404).json({ error: 'File not found.' });

  const filepath = path.join(UPLOADS_DIR, files[idx].filename);
  if (fs.existsSync(filepath)) fs.unlinkSync(filepath);
  fileRegistry[ip].splice(idx, 1);
  res.json({ success: true });
});

// Delete all files for this IP
app.delete('/api/files', (req, res) => {
  const ip = getClientIP(req);
  const files = fileRegistry[ip] || [];
  files.forEach(f => {
    const filepath = path.join(UPLOADS_DIR, f.filename);
    if (fs.existsSync(filepath)) fs.unlinkSync(filepath);
  });
  fileRegistry[ip] = [];
  res.json({ success: true });
});

// Auto-delete files older than 2 hours
cron.schedule('*/15 * * * *', () => {
  const cutoff = Date.now() - MAX_FILE_AGE_HOURS * 60 * 60 * 1000;
  for (const ip in fileRegistry) {
    fileRegistry[ip] = fileRegistry[ip].filter(f => {
      if (f.uploadedAt < cutoff) {
        const filepath = path.join(UPLOADS_DIR, f.filename);
        if (fs.existsSync(filepath)) fs.unlinkSync(filepath);
        return false;
      }
      return true;
    });
    if (fileRegistry[ip].length === 0) delete fileRegistry[ip];
  }
});

app.listen(PORT, () => console.log(`Server running on http://localhost:${PORT}`));
