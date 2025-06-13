import React, { useState, useRef } from 'react';
import { 
  uploadResumeFile, 
  processResumeWithAI, 
  downloadProcessedResume 
} from 'wasp/client/operations';
import { getUserCredits } from 'wasp/client/operations';
import { useQuery } from 'wasp/client/operations';

export default function ResumeProcessor() {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [resumeId, setResumeId] = useState(null);
  const [jobUrl, setJobUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [processedResult, setProcessedResult] = useState(null);
  const [error, setError] = useState('');
  const fileInputRef = useRef(null);
  
  const { data: userCredits, isLoading: creditsLoading } = useQuery(getUserCredits);

  const handleFileUpload = async (file) => {
    setError('');
    
    // Upload file to server first
    const formData = new FormData();
    formData.append('resume', file);
    
    try {
      const response = await fetch('/api/upload-resume', {
        method: 'POST',
        body: formData
      });
      
      const result = await response.json();
      
      if (result.success) {
        // Create resume record
        const resume = await uploadResumeFile({
          filename: result.filename,
          originalName: result.originalName,
          jobUrl: jobUrl
        });
        
        setUploadedFile(file);
        setResumeId(resume.id);
      } else {
        setError(result.error || 'Upload failed');
      }
    } catch (err) {
      setError('Upload failed: ' + err.message);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleFileSelect = (e) => {
    const files = e.target.files;
    if (files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const handleProcess = async () => {
    if (!resumeId || !jobUrl.trim()) {
      setError('Please upload a resume and provide a job URL');
      return;
    }
    
    if (userCredits?.credits <= 0) {
      setError('Insufficient credits. Please purchase more credits.');
      return;
    }

    setIsProcessing(true);
    setError('');

    try {
      const result = await processResumeWithAI({
        resumeId: resumeId,
        jobUrl: jobUrl.trim()
      });

      setProcessedResult(result);
    } catch (err) {
      setError(err.message || 'Processing failed');
    } finally {
      setIsProcessing(false);
    }
  };

  const styles = {
    container: {
      maxWidth: '1200px',
      margin: '0 auto',
      padding: '24px'
    },
    card: {
      backgroundColor: 'white',
      borderRadius: '8px',
      boxShadow: '0 4px 6px rgba(0, 0, 0, 0.1)',
      padding: '32px'
    },
    title: {
      fontSize: '1.875rem',
      fontWeight: 'bold',
      color: '#1f2937',
      marginBottom: '16px',
      textAlign: 'center'
    },
    subtitle: {
      color: '#6b7280',
      textAlign: 'center',
      marginBottom: '32px'
    },
    creditsDisplay: {
      display: 'inline-block',
      backgroundColor: '#dbeafe',
      color: '#1e40af',
      padding: '8px 16px',
      borderRadius: '9999px',
      marginTop: '16px'
    },
    grid: {
      display: 'grid',
      gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
      gap: '32px'
    },
    sectionTitle: {
      fontSize: '1.25rem',
      fontWeight: '600',
      marginBottom: '16px'
    },
    uploadArea: {
      border: '2px dashed #d1d5db',
      borderRadius: '8px',
      padding: '32px',
      textAlign: 'center',
      cursor: 'pointer',
      transition: 'border-color 0.3s',
      backgroundColor: '#f9fafb'
    },
    uploadAreaHover: {
      borderColor: '#3b82f6'
    },
    uploadIcon: {
      fontSize: '2rem',
      marginBottom: '16px'
    },
    textarea: {
      width: '100%',
      padding: '12px',
      border: '1px solid #d1d5db',
      borderRadius: '8px',
      resize: 'none',
      fontSize: '1rem'
    },
    button: {
      width: '100%',
      marginTop: '24px',
      backgroundColor: '#10b981',
      color: 'white',
      padding: '12px 24px',
      borderRadius: '8px',
      fontWeight: '600',
      border: 'none',
      cursor: 'pointer',
      transition: 'background-color 0.3s'
    },
    buttonDisabled: {
      opacity: '0.5',
      cursor: 'not-allowed'
    },
    alert: {
      padding: '12px 16px',
      borderRadius: '4px',
      marginBottom: '16px'
    },
    alertError: {
      backgroundColor: '#fee2e2',
      border: '1px solid #fca5a5',
      color: '#991b1b'
    },
    alertInfo: {
      backgroundColor: '#dbeafe',
      border: '1px solid #93c5fd',
      color: '#1e40af'
    },
    alertSuccess: {
      backgroundColor: '#d1fae5',
      border: '1px solid #6ee7b7',
      color: '#065f46'
    },
    downloadLink: {
      display: 'inline-block',
      backgroundColor: '#10b981',
      color: 'white',
      padding: '8px 16px',
      borderRadius: '4px',
      textDecoration: 'none',
      marginTop: '12px',
      transition: 'background-color 0.3s'
    }
  };

  return (
    <div style={styles.container}>
      <div style={styles.card}>
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1 style={styles.title}>
            AI Resume Processor
          </h1>
          <p style={styles.subtitle}>
            Upload your resume and paste a job URL to create a tailored version
          </p>
          {!creditsLoading && (
            <div style={styles.creditsDisplay}>
              Credits remaining: {userCredits?.credits || 0}
            </div>
          )}
        </div>

        <div style={styles.grid}>
          {/* Upload Section */}
          <div>
            <h2 style={styles.sectionTitle}>Upload Resume</h2>
            <div
              style={styles.uploadArea}
              onDrop={handleDrop}
              onDragOver={(e) => e.preventDefault()}
              onClick={() => fileInputRef.current?.click()}
            >
              <div style={styles.uploadIcon}>📄</div>
              <p style={{ marginBottom: '8px' }}>
                {uploadedFile ? uploadedFile.name : 'Drag & drop your resume here'}
              </p>
              <p style={{ fontSize: '0.875rem', color: '#6b7280' }}>or click to select</p>
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileSelect}
                style={{ display: 'none' }}
              />
            </div>

            <div style={{ marginTop: '24px' }}>
              <h2 style={styles.sectionTitle}>Job URL</h2>
              <textarea
                value={jobUrl}
                onChange={(e) => setJobUrl(e.target.value)}
                placeholder="Paste the job posting URL here..."
                style={styles.textarea}
                rows={3}
              />
            </div>

            {uploadedFile && jobUrl.trim() && (
              <button
                onClick={handleProcess}
                disabled={isProcessing || userCredits?.credits <= 0}
                style={{
                  ...styles.button,
                  ...(isProcessing || userCredits?.credits <= 0 ? styles.buttonDisabled : {})
                }}
              >
                {isProcessing ? 'Processing...' : 'Generate Tailored Resume'}
              </button>
            )}
          </div>

          {/* Results Section */}
          <div>
            <h2 style={styles.sectionTitle}>Results</h2>
            
            {error && (
              <div style={{ ...styles.alert, ...styles.alertError }}>
                {error}
              </div>
            )}

            {isProcessing && (
              <div style={{ ...styles.alert, ...styles.alertInfo }}>
                Analyzing job description and tailoring your resume...
              </div>
            )}

            {processedResult && (
              <div style={{ ...styles.alert, ...styles.alertSuccess }}>
                <p style={{ marginBottom: '12px' }}>Resume successfully processed!</p>
                <a
                  href={processedResult.downloadUrl}
                  download
                  style={styles.downloadLink}
                >
                  Download Tailored Resume
                </a>
              </div>
            )}

            {!uploadedFile && !isProcessing && !processedResult && (
              <div style={{ textAlign: 'center', color: '#6b7280', padding: '32px 0' }}>
                <p>Your processed resume will appear here</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}