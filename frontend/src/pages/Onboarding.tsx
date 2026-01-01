import React, { useState } from 'react';
import {
    CheckCircle,
    FileText,
    Upload,
    Settings,
    ArrowRight,
    ArrowLeft,
    Sparkles,
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';

interface OnboardingStep {
    id: number;
    title: string;
    description: string;
    icon: React.ReactNode;
    completed: boolean;
}

const Onboarding: React.FC = () => {
    const navigate = useNavigate();
    const [currentStep, setCurrentStep] = useState(0);
    const [steps, setSteps] = useState<OnboardingStep[]>([
        {
            id: 1,
            title: 'Welcome to StatementXL',
            description: 'Transform your financial PDFs into structured Excel templates with AI-powered extraction.',
            icon: <Sparkles className="w-12 h-12 text-green-600" />,
            completed: false,
        },
        {
            id: 2,
            title: 'Upload Documents',
            description: 'Upload PDF financial statements. We support Income Statements, Balance Sheets, and Cash Flow statements.',
            icon: <Upload className="w-12 h-12 text-green-600" />,
            completed: false,
        },
        {
            id: 3,
            title: 'Review & Map',
            description: 'Review extracted data, verify classifications, and map line items to your preferred template.',
            icon: <FileText className="w-12 h-12 text-green-600" />,
            completed: false,
        },
        {
            id: 4,
            title: 'Export to Excel',
            description: 'Download professionally formatted Excel files with working formulas and clean styling.',
            icon: <Settings className="w-12 h-12 text-green-600" />,
            completed: false,
        },
    ]);

    const handleNext = () => {
        if (currentStep < steps.length - 1) {
            setSteps(prev => prev.map((step, index) =>
                index === currentStep ? { ...step, completed: true } : step
            ));
            setCurrentStep(prev => prev + 1);
        } else {
            // Complete onboarding
            navigate('/upload');
        }
    };

    const handlePrevious = () => {
        if (currentStep > 0) {
            setCurrentStep(prev => prev - 1);
        }
    };

    const handleSkip = () => {
        navigate('/upload');
    };

    return (
        <div className="min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-6">
            <div className="max-w-2xl w-full">
                {/* Progress Indicator */}
                <div className="mb-8">
                    <div className="flex justify-between items-center mb-4">
                        {steps.map((step, index) => (
                            <div key={step.id} className="flex items-center">
                                <div
                                    className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold transition-all ${index < currentStep
                                            ? 'bg-green-600 text-white'
                                            : index === currentStep
                                                ? 'bg-green-100 text-green-600 border-2 border-green-600'
                                                : 'bg-gray-100 text-gray-400'
                                        }`}
                                >
                                    {index < currentStep ? (
                                        <CheckCircle className="w-5 h-5" />
                                    ) : (
                                        index + 1
                                    )}
                                </div>
                                {index < steps.length - 1 && (
                                    <div
                                        className={`w-16 h-1 mx-2 rounded ${index < currentStep ? 'bg-green-600' : 'bg-gray-200'
                                            }`}
                                    />
                                )}
                            </div>
                        ))}
                    </div>
                </div>

                {/* Content Card */}
                <div className="bg-white rounded-2xl shadow-xl p-8 border border-gray-100">
                    <div className="text-center mb-8">
                        <div className="inline-flex items-center justify-center w-20 h-20 bg-green-50 rounded-full mb-6">
                            {steps[currentStep].icon}
                        </div>
                        <h1 className="text-3xl font-bold text-gray-900 mb-4">
                            {steps[currentStep].title}
                        </h1>
                        <p className="text-lg text-gray-600 max-w-md mx-auto">
                            {steps[currentStep].description}
                        </p>
                    </div>

                    {/* Step-specific content */}
                    {currentStep === 0 && (
                        <div className="bg-green-50 rounded-xl p-6 mb-8">
                            <h3 className="font-semibold text-green-900 mb-3">What you can do:</h3>
                            <ul className="space-y-2 text-green-800">
                                <li className="flex items-center space-x-2">
                                    <CheckCircle className="w-5 h-5" />
                                    <span>Extract tables from PDF financial statements</span>
                                </li>
                                <li className="flex items-center space-x-2">
                                    <CheckCircle className="w-5 h-5" />
                                    <span>AI-powered GAAP classification</span>
                                </li>
                                <li className="flex items-center space-x-2">
                                    <CheckCircle className="w-5 h-5" />
                                    <span>Export to professional Excel templates</span>
                                </li>
                            </ul>
                        </div>
                    )}

                    {/* Navigation */}
                    <div className="flex justify-between items-center">
                        <button
                            onClick={handlePrevious}
                            disabled={currentStep === 0}
                            className={`flex items-center space-x-2 px-4 py-2 rounded-lg transition-all ${currentStep === 0
                                    ? 'text-gray-300 cursor-not-allowed'
                                    : 'text-gray-600 hover:bg-gray-100'
                                }`}
                        >
                            <ArrowLeft className="w-4 h-4" />
                            <span>Previous</span>
                        </button>

                        <button
                            onClick={handleSkip}
                            className="text-gray-500 hover:text-gray-700 text-sm"
                        >
                            Skip onboarding
                        </button>

                        <button
                            onClick={handleNext}
                            className="flex items-center space-x-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-500 transition-all shadow-lg hover:shadow-xl"
                        >
                            <span>{currentStep === steps.length - 1 ? 'Get Started' : 'Next'}</span>
                            <ArrowRight className="w-4 h-4" />
                        </button>
                    </div>
                </div>

                {/* Footer */}
                <p className="text-center text-gray-500 text-sm mt-6">
                    Step {currentStep + 1} of {steps.length}
                </p>
            </div>
        </div>
    );
};

export default Onboarding;
