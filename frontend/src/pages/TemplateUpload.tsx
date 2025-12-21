import React from 'react';
import { useNavigate } from 'react-router-dom';
import { FileSpreadsheet, ArrowRight, Grid3X3, GitBranch, Layers } from 'lucide-react';
import FileUpload from '../components/FileUpload';
import { uploadTemplate } from '../api/client';
import { useTemplateStore, useUIStore } from '../stores';

const TemplateUpload: React.FC = () => {
    const navigate = useNavigate();
    const { templates, addTemplate, setCurrentTemplate } = useTemplateStore();
    const { addNotification } = useUIStore();

    const handleUpload = async (file: File) => {
        try {
            const result = await uploadTemplate(file);

            const newTemplate = {
                id: result.template_id,
                filename: result.filename,
                sheetCount: result.sheet_count,
                status: 'completed' as const,
                createdAt: new Date().toISOString(),
            };

            addTemplate(newTemplate);
            setCurrentTemplate(newTemplate);
            addNotification('success', `Template analyzed: ${result.structure?.sections?.length || 0} sections detected`);

            setTimeout(() => navigate('/mapping'), 1500);
        } catch (error: any) {
            addNotification('error', error.message || 'Template upload failed');
            throw error;
        }
    };

    return (
        <div className="space-y-8 animate-fade-in">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold text-dark-100">Upload Template</h1>
                <p className="text-dark-400 mt-2">
                    Upload your Excel template to map extracted data
                </p>
            </div>

            {/* Upload Area */}
            <div className="card p-8">
                <FileUpload
                    accept=".xlsx,.xls"
                    onUpload={handleUpload}
                    title="Drop Excel Template Here"
                    description="Financial model templates with input cells"
                    maxSize={25 * 1024 * 1024}
                />
            </div>

            {/* Template Analysis Preview */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[
                    { icon: Grid3X3, label: 'Sections Detected', value: 'Auto', desc: 'Income, Balance, Cash Flow' },
                    { icon: GitBranch, label: 'Dependencies', value: 'Auto', desc: 'Formula relationships mapped' },
                    { icon: Layers, label: 'Input Cells', value: 'Auto', desc: 'Cells awaiting data' },
                ].map((item) => (
                    <div key={item.label} className="card p-6">
                        <div className="flex items-center space-x-3 mb-3">
                            <div className="p-2 rounded-lg bg-accent-500/10">
                                <item.icon className="w-5 h-5 text-accent-400" />
                            </div>
                            <span className="font-medium text-dark-100">{item.label}</span>
                        </div>
                        <p className="text-2xl font-bold text-dark-100">{item.value}</p>
                        <p className="text-sm text-dark-400 mt-1">{item.desc}</p>
                    </div>
                ))}
            </div>

            {/* Recent Templates */}
            {templates.length > 0 && (
                <div className="card p-6">
                    <h2 className="text-lg font-semibold text-dark-100 mb-4">Recent Templates</h2>
                    <div className="space-y-3">
                        {templates.slice(0, 3).map((template) => (
                            <div
                                key={template.id}
                                className="flex items-center justify-between p-4 rounded-lg bg-dark-800/50 hover:bg-dark-800 transition-colors cursor-pointer group"
                                onClick={() => {
                                    setCurrentTemplate(template);
                                    navigate('/mapping');
                                }}
                            >
                                <div className="flex items-center space-x-4">
                                    <div className="p-2 rounded-lg bg-accent-500/10">
                                        <FileSpreadsheet className="w-5 h-5 text-accent-400" />
                                    </div>
                                    <div>
                                        <p className="font-medium text-dark-100">{template.filename}</p>
                                        <p className="text-sm text-dark-400">
                                            {template.sheetCount} sheets • {new Date(template.createdAt).toLocaleDateString()}
                                        </p>
                                    </div>
                                </div>
                                <ArrowRight className="w-4 h-4 text-dark-500 group-hover:text-accent-400 transition-colors" />
                            </div>
                        ))}
                    </div>
                </div>
            )}
        </div>
    );
};

export default TemplateUpload;
