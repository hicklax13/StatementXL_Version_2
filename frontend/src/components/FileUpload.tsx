import React, { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload, FileText, CheckCircle, XCircle, Loader2 } from 'lucide-react';

interface FileUploadProps {
    accept?: string;
    onUpload: (file: File) => Promise<void>;
    title?: string;
    description?: string;
    maxSize?: number;
}

const FileUpload: React.FC<FileUploadProps> = ({
    accept = '.pdf',
    onUpload,
    title = 'Upload File',
    description = 'Drag and drop or click to select',
    maxSize = 50 * 1024 * 1024, // 50MB
}) => {
    const [uploading, setUploading] = useState(false);
    const [uploadStatus, setUploadStatus] = useState<'idle' | 'success' | 'error'>('idle');
    const [fileName, setFileName] = useState<string | null>(null);

    const onDrop = useCallback(async (acceptedFiles: File[]) => {
        if (acceptedFiles.length === 0) return;

        const file = acceptedFiles[0];
        setFileName(file.name);
        setUploading(true);
        setUploadStatus('idle');

        try {
            await onUpload(file);
            setUploadStatus('success');
        } catch (error) {
            console.error('Upload failed:', error);
            setUploadStatus('error');
        } finally {
            setUploading(false);
        }
    }, [onUpload]);

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: accept.split(',').reduce((acc, type) => {
            const mimeType = type.includes('/') ? type : `application/${type.replace('.', '')}`;
            acc[mimeType] = [type];
            return acc;
        }, {} as Record<string, string[]>),
        maxSize,
        multiple: false,
    });

    return (
        <div
            {...getRootProps()}
            className={`
        relative border-2 border-dashed rounded-xl p-8 text-center cursor-pointer
        transition-all duration-300 ease-in-out
        ${isDragActive
                    ? 'border-primary-500 bg-primary-500/10 scale-[1.02]'
                    : 'border-dark-600 hover:border-dark-500 hover:bg-dark-800/50'
                }
        ${uploading ? 'pointer-events-none opacity-75' : ''}
      `}
        >
            <input {...getInputProps()} />

            <div className="flex flex-col items-center space-y-4">
                {uploading ? (
                    <Loader2 className="w-12 h-12 text-primary-500 animate-spin" />
                ) : uploadStatus === 'success' ? (
                    <CheckCircle className="w-12 h-12 text-green-500 animate-fade-in" />
                ) : uploadStatus === 'error' ? (
                    <XCircle className="w-12 h-12 text-red-500 animate-fade-in" />
                ) : isDragActive ? (
                    <Upload className="w-12 h-12 text-primary-500 animate-pulse" />
                ) : (
                    <FileText className="w-12 h-12 text-dark-400" />
                )}

                <div>
                    <h3 className="text-lg font-semibold text-dark-100">
                        {uploading ? 'Uploading...' : uploadStatus === 'success' ? 'Upload Complete!' : title}
                    </h3>
                    <p className="text-sm text-dark-400 mt-1">
                        {uploading
                            ? `Processing ${fileName || 'file'}...`
                            : uploadStatus === 'success'
                                ? fileName
                                : description}
                    </p>
                </div>

                {!uploading && uploadStatus === 'idle' && (
                    <div className="flex items-center space-x-2">
                        <span className="px-3 py-1 text-xs font-medium text-primary-400 bg-primary-500/10 rounded-full">
                            {accept.toUpperCase().replace('.', '')}
                        </span>
                        <span className="text-xs text-dark-500">
                            Max {(maxSize / (1024 * 1024)).toFixed(0)}MB
                        </span>
                    </div>
                )}
            </div>
        </div>
    );
};

export default FileUpload;
