import React, { useState } from 'react';
import {
    CheckCircle,
    Circle,
    Upload,
    FileText,
    Download,
    ArrowRight,
    ArrowLeft,
    Sparkles,
} from 'lucide-react';

interface OnboardingStep {
    id: number;
    title: string;
    description: string;
    icon: React.ReactNode;
    completed: boolean;
}

const Onboarding: React.FC = () =& gt; {
    const [currentStep, setCurrentStep] = useState(0);
    const [steps, setSteps] = useState & lt; OnboardingStep[] & gt; ([
        {
            id: 1,
            title: 'Welcome to StatementXL',
            description: 'Transform your financial PDFs into structured Excel templates with AI-powered extraction.',
            icon: & lt; Sparkles className="w-12 h-12 text-green-600" /& gt;,
        completed: false,
        },
{
    id: 2,
        title: 'Upload Your First Document',
            description: 'Upload a PDF financial statement (Income Statement, Balance Sheet, or Cash Flow).',
                icon: & lt;Upload className = "w-12 h-12 text-green-600" /& gt;,
    completed: false,
        },
{
    id: 3,
        title: 'Review Extracted Data',
            description: 'Our AI extracts tables and classifies line items using GAAP standards.',
                icon: & lt;FileText className = "w-12 h-12 text-green-600" /& gt;,
    completed: false,
        },
{
    id: 4,
        title: 'Export to Excel',
            description: 'Download your professionally formatted Excel file with formulas intact.',
                icon: & lt;Download className = "w-12 h-12 text-green-600" /& gt;,
    completed: false,
        },
    ]);

const handleNext = () =& gt; {
    if (currentStep & lt; steps.length - 1) {
        const updatedSteps = [...steps];
        updatedSteps[currentStep].completed = true;
        setSteps(updatedSteps);
        setCurrentStep(currentStep + 1);
    } else {
        // Mark last step as complete and redirect to upload
        const updatedSteps = [...steps];
        updatedSteps[currentStep].completed = true;
        setSteps(updatedSteps);

        // Save onboarding completion to localStorage
        localStorage.setItem('onboarding_completed', 'true');

        // Redirect to upload page
        window.location.href = '/upload';
    }
};

const handlePrevious = () =& gt; {
    if (currentStep & gt; 0) {
        setCurrentStep(currentStep - 1);
    }
};

const handleSkip = () =& gt; {
    localStorage.setItem('onboarding_completed', 'true');
    window.location.href = '/upload';
};

const currentStepData = steps[currentStep];
const progress = ((currentStep + 1) / steps.length) * 100;

return (
        & lt;div className = "min-h-screen bg-gradient-to-br from-green-50 to-white flex items-center justify-center p-6" & gt;
            & lt;div className = "max-w-4xl w-full" & gt;
{/* Progress Bar */ }
                & lt;div className = "mb-8" & gt;
                    & lt;div className = "flex items-center justify-between mb-2" & gt;
                        & lt;span className = "text-sm font-medium text-gray-700" & gt;
                            Step { currentStep + 1 } of { steps.length }
                        & lt;/span&gt;
                        & lt;span className = "text-sm text-gray-500" & gt; { Math.round(progress) }% complete & lt;/span&gt;
                    & lt;/div&gt;
                    & lt;div className = "w-full bg-gray-200 rounded-full h-2" & gt;
                        & lt; div
className = "bg-green-600 h-2 rounded-full transition-all duration-300"
style = {{ width: `${progress}%` }}
                        & gt;& lt;/div&gt;
                    & lt;/div&gt;
                & lt;/div&gt;

{/* Step Indicators */ }
                & lt;div className = "flex items-center justify-between mb-12" & gt;
{
    steps.map((step, index) =& gt; (
                        & lt;div key = { step.id } className = "flex items-center" & gt;
                            & lt; button
    onClick = {() =& gt; setCurrentStep(index)
}
className = {`flex items-center justify-center w-12 h-12 rounded-full border-2 transition-all ${index === currentStep
    ? 'border-green-600 bg-green-50'
    : step.completed
        ? 'border-green-600 bg-green-600'
        : 'border-gray-300 bg-white'
    }`}
                            & gt;
{
    step.completed ? (
                                    & lt;CheckCircle className = "w-6 h-6 text-white" /& gt;
                                ) : (
                                    & lt; Circle
    className = {`w-6 h-6 ${index === currentStep ? 'text-green-600' : 'text-gray-400'
        }`
}
                                    /&gt;
                                )}
                            & lt;/button&gt;
{
    index & lt; steps.length - 1 & amp;& amp; (
                                & lt; div
    className = {`w-16 h-0.5 mx-2 ${step.completed ? 'bg-green-600' : 'bg-gray-300'
        }`
}
                                & gt;& lt;/div&gt;
                            )}
                        & lt;/div&gt;
                    ))}
                & lt;/div&gt;

{/* Main Content Card */ }
                & lt;div className = "bg-white rounded-2xl shadow-xl border border-gray-200 p-12" & gt;
                    & lt;div className = "text-center mb-8" & gt;
                        & lt;div className = "flex justify-center mb-6" & gt; { currentStepData.icon }& lt;/div&gt;
                        & lt;h1 className = "text-3xl font-bold text-gray-900 mb-4" & gt;
{ currentStepData.title }
                        & lt;/h1&gt;
                        & lt;p className = "text-lg text-gray-600 max-w-2xl mx-auto" & gt;
{ currentStepData.description }
                        & lt;/p&gt;
                    & lt;/div&gt;

{/* Step-specific content */ }
                    & lt;div className = "mt-12" & gt;
{
    currentStep === 0 & amp;& amp; (
                            & lt;div className = "grid grid-cols-3 gap-6 text-center" & gt;
                                & lt;div className = "p-6 bg-green-50 rounded-xl" & gt;
                                    & lt;div className = "text-3xl font-bold text-green-600 mb-2" & gt; AI - Powered & lt;/div&gt;
                                    & lt;p className = "text-sm text-gray-600" & gt;
                                        Intelligent extraction using Google Gemini
                                    & lt;/p&gt;
                                & lt;/div&gt;
                                & lt;div className = "p-6 bg-green-50 rounded-xl" & gt;
                                    & lt;div className = "text-3xl font-bold text-green-600 mb-2" & gt;GAAP Compliant & lt;/div&gt;
                                    & lt;p className = "text-sm text-gray-600" & gt;
                                        Automatic classification to accounting standards
        & lt;/p&gt;
                                & lt;/div&gt;
                                & lt;div className = "p-6 bg-green-50 rounded-xl" & gt;
                                    & lt;div className = "text-3xl font-bold text-green-600 mb-2" & gt;Formula Ready & lt;/div&gt;
                                    & lt;p className = "text-sm text-gray-600" & gt;
                                        Excel files with working formulas, not static values
        & lt;/p&gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        )
}

{
    currentStep === 1 & amp;& amp; (
                            & lt;div className = "bg-gray-50 rounded-xl p-8 border-2 border-dashed border-gray-300" & gt;
                                & lt;div className = "text-center" & gt;
                                    & lt;Upload className = "w-16 h-16 text-gray-400 mx-auto mb-4" /& gt;
                                    & lt;p className = "text-gray-600 mb-2" & gt;
                                        Supported formats: PDF
        & lt;/p&gt;
                                    & lt;p className = "text-sm text-gray-500" & gt;
                                        Maximum file size: 50MB
        & lt;/p&gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        )
}

{
    currentStep === 2 & amp;& amp; (
                            & lt;div className = "space-y-4" & gt;
                                & lt;div className = "flex items-start space-x-4 p-4 bg-gray-50 rounded-lg" & gt;
                                    & lt;CheckCircle className = "w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" /& gt;
                                    & lt; div & gt;
                                        & lt;h3 className = "font-semibold text-gray-900" & gt;Table Detection & lt;/h3&gt;
                                        & lt;p className = "text-sm text-gray-600" & gt;
                                            Automatically identifies financial tables in your PDF
        & lt;/p&gt;
                                    & lt;/div&gt;
                                & lt;/div&gt;
                                & lt;div className = "flex items-start space-x-4 p-4 bg-gray-50 rounded-lg" & gt;
                                    & lt;CheckCircle className = "w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" /& gt;
                                    & lt; div & gt;
                                        & lt;h3 className = "font-semibold text-gray-900" & gt;Line Item Classification & lt;/h3&gt;
                                        & lt;p className = "text-sm text-gray-600" & gt;
                                            AI classifies each line item to GAAP categories
        & lt;/p&gt;
                                    & lt;/div&gt;
                                & lt;/div&gt;
                                & lt;div className = "flex items-start space-x-4 p-4 bg-gray-50 rounded-lg" & gt;
                                    & lt;CheckCircle className = "w-6 h-6 text-green-600 flex-shrink-0 mt-0.5" /& gt;
                                    & lt; div & gt;
                                        & lt;h3 className = "font-semibold text-gray-900" & gt;Smart Aggregation & lt;/h3&gt;
                                        & lt;p className = "text-sm text-gray-600" & gt;
                                            Combines related items(e.g., "Social Security" + "Medicaid" = Revenue)
        & lt;/p&gt;
                                    & lt;/div&gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        )
}

{
    currentStep === 3 & amp;& amp; (
                            & lt;div className = "bg-gradient-to-r from-green-50 to-green-100 rounded-xl p-8" & gt;
                                & lt;div className = "flex items-center justify-between" & gt;
                                    & lt; div & gt;
                                        & lt;h3 className = "text-xl font-semibold text-gray-900 mb-2" & gt;
                                            Professional Excel Templates
        & lt;/h3&gt;
                                        & lt;ul className = "space-y-2 text-gray-700" & gt;
                                            & lt;li className = "flex items-center space-x-2" & gt;
                                                & lt;CheckCircle className = "w-5 h-5 text-green-600" /& gt;
                                                & lt; span & gt; Basic, Corporate, and Professional styles & lt;/span&gt;
                                            & lt;/li&gt;
                                            & lt;li className = "flex items-center space-x-2" & gt;
                                                & lt;CheckCircle className = "w-5 h-5 text-green-600" /& gt;
                                                & lt; span & gt;Working formulas(not static values) & lt;/span&gt;
                                            & lt;/li&gt;
                                            & lt;li className = "flex items-center space-x-2" & gt;
                                                & lt;CheckCircle className = "w-5 h-5 text-green-600" /& gt;
                                                & lt; span & gt; Audit - ready formatting & lt;/span&gt;
                                            & lt;/li&gt;
                                        & lt;/ul&gt;
                                    & lt;/div&gt;
                                    & lt;Download className = "w-24 h-24 text-green-600 opacity-20" /& gt;
                                & lt;/div&gt;
                            & lt;/div&gt;
                        )
}
                    & lt;/div&gt;

{/* Navigation Buttons */ }
                    & lt;div className = "flex items-center justify-between mt-12" & gt;
                        & lt; button
onClick = { handleSkip }
className = "text-gray-600 hover:text-gray-900 font-medium"
    & gt;
                            Skip tutorial
    & lt;/button&gt;
                        & lt;div className = "flex items-center space-x-3" & gt;
{
    currentStep & gt; 0 & amp;& amp; (
                                & lt; button
    onClick = { handlePrevious }
    className = "flex items-center space-x-2 px-6 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 font-medium"
        & gt;
                                    & lt;ArrowLeft className = "w-5 h-5" /& gt;
                                    & lt; span & gt; Previous & lt;/span&gt;
                                & lt;/button&gt;
                            )
}
                            & lt; button
onClick = { handleNext }
className = "flex items-center space-x-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 font-medium"
    & gt;
                                & lt; span & gt; { currentStep === steps.length - 1 ? 'Get Started' : 'Next' }& lt;/span&gt;
                                & lt;ArrowRight className = "w-5 h-5" /& gt;
                            & lt;/button&gt;
                        & lt;/div&gt;
                    & lt;/div&gt;
                & lt;/div&gt;
            & lt;/div&gt;
        & lt;/div&gt;
    );
};

export default Onboarding;
