import React from 'react';
import { NavLink } from 'react-router-dom';
import {
    Upload,
    FileSearch,
    FileSpreadsheet,
    GitMerge,
    History,
    ChevronLeft,
    ChevronRight,
    Library,
    Download,
} from 'lucide-react';
import { useUIStore } from '../stores';
import logo from '../assets/logo.png';

const navItems = [
    { path: '/', icon: Upload, label: 'Upload PDF' },
    { path: '/extraction', icon: FileSearch, label: 'Extraction Review' },
    { path: '/template', icon: FileSpreadsheet, label: 'Template Upload' },
    { path: '/mapping', icon: GitMerge, label: 'Mapping Review' },
    { path: '/export', icon: Download, label: 'Export to Excel' },
    { path: '/audit', icon: History, label: 'Audit Trail' },
    { path: '/library', icon: Library, label: 'Template Library' },
];

const Sidebar: React.FC = () => {
    const { sidebarOpen, toggleSidebar } = useUIStore();

    return (
        <aside
            className={`
        fixed left-0 top-0 h-screen bg-gradient-to-b from-green-800 to-green-700
        transition-all duration-300 ease-in-out z-20 shadow-xl
        ${sidebarOpen ? 'w-64' : 'w-20'}
      `}
        >
            {/* Logo Section - Properly Integrated */}
            <div className="flex items-center h-16 px-4 border-b border-green-600/30">
                <NavLink to="/" className="flex items-center space-x-3 group">
                    <div className="flex-shrink-0 bg-white rounded-lg p-1.5 shadow-sm group-hover:shadow-md transition-shadow">
                        <img
                            src={logo}
                            alt="StatementXL"
                            className="h-7 w-auto"
                        />
                    </div>
                    {sidebarOpen && (
                        <div className="flex flex-col animate-fade-in">
                            <span className="font-bold text-white text-lg leading-tight">
                                StatementXL
                            </span>
                            <span className="text-green-200 text-xs">
                                Financial Automation
                            </span>
                        </div>
                    )}
                </NavLink>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-6 px-3 space-y-1">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `
              flex items-center px-3 py-3 rounded-lg transition-all duration-200
              ${isActive
                                ? 'bg-white/20 text-white border-l-2 border-white shadow-sm'
                                : 'text-green-100 hover:text-white hover:bg-white/10'
                            }
            `}
                    >
                        <item.icon className="w-5 h-5 flex-shrink-0" />
                        {sidebarOpen && (
                            <span className="ml-3 font-medium animate-fade-in">{item.label}</span>
                        )}
                    </NavLink>
                ))}
            </nav>

            {/* Toggle Button */}
            <button
                onClick={toggleSidebar}
                className="absolute -right-3 top-20 w-6 h-6 bg-green-600 rounded-full flex items-center justify-center border-2 border-white hover:bg-green-500 transition-colors shadow-lg"
            >
                {sidebarOpen ? (
                    <ChevronLeft className="w-4 h-4 text-white" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-white" />
                )}
            </button>

            {/* Footer */}
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-green-600/30">
                {sidebarOpen ? (
                    <div className="flex items-center justify-center space-x-2 animate-fade-in">
                        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                        <span className="text-xs text-green-200">Version 2.0.0</span>
                    </div>
                ) : (
                    <div className="flex justify-center">
                        <div className="w-2 h-2 bg-green-400 rounded-full animate-pulse"></div>
                    </div>
                )}
            </div>
        </aside>
    );
};

export default Sidebar;
