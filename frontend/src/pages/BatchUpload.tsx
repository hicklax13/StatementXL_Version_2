import React, { useState, useCallback } from 'react';

interface BatchFile {
  id: string;
  file: File;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
  result?: {
    tables: number;
    confidence: number;
  };
  error?: string;
}

interface BatchResult {
  job_id: string;
  total_files: number;
  successful: number;
  failed: number;
  processing_time_ms: number;
}

const BatchUpload: React.FC = () => {
  const [files, setFiles] = useState<BatchFile[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const [batchResult, setBatchResult] = useState<BatchResult | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles) return;

    const newFiles: BatchFile[] = Array.from(selectedFiles).map((file, index) => ({
      id: `file-${Date.now()}-${index}`,
      file,
      status: 'pending',
      progress: 0,
    }));

    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleDrop = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    const droppedFiles = event.dataTransfer.files;
    
    const newFiles: BatchFile[] = Array.from(droppedFiles)
      .filter(file => file.type === 'application/pdf')
      .map((file, index) => ({
        id: `file-${Date.now()}-${index}`,
        file,
        status: 'pending',
        progress: 0,
      }));

    setFiles(prev => [...prev, ...newFiles]);
  }, []);

  const handleDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
  }, []);

  const removeFile = useCallback((id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
  }, []);

  const processFiles = async () => {
    setIsProcessing(true);
    setBatchResult(null);

    const startTime = Date.now();
    let successful = 0;
    let failed = 0;

    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      
      setFiles(prev => prev.map(f => 
        f.id === file.id ? { ...f, status: 'processing', progress: 0 } : f
      ));

      try {
        const formData = new FormData();
        formData.append('file', file.file);

        const response = await fetch('/api/v1/upload', {
          method: 'POST',
          body: formData,
        });

        if (response.ok) {
          const result = await response.json();
          setFiles(prev => prev.map(f => 
            f.id === file.id ? {
              ...f,
              status: 'completed',
              progress: 100,
              result: {
                tables: result.tables?.length || 0,
                confidence: 0.95,
              },
            } : f
          ));
          successful++;
        } else {
          throw new Error('Upload failed');
        }
      } catch (error) {
        setFiles(prev => prev.map(f => 
          f.id === file.id ? {
            ...f,
            status: 'failed',
            progress: 0,
            error: error instanceof Error ? error.message : 'Unknown error',
          } : f
        ));
        failed++;
      }
    }

    setBatchResult({
      job_id: `batch-${Date.now()}`,
      total_files: files.length,
      successful,
      failed,
      processing_time_ms: Date.now() - startTime,
    });

    setIsProcessing(false);
  };

  const clearFiles = () => {
    setFiles([]);
    setBatchResult(null);
  };

  const getStatusColor = (status: BatchFile['status']) => {
    switch (status) {
      case 'completed': return '#22c55e';
      case 'failed': return '#ef4444';
      case 'processing': return '#3b82f6';
      default: return '#6b7280';
    }
  };

  const getStatusIcon = (status: BatchFile['status']) => {
    switch (status) {
      case 'completed': return '✓';
      case 'failed': return '✗';
      case 'processing': return '◐';
      default: return '○';
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '1200px', margin: '0 auto' }}>
      <h1 style={{ fontSize: '2rem', fontWeight: 'bold', marginBottom: '1.5rem', color: '#111827' }}>
        Batch Upload
      </h1>
      
      <p style={{ color: '#6b7280', marginBottom: '2rem' }}>
        Upload multiple PDF financial statements for parallel processing.
      </p>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        style={{
          border: '2px dashed #d1d5db',
          borderRadius: '12px',
          padding: '3rem',
          textAlign: 'center',
          backgroundColor: '#f9fafb',
          marginBottom: '2rem',
          cursor: 'pointer',
        }}
      >
        <div style={{ marginBottom: '1rem' }}>
          <span style={{ fontSize: '3rem' }}>📁</span>
        </div>
        <p style={{ color: '#374151', fontWeight: '500', marginBottom: '0.5rem' }}>
          Drop PDF files here or click to browse
        </p>
        <p style={{ color: '#9ca3af', fontSize: '0.875rem' }}>
          Supports multiple files • Max 50MB per file
        </p>
        <input
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileSelect}
          style={{
            position: 'absolute',
            opacity: 0,
            width: '100%',
            height: '100%',
            cursor: 'pointer',
          }}
        />
        <button
          onClick={() => document.querySelector<HTMLInputElement>('input[type="file"]')?.click()}
          style={{
            marginTop: '1rem',
            padding: '0.75rem 1.5rem',
            backgroundColor: '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            fontWeight: '500',
            cursor: 'pointer',
          }}
        >
          Select Files
        </button>
      </div>

      {/* Template Selection */}
      <div style={{ marginBottom: '2rem' }}>
        <label style={{ display: 'block', marginBottom: '0.5rem', fontWeight: '500' }}>
          Apply Template (Optional)
        </label>
        <select
          value={selectedTemplate}
          onChange={(e) => setSelectedTemplate(e.target.value)}
          style={{
            width: '100%',
            padding: '0.75rem',
            border: '1px solid #d1d5db',
            borderRadius: '8px',
            backgroundColor: 'white',
          }}
        >
          <option value="">No template - extract only</option>
          <option value="lbo">LBO Model Template</option>
          <option value="dcf">DCF Valuation Template</option>
          <option value="3stmt">Three Statement Model</option>
        </select>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div style={{
          border: '1px solid #e5e7eb',
          borderRadius: '12px',
          overflow: 'hidden',
          marginBottom: '2rem',
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            padding: '1rem',
            backgroundColor: '#f9fafb',
            borderBottom: '1px solid #e5e7eb',
          }}>
            <span style={{ fontWeight: '500' }}>
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={clearFiles}
              style={{
                color: '#ef4444',
                background: 'none',
                border: 'none',
                cursor: 'pointer',
              }}
            >
              Clear all
            </button>
          </div>
          
          <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
            {files.map(file => (
              <div
                key={file.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '1rem',
                  borderBottom: '1px solid #e5e7eb',
                }}
              >
                <span
                  style={{
                    width: '24px',
                    height: '24px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    borderRadius: '50%',
                    backgroundColor: getStatusColor(file.status),
                    color: 'white',
                    marginRight: '1rem',
                    fontSize: '0.75rem',
                  }}
                >
                  {getStatusIcon(file.status)}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: '500' }}>{file.file.name}</div>
                  <div style={{ fontSize: '0.875rem', color: '#6b7280' }}>
                    {(file.file.size / 1024 / 1024).toFixed(2)} MB
                    {file.result && ` • ${file.result.tables} tables found`}
                    {file.error && <span style={{ color: '#ef4444' }}> • {file.error}</span>}
                  </div>
                </div>
                {file.status === 'pending' && (
                  <button
                    onClick={() => removeFile(file.id)}
                    style={{
                      color: '#6b7280',
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                    }}
                  >
                    ✕
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Process Button */}
      {files.length > 0 && !batchResult && (
        <button
          onClick={processFiles}
          disabled={isProcessing}
          style={{
            width: '100%',
            padding: '1rem',
            backgroundColor: isProcessing ? '#9ca3af' : '#10b981',
            color: 'white',
            border: 'none',
            borderRadius: '8px',
            fontWeight: '600',
            fontSize: '1rem',
            cursor: isProcessing ? 'not-allowed' : 'pointer',
          }}
        >
          {isProcessing ? 'Processing...' : `Process ${files.length} Files`}
        </button>
      )}

      {/* Batch Result */}
      {batchResult && (
        <div style={{
          padding: '1.5rem',
          backgroundColor: '#f0fdf4',
          borderRadius: '12px',
          border: '1px solid #86efac',
        }}>
          <h3 style={{ fontWeight: '600', marginBottom: '1rem', color: '#166534' }}>
            Batch Processing Complete
          </h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#166534' }}>
                {batchResult.successful}
              </div>
              <div style={{ color: '#6b7280' }}>Successful</div>
            </div>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#dc2626' }}>
                {batchResult.failed}
              </div>
              <div style={{ color: '#6b7280' }}>Failed</div>
            </div>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#111827' }}>
                {batchResult.total_files}
              </div>
              <div style={{ color: '#6b7280' }}>Total</div>
            </div>
            <div>
              <div style={{ fontSize: '2rem', fontWeight: 'bold', color: '#111827' }}>
                {(batchResult.processing_time_ms / 1000).toFixed(1)}s
              </div>
              <div style={{ color: '#6b7280' }}>Time</div>
            </div>
          </div>
          <button
            onClick={() => window.open('/api/v1/batch/' + batchResult.job_id + '/download')}
            style={{
              marginTop: '1.5rem',
              padding: '0.75rem 1.5rem',
              backgroundColor: '#10b981',
              color: 'white',
              border: 'none',
              borderRadius: '8px',
              fontWeight: '500',
              cursor: 'pointer',
            }}
          >
            Download All Results (ZIP)
          </button>
        </div>
      )}
    </div>
  );
};

export default BatchUpload;
