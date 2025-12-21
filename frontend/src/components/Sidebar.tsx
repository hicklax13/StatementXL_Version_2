```
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
        fixed left - 0 top - 0 h - screen bg - dark - 900 border - r border - dark - 700
transition - all duration - 300 ease -in -out z - 20
        ${ sidebarOpen ? 'w-64' : 'w-20' }
`}
        >
            {/* Logo */}
            <div className="flex items-center justify-between h-16 px-4 border-b border-dark-700">
                <div className="flex items-center space-x-3">
                    <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
                        <span className="text-white font-bold text-lg">S</span>
                    </div>
                    {sidebarOpen && (
                        <span className="font-bold text-lg gradient-text animate-fade-in">
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
              flex items - center px - 3 py - 3 rounded - lg transition - all duration - 200
              ${
    isActive
        ? 'bg-primary-500/10 text-primary-400 border-l-2 border-primary-500'
        : 'text-dark-400 hover:text-dark-100 hover:bg-dark-800'
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
                className="absolute -right-3 top-20 w-6 h-6 bg-dark-700 rounded-full flex items-center justify-center border border-dark-600 hover:bg-dark-600 transition-colors"
            >
                {sidebarOpen ? (
                    <ChevronLeft className="w-4 h-4 text-dark-300" />
                ) : (
                    <ChevronRight className="w-4 h-4 text-dark-300" />
                )}
            </button>

            {/* Footer */}
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-dark-700">
                {sidebarOpen && (
                    <div className="text-xs text-dark-500 text-center animate-fade-in">
                        Version 2.0.0
                    </div>
                )}
            </div>
        </aside>
    );
};

export default Sidebar;
