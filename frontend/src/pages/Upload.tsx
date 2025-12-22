import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { FileText, Clock, CheckCircle, AlertCircle, ArrowRight } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadDocument } from '../api/client';
import { useDocumentStore, useUIStore } from '../stores';
import logo from '../assets/logo.png';

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
        <div className="space-y-8 animate-fade-in">
            {/* Branded Header Section */}
            <div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg">
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
            </div>

            {/* Upload Area */}
            <div className="bg-white rounded-xl border border-gray-200 p-8 shadow-sm">
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
                <div className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Recent Uploads</h2>
                    <div className="space-y-3">
                        {(recentUploads.length > 0 ? recentUploads : documents.slice(0, 5)).map((doc) => (
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
            )}

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
        </div>
    );
};

export default Upload;
