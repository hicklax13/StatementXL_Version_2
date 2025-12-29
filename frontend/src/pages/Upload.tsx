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
    const [recentUploads, setRecentUploads] = useState<{
        id: string;
        filename: string;
        status: 'completed' | 'processing' | 'failed' | 'reasoning';
        pageCount?: number;
        createdAt: string;
    }[]>([]);

    const [currentPhase, setCurrentPhase] = useState<'uploading' | 'extracting' | 'classifying' | 'reasoning' | 'completed'>('uploading');
    const [progress, setProgress] = useState(0);

    const handleUpload = async (file: File) => {
        try {
            const result = await uploadDocument(file);

            // Simulate phases for better UX
            setCurrentPhase('extracting');
            setProgress(30);
            await new Promise(r => setTimeout(r, 1000));

            setCurrentPhase('classifying');
            setProgress(60);
            await new Promise(r => setTimeout(r, 1000));

            setCurrentPhase('reasoning');
            setProgress(85);
            await new Promise(r => setTimeout(r, 1500));

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
            setCurrentPhase('completed');
            setProgress(100);
            addNotification('success', `Successfully processed ${file.name}`);

            // Navigate to extraction review
            setTimeout(() => navigate('/extraction'), 1000);
        } catch (error: unknown) {
            addNotification('error', error instanceof Error ? error.message : 'Upload failed');
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
            < div className="bg-white rounded-xl border border-gray-200 p-8 shadow-sm" >
                {currentPhase === 'uploading' ? (
                    <FileUpload
                        accept=".pdf"
                        onUpload={handleUpload}
                        title="Drop PDF Here"
                        description="Income statements, balance sheets, cash flow statements"
                        maxSize={50 * 1024 * 1024}
                    />
                ) : (
                    <div className="text-center py-12 space-y-6">
                        <div className="relative w-24 h-24 mx-auto">
                            <div className="absolute inset-0 border-4 border-gray-100 rounded-full"></div>
                            <div
                                className="absolute inset-0 border-4 border-green-600 rounded-full transition-all duration-300 ease-out"
                                style={{
                                    clipPath: `inset(0 ${100 - progress}% 0 0)`,
                                    transform: 'rotate(-90deg)'
                                }}
                            ></div>
                            <div className="absolute inset-0 flex items-center justify-center">
                                <span className="text-xl font-bold text-green-700">{progress}%</span>
                            </div>
                        </div>

                        <div>
                            <h3 className="text-xl font-semibold text-gray-900 mb-2">
                                {currentPhase === 'extracting' && 'Extracting Data...'}
                                {currentPhase === 'classifying' && 'Classifying Line Items...'}
                                {currentPhase === 'reasoning' && 'Applying AI Reasoning...'}
                                {currentPhase === 'completed' && 'Processing Complete!'}
                            </h3>
                            <p className="text-gray-500">
                                {currentPhase === 'reasoning'
                                    ? "Analyzing GAAP context for ambiguous items..."
                                    : "Please wait while we process your document"}
                            </p>
                        </div>

                        {/* Phase Steps */}
                        <div className="flex justify-center space-x-2 mt-8">
                            {['extracting', 'classifying', 'reasoning'].map((step, idx) => {
                                const stepStatus =
                                    currentPhase === 'completed' ? 'completed' :
                                        currentPhase === step ? 'current' :
                                            ['extracting', 'classifying', 'reasoning'].indexOf(currentPhase) > idx ? 'completed' : 'pending';

                                return (
                                    <div key={step} className="flex items-center">
                                        <div className={`
                                            w-3 h-3 rounded-full transition-colors duration-300
                                            ${stepStatus === 'completed' ? 'bg-green-600' :
                                                stepStatus === 'current' ? 'bg-green-400 animate-pulse' : 'bg-gray-200'}
                                        `} />
                                        {idx < 2 && <div className={`w-8 h-1 ${stepStatus === 'completed' ? 'bg-green-200' : 'bg-gray-100'}`} />}
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                )}
            </div >

            {/* Recent Uploads */}
            {
                (recentUploads.length > 0 || documents.length > 0) && (
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
