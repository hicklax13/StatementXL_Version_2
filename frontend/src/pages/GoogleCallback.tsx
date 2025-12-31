import React, { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Loader2, AlertCircle } from 'lucide-react';
import { googleOAuthCallback, setAuthToken, getErrorMessage } from '../api/client';
import { useUIStore } from '../stores';
import logo from '../assets/logo.png';

const GoogleCallback: React.FC = () => {
    const navigate = useNavigate();
    const [searchParams] = useSearchParams();
    const { addNotification } = useUIStore();
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const handleCallback = async () => {
            const code = searchParams.get('code');
            const state = searchParams.get('state');
            const errorParam = searchParams.get('error');

            if (errorParam) {
                setError(`Google authentication failed: ${errorParam}`);
                return;
            }

            if (!code) {
                setError('No authorization code received from Google');
                return;
            }

            try {
                const response = await googleOAuthCallback(code, state || undefined);

                // Store tokens
                localStorage.setItem('access_token', response.access_token);
                localStorage.setItem('refresh_token', response.refresh_token);
                setAuthToken(response.access_token);

                addNotification('success', 'Successfully signed in with Google!');
                navigate('/');
            } catch (err) {
                setError(getErrorMessage(err));
            }
        };

        handleCallback();
    }, [searchParams, navigate, addNotification]);

    if (error) {
        return (
            <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-4">
                <div className="w-full max-w-md text-center">
                    <div className="inline-flex items-center justify-center bg-white rounded-2xl p-4 shadow-lg mb-4">
                        <img src={logo} alt="StatementXL" className="h-12 w-auto" />
                    </div>

                    <div className="bg-white rounded-2xl shadow-xl p-8">
                        <div className="flex items-center justify-center w-16 h-16 mx-auto mb-4 bg-red-100 rounded-full">
                            <AlertCircle className="w-8 h-8 text-red-600" />
                        </div>
                        <h2 className="text-xl font-semibold text-gray-900 mb-2">
                            Authentication Failed
                        </h2>
                        <p className="text-gray-600 mb-6">{error}</p>
                        <button
                            onClick={() => navigate('/login')}
                            className="w-full py-3 bg-green-600 text-white rounded-lg font-semibold hover:bg-green-500 transition-colors"
                        >
                            Back to Login
                        </button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-4">
            <div className="w-full max-w-md text-center">
                <div className="inline-flex items-center justify-center bg-white rounded-2xl p-4 shadow-lg mb-4">
                    <img src={logo} alt="StatementXL" className="h-12 w-auto" />
                </div>

                <div className="bg-white rounded-2xl shadow-xl p-8">
                    <Loader2 className="w-12 h-12 animate-spin text-green-600 mx-auto mb-4" />
                    <h2 className="text-xl font-semibold text-gray-900 mb-2">
                        Completing Sign In
                    </h2>
                    <p className="text-gray-500">
                        Please wait while we complete your Google sign in...
                    </p>
                </div>
            </div>
        </div>
    );
};

export default GoogleCallback;
