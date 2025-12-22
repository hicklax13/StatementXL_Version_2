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
} from 'lucide-react';
import { useUIStore } from '../stores';

const navItems = [
    { path: '/', icon: Upload, label: 'Upload PDF' },
    { path: '/extraction', icon: FileSearch, label: 'Extraction Review' },
    { path: '/template', icon: FileSpreadsheet, label: 'Template Upload' },
    { path: '/mapping', icon: GitMerge, label: 'Mapping Review' },
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
            {/* Logo */}
            <div className="flex items-center justify-between h-16 px-4 border-b border-green-600/30">
                <div className="flex items-center space-x-3">
                    <img
                        src="/Logos/StatementXL_Logo_v2.png"
                        alt="StatementXL"
                        className="h-10 w-auto object-contain"
                    />
                    {sidebarOpen && (
                        <span className="font-bold text-lg text-white animate-fade-in">
                            StatementXL
                        </span>
                    )}
                </div>
            </div>

            {/* Navigation */}
            <nav className="flex-1 py-6 px-3 space-y-2">
                {navItems.map((item) => (
                    <NavLink
                        key={item.path}
                        to={item.path}
                        className={({ isActive }) => `
              flex items-center px-3 py-3 rounded-lg transition-all duration-200
              ${isActive
                                ? 'bg-white/20 text-white border-l-2 border-white'
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
                {sidebarOpen && (
                    <div className="text-xs text-green-200 text-center animate-fade-in">
                        Version 2.0.0
                    </div>
                )}
            </div>
        </aside>
    );
};

export default Sidebar;
