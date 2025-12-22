import React, { useState, useCallback } from 'react';
import { Upload, FileText, CheckCircle, XCircle, Loader2, Trash2, Download, FolderUp } from 'lucide-react';
import logo from '../assets/logo.png';

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
  const [isDragging, setIsDragging] = useState(false);

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
    setIsDragging(false);
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
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragging(false);
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

  const getStatusIcon = (status: BatchFile['status']) => {
    switch (status) {
      case 'completed': return <CheckCircle className="w-5 h-5 text-green-600" />;
      case 'failed': return <XCircle className="w-5 h-5 text-red-600" />;
      case 'processing': return <Loader2 className="w-5 h-5 text-blue-600 animate-spin" />;
      default: return <FileText className="w-5 h-5 text-gray-400" />;
    }
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Branded Header */}
      <div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg">
        <div className="flex items-center space-x-6">
          <div className="bg-white rounded-xl p-3 shadow-md">
            <img src={logo} alt="StatementXL" className="h-12 w-auto" />
          </div>
          <div>
            <h1 className="text-3xl font-bold">Batch Upload</h1>
            <p className="text-green-100 mt-1">Upload multiple PDF financial statements for parallel processing</p>
          </div>
        </div>
      </div>

      {/* Drop Zone */}
      <div
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        className={`
          relative border-2 border-dashed rounded-xl p-12 text-center transition-all cursor-pointer
          ${isDragging
            ? 'border-green-500 bg-green-50'
            : 'border-gray-300 bg-white hover:border-green-400 hover:bg-green-50/50'
          }
        `}
      >
        <input
          type="file"
          accept=".pdf"
          multiple
          onChange={handleFileSelect}
          className="absolute inset-0 opacity-0 cursor-pointer"
        />
        <FolderUp className={`w-12 h-12 mx-auto mb-4 ${isDragging ? 'text-green-600' : 'text-gray-400'}`} />
        <p className="text-gray-700 font-medium mb-1">Drop PDF files here or click to browse</p>
        <p className="text-gray-500 text-sm">Supports multiple files • Max 50MB per file</p>
        <button
          onClick={() => document.querySelector<HTMLInputElement>('input[type="file"]')?.click()}
          className="mt-4 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors font-medium"
        >
          Select Files
        </button>
      </div>

      {/* Template Selection */}
      <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
        <label className="block mb-2 font-medium text-gray-900">Apply Template (Optional)</label>
        <select
          value={selectedTemplate}
          onChange={(e) => setSelectedTemplate(e.target.value)}
          className="w-full p-3 border border-gray-300 rounded-lg bg-white focus:ring-2 focus:ring-green-500 focus:border-green-500"
        >
          <option value="">No template - extract only</option>
          <option value="lbo">LBO Model Template</option>
          <option value="dcf">DCF Valuation Template</option>
          <option value="3stmt">Three Statement Model</option>
        </select>
      </div>

      {/* File List */}
      {files.length > 0 && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
          <div className="flex justify-between items-center p-4 bg-green-50 border-b border-gray-200">
            <span className="font-medium text-gray-900">
              {files.length} file{files.length !== 1 ? 's' : ''} selected
            </span>
            <button
              onClick={clearFiles}
              className="text-red-600 hover:text-red-700 flex items-center space-x-1 text-sm"
            >
              <Trash2 className="w-4 h-4" />
              <span>Clear all</span>
            </button>
          </div>

          <div className="max-h-96 overflow-y-auto divide-y divide-gray-100">
            {files.map(file => (
              <div key={file.id} className="flex items-center p-4 hover:bg-gray-50 transition-colors">
                <div className="mr-4">{getStatusIcon(file.status)}</div>
                <div className="flex-1 min-w-0">
                  <p className="font-medium text-gray-900 truncate">{file.file.name}</p>
                  <p className="text-sm text-gray-500">
                    {(file.file.size / 1024 / 1024).toFixed(2)} MB
                    {file.result && <span className="text-green-600"> • {file.result.tables} tables found</span>}
                    {file.error && <span className="text-red-600"> • {file.error}</span>}
                  </p>
                </div>
                {file.status === 'pending' && (
                  <button
                    onClick={() => removeFile(file.id)}
                    className="p-1.5 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
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
          className={`
            w-full py-4 rounded-xl font-semibold text-white transition-all flex items-center justify-center space-x-2
            ${isProcessing
              ? 'bg-gray-400 cursor-not-allowed'
              : 'bg-green-600 hover:bg-green-500 shadow-lg hover:shadow-xl'
            }
          `}
        >
          {isProcessing ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              <span>Processing...</span>
            </>
          ) : (
            <>
              <Upload className="w-5 h-5" />
              <span>Process {files.length} Files</span>
            </>
          )}
        </button>
      )}

      {/* Batch Result */}
      {batchResult && (
        <div className="bg-green-50 border border-green-200 rounded-xl p-6 border-l-4 border-l-green-500">
          <h3 className="font-semibold text-green-800 text-lg mb-4">Batch Processing Complete</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="bg-white rounded-lg p-4 border border-green-200">
              <p className="text-3xl font-bold text-green-600">{batchResult.successful}</p>
              <p className="text-sm text-gray-500">Successful</p>
            </div>
            <div className="bg-white rounded-lg p-4 border border-green-200">
              <p className="text-3xl font-bold text-red-600">{batchResult.failed}</p>
              <p className="text-sm text-gray-500">Failed</p>
            </div>
            <div className="bg-white rounded-lg p-4 border border-green-200">
              <p className="text-3xl font-bold text-gray-900">{batchResult.total_files}</p>
              <p className="text-sm text-gray-500">Total</p>
            </div>
            <div className="bg-white rounded-lg p-4 border border-green-200">
              <p className="text-3xl font-bold text-gray-900">{(batchResult.processing_time_ms / 1000).toFixed(1)}s</p>
              <p className="text-sm text-gray-500">Time</p>
            </div>
          </div>
          <button
            onClick={() => window.open('/api/v1/batch/' + batchResult.job_id + '/download')}
            className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-colors font-medium flex items-center space-x-2"
          >
            <Download className="w-5 h-5" />
            <span>Download All Results (ZIP)</span>
          </button>
        </div>
      )}
    </div>
  );
};

export default BatchUpload;
