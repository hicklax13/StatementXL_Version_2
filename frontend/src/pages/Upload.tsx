import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, CheckCircle, AlertCircle, ArrowRight, Upload as UploadIcon, X } from 'lucide-react';
import { useDropzone } from 'react-dropzone';
import { uploadDocument } from '../api/client';
import { useDocumentStore, useUIStore } from '../stores';
import logo from '../assets/logo.png';

interface UploadItem {
    id: string;
    file: File;
    status: 'pending' | 'uploading' | 'completed' | 'error';
    progress: number;
    error?: string;
}

const Upload: React.FC = () => {
    const navigate = useNavigate();
    const { documents, addDocument, setCurrentDocument } = useDocumentStore();
    const { addNotification } = useUIStore();
    const [uploadQueue, setUploadQueue] = useState<UploadItem[]>([]);
    const [isProcessing, setIsProcessing] = useState(false);

    const onDrop = (acceptedFiles: File[]) => {
        const newItems = acceptedFiles.map(file => ({
            id: Math.random().toString(36).substring(7),
            file,
            status: 'pending' as const,
            progress: 0
        }));
        setUploadQueue(prev => [...prev, ...newItems]);
    };

    const { getRootProps, getInputProps, isDragActive } = useDropzone({
        onDrop,
        accept: { 'application/pdf': ['.pdf'] }
    });

    const processQueue = async () => {
        if (isProcessing) return;

        const pendingItem = uploadQueue.find(item => item.status === 'pending');
        if (!pendingItem) return;

        setIsProcessing(true);
        const itemId = pendingItem.id;

        // Update status to uploading
        setUploadQueue(prev => prev.map(item =>
            item.id === itemId ? { ...item, status: 'uploading', progress: 0 } : item
        ));

        try {
            // Upload
            const result = await uploadDocument(pendingItem.file);

            // Simulate extracting/classifying/reasoning steps for visual feedback
            // In a real batch scenario, you might rely on server-sent events or polling, 
            // but for now we'll simulate progress updates
            for (let p = 10; p <= 90; p += 20) {
                setUploadQueue(prev => prev.map(item =>
                    item.id === itemId ? { ...item, progress: p } : item
                ));
                await new Promise(r => setTimeout(r, 500));
            }

            const newDoc = {
                id: result.document_id,
                filename: result.filename,
                status: 'completed' as const,
                pageCount: result.page_count,
                createdAt: new Date().toISOString(),
            };

            addDocument(newDoc);
            addDocument(newDoc);

            setUploadQueue(prev => prev.map(item =>
                item.id === itemId ? { ...item, status: 'completed', progress: 100 } : item
            ));

        } catch (error: unknown) {
            setUploadQueue(prev => prev.map(item =>
                item.id === itemId ? {
                    ...item,
                    status: 'error',
                    progress: 0,
                    error: error instanceof Error ? error.message : 'Upload failed'
                } : item
            ));
            addNotification('error', `Failed to upload ${pendingItem.file.name}`);
        } finally {
            setIsProcessing(false);
        }
    };

    // Auto-process queue
    React.useEffect(() => {
        processQueue();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [uploadQueue, isProcessing]);

    const removeQueueItem = (id: string, e: React.MouseEvent) => {
        e.stopPropagation();
        setUploadQueue(prev => prev.filter(item => item.id !== id));
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed':
                return <CheckCircle className="w-4 h-4 text-green-600" />;
            case 'processing':
                return <Clock className="w-4 h-4 text-amber-500 animate-pulse" />;
            case 'failed':
                return <AlertCircle className="w-4 h-4 text-red-500" />;
            default:
                return <Clock className="w-4 h-4 text-gray-400" />;
        }
    };

    return (
        <div className="space-y-8 animate-fade-in" >
            {/* Branded Header Section */}
            < div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg" >
                <div className="flex items-center space-x-6">
                    <div className="bg-white rounded-xl p-3 shadow-md">
                        <img
                            src={logo}
                            alt="StatementXL"
                            className="h-12 w-auto"
                        />
                    </div>
                    <div>
                        <h1 className="text-3xl font-bold">Upload Financial Statement</h1>
                        <p className="text-green-100 mt-1">
                            Upload a PDF to extract financial data and map to your template
                        </p>
                    </div>
                </div>
            </div >

            {/* Upload Area */}
            <div className="bg-white rounded-xl border border-gray-200 p-8 shadow-sm">
                <div {...getRootProps()} className={`
                    border-2 border-dashed rounded-xl p-12 text-center cursor-pointer transition-colors
                    ${isDragActive ? 'border-green-500 bg-green-50' : 'border-gray-200 hover:border-green-400 hover:bg-gray-50'}
                `}>
                    <input {...getInputProps()} />
                    <div className="w-16 h-16 bg-green-100 text-green-600 rounded-full flex items-center justify-center mx-auto mb-4">
                        <UploadIcon className="w-8 h-8" />
                    </div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                        {isDragActive ? "Drop files here..." : "Drag & Drop PDF Statements"}
                    </h3>
                    <p className="text-gray-500 mb-6">Support for multiple files extraction</p>
                    <button className="px-6 py-2 bg-green-600 text-white rounded-lg font-medium hover:bg-green-700 transition-colors">
                        Browse Files
                    </button>
                </div>

                {/* Upload Queue */}
                {uploadQueue.length > 0 && (
                    <div className="mt-8 space-y-4">
                        <h3 className="font-semibold text-gray-900">Upload Queue</h3>
                        <div className="space-y-3">
                            {uploadQueue.map(item => (
                                <div key={item.id} className="bg-gray-50 rounded-lg p-4 border border-gray-200 relative overflow-hidden">
                                    {item.status === 'uploading' && (
                                        <div
                                            className="absolute bottom-0 left-0 h-1 bg-green-500 transition-all duration-300"
                                            style={{ width: `${item.progress}%` }}
                                        />
                                    )}
                                    <div className="flex items-center justify-between relative z-10">
                                        <div className="flex items-center space-x-3">
                                            <div className="p-2 bg-white rounded-lg border border-gray-200">
                                                <FileText className="w-5 h-5 text-gray-500" />
                                            </div>
                                            <div>
                                                <p className="font-medium text-gray-900">{item.file.name}</p>
                                                <p className="text-sm text-gray-500">
                                                    {(item.file.size / 1024 / 1024).toFixed(2)} MB
                                                </p>
                                            </div>
                                        </div>
                                        <div className="flex items-center space-x-4">
                                            {item.status === 'pending' && <span className="text-sm text-gray-500">Pending...</span>}
                                            {item.status === 'uploading' && <span className="text-sm text-blue-600 font-medium">Processing... {item.progress}%</span>}
                                            {item.status === 'completed' && (
                                                <span className="flex items-center text-sm text-green-600 font-medium">
                                                    <CheckCircle className="w-4 h-4 mr-1" />
                                                    Done
                                                </span>
                                            )}
                                            {item.status === 'error' && (
                                                <span className="flex items-center text-sm text-red-600 font-medium">
                                                    <AlertCircle className="w-4 h-4 mr-1" />
                                                    Failed
                                                </span>
                                            )}

                                            {item.status !== 'uploading' && (
                                                <button
                                                    onClick={(e) => removeQueueItem(item.id, e)}
                                                    className="p-1 hover:bg-gray-200 rounded-full text-gray-400 hover:text-red-500 transition-colors"
                                                >
                                                    <X className="w-4 h-4" />
                                                </button>
                                            )}
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            {/* Recent Uploads */}
            {
                documents.length > 0 && (
                    <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                        <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Uploads</h2>
                        <div className="space-y-3">
                            {documents.slice(0, 5).map((doc) => (
                                <div
                                    key={doc.id}
                                    className="flex items-center justify-between p-4 rounded-lg bg-green-50 hover:bg-green-100 transition-colors cursor-pointer group border border-green-200"
                                    onClick={() => {
                                        setCurrentDocument(doc);
                                        navigate('/extraction');
                                    }}
                                >
                                    <div className="flex items-center space-x-4">
                                        <div className="p-2 rounded-lg bg-green-600">
                                            <FileText className="w-5 h-5 text-white" />
                                        </div>
                                        <div>
                                            <p className="font-medium text-gray-900">{doc.filename}</p>
                                            <p className="text-sm text-gray-500">
                                                {doc.pageCount} pages • {new Date(doc.createdAt).toLocaleDateString()}
                                            </p>
                                        </div>
                                    </div>
                                    <div className="flex items-center space-x-4">
                                        {getStatusIcon(doc.status)}
                                        <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-green-600 transition-colors" />
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )
            }

            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                    <p className="text-sm text-gray-500">Documents Processed</p>
                    <p className="text-2xl font-bold mt-1 text-green-600">{documents.length}</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                    <p className="text-sm text-gray-500">Success Rate</p>
                    <p className="text-2xl font-bold mt-1 text-green-600">98%</p>
                </div>
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                    <p className="text-sm text-gray-500">Avg. Confidence</p>
                    <p className="text-2xl font-bold mt-1 text-green-600">94%</p>
                </div>
            </div>
        </div >
    );
};

export default Upload;
