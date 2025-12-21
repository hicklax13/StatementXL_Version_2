import React, { useState, useEffect } from 'react';
import {
    Search,
    Grid3X3,
    List,
    Star,
    Download,
    Plus,
    Filter,
    X,
    FileSpreadsheet,
    Tag,
    Clock,
    Users,
} from 'lucide-react';

interface LibraryTemplate {
    id: string;
    name: string;
    description: string | null;
    category: string | null;
    industry: string | null;
    tags: string[];
    downloadCount: number;
    useCount: number;
    rating: number;
    isFeatured: boolean;
    author: string | null;
    createdAt: string;
}

const TemplateLibrary: React.FC = () => {
    const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
    const [searchQuery, setSearchQuery] = useState('');
    const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
    const [selectedIndustry, setSelectedIndustry] = useState<string | null>(null);
    const [showFilters, setShowFilters] = useState(false);

    // Mock data
    const templates: LibraryTemplate[] = [
        {
            id: '1',
            name: 'LBO Model Template',
            description: 'Comprehensive leveraged buyout model with debt schedules',
            category: 'lbo',
            industry: 'private-equity',
            tags: ['lbo', 'debt', 'buyout'],
            downloadCount: 1250,
            useCount: 890,
            rating: 4.8,
            isFeatured: true,
            author: 'StatementXL Team',
            createdAt: '2024-01-15T10:00:00Z',
        },
        {
            id: '2',
            name: 'DCF Valuation Model',
            description: 'Discounted cash flow model with sensitivity analysis',
            category: 'valuation',
            industry: 'investment-banking',
            tags: ['dcf', 'valuation', 'wacc'],
            downloadCount: 2100,
            useCount: 1500,
            rating: 4.9,
            isFeatured: true,
            author: 'StatementXL Team',
            createdAt: '2024-02-20T10:00:00Z',
        },
        {
            id: '3',
            name: 'Three Statement Model',
            description: 'Integrated income, balance sheet, and cash flow statements',
            category: 'financial-statements',
            industry: 'corporate-finance',
            tags: ['is', 'bs', 'cf', 'integrated'],
            downloadCount: 3400,
            useCount: 2800,
            rating: 4.7,
            isFeatured: false,
            author: 'Community',
            createdAt: '2024-03-10T10:00:00Z',
        },
        {
            id: '4',
            name: 'M&A Accretion/Dilution',
            description: 'Merger analysis with accretion/dilution modeling',
            category: 'ma',
            industry: 'investment-banking',
            tags: ['ma', 'merger', 'acquisition'],
            downloadCount: 890,
            useCount: 650,
            rating: 4.6,
            isFeatured: false,
            author: 'StatementXL Team',
            createdAt: '2024-04-05T10:00:00Z',
        },
    ];

    const categories = ['lbo', 'valuation', 'financial-statements', 'ma', 'real-estate'];
    const industries = ['private-equity', 'investment-banking', 'corporate-finance', 'consulting'];

    const filteredTemplates = templates.filter((t) => {
        if (searchQuery && !t.name.toLowerCase().includes(searchQuery.toLowerCase())) {
            return false;
        }
        if (selectedCategory && t.category !== selectedCategory) {
            return false;
        }
        if (selectedIndustry && t.industry !== selectedIndustry) {
            return false;
        }
        return true;
    });

    const renderStars = (rating: number) => {
        const stars = [];
        for (let i = 1; i <= 5; i++) {
            stars.push(
                <Star
                    key={i}
                    className={`w-4 h-4 ${i <= rating ? 'text-yellow-400 fill-yellow-400' : 'text-dark-600'
                        }`}
                />
            );
        }
        return stars;
    };

    return (
        <div className="space-y-6 animate-fade-in">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    <h1 className="text-3xl font-bold text-dark-100">Template Library</h1>
                    <p className="text-dark-400 mt-1">
                        Browse and download pre-built financial templates
                    </p>
                </div>
                <button className="btn btn-primary flex items-center space-x-2">
                    <Plus className="w-4 h-4" />
                    <span>Upload Template</span>
                </button>
            </div>

            {/* Search and Filters */}
            <div className="card p-4">
                <div className="flex items-center space-x-4">
                    {/* Search */}
                    <div className="flex-1 relative">
                        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-dark-400" />
                        <input
                            type="text"
                            placeholder="Search templates..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="input pl-10"
                        />
                    </div>

                    {/* Filter Toggle */}
                    <button
                        onClick={() => setShowFilters(!showFilters)}
                        className={`btn ${showFilters ? 'btn-primary' : 'btn-secondary'} flex items-center space-x-2`}
                    >
                        <Filter className="w-4 h-4" />
                        <span>Filters</span>
                    </button>

                    {/* View Mode */}
                    <div className="flex items-center bg-dark-700 rounded-lg p-1">
                        <button
                            onClick={() => setViewMode('grid')}
                            className={`p-2 rounded ${viewMode === 'grid' ? 'bg-dark-600 text-primary-400' : 'text-dark-400'}`}
                        >
                            <Grid3X3 className="w-4 h-4" />
                        </button>
                        <button
                            onClick={() => setViewMode('list')}
                            className={`p-2 rounded ${viewMode === 'list' ? 'bg-dark-600 text-primary-400' : 'text-dark-400'}`}
                        >
                            <List className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Filter Options */}
                {showFilters && (
                    <div className="mt-4 pt-4 border-t border-dark-700 grid grid-cols-2 gap-4 animate-slide-down">
                        <div>
                            <label className="block text-sm font-medium text-dark-300 mb-2">Category</label>
                            <div className="flex flex-wrap gap-2">
                                {categories.map((cat) => (
                                    <button
                                        key={cat}
                                        onClick={() => setSelectedCategory(selectedCategory === cat ? null : cat)}
                                        className={`
                      px-3 py-1 rounded-full text-sm transition-all
                      ${selectedCategory === cat
                                                ? 'bg-primary-500/20 text-primary-400 border border-primary-500'
                                                : 'bg-dark-700 text-dark-300 border border-dark-600 hover:border-dark-500'
                                            }
                    `}
                                    >
                                        {cat}
                                    </button>
                                ))}
                            </div>
                        </div>
                        <div>
                            <label className="block text-sm font-medium text-dark-300 mb-2">Industry</label>
                            <div className="flex flex-wrap gap-2">
                                {industries.map((ind) => (
                                    <button
                                        key={ind}
                                        onClick={() => setSelectedIndustry(selectedIndustry === ind ? null : ind)}
                                        className={`
                      px-3 py-1 rounded-full text-sm transition-all
                      ${selectedIndustry === ind
                                                ? 'bg-accent-500/20 text-accent-400 border border-accent-500'
                                                : 'bg-dark-700 text-dark-300 border border-dark-600 hover:border-dark-500'
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

            {/* Featured Section */}
            {filteredTemplates.some((t) => t.isFeatured) && !searchQuery && (
                <div>
                    <h2 className="text-lg font-semibold text-dark-100 mb-4">Featured</h2>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {filteredTemplates.filter((t) => t.isFeatured).map((template) => (
                            <div
                                key={template.id}
                                className="card p-6 hover-lift cursor-pointer border-l-4 border-accent-500"
                            >
                                <div className="flex items-start justify-between">
                                    <div className="flex items-center space-x-3">
                                        <div className="p-3 rounded-lg bg-accent-500/10">
                                            <FileSpreadsheet className="w-6 h-6 text-accent-400" />
                                        </div>
                                        <div>
                                            <h3 className="font-semibold text-dark-100">{template.name}</h3>
                                            <p className="text-sm text-dark-400 mt-1">{template.description}</p>
                                        </div>
                                    </div>
                                    <Star className="w-5 h-5 text-yellow-400 fill-yellow-400" />
                                </div>
                                <div className="mt-4 flex items-center justify-between">
                                    <div className="flex items-center space-x-4 text-sm text-dark-400">
                                        <span className="flex items-center space-x-1">
                                            <Download className="w-4 h-4" />
                                            <span>{template.downloadCount}</span>
                                        </span>
                                        <span className="flex items-center space-x-1">
                                            <Users className="w-4 h-4" />
                                            <span>{template.useCount}</span>
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
            <div>
                <h2 className="text-lg font-semibold text-dark-100 mb-4">
                    All Templates ({filteredTemplates.length})
                </h2>

                {viewMode === 'grid' ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                        {filteredTemplates.map((template) => (
                            <div key={template.id} className="card p-5 hover-lift cursor-pointer group">
                                <div className="flex items-center space-x-3">
                                    <div className="p-3 rounded-lg bg-primary-500/10 group-hover:bg-primary-500/20 transition-colors">
                                        <FileSpreadsheet className="w-5 h-5 text-primary-400" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <h3 className="font-medium text-dark-100 truncate">{template.name}</h3>
                                        <p className="text-xs text-dark-400">{template.author}</p>
                                    </div>
                                </div>
                                <p className="mt-3 text-sm text-dark-400 line-clamp-2">{template.description}</p>
                                <div className="mt-4 flex items-center flex-wrap gap-2">
                                    {template.tags.slice(0, 3).map((tag) => (
                                        <span key={tag} className="px-2 py-0.5 text-xs bg-dark-700 text-dark-300 rounded">
                                            {tag}
                                        </span>
                                    ))}
                                </div>
                                <div className="mt-4 pt-4 border-t border-dark-700 flex items-center justify-between">
                                    <div className="flex items-center space-x-1">{renderStars(template.rating)}</div>
                                    <span className="text-sm text-dark-400">
                                        {template.downloadCount.toLocaleString()} downloads
                                    </span>
                                </div>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div className="card overflow-hidden">
                        <table className="w-full">
                            <thead className="table-header">
                                <tr>
                                    <th className="px-6 py-3 text-left">Template</th>
                                    <th className="px-6 py-3 text-left">Category</th>
                                    <th className="px-6 py-3 text-center">Rating</th>
                                    <th className="px-6 py-3 text-right">Downloads</th>
                                    <th className="px-6 py-3 text-center">Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {filteredTemplates.map((template) => (
                                    <tr key={template.id} className="table-row">
                                        <td className="px-6 py-4">
                                            <div className="flex items-center space-x-3">
                                                <FileSpreadsheet className="w-5 h-5 text-primary-400" />
                                                <div>
                                                    <p className="font-medium text-dark-100">{template.name}</p>
                                                    <p className="text-sm text-dark-400">{template.author}</p>
                                                </div>
                                            </div>
                                        </td>
                                        <td className="px-6 py-4">
                                            <span className="px-2 py-1 text-xs bg-dark-700 text-dark-300 rounded">
                                                {template.category}
                                            </span>
                                        </td>
                                        <td className="px-6 py-4">
                                            <div className="flex items-center justify-center space-x-1">
                                                {renderStars(template.rating)}
                                            </div>
                                        </td>
                                        <td className="px-6 py-4 text-right text-dark-200">
                                            {template.downloadCount.toLocaleString()}
                                        </td>
                                        <td className="px-6 py-4 text-center">
                                            <button className="p-2 rounded-lg text-dark-400 hover:text-primary-400 hover:bg-primary-500/10 transition-colors">
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
        </div>
    );
};

export default TemplateLibrary;
