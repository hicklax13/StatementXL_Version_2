import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import { useUIStore } from '../stores';
import { X } from 'lucide-react';

const Layout: React.FC = () => {
    const { sidebarOpen, notifications, removeNotification } = useUIStore();

    return (
        <div className="min-h-screen bg-gray-50">
            <Sidebar />

            {/* Main Content */}
            <main
                className={`
          transition-all duration-300 ease-in-out
          ${sidebarOpen ? 'ml-64' : 'ml-20'}
        `}
            >
                <div className="min-h-screen p-8">
                    <Outlet />
                </div>
            </main>

            {/* Notifications */}
            <div className="fixed bottom-4 right-4 space-y-2 z-50">
                {notifications.map((notification) => (
                    <div
                        key={notification.id}
                        className={`
              flex items-center space-x-3 px-4 py-3 rounded-lg shadow-lg animate-slide-up
              ${notification.type === 'success' ? 'bg-green-600 text-white' :
                                notification.type === 'error' ? 'bg-red-500 text-white' :
                                    'bg-green-500 text-white'}
            `}
                    >
                        <span>{notification.message}</span>
                        <button
                            onClick={() => removeNotification(notification.id)}
                            className="p-1 hover:bg-white/20 rounded transition-colors"
                        >
                            <X className="w-4 h-4" />
                        </button>
                    </div>
                ))}
            </div>
        </div>
    );
};

export default Layout;
