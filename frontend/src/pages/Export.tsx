import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
    Download,
    FileSpreadsheet,
    Palette,
    Layout,
    Building2,
    Check,
    Loader2,
    ChevronRight
} from 'lucide-react';
import {
    getExportOptions,
    exportToExcel,
    downloadExport,
} from '../api/client';
import type { StyleInfo, ColorwayInfo, ExportRequest } from '../api/client';
import { useDocumentStore, useUIStore } from '../stores';

interface ExportConfig {
    statementType: 'income_statement' | 'balance_sheet' | 'cash_flow';
    style: 'basic' | 'corporate' | 'professional';
    colorway: string;
    companyName: string;
}

export default function Export() {
    const navigate = useNavigate();
    const { currentDocument } = useDocumentStore();
    const { addNotification } = useUIStore();

    const [styles, setStyles] = useState<StyleInfo[]>([]);
    const [colorways, setColorways] = useState<ColorwayInfo[]>([]);
    const [loading, setLoading] = useState(true);
    const [exporting, setExporting] = useState(false);
    const [exportResult, setExportResult] = useState<{ filename: string; downloadUrl: string } | null>(null);

    const [config, setConfig] = useState<ExportConfig>({
        statementType: 'income_statement',
        style: 'basic',
        colorway: 'green',
        companyName: '',
    });

    // Load export options on mount
    useEffect(() => {
        const loadOptions = async () => {
            try {
                const options = await getExportOptions();
                setStyles(options.styles);
                setColorways(options.colorways);
            } catch (error) {
                console.error('Failed to load export options:', error);
                addNotification('error', 'Failed to load export options');
            } finally {
                setLoading(false);
            }
        };
        loadOptions();
    }, [addNotification]);

    const handleExport = async () => {
        if (!currentDocument) {
            addNotification('error', 'Please select a document to export');
            return;
        }

        setExporting(true);
        setExportResult(null);

        try {
            const request: ExportRequest = {
                document_id: currentDocument.id,
                statement_type: config.statementType,
                style: config.style,
                colorway: config.colorway,
                company_name: config.companyName || undefined,
            };

            const result = await exportToExcel(request);

            setExportResult({
                filename: result.filename,
                downloadUrl: downloadExport(result.export_id),
            });

            addNotification('success', `Excel file generated: ${result.filename}`);
        } catch (error) {
            console.error('Export failed:', error);
            addNotification('error', 'Export failed. Please try again.');
        } finally {
            setExporting(false);
        }
    };

    const statementTypes = [
        { id: 'income_statement', name: 'Income Statement', icon: FileSpreadsheet },
        { id: 'balance_sheet', name: 'Balance Sheet', icon: Layout },
        { id: 'cash_flow', name: 'Cash Flow', icon: Building2 },
    ];

    if (loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="w-8 h-8 animate-spin text-green-600" />
            </div>
        );
    }

    return (
        <div className="p-6 max-w-4xl mx-auto">
            {/* Header */}
            <div className="bg-green-600 rounded-xl p-6 mb-8 flex items-center gap-4">
                <div className="bg-white/10 backdrop-blur-sm rounded-xl p-3">
                    <Download className="w-8 h-8 text-white" />
                </div>
                <div>
                    <h1 className="text-2xl font-bold text-white">Export to Excel</h1>
                    <p className="text-green-100">
                        Generate a formatted Excel file from your extracted data
                    </p>
                </div>
            </div>

            {/* Current Document */}
            {currentDocument ? (
                <div className="bg-white rounded-xl border border-gray-200 p-4 mb-6 flex items-center gap-4">
                    <FileSpreadsheet className="w-10 h-10 text-green-600" />
                    <div className="flex-1">
                        <h3 className="font-semibold text-gray-900">{currentDocument.filename}</h3>
                        <p className="text-sm text-gray-500">Selected document for export</p>
                    </div>
                    <button
                        onClick={() => navigate('/extraction')}
                        className="text-green-600 hover:text-green-700 text-sm font-medium"
                    >
                        Change
                    </button>
                </div>
            ) : (
                <div className="bg-yellow-50 rounded-xl border border-yellow-200 p-4 mb-6">
                    <p className="text-yellow-800">
                        No document selected.
                        <button
                            onClick={() => navigate('/upload')}
                            className="ml-2 text-yellow-900 font-medium underline"
                        >
                            Upload a PDF
                        </button>
                    </p>
                </div>
            )}

            {/* Company Name Input */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">Company Name</h2>
                <input
                    type="text"
                    value={config.companyName}
                    onChange={(e) => setConfig({ ...config, companyName: e.target.value })}
                    placeholder="Enter company name (optional)"
                    className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                />
            </div>

            {/* Statement Type Selection */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <FileSpreadsheet className="w-5 h-5 text-green-600" />
                    Statement Type
                </h2>
                <div className="grid grid-cols-3 gap-4">
                    {statementTypes.map((type) => (
                        <button
                            key={type.id}
                            onClick={() => setConfig({ ...config, statementType: type.id as ExportConfig['statementType'] })}
                            className={`p-4 rounded-xl border-2 transition-all ${config.statementType === type.id
                                ? 'border-green-500 bg-green-50'
                                : 'border-gray-200 hover:border-gray-300'
                                }`}
                        >
                            <type.icon className={`w-8 h-8 mx-auto mb-2 ${config.statementType === type.id ? 'text-green-600' : 'text-gray-400'
                                }`} />
                            <p className={`text-sm font-medium ${config.statementType === type.id ? 'text-green-700' : 'text-gray-700'
                                }`}>
                                {type.name}
                            </p>
                        </button>
                    ))}
                </div>
            </div>

            {/* Style Selection */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Layout className="w-5 h-5 text-green-600" />
                    Template Style
                </h2>
                <div className="grid grid-cols-3 gap-4">
                    {styles.map((style) => (
                        <button
                            key={style.id}
                            onClick={() => setConfig({ ...config, style: style.id as ExportConfig['style'] })}
                            className={`p-4 rounded-xl border-2 transition-all text-left ${config.style === style.id
                                ? 'border-green-500 bg-green-50'
                                : 'border-gray-200 hover:border-gray-300'
                                }`}
                        >
                            <div className="flex items-center justify-between mb-2">
                                <span className={`font-semibold ${config.style === style.id ? 'text-green-700' : 'text-gray-700'
                                    }`}>
                                    {style.name}
                                </span>
                                {config.style === style.id && (
                                    <Check className="w-5 h-5 text-green-600" />
                                )}
                            </div>
                            <p className="text-xs text-gray-500">{style.description}</p>
                        </button>
                    ))}
                </div>
            </div>

            {/* Colorway Selection */}
            <div className="bg-white rounded-xl border border-gray-200 p-6 mb-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center gap-2">
                    <Palette className="w-5 h-5 text-green-600" />
                    Color Theme
                </h2>
                <div className="flex flex-wrap gap-3">
                    {colorways.map((colorway) => (
                        <button
                            key={colorway.id}
                            onClick={() => setConfig({ ...config, colorway: colorway.id })}
                            className={`flex items-center gap-3 px-4 py-3 rounded-xl border-2 transition-all ${config.colorway === colorway.id
                                ? 'border-gray-800 bg-gray-50'
                                : 'border-gray-200 hover:border-gray-300'
                                }`}
                        >
                            <div
                                className="w-6 h-6 rounded-full border-2 border-white shadow-md"
                                style={{ backgroundColor: colorway.primary_color }}
                            />
                            <span className={`text-sm font-medium ${config.colorway === colorway.id ? 'text-gray-900' : 'text-gray-600'
                                }`}>
                                {colorway.name}
                            </span>
                            {config.colorway === colorway.id && (
                                <Check className="w-4 h-4 text-green-600" />
                            )}
                        </button>
                    ))}
                </div>
            </div>

            {/* Export Button */}
            <div className="flex items-center justify-between">
                <button
                    onClick={() => navigate('/extraction')}
                    className="px-6 py-3 text-gray-600 hover:text-gray-800 font-medium"
                >
                    ← Back to Review
                </button>

                <button
                    onClick={handleExport}
                    disabled={exporting || !currentDocument}
                    className="flex items-center gap-2 px-8 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                >
                    {exporting ? (
                        <>
                            <Loader2 className="w-5 h-5 animate-spin" />
                            Generating...
                        </>
                    ) : (
                        <>
                            <Download className="w-5 h-5" />
                            Generate Excel
                        </>
                    )}
                </button>
            </div>

            {/* Export Result */}
            {exportResult && (
                <div className="mt-6 bg-green-50 rounded-xl border border-green-200 p-6">
                    <div className="flex items-center gap-4">
                        <div className="bg-green-100 rounded-full p-3">
                            <Check className="w-6 h-6 text-green-600" />
                        </div>
                        <div className="flex-1">
                            <h3 className="font-semibold text-green-900">Export Complete!</h3>
                            <p className="text-sm text-green-700">{exportResult.filename}</p>
                        </div>
                        <a
                            href={exportResult.downloadUrl}
                            download
                            className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white font-semibold rounded-xl hover:bg-green-700 transition-colors"
                        >
                            <Download className="w-5 h-5" />
                            Download
                            <ChevronRight className="w-4 h-4" />
                        </a>
                    </div>
                </div>
            )}
        </div>
    );
}
