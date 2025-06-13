import express from 'express';
import multer from 'multer';
import path from 'path';
import fs from 'fs';

// Ensure uploads directory exists
const uploadsDir = 'uploads';
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

// Configure multer for file uploads
const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    cb(null, 'uploads/');
  },
  filename: function (req, file, cb) {
    const uniqueSuffix = Date.now() + '-' + Math.round(Math.random() * 1E9);
    cb(null, uniqueSuffix + '-' + file.originalname);
  }
});

const upload = multer({ 
  storage: storage,
  limits: { fileSize: 16 * 1024 * 1024 }, // 16MB limit
  fileFilter: function (req, file, cb) {
    const allowedTypes = /pdf|doc|docx|txt/;
    const extname = allowedTypes.test(path.extname(file.originalname).toLowerCase());
    const mimetype = allowedTypes.test(file.mimetype) || 
                     file.mimetype === 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    
    if (mimetype && extname) {
      return cb(null, true);
    } else {
      cb(new Error('Only PDF, DOC, DOCX, and TXT files are allowed'));
    }
  }
});

export const serverSetup = (expressApp, context) => {
  console.log('Setting up server with expressApp:', typeof expressApp);
  
  // Check if expressApp has the use method
  if (!expressApp || typeof expressApp.use !== 'function') {
    console.error('Express app not available in serverSetup');
    return;
  }

  // Serve uploaded files
  expressApp.use('/uploads', express.static('uploads'));
  
  // File upload endpoint
  expressApp.post('/api/upload-resume', upload.single('resume'), (req, res) => {
    if (!req.file) {
      return res.status(400).json({ error: 'No file uploaded' });
    }
    
    res.json({
      success: true,
      filename: req.file.filename,
      originalName: req.file.originalname,
      path: req.file.path
    });
  });
  
  // Error handling middleware
  expressApp.use((error, req, res, next) => {
    if (error instanceof multer.MulterError) {
      if (error.code === 'LIMIT_FILE_SIZE') {
        return res.status(400).json({ error: 'File too large. Maximum size is 16MB.' });
      }
    }
    
    if (error.message) {
      return res.status(400).json({ error: error.message });
    }
    
    next(error);
  });
  
  console.log('Server setup completed successfully');
};