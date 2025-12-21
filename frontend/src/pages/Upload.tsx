import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadDocument } from '../api/client';
import { useDocumentStore, useUIStore } from '../stores';

const Upload: React.FC = () => {
    const navigate = useNavigate();
    const { documents, addDocument, setCurrentDocument } = useDocumentStore();
    const { addNotification } = useUIStore();
    const [recentUploads, setRecentUploads] = useState<any[]>([]);

    const handleUpload = async (file: File) => {
        try {
            const result = await uploadDocument(file);

            const newDoc = {
                id: result.document_id,
                filename: result.filename,
                status: 'completed' as const,
                pageCount: result.page_count,
                createdAt: new Date().toISOString(),
            };

            addDocument(newDoc);
            setRecentUploads((prev) => [newDoc, ...prev.slice(0, 4)]);
            setCurrentDocument(newDoc);
            addNotification('success', `Successfully processed ${file.name}`);

            // Navigate to extraction review
            setTimeout(() => navigate('/extraction'), 1500);
        } catch (error: any) {
            addNotification('error', error.message || 'Upload failed');
            throw error;
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'completed':
                return <CheckCircle className="w-4 h-4 text-green-500" />;
            case 'processing':
                return <Clock className="w-4 h-4 text-yellow-500 animate-pulse" />;
            case 'failed':
                return <AlertCircle className="w-4 h-4 text-red-500" />;
            default:
                return <Clock className="w-4 h-4 text-dark-400" />;
        }
    };

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-dark-100">Upload Financial Statement</h1>
                <p className="text-dark-400 mt-2">
                    Upload a PDF to extract financial data and map to your template
                </p>
            </div>

            {/* Upload Area */}
            <div className="card p-8">
                <FileUpload
                    accept=".pdf"
                    onUpload={handleUpload}
                    title="Drop PDF Here"
                    description="Income statements, balance sheets, cash flow statements"
                    maxSize={50 * 1024 * 1024}
                />
            </div>

            {/* Recent Uploads */}
            {(recentUploads.length > 0 || documents.length > 0) && (
                <div className="card p-6">
                    <h2 className="text-lg font-semibold text-dark-100 mb-4">Recent Uploads</h2>
                    <div className="space-y-3">
                        {(recentUploads.length > 0 ? recentUploads : documents.slice(0, 5)).map((doc) => (
                            <div
                                key={doc.id}
                                className="flex items-center justify-between p-4 rounded-lg bg-dark-800/50 hover:bg-dark-800 transition-colors cursor-pointer group"
                                onClick={() => {
                                    setCurrentDocument(doc);
                                    navigate('/extraction');
                                }}
                            >
                                <div className="flex items-center space-x-4">
                                    <div className="p-2 rounded-lg bg-primary-500/10">
                                        <FileText className="w-5 h-5 text-primary-400" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-dark-100">{doc.filename}</p>
                                        <p className="text-sm text-dark-400">
                                            {doc.pageCount} pages • {new Date(doc.createdAt).toLocaleDateString()}
                                        </p>
                                    </div>
                                </div>
                                <div className="flex items-center space-x-4">
                                    {getStatusIcon(doc.status)}
                                    <ArrowRight className="w-4 h-4 text-dark-500 group-hover:text-primary-400 transition-colors" />
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Quick Stats */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                    { label: 'Documents Processed', value: documents.length.toString(), color: 'primary' },
                    { label: 'Success Rate', value: '98%', color: 'green' },
                    { label: 'Avg. Confidence', value: '94%', color: 'accent' },
                ].map((stat) => (
                    <div key={stat.label} className="card p-6">
                        <p className="text-sm text-dark-400">{stat.label}</p>
                        <p className={`text-2xl font-bold mt-1 text-${stat.color}-400`}>{stat.value}</p>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Upload;
