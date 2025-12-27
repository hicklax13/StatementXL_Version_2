import React, { useState, useEffect } from 'react';
import {
    Search,
    Grid3X3,
    List,
    Star,
    Download,
    Plus,
    Filter,
    FileSpreadsheet,
    Users,
    Loader2,
    AlertCircle,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useTemplateStore, useUIStore } from '../stores';
import logo from '../assets/logo.png';

interface LibraryTemplate {
    id: string;
    template_id: string;
    name: string;
    description: string | null;
    category: string | null;
    industry: string | null;
    tags: string[];
    download_count: number;
    use_count: number;
    rating: number;
    is_featured: boolean;
    author: string | null;
    created_at: string;
}

// Statement type options
const STATEMENT_TYPES = [
    { value: 'income-statement', label: 'Income Statement (IS)' },
    { value: 'balance-sheet', label: 'Balance Sheet (BS)' },
    { value: 'cash-flow', label: 'Cash Flow (CF)' },
    { value: 'three-statement', label: 'Three Statement Model' },
];

const TemplateLibrary: React.FC = () => {
    const navigate = useNavigate();
    const { setCurrentTemplate, addTemplate } = useTemplateStore();
    const { addNotification } = useUIStore();

    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
    const [selectedStatementType, setSelectedStatementType] = useState<string | null>(null);
    const [showFilters, setShowFilters] = useState(false);

    // API state
    const [templates, setTemplates] = useState<LibraryTemplate[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Fetch templates from API
    useEffect(() => {
        const fetchTemplates = async () => {
            try {
                setLoading(true);
                setError(null);

                const params = new URLSearchParams();
                if (selectedCategory) params.append('category', selectedCategory);
                if (selectedIndustry) params.append('industry', selectedIndustry);
                if (searchQuery) params.append('search', searchQuery);

                const response = await fetch(`/api/v1/library/templates?${params}`);

                if (!response.ok) {
                    throw new Error(`Failed to fetch templates: ${response.status}`);
                }

                const data = await response.json();
                setTemplates(data);
            } catch (err) {
                console.error('Failed to fetch templates:', err);
                setError(err instanceof Error ? err.message : 'Failed to load templates');
                // Use demo data as fallback
                setTemplates([
                    {
                        id: '1',
                        template_id: '1',
                        name: 'Income Statement Template',
                        description: 'Standard income statement with revenue, expenses, and net income sections',
                        category: 'income-statement',
                        industry: 'general',
                        tags: ['is', 'revenue', 'expenses'],
                        download_count: 1250,
                        use_count: 890,
                        rating: 4.8,
                        is_featured: true,
                        author: 'StatementXL Team',
                        created_at: '2024-01-15T10:00:00Z',
                    },
                    {
                        id: '2',
                        template_id: '2',
                        name: 'Balance Sheet Template',
                        description: 'Complete balance sheet with assets, liabilities, and equity sections',
                        category: 'balance-sheet',
                        industry: 'general',
                        tags: ['bs', 'assets', 'liabilities', 'equity'],
                        download_count: 2100,
                        use_count: 1500,
                        rating: 4.9,
                        is_featured: true,
                        author: 'StatementXL Team',
                        created_at: '2024-02-20T10:00:00Z',
                    },
                    {
                        id: '3',
                        template_id: '3',
                        name: 'Cash Flow Statement',
                        description: 'Cash flow statement with operating, investing, and financing activities',
                        category: 'cash-flow',
                        industry: 'general',
                        tags: ['cf', 'operating', 'investing', 'financing'],
                        download_count: 1800,
                        use_count: 1200,
                        rating: 4.7,
                        is_featured: false,
                        author: 'StatementXL Team',
                        created_at: '2024-03-10T10:00:00Z',
                    },
                    {
                        id: '4',
                        template_id: '4',
                        name: 'Three Statement Model',
                        description: 'Integrated income, balance sheet, and cash flow statements',
                        category: 'three-statement',
                        industry: 'corporate-finance',
                        tags: ['is', 'bs', 'cf', 'integrated'],
                        download_count: 3400,
                        use_count: 2800,
                        rating: 4.9,
                        is_featured: true,
                        author: 'Community',
                        created_at: '2024-04-05T10:00:00Z',
                    },
                ]);
            } finally {
                setLoading(false);
            }
        };

        fetchTemplates();
    }, [selectedCategory, selectedIndustry, searchQuery]);

    const categories = ['income-statement', 'balance-sheet', 'cash-flow', 'three-statement', 'lbo', 'valuation', 'ma'];
    const industries = ['general', 'technology', 'healthcare', 'financial-services', 'retail', 'manufacturing'];

    // Filter by statement type
    const filteredTemplates = templates.filter((t) => {
        if (selectedStatementType && t.category !== selectedStatementType) {
            return false;
        }
        return true;
    });

    // Handle template selection
    const handleSelectTemplate = (template: LibraryTemplate) => {
        const newTemplate = {
            id: template.template_id,
            filename: template.name,
            sheetCount: 1,
            status: 'completed' as const,
            createdAt: template.created_at,
        };
        addTemplate(newTemplate);
        setCurrentTemplate(newTemplate);
        addNotification('success', `Selected template: ${template.name}`);
        navigate('/mapping');
    };

    const renderStars = (rating: number) => {
        const stars = [];
        for (let i = 1; i <= 5; i++) {
            stars.push(
                <Star
                    key={i}
                    className={`w-4 h-4 ${i <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-gray-300'}`}
                />
            );
        }
        return stars;
    };

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Branded Header Section */}
            <div className="bg-gradient-to-r from-green-600 to-green-500 rounded-2xl p-8 text-white shadow-lg">
                <div className="flex items-center justify-between">
                    <div className="flex items-center space-x-6">
                        <div className="bg-white rounded-xl p-3 shadow-md">
                            <img
                                src={logo}
                                alt="StatementXL"
                                className="h-12 w-auto"
                            />
                        </div>
                        <div>
                            <h1 className="text-3xl font-bold">Template Library</h1>
                            <p className="text-green-100 mt-1">
                                Browse and download pre-built financial templates
                            </p>
                        </div>
                    </div>
                    <button className="px-4 py-2 bg-white text-green-600 rounded-lg hover:bg-green-50 transition-colors flex items-center space-x-2 font-medium shadow-sm">
                        <Plus className="w-4 h-4" />
                        <span>Upload Template</span>
                    </button>
                </div>
            </div>

            {/* Search and Filters */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <div className="flex items-center space-x-4">
                    {/* Search */}
                    <div className="flex-1 relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
                        <input
                            type="text"
                            placeholder="Search templates..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-500 focus:border-green-500"
                        />
                    </div>

                    {/* Filter Toggle */}
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`px-4 py-2 rounded-lg flex items-center space-x-2 transition-colors ${showFilters
                            ? 'bg-green-600 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                    >
                        <Filter className="w-4 h-4" />
                        <span>Filters</span>
                    </button>

                    {/* View Mode */}
                    <div className="flex items-center bg-gray-100 rounded-lg p-1">
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-white text-green-600 shadow-sm' : 'text-gray-500'}`}
                            title="Grid view"
                        >
                            <Grid3X3 className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2 rounded ${viewMode === 'list' ? 'bg-white text-green-600 shadow-sm' : 'text-gray-500'}`}
                            title="List view"
                        >
                            <List className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Filter Options */}
                {showFilters && (
                    <div className="mt-4 pt-4 border-t border-gray-200 grid grid-cols-2 gap-4 animate-slide-down">
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
                            <div className="flex flex-wrap gap-2">
                                {categories.map((cat) => (
                                    <button
                                        key={cat}
                                        onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                                        className={`
                                            px-3 py-1 rounded-full text-sm transition-all
                                            ${selectedCategory === cat
                                                ? 'bg-green-100 text-green-700 border border-green-500'
                                                : 'bg-gray-100 text-gray-600 border border-gray-200 hover:border-gray-300'
                                            }
                                        `}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-gray-700 mb-2">Industry</label>
                            <div className="flex flex-wrap gap-2">
                                {industries.map((ind) => (
                                    <button
                                        key={ind}
                                        onClick={() => setSelectedIndustry(selectedIndustry === ind ? null : ind)}
                                        className={`
                                            px-3 py-1 rounded-full text-sm transition-all
                                            ${selectedIndustry === ind
                                                ? 'bg-emerald-100 text-emerald-700 border border-emerald-500'
                                                : 'bg-gray-100 text-gray-600 border border-gray-200 hover:border-gray-300'
                                            }
                                        `}
                                    >
                                        {ind}
                                    </button>
                                ))}
                            </div>
                        </div>
                    </div>
                )}
            </div>

            {/* Statement Type Filter (Quick Access) */}
            <div className="bg-white rounded-xl border border-gray-200 p-4 shadow-sm">
                <label className="block text-sm font-medium text-gray-700 mb-3">Statement Type</label>
                <div className="flex flex-wrap gap-3">
                    <button
                        onClick={() => setSelectedStatementType(null)}
                        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${selectedStatementType === null
                            ? 'bg-green-600 text-white'
                            : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                            }`}
                    >
                        All Types
                    </button>
                    {STATEMENT_TYPES.map((type) => (
                        <button
                            key={type.value}
                            onClick={() => setSelectedStatementType(selectedStatementType === type.value ? null : type.value)}
                            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${selectedStatementType === type.value
                                ? 'bg-green-600 text-white'
                                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                                }`}
                        >
                            {type.label}
                        </button>
                    ))}
                </div>
            </div>

            {/* Loading State */}
            {loading && (
                <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 text-green-600 animate-spin" />
                    <span className="ml-3 text-gray-600">Loading templates...</span>
                </div>
            )}

            {/* Error State */}
            {error && !loading && (
                <div className="bg-yellow-50 border border-yellow-200 rounded-xl p-4 flex items-center space-x-3">
                    <AlertCircle className="w-5 h-5 text-yellow-600" />
                    <span className="text-yellow-800">Using demo templates - {error}</span>
                </div>
            )}

            {/* Featured Section */}
            {!loading && filteredTemplates.some((t) => t.is_featured) && !searchQuery && (
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">Featured</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {filteredTemplates.filter((t) => t.is_featured).map((template) => (
                            <div
                                key={template.id}
                                onClick={() => handleSelectTemplate(template)}
                                className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm hover:shadow-md transition-shadow cursor-pointer border-l-4 border-l-green-500"
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center space-x-3">
                                        <div className="p-3 rounded-lg bg-green-100">
                                            <FileSpreadsheet className="w-6 h-6 text-green-600" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-gray-900">{template.name}</h3>
                                            <p className="text-sm text-gray-500 mt-1">{template.description}</p>
                                        </div>
                                    </div>
                                    <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                                </div>
                                <div className="mt-4 flex items-center justify-between">
                                    <div className="flex items-center space-x-4 text-sm text-gray-500">
                                        <span className="flex items-center space-x-1">
                                            <Download className="w-4 h-4" />
                                            <span>{template.download_count}</span>
                                        </span>
                                        <span className="flex items-center space-x-1">
                                            <Users className="w-4 h-4" />
                                            <span>{template.use_count}</span>
                                        </span>
                                    </div>
                                    <div className="flex items-center space-x-1">{renderStars(template.rating)}</div>
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* All Templates */}
            {!loading && (
                <div>
                    <h2 className="text-lg font-semibold text-gray-900 mb-4">
                        All Templates ({filteredTemplates.length})
                    </h2>

                    {viewMode === 'grid' ? (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {filteredTemplates.map((template) => (
                                <div key={template.id} onClick={() => handleSelectTemplate(template)} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm hover:shadow-md transition-shadow cursor-pointer group">
                                    <div className="flex items-center space-x-3">
                                        <div className="p-3 rounded-lg bg-green-50 group-hover:bg-green-100 transition-colors">
                                            <FileSpreadsheet className="w-5 h-5 text-green-600" />
                                        </div>
                                        <div className="flex-1 min-w-0">
                                            <h3 className="font-medium text-gray-900 truncate">{template.name}</h3>
                                            <p className="text-xs text-gray-500">{template.author}</p>
                                        </div>
                                    </div>
                                    <p className="mt-3 text-sm text-gray-500 line-clamp-2">{template.description}</p>
                                    <div className="mt-4 flex items-center flex-wrap gap-2">
                                        {template.tags.slice(0, 3).map((tag) => (
                                            <span key={tag} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded">
                                                {tag}
                                            </span>
                                        ))}
                                    </div>
                                    <div className="mt-4 pt-4 border-t border-gray-100 flex items-center justify-between">
                                        <div className="flex items-center space-x-1">{renderStars(template.rating)}</div>
                                        <span className="text-sm text-gray-500">
                                            {template.download_count.toLocaleString()} downloads
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    ) : (
                        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden shadow-sm">
                            <table className="w-full">
                                <thead className="bg-green-50">
                                    <tr>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Template</th>
                                        <th className="px-6 py-3 text-left text-xs font-medium text-green-800 uppercase tracking-wider">Category</th>
                                        <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider">Rating</th>
                                        <th className="px-6 py-3 text-right text-xs font-medium text-green-800 uppercase tracking-wider">Downloads</th>
                                        <th className="px-6 py-3 text-center text-xs font-medium text-green-800 uppercase tracking-wider">Actions</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-gray-100">
                                    {filteredTemplates.map((template) => (
                                        <tr key={template.id} className="hover:bg-green-50/50 transition-colors">
                                            <td className="px-6 py-4">
                                                <div className="flex items-center space-x-3">
                                                    <FileSpreadsheet className="w-5 h-5 text-green-600" />
                                                    <div>
                                                        <p className="font-medium text-gray-900">{template.name}</p>
                                                        <p className="text-sm text-gray-500">{template.author}</p>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="px-6 py-4">
                                                <span className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded">
                                                    {template.category}
                                                </span>
                                            </td>
                                            <td className="px-6 py-4">
                                                <div className="flex items-center justify-center space-x-1">
                                                    {renderStars(template.rating)}
                                                </div>
                                            </td>
                                            <td className="px-6 py-4 text-right text-gray-700">
                                                {template.download_count.toLocaleString()}
                                            </td>
                                            <td className="px-6 py-4 text-center">
                                                <button className="p-2 rounded-lg text-gray-500 hover:text-green-600 hover:bg-green-50 transition-colors" title="Download template">
                                                    <Download className="w-4 h-4" />
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
};

export default TemplateLibrary;
